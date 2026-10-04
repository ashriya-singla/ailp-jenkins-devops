"""Exercise the installed staging wheel over HTTP, including consent revocation."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = Path(os.environ.get("AILP_RUNTIME", str(ROOT / "runtime")))
tokens = json.loads((runtime / "credentials.json").read_text())


def call(path, method="GET", body=None, role="STUDENT", expected=200):
    request = urllib.request.Request(
        f"http://127.0.0.1:8081{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {tokens[role + '_TOKEN']}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(  # nosec B310
            request, timeout=5
        ) as response:
            code, data = response.status, response.read()
    except urllib.error.HTTPError as error:
        code, data = error.code, error.read()
    if code != expected:
        raise RuntimeError(f"{method} {path}: expected {expected}, got {code}")
    return json.loads(data) if data else None


if __name__ == "__main__":
    record = call(
        "/api/evidence",
        "POST",
        {
            "source": "CI smoke test",
            "prompt": "Explain CI",
            "response": "Automate checks",
            "consent": True,
        },
        expected=201,
    )
    try:
        call(
            f"/api/evidence/{record['id']}/decision",
            "PUT",
            {"decision": "Modified", "reasoning": "Verified against project requirements"},
        )
        call("/api/privacy", "PUT", {"shared": False})
        call("/api/passport", role="EDUCATOR", expected=403)
        call("/api/privacy", "PUT", {"shared": True})
        result = call("/api/passport", role="EDUCATOR")
        if record["id"] not in [row["id"] for row in result["evidence"]]:
            raise RuntimeError("Missing source evidence")
        call("/api/privacy", "PUT", {"shared": False})
        call("/api/passport", role="EDUCATOR", expected=403)
    finally:
        call(f"/api/evidence/{record['id']}", "DELETE", expected=204)
    print("HTTP smoke checks passed: import, decision, review consent, revocation, deletion")
