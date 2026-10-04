"""Continuous local health monitor with an alert inbox and a real incident drill."""

import argparse
import json
import os
import subprocess  # nosec B404
import sys
import time
import urllib.request
from pathlib import Path

from deploy import RUNTIME, healthy, start, stop


def record(kind, detail):
    event = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": kind,
        "detail": detail,
    }
    with (RUNTIME / "alerts.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    print(json.dumps(event), flush=True)


def check(state):
    up = healthy(8082)
    state["failures"] = 0 if up else state["failures"] + 1
    if state["failures"] >= 2 and not state["alerting"]:
        record("FIRING", "Production health failed twice consecutively")
        state["alerting"] = True
    if up and state["alerting"]:
        record("RESOLVED", "Production health recovered")
        state["alerting"] = False
    state["up"] = up
    state["checked_at"] = time.time()
    (RUNTIME / "monitor-state.json").write_text(json.dumps(state))


def incident():
    """Stop the actual production process, detect it, and verify recovery."""
    manifest = json.loads((RUNTIME / "production.json").read_text())
    before = (
        len((RUNTIME / "alerts.jsonl").read_text().splitlines())
        if (RUNTIME / "alerts.jsonl").exists()
        else 0
    )
    state = {"failures": 0, "alerting": False}
    stop("production")
    try:
        check(state)
        time.sleep(1)
        check(state)
        if not state["alerting"]:
            raise RuntimeError("Incident did not trigger alert")
    finally:
        start("production", Path(manifest["release"]), manifest["version"])
    check(state)
    if state["alerting"] or not state["up"]:
        raise RuntimeError("Recovery not verified")
    lines = (RUNTIME / "alerts.jsonl").read_text().splitlines()[before:]
    Path("reports/incident.json").write_text(
        json.dumps([json.loads(line) for line in lines], indent=2)
    )
    print("Incident drill passed: outage, FIRING alert, restart, RESOLVED alert")


def daemon():
    state = {"failures": 0, "alerting": False}
    while True:
        check(state)
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["incident", "start", "daemon"])
    args = parser.parse_args()
    if args.mode == "incident":
        incident()
    elif args.mode == "daemon":
        daemon()
    else:
        pidfile = RUNTIME / "monitor.pid"
        running = False
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), 0)
                running = True
            except ProcessLookupError:
                pass
        if not running:
            env = os.environ.copy()
            env.update(JENKINS_NODE_COOKIE="ailp-monitor", BUILD_ID="dontKillMe")
            with (RUNTIME / "monitor.log").open("ab") as log:
                process = subprocess.Popen(  # nosec B603
                    [sys.executable, str(Path(__file__).resolve()), "daemon"],
                    env=env,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            pidfile.write_text(str(process.pid))
        with urllib.request.urlopen(  # nosec B310
            "http://127.0.0.1:8082/metrics", timeout=5
        ) as response:
            Path("reports/production-metrics.txt").write_bytes(response.read())
        print("Continuous monitor active; local alerts: runtime/alerts.jsonl")
