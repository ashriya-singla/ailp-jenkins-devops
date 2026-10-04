"""Deploy immutable wheel releases on a local assessment host."""

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess  # nosec B404
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("AILP_RUNTIME", str(ROOT / "runtime"))).resolve()


def credentials():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    path = RUNTIME / "credentials.json"
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(
                {
                    "STUDENT_TOKEN": secrets.token_urlsafe(32),
                    "EDUCATOR_TOKEN": secrets.token_urlsafe(32),
                },
                stream,
            )
    return json.loads(path.read_text())


def stop(environment):
    pidfile = RUNTIME / f"{environment}.pid"
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), signal.SIGTERM)
        except ProcessLookupError:
            pass
        pidfile.unlink()
        time.sleep(1)


def healthy(port, version=None):
    try:
        with urllib.request.urlopen(  # nosec B310
            f"http://127.0.0.1:{port}/health", timeout=2
        ) as response:
            data = json.load(response)
        return data["status"] == "ok" and (version is None or data["version"] == version)
    except (OSError, ValueError):
        return False


def start(environment, release, version):
    port = 8081 if environment == "staging" else 8082
    env = os.environ.copy()
    env.update({f"AILP_{key}": value for key, value in credentials().items()})
    env.update(
        AILP_DATABASE=str(RUNTIME / f"{environment}.db"),
        AILP_VERSION=version,
        JENKINS_NODE_COOKIE="ailp-service",
        BUILD_ID="dontKillMe",
    )
    env.pop("PYTHONPATH", None)
    with (RUNTIME / f"{environment}.log").open("ab") as log:
        process = subprocess.Popen(  # nosec B603
            [
                str(release / "venv/bin/python"),
                "-m",
                "gunicorn",
                "--bind",
                f"127.0.0.1:{port}",
                "--workers",
                "1",
                "--access-logfile",
                "-",
                "ailp:create_app()",
            ],
            cwd=release,
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    (RUNTIME / f"{environment}.pid").write_text(str(process.pid))
    for _ in range(30):
        if healthy(port, version):
            return
        time.sleep(0.5)
    stop(environment)
    raise RuntimeError(f"{environment} failed readiness")


def deploy(environment, version):
    if not version.replace("-", "").isalnum():
        raise ValueError("Version must contain letters, digits and hyphens")
    release = RUNTIME / "releases" / version
    manifest = RUNTIME / f"{environment}.json"
    previous = json.loads(manifest.read_text()) if manifest.exists() else None
    if environment == "staging":
        if release.exists():
            raise ValueError("Release already exists; use a new build version")
        release.mkdir(parents=True)
        wheel = next((ROOT / "dist").glob("ailp-*.whl"))
        shutil.copy2(wheel, release / wheel.name)
        subprocess.run(  # nosec B603
            [sys.executable, "-m", "venv", str(release / "venv")], check=True
        )
        subprocess.run(  # nosec B603
            [
                str(release / "venv/bin/python"),
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / "requirements.txt"),
                str(release / wheel.name),
            ],
            check=True,
        )
    else:
        staged = json.loads((RUNTIME / "staging.json").read_text())
        if staged["version"] != version or not healthy(8081, version):
            raise RuntimeError("Only the healthy staging version may be promoted")
    stop(environment)
    try:
        start(environment, release, version)
    except Exception:
        if previous:
            start(environment, Path(previous["release"]), previous["version"])
        raise
    manifest.write_text(
        json.dumps({"version": version, "release": str(release), "previous": previous}, indent=2)
    )
    print(f"{environment}: {version} healthy on the {environment} port")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=["staging", "production"])
    parser.add_argument("version")
    args = parser.parse_args()
    deploy(args.environment, args.version)
