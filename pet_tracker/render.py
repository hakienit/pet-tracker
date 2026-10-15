"""Vẽ hình khử răng cưa (anti-aliased) bằng tính coverage từng pixel.

tkinter Canvas trên Windows không antialias oval/arc, nên bóng và thanh progress được render
thành PhotoImage: mỗi pixel tính độ phủ theo khoảng cách tới biên hình (signed distance) rồi
trộn màu. Kích thước nhỏ (bóng ~96x96, thanh ~520x9) nên chỉ tốn vài ms và được cache.
"""
from __future__ import annotations

import math
import struct
import zlib


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
                hover: bool, P: dict, update: str | None = None, rgba: bool = False) -> list:
    """Bóng tròn: đĩa gradient + vòng quota (bo đầu) + viền + badge busy + chấm cảnh báo context.
    Pixel ngoài hình = P['key'] (màu trong suốt của cửa sổ). rgba=True: trả từng hàng là list
    (r, g, b, a) với alpha thật (dùng cho macOS, nơi cửa sổ trong suốt theo alpha thay vì color key)."""
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
    if update:  # chấm báo có bản mới, góc trên-trái
        ru = 5.0 * S
        k = (R - ru * 0.4) * 0.7071
        dots.append((cx - k, cy - k, ru, hex2rgb(update)))
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
            if rgba:
                if A <= 0:
                    row.append((0, 0, 0, 0))
                else:
                    row.append((int(cr / A + 0.5), int(cg / A + 0.5), int(cb / A + 0.5), int(255 * A + 0.5)))
                continue
            if A < 0.4:
                row.append(key)
                continue
            col = (cr / A, cg / A, cb / A)
            if A < 1:
                col = mix(fringe, col, A)
            row.append(rgb2hex(col))
        rows.append(row)
    return rows


def png_bytes(rows) -> bytes:
    """Mã hoá ảnh RGBA (list hàng, mỗi pixel (r, g, b, a)) thành PNG, chỉ dùng zlib."""
    h = len(rows)
    w = len(rows[0]) if h else 0
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b)), min(255, max(0, a))))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def bubble_png(s: int, S: float, pct, prog: str, badge, warn, hover: bool, P: dict, update=None) -> bytes:
    """Bóng dạng PNG có alpha thật (macOS)."""
    return png_bytes(bubble_rows(s, S, pct, prog, badge, warn, hover, P, update=update, rgba=True))


# ---------------------------------------------------------------- logo Wisp
# Đốm lửa nhỏ (wisp) có mắt nằm trong đĩa tối, bao quanh bởi vòng quota cam (giống bóng trong app).
_L_TOP, _L_BOT = (0x2D, 0x2E, 0x38), (0x16, 0x17, 0x1C)
_L_TRACK = (0x34, 0x35, 0x40)
_L_RING_A, _L_RING_B = (0xF4, 0xB0, 0x5E), (0xE0, 0x62, 0x4C)   # đầu vòng vàng cam -> cuối cam đỏ
_L_CORE, _L_MID, _L_TIP = (0xFF, 0xF0, 0xC8), (0xF8, 0xA8, 0x5C), (0xE2, 0x5F, 0x48)
_L_EYE = (0x2A, 0x17, 0x14)
_L_SWEEP = 0.72


def _logo_sample(n: int, px: float, py: float):
    """Màu (r, g, b) tại điểm (px, py) của logo cỡ n, hoặc None nếu nằm ngoài đĩa."""
    cx = cy = n / 2
    dx, dy = px - cx, py - cy
    d = math.hypot(dx, dy)
    R = n / 2 - max(0.5, n / 64)
    if d > R:
        return None
    small = n < 32
    col = mix(_L_TOP, _L_BOT, py / n)
    # quầng sáng sau đốm lửa
    gx, gy = cx, cy + 0.04 * n
    g = math.exp(-((px - gx) ** 2 + (py - gy) ** 2) / (0.2 * n) ** 2)
    col = mix(col, _L_RING_B, 0.30 * g)
    # vòng quota bo đầu
    ring_w = n * (0.13 if small else 0.10)
    r_out = R - max(0.5, n * 0.045)
    r_in = r_out - ring_w
    rc, hw = (r_in + r_out) / 2, ring_w / 2
    sweep = 2 * math.pi * _L_SWEEP
    th = math.atan2(dx, -dy) % (2 * math.pi)
    on_arc = r_in <= d <= r_out and th <= sweep
    cap_s = math.hypot(px - cx, py - (cy - rc)) <= hw
    cap_e = math.hypot(px - (cx + rc * math.sin(sweep)), py - (cy - rc * math.cos(sweep))) <= hw
    if on_arc or cap_s or cap_e:
        t = 0.0 if cap_s and not on_arc else (1.0 if cap_e and not on_arc else th / sweep)
        return mix(_L_RING_A, _L_RING_B, t)
    if r_in <= d <= r_out:
        return _L_TRACK
    # đốm lửa: hình giọt nước (hình tròn đáy + nón tiếp tuyến tới đỉnh), phần trên uốn cong sang phải
    s = 1.15 if small else 1.0
    Cx, Cy, r = cx, cy + 0.085 * n, 0.165 * n * s
    Tx, Ty = Cx, cy - 0.235 * n * s
    h = _c((Cy - py) / (Cy - Ty))
    qx = px - 0.075 * n * s * h * h  # toạ độ đã "duỗi thẳng" để thử với giọt nước thẳng đứng
    inside = math.hypot(qx - Cx, py - Cy) <= r
    if not inside:
        ux, uy = Cx - Tx, Cy - Ty
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        vx, vy = qx - Tx, py - Ty
        t = vx * ux + vy * uy
        perp = abs(vx * uy - vy * ux)
        sin_a = r / L
        cos_a = math.sqrt(1 - sin_a * sin_a)
        inside = 0 < t <= L * cos_a * cos_a and perp <= t * sin_a / cos_a
    if not inside:
        return col
    # màu lửa: đỉnh cam đỏ -> giữa cam -> lõi sáng gần đáy
    v = _c((py - Ty) / (Cy + r - Ty))
    fire = mix(_L_TIP, _L_MID, _c(v / 0.55)) if v < 0.55 else _L_MID
    core = math.exp(-((px - Cx) ** 2 + (py - (Cy + 0.02 * n)) ** 2) / (0.085 * n) ** 2)
    fire = mix(fire, _L_CORE, 0.85 * core)
    if not small:
        ey = Cy - 0.01 * n
        for ex in (Cx - 0.062 * n, Cx + 0.062 * n):
            if ((px - ex) / (0.027 * n)) ** 2 + ((py - ey) / (0.038 * n)) ** 2 <= 1:
                if n >= 64 and math.hypot(px - (ex - 0.009 * n), py - (ey - 0.014 * n)) <= 0.0095 * n:
                    return (0xFF, 0xF6, 0xE6)  # điểm sáng trong mắt
                return _L_EYE
    return fire


def logo_rgba(n: int) -> list:
    """Logo cỡ n x n: list hàng, mỗi pixel (r, g, b, a) int; supersample để mịn ở cỡ nhỏ."""
    ss = 4 if n <= 256 else 2
    k = ss * ss
    rows = []
    for y in range(n):
        row = []
        for x in range(n):
            acc_r = acc_g = acc_b = 0.0
            hits = 0
            for sy in range(ss):
                for sx in range(ss):
                    c = _logo_sample(n, x + (sx + 0.5) / ss, y + (sy + 0.5) / ss)
                    if c is not None:
                        acc_r += c[0]
                        acc_g += c[1]
                        acc_b += c[2]
                        hits += 1
            if not hits:
                row.append((0, 0, 0, 0))
            else:
                row.append((int(acc_r / hits + 0.5), int(acc_g / hits + 0.5), int(acc_b / hits + 0.5),
                            int(255 * hits / k + 0.5)))
        rows.append(row)
    return rows


def logo_rows(n: int, bg: str) -> list:
    """Logo trộn lên nền đặc `bg`, dạng hàng màu hex cho PhotoImage.put."""
    b = hex2rgb(bg)
    return [[rgb2hex(mix(b, (r, g, bl), a / 255)) for r, g, bl, a in row] for row in logo_rgba(n)]
