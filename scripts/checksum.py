"""Record immutable artifact hashes."""

import hashlib
from pathlib import Path

files = sorted(Path("dist").glob("*.whl"))
if not files:
    raise RuntimeError("No build artifact")
Path("reports/checksums.txt").write_text(
    "\n".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in files)
    + "\n"
)
