"""Chụp ảnh minh hoạ cho README từ landing docs/site/index.html bằng Chrome/Edge headless.

    python tools/shoot.py            # mọi ảnh, cả en và vi
    python tools/shoot.py hero panel # chỉ vài ảnh

Ảnh ra docs/site/img/<tên>-<en|vi>.png. Landing tải font Archivo từ Google Fonts nên cần mạng.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "site" / "index.html"
OUT = ROOT / "docs" / "site" / "img"

# tên -> (tham số trang, rộng, cao). Cao chọn vừa nội dung vì không cắt ảnh được khi chỉ dùng stdlib.
SHOTS = {
    "hero": ("shot=hero&theme=dark&coll=run,done,idle,closed", 1240, 950),
    "island": ("shot=island", 1240, 470),
    "bubble-signal": ("shot=custom&bub=signal&theme=dark", 1240, 820),
    "bubble-mascot": ("shot=custom&bub=mascot&theme=dark", 1240, 860),
    "mascots": ("shot=mascots", 1240, 820),
    "panel": ("shot=panel", 1240, 1360),
}
LANGS = ("en", "vi")


def find_browser() -> str:
    cands = [
        os.environ.get("CHROME"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
    ]
    for c in cands:
        if c and Path(c).exists():
            return c
    sys.exit("Không tìm thấy Chrome/Edge. Đặt biến CHROME=<đường dẫn> rồi chạy lại.")


def main(names: list) -> None:
    browser = find_browser()
    OUT.mkdir(parents=True, exist_ok=True)
    picked = names or list(SHOTS)
    bad = [n for n in picked if n not in SHOTS]
    if bad:
        sys.exit(f"Không có ảnh: {', '.join(bad)}. Có: {', '.join(SHOTS)}")
    with tempfile.TemporaryDirectory() as prof:  # profile riêng: không đụng Chrome đang mở
        for name in picked:
            query, w, h = SHOTS[name]
            for lang in LANGS:
                out = OUT / f"{name}-{lang}.png"
                url = f"{PAGE.as_uri()}?{query}&lang={lang}"
                subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                f"--user-data-dir={prof}", f"--window-size={w},{h}",
                                "--run-all-compositor-stages-before-draw", f"--screenshot={out}", url],
                               check=True, timeout=120, capture_output=True)
                print(f"{out.relative_to(ROOT)}  {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
