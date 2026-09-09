"""Safe current-source scan; output only rule, filename and line, never matching values.

Use --export to copy the same nonignored source inventory into an ignored directory
for a full Gitleaks scan. This helper is an extra guard, not a replacement for Gitleaks.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--export", action="store_true")
args = parser.parse_args()
paths = sorted(set(subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root,
).decode().split("\0")) - {""})
rules = {
    "provider-secret-assignment": re.compile(
        r'''(?i)(?:VITE_)?(?:TMDB|FOURSQUARE|GEOAPIFY|RESEND)[A-Z_]*(?:KEY|TOKEN)\s*[:=]\s*["']?[A-Za-z0-9_/+=-]{16,}'''
    ),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
}
problems = []
export = root / ".verification" / ("scan-" + uuid4().hex) if args.export else None
for relative in paths:
    path = root / relative
    if path.name.startswith(".env") and path.name != ".env.example":
        problems.append((relative, 0, "environment-file-in-source-inventory"))
        continue
    if not path.is_file():
        continue  # staged deletion; never read historical blob into current snapshot
    if path.is_symlink():
        problems.append((relative, 0, "symlink-requires-review"))
        continue
    if export:
        destination = export / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    content = path.read_bytes()
    if b"\0" in content:
        continue
    for number, line in enumerate(content.decode("utf-8", errors="replace").splitlines(), 1):
        if path.name == ".env.example" and not re.fullmatch(r"[A-Z][A-Z0-9_]*=", line):
            problems.append((relative, number, "example-must-contain-names-only"))
        for rule, pattern in rules.items():
            if pattern.search(line):
                problems.append((relative, number, rule))
for filename, line, rule in problems:
    print(f"{filename}:{line}: {rule}")
print(f"Scanned {len(paths)} source paths; {len(problems)} findings (values suppressed).")
if export:
    print(f"Gitleaks snapshot: {export}")
sys.exit(bool(problems))
