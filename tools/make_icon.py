"""Tạo assets/pet-tracker.ico (16–256 px) và assets/pet-tracker.png: bóng tối, vòng cam Claude.

Chỉ dùng stdlib: tự tính coverage (khử răng cưa) cho từng pixel với alpha thật, ghi PNG bằng
zlib, rồi gói các PNG vào file .ico (định dạng ICO chứa PNG, Windows Vista trở lên đọc được).
Chạy: python tools/make_icon.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)

TOP = (0x2D, 0x2E, 0x38)
BOT = (0x18, 0x19, 0x1F)
TRACK = (0x35, 0x36, 0x41)
RING = (0xD9, 0x77, 0x57)
EYE = (0xEE, 0xEE, 0xF3)
SWEEP = 0.72  # phần vòng tô màu


def _c(x):
    return 0.0 if x <= 0 else 1.0 if x >= 1 else x


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def render(n: int) -> bytes:
    """Trả RGBA bytes n x n."""
    ss = 4  # supersample để icon nhỏ vẫn mịn
    cx = cy = n / 2
    R = n / 2 - max(0.5, n / 64)
    ring_w = max(1.5, n * 0.11)
    r_out = R - max(0.5, n * 0.05)
    r_in = r_out - ring_w
    rc, hw = (r_in + r_out) / 2, ring_w / 2
    sweep = 2 * math.pi * SWEEP
    ex, ey = cx + rc * math.sin(sweep), cy - rc * math.cos(sweep)
    sx0, sy0 = cx, cy - rc
    eye_r = max(0.9, n * 0.055)
    eyes = ((cx - n * 0.12, cy - n * 0.02), (cx + n * 0.12, cy - n * 0.02))
    out = bytearray()
    for y in range(n):
        for x in range(n):
            acc = [0.0, 0.0, 0.0]
            A = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    px = x + (sx + 0.5) / ss
                    py = y + (sy + 0.5) / ss
                    dx, dy = px - cx, py - cy
                    d = math.hypot(dx, dy)
                    if d > R:
                        continue
                    col = _mix(TOP, BOT, py / n)
                    if r_in <= d <= r_out:
                        col = TRACK
                        th = math.atan2(dx, -dy) % (2 * math.pi)
                        if th <= sweep:
                            col = RING
                    if math.hypot(px - ex, py - ey) <= hw or math.hypot(px - sx0, py - sy0) <= hw:
                        col = RING
                    if n >= 24 and any(math.hypot(px - ex_, py - ey_) <= eye_r for ex_, ey_ in eyes):
                        col = EYE
                    acc[0] += col[0]
                    acc[1] += col[1]
                    acc[2] += col[2]
                    A += 1
            if A == 0:
                out += b"\x00\x00\x00\x00"
                continue
            k = ss * ss
            out += bytes((int(acc[0] / A + 0.5), int(acc[1] / A + 0.5), int(acc[2] / A + 0.5),
                          int(255 * A / k + 0.5)))
    return bytes(out)


def png(n: int, rgba: bytes) -> bytes:
    raw = b"".join(b"\x00" + rgba[y * n * 4:(y + 1) * n * 4] for y in range(n))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pngs = [(n, png(n, render(n))) for n in SIZES]
    (OUT / "pet-tracker.ico").write_bytes(ico(pngs))
    (OUT / "pet-tracker.png").write_bytes(dict(pngs)[256])
    print("wrote", OUT / "pet-tracker.ico", OUT / "pet-tracker.png")


if __name__ == "__main__":
    main()
