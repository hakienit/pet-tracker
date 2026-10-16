"""Đường dẫn tới thư mục assets/: cạnh mã nguồn khi chạy source, trong thư mục giải nén khi chạy bản PyInstaller."""
from __future__ import annotations

import sys
from pathlib import Path

ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"


def asset_path(*parts: str) -> Path:
    return ASSETS.joinpath(*parts)
