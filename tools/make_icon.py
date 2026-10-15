"""Tạo assets/wisp.ico (16–256 px) và assets/wisp.png từ logo Wisp (đốm lửa có mắt trong vòng quota).

Hình vẽ nằm ở pet_tracker/render.py (logo_rgba), dùng chung với logo trên header panel. Chỉ dùng
stdlib: PNG ghi bằng zlib, rồi gói các PNG vào file .ico (định dạng ICO chứa PNG, Windows Vista
trở lên đọc được).
Chạy: python tools/make_icon.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pet_tracker.render import logo_rgba, png_bytes  # noqa: E402

OUT = ROOT / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def ico(pngs: list) -> bytes:
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    dirs, blobs = b"", b""
    for n, data in pngs:
        b = 0 if n >= 256 else n
        dirs += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return head + dirs + blobs


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--png-size", type=int, help="chỉ xuất một PNG kích thước này (vd. 1024 cho .icns macOS)")
    ap.add_argument("--out", help="đường dẫn PNG khi dùng --png-size")
    args = ap.parse_args(argv)
    if args.png_size:
        out = Path(args.out or (OUT / f"wisp-{args.png_size}.png"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png_bytes(logo_rgba(args.png_size)))
        print("wrote", out)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    pngs = [(n, png_bytes(logo_rgba(n))) for n in SIZES]
    (OUT / "wisp.ico").write_bytes(ico(pngs))
    (OUT / "wisp.png").write_bytes(dict(pngs)[256])
    print("wrote", OUT / "wisp.ico", OUT / "wisp.png")


if __name__ == "__main__":
    main()
