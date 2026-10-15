"""Vẽ hình khử răng cưa (anti-aliased) bằng tính coverage từng pixel.

tkinter Canvas trên Windows không antialias oval/arc, nên bóng và thanh progress được render
thành PhotoImage: mỗi pixel tính độ phủ theo khoảng cách tới biên hình (signed distance) rồi
trộn màu. Kích thước nhỏ (bóng ~96x96, thanh ~520x9) nên chỉ tốn vài ms và được cache.
"""
from __future__ import annotations

import math


def hex2rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb2hex(c) -> str:
    return "#%02x%02x%02x" % tuple(0 if v < 0 else 255 if v > 255 else int(v + 0.5) for v in c)


def mix(a, b, t: float) -> tuple:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _c(x: float) -> float:
    return 0.0 if x <= 0 else 1.0 if x >= 1 else x


def to_photo_data(rows) -> str:
    return " ".join("{" + " ".join(r) + "}" for r in rows)


def capsule_rows(w: int, h: int, frac: float, fg: str, track: str, bg: str) -> list:
    """Thanh bo tròn hai đầu: nền `track`, phần đã dùng `frac` (0..1) màu `fg`, ngoài hình là `bg`."""
    r = h / 2.0
    fg_, tr_, bg_ = hex2rgb(fg), hex2rgb(track), hex2rgb(bg)
    frac = 0.0 if frac < 0 else 1.0 if frac > 1 else frac
    x_end = max(r, min(w - r, frac * w - r)) if frac > 0 else None
    rows = []
    for y in range(h):
        dy = y + 0.5 - r
        row = []
        for x in range(w):
            px = x + 0.5
            sx = r if px < r else (w - r if px > w - r else px)
            a = _c(0.5 - (math.hypot(px - sx, dy) - r))
            if a <= 0:
                row.append(bg)
                continue
            col = tr_
            if x_end is not None:
                sx2 = r if px < r else (x_end if px > x_end else px)
                p = _c(0.5 - (math.hypot(px - sx2, dy) - r))
                if p > 0:
                    col = mix(col, fg_, p)
            row.append(rgb2hex(mix(bg_, col, a)))
        rows.append(row)
    return rows


def bubble_rows(s: int, S: float, pct, prog: str, badge: str | None, warn: str | None,
                hover: bool, P: dict) -> list:
    """Bóng tròn: đĩa gradient + vòng quota (bo đầu) + viền + badge busy + chấm cảnh báo context.
    Pixel ngoài hình = P['key'] (màu trong suốt của cửa sổ)."""
    cx = cy = s / 2.0
    R = s / 2.0 - 0.75
    ring_w = 5.0 * S
    r_out = R - 3.5 * S
    r_in = r_out - ring_w
    rc = (r_in + r_out) / 2.0
    hw = ring_w / 2.0
    has_prog = pct is not None and pct > 0
    sweep = 2 * math.pi * max(0.0, min(100.0, pct or 0.0)) / 100.0
    sx0, sy0 = cx, cy - rc
    ex, ey = cx + rc * math.sin(sweep), cy - rc * math.cos(sweep)

    top, bot = hex2rgb(P["disc_top"]), hex2rgb(P["disc_bot"])
    track, prog_ = hex2rgb(P["track"]), hex2rgb(prog)
    rim = hex2rgb(P["rim_hover"] if hover else P["rim"])
    rim_a = 0.95 if hover else 0.5
    fringe = hex2rgb(P["fringe"])
    cut = hex2rgb(P["cutout"])
    key = P["key"]

    dots = []
    if badge:
        rb = 8.5 * S
        dots.append((s - rb - 0.75, rb + 0.75, rb, hex2rgb(badge)))
    if warn:
        rw = 5.5 * S
        k = (R - rw * 0.4) * 0.7071
        dots.append((cx - k, cy + k, rw, hex2rgb(warn)))
    ring_cut = 2.0 * S

    rows = []
    for y in range(s):
        py = y + 0.5
        dc = mix(top, bot, py / s)
        row = []
        for x in range(s):
            px = x + 0.5
            dx, dy = px - cx, py - cy
            d = math.sqrt(dx * dx + dy * dy)
            A = 0.0
            cr = cg = cb = 0.0
            a = R - d + 0.5
            if a > 0:
                a = 1.0 if a > 1 else a
                col = dc
                band = _c(r_out - d + 0.5) * _c(d - r_in + 0.5)
                if band > 0:
                    col = mix(col, track, band)
                if has_prog and r_in - 1 < d < r_out + 1:
                    p = 0.0
                    if band > 0:
                        th = math.atan2(dx, -dy)
                        if th < 0:
                            th += 2 * math.pi
                        if th <= sweep:
                            p = band
                    p = max(p, _c(hw - math.hypot(px - ex, py - ey) + 0.5),
                            _c(hw - math.hypot(px - sx0, py - sy0) + 0.5))
                    if p > 0:
                        col = mix(col, prog_, p)
                rcov = _c(1.0 - abs(d - (R - 0.9))) * rim_a
                if rcov > 0:
                    col = mix(col, rim, rcov)
                cr, cg, cb, A = col[0] * a, col[1] * a, col[2] * a, a
            for ox, oy, orad, fill in dots:
                dd = math.hypot(px - ox, py - oy)
                ab = _c(orad + ring_cut - dd + 0.5)
                if ab > 0:
                    cr, cg, cb = cut[0] * ab + cr * (1 - ab), cut[1] * ab + cg * (1 - ab), cut[2] * ab + cb * (1 - ab)
                    A = ab + A * (1 - ab)
                    af = _c(orad - dd + 0.5)
                    if af > 0:
                        cr, cg, cb = fill[0] * af + cr * (1 - af), fill[1] * af + cg * (1 - af), fill[2] * af + cb * (1 - af)
                        A = af + A * (1 - af)
            if A < 0.4:
                row.append(key)
                continue
            col = (cr / A, cg / A, cb / A)
            if A < 1:
                col = mix(fringe, col, A)
            row.append(rgb2hex(col))
        rows.append(row)
    return rows
