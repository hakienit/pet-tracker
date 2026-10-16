"""Bộ vẽ SVG tối giản, Python thuần, khử răng cưa: đủ cho hình mascot (assets/mascots.json).

Hỗ trợ: <path d> (M L H V C S Q T A Z, cả chữ thường), <circle>, <ellipse>, <rect rx>, fill, stroke, stroke-width,
stroke-linecap / linejoin (round / butt), opacity, transform rotate / translate / scale. Fill rule nonzero.
Không hỗ trợ (mascot không dùng): gradient, text, clip-path, dash.

    shapes = parse(svg)
    rows = rasterize(shapes, w, h, affine(...))   # list hàng, mỗi pixel (r, g, b, a) int 0..255
"""
from __future__ import annotations

import math
import re

_TAG = re.compile(r"<(path|circle|ellipse|rect)\b([^>]*)/?>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_CMD = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)")
CURVE_STEPS = 14
SUB = 4  # số đường quét con mỗi hàng pixel (khử răng cưa theo chiều dọc)


# ---------------------------------------------------------------- màu + ma trận
def parse_color(s):
    s = (s or "").strip()
    if not s or s in ("none", "transparent"):
        return None
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return None


def hue_rotate(rgb, deg: float):
    """Giống CSS filter hue-rotate(deg)."""
    if not deg or rgb is None:
        return rgb
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    m = (0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
         0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283,
         0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072)
    r, g, b = rgb
    return tuple(max(0, min(255, int(round(m[i] * r + m[i + 1] * g + m[i + 2] * b)))) for i in (0, 3, 6))


def affine(scale: float = 1.0, sx: float = 1.0, sy: float = 1.0, rot: float = 0.0, origin=(0.0, 0.0),
           tx: float = 0.0, ty: float = 0.0):
    """Ma trận (a, b, c, d, e, f): toạ độ hình -> pixel. Co giãn sx/sy và xoay rot (độ) quanh origin (toạ độ hình),
    sau đó nhân scale rồi dời (tx, ty) pixel."""
    ox, oy = origin
    r = math.radians(rot)
    cr, sr = math.cos(r), math.sin(r)
    a, b, c, d = cr * sx, sr * sx, -sr * sy, cr * sy
    e = ox - a * ox - c * oy
    f = oy - b * ox - d * oy
    return (a * scale, b * scale, c * scale, d * scale, e * scale + tx, f * scale + ty)


def _mul(m1, m2):
    """m1 sau m2 (áp m2 trước)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _apply(m, pts):
    a, b, c, d, e, f = m
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in pts]


def _parse_transform(s: str):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", s or ""):
        v = [float(x) for x in _NUM.findall(args)]
        if name == "rotate" and v:
            a = math.radians(v[0])
            cx, cy = (v[1], v[2]) if len(v) >= 3 else (0.0, 0.0)
            ca, sa = math.cos(a), math.sin(a)
            t = (ca, sa, -sa, ca, cx - ca * cx + sa * cy, cy - sa * cx - ca * cy)
        elif name == "translate" and v:
            t = (1.0, 0.0, 0.0, 1.0, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale" and v:
            t = (v[0], 0.0, 0.0, v[1] if len(v) > 1 else v[0], 0.0, 0.0)
        else:
            continue
        m = _mul(m, t)
    return m


# ---------------------------------------------------------------- hình -> danh sách đường gấp khúc
def _arc(x0, y0, rx, ry, phi, large, sweep, x1, y1):
    """Cung elip SVG (endpoint) -> các điểm, theo SVG spec F.6."""
    if rx == 0 or ry == 0:
        return [(x1, y1)]
    rx, ry = abs(rx), abs(ry)
    p = math.radians(phi)
    cp, sp = math.cos(p), math.sin(p)
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    k = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        k = -k
    cxp, cyp = k * rx * y1p / ry, -k * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x0 + x1) / 2
    cy = sp * cxp + cp * cyp + (y0 + y1) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(2, int(abs(dt) / math.radians(8)) + 1)
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def path_points(d: str) -> list:
    """d -> [(điểm..., đóng?)] các đường con."""
    subs, cur = [], []
    x = y = sx = sy = 0.0
    lc = None   # điểm điều khiển cuối (cho S / T)
    prev = ""
    closed = False

    def flush(close):
        nonlocal cur
        if len(cur) > 1:
            subs.append((cur, close))
        cur = []

    for cmd, args in _CMD.findall(d):
        v = [float(n) for n in _NUM.findall(args)]
        rel = cmd.islower()
        C = cmd.upper()
        if C == "Z":
            if cur:
                cur.append((sx, sy))
            flush(True)
            x, y = sx, sy
            cur = [(x, y)]
            prev, lc = "Z", None
            continue
        step = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}[C]
        if step and not v:
            continue
        for i in range(0, len(v) - step + 1, step):
            a = v[i:i + step]
            ox, oy = (x, y) if rel else (0.0, 0.0)
            if C == "M":
                if i == 0:
                    flush(False)
                    x, y = a[0] + ox, a[1] + oy
                    sx, sy = x, y
                    cur = [(x, y)]
                    lc = None
                    continue
                C2 = "L"  # các cặp sau M là L
            else:
                C2 = C
            if C2 == "L":
                x, y = a[0] + ox, a[1] + oy
                cur.append((x, y))
                lc = None
            elif C2 == "H":
                x = a[0] + (x if rel else 0.0)
                cur.append((x, y))
                lc = None
            elif C2 == "V":
                y = a[0] + (y if rel else 0.0)
                cur.append((x, y))
                lc = None
            elif C2 in ("C", "S"):
                if C2 == "C":
                    x1, y1, x2, y2, ex, ey = a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy, a[4] + ox, a[5] + oy
                else:
                    if lc and prev in ("C", "S"):
                        x1, y1 = 2 * x - lc[0], 2 * y - lc[1]
                    else:
                        x1, y1 = x, y
                    x2, y2, ex, ey = a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy
                for k in range(1, CURVE_STEPS + 1):
                    t = k / CURVE_STEPS
                    u = 1 - t
                    cur.append((u ** 3 * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * ex,
                                u ** 3 * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * ey))
                lc = (x2, y2)
                x, y = ex, ey
            elif C2 in ("Q", "T"):
                if C2 == "Q":
                    qx, qy, ex, ey = a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy
                else:
                    qx, qy = (2 * x - lc[0], 2 * y - lc[1]) if lc and prev in ("Q", "T") else (x, y)
                    ex, ey = a[0] + ox, a[1] + oy
                for k in range(1, CURVE_STEPS + 1):
                    t = k / CURVE_STEPS
                    u = 1 - t
                    cur.append((u * u * x + 2 * u * t * qx + t * t * ex, u * u * y + 2 * u * t * qy + t * t * ey))
                lc = (qx, qy)
                x, y = ex, ey
            elif C2 == "A":
                ex, ey = a[5] + ox, a[6] + oy
                cur.extend(_arc(x, y, a[0], a[1], a[2], bool(a[3]), bool(a[4]), ex, ey))
                x, y = ex, ey
                lc = None
            prev = C2
        prev = C if C != "M" else "L"
    flush(closed)
    return subs


def _ellipse(cx, cy, rx, ry, n=None):
    n = n or max(24, int(max(rx, ry) * 2.5))
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _round_rect(x, y, w, h, rx):
    rx = max(0.0, min(rx, w / 2, h / 2))
    if rx <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pts = []
    for cx, cy, a0 in ((x + w - rx, y + rx, -90), (x + w - rx, y + h - rx, 0), (x + rx, y + h - rx, 90),
                       (x + rx, y + rx, 180)):
        for i in range(7):
            a = math.radians(a0 + 15 * i)
            pts.append((cx + rx * math.cos(a), cy + rx * math.sin(a)))
    return pts


def _area(p):
    return sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p))) / 2


def _ccw(p):
    return p if _area(p) >= 0 else p[::-1]


def _stroke_polys(sub, closed, width, cap):
    """Đường gấp khúc -> các đa giác (cùng chiều) mà hợp của chúng là nét vẽ. Nối / đầu tròn bằng hình tròn."""
    hw = width / 2
    pts = sub[:]
    if closed and pts[0] != pts[-1]:
        pts.append(pts[0])
    polys = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        nx, ny = -dy / L * hw, dx / L * hw
        polys.append(_ccw([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]))
    joints = pts[1:-1] if not closed else pts[:-1]
    if cap == "round" or True:  # nối giữa các đoạn luôn tròn: đủ mượt cho nét ngắn của mascot
        for (x, y) in joints:
            polys.append(_ccw(_ellipse(x, y, hw, hw, 16)))
    if cap == "round" and not closed:
        for (x, y) in (pts[0], pts[-1]):
            polys.append(_ccw(_ellipse(x, y, hw, hw, 16)))
    return polys


# ---------------------------------------------------------------- phân tích SVG
def parse(svg: str, hue: float = 0.0) -> list:
    """SVG (chuỗi các thẻ) -> [(đa giác[], (r, g, b), opacity)] theo thứ tự vẽ. hue: xoay màu (độ)."""
    shapes = []
    for tag, attr_s in _TAG.findall(svg):
        A = dict(_ATTR.findall(attr_s))
        num = lambda k, dflt=0.0: float(A.get(k, dflt))  # noqa: E731
        if tag == "path":
            subs = path_points(A.get("d", ""))
        elif tag == "circle":
            subs = [(_ellipse(num("cx"), num("cy"), num("r"), num("r")), True)]
        elif tag == "ellipse":
            subs = [(_ellipse(num("cx"), num("cy"), num("rx"), num("ry")), True)]
        else:
            subs = [(_round_rect(num("x"), num("y"), num("width"), num("height"), num("rx", A.get("ry", 0))), True)]
        m = _parse_transform(A.get("transform", ""))
        subs = [(_apply(m, p), c) for p, c in subs]
        op = float(A.get("opacity", 1.0))
        fill = parse_color(A.get("fill", "#000000"))
        if fill is not None:
            shapes.append(([p for p, _ in subs if len(p) > 2], hue_rotate(fill, hue), op))
        stroke = parse_color(A.get("stroke"))
        sw = float(A.get("stroke-width", 1.0)) * math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        if stroke is not None and sw > 0:
            polys = []
            for p, closed in subs:
                polys.extend(_stroke_polys(p, closed, sw, A.get("stroke-linecap", "butt")))
            shapes.append((polys, hue_rotate(stroke, hue), op))
    return shapes


# ---------------------------------------------------------------- tô
def _coverage(polys, w: int, h: int) -> list:
    """Độ phủ (0..1) từng pixel theo luật nonzero, SUB đường quét / hàng, phủ ngang tính chính xác."""
    edges = []
    for p in polys:
        n = len(p)
        for i in range(n):
            x0, y0 = p[i]
            x1, y1 = p[(i + 1) % n]
            if y0 == y1:
                continue
            wdir = 1 if y1 > y0 else -1
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), wdir))
    cov = [None] * h
    if not edges:
        return cov
    ymin = max(0, int(min(e[0] for e in edges)))
    ymax = min(h, int(max(e[1] for e in edges)) + 1)
    wsub = 1.0 / SUB
    for py in range(ymin, ymax):
        row = None
        for k in range(SUB):
            sy = py + (k + 0.5) / SUB
            xs = [(x0 + (sy - y0) * dxdy, wd) for (y0, y1, x0, dxdy, wd) in edges if y0 <= sy < y1]
            if not xs:
                continue
            xs.sort()
            if row is None:
                row = [0.0] * w
            wind = 0
            for i in range(len(xs) - 1):
                wind += xs[i][1]
                if wind == 0:
                    continue
                a, b = max(0.0, xs[i][0]), min(float(w), xs[i + 1][0])
                if b <= a:
                    continue
                ia, ib = int(a), int(b)
                if ia == ib:
                    row[ia] += (b - a) * wsub
                    continue
                row[ia] += (ia + 1 - a) * wsub
                for j in range(ia + 1, min(ib, w)):
                    row[j] += wsub
                if ib < w:
                    row[ib] += (b - ib) * wsub
        cov[py] = row
    return cov


def rasterize(shapes: list, w: int, h: int, m=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)) -> list:
    """Vẽ shapes (từ parse) lên ảnh w x h trong suốt, toạ độ biến đổi bằng ma trận m. Trả hàng pixel RGBA."""
    buf = [[[0.0, 0.0, 0.0, 0.0] for _ in range(w)] for _ in range(h)]  # premultiplied
    for polys, (r, g, b), op in shapes:
        cov = _coverage([_apply(m, p) for p in polys], w, h)
        for y, row in enumerate(cov):
            if row is None:
                continue
            brow = buf[y]
            for x, c in enumerate(row):
                if c <= 0.0:
                    continue
                a = (1.0 if c > 1.0 else c) * op
                px = brow[x]
                k = 1.0 - a
                px[0] = r * a + px[0] * k
                px[1] = g * a + px[1] * k
                px[2] = b * a + px[2] * k
                px[3] = a + px[3] * k
    out = []
    for brow in buf:
        row = []
        for pr, pg, pb, pa in brow:
            if pa <= 0.002:
                row.append((0, 0, 0, 0))
            else:
                row.append((int(pr / pa + 0.5), int(pg / pa + 0.5), int(pb / pa + 0.5), int(pa * 255 + 0.5)))
        out.append(row)
    return out
