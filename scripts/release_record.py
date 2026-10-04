"""Archive version and artifact identity without runtime credentials."""

import json
import os
from pathlib import Path

root = Path(os.environ["AILP_RUNTIME"])
record = json.loads((root / "production.json").read_text())
record["commit"] = os.environ.get("GIT_COMMIT")
record["build"] = os.environ.get("BUILD_NUMBER")
record["sha256"] = Path("reports/checksums.txt").read_text().strip()
Path("reports/release.json").write_text(json.dumps(record, indent=2))
