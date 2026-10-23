"""Chạy Wisp từ source và tự khởi động lại khi file .py đổi (không cần build).

  /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 tools/dev.py

Dùng Python python.org (Tk 8.6, giống bản release). Ctrl+C để dừng.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def stamp() -> tuple:
    return tuple(sorted((str(p), p.stat().st_mtime_ns) for p in ROOT.glob("**/*.py") if "build" not in p.parts))


proc, seen = None, None
try:
    while True:
        now = stamp()
        if now != seen:
            seen = now
            if proc:
                proc.terminate()
                proc.wait()
            print("start", time.strftime("%H:%M:%S"), flush=True)
            proc = subprocess.Popen([sys.executable, str(ROOT / "main.py")])
        time.sleep(0.5)
except KeyboardInterrupt:
    if proc:
        proc.terminate()
