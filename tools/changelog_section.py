"""In phần CHANGELOG của một version (dùng làm release notes).

    python tools/changelog_section.py v0.1.0 > notes.md
Thoát mã 1 nếu CHANGELOG.md chưa có mục cho version đó.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def section(text: str, version: str):
    version = version.lstrip("vV")
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else None


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    body = section(path.read_text(encoding="utf-8"), argv[1])
    if not body:
        print(f"CHANGELOG.md chưa có mục cho {argv[1]}", file=sys.stderr)
        return 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
