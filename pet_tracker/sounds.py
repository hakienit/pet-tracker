"""Phát âm thanh thông báo, không chặn UI. Windows: winsound. macOS: afplay."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .assets import asset_path


def play(kind: str) -> None:
    """kind: "wait" | "done". Lỗi (thiếu file, không có thiết bị âm thanh) thì im lặng."""
    p: Path = asset_path("sounds", f"{kind}.wav")
    if not p.exists():
        return
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(str(p), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
