"""Đồ hoạ của giao diện: icon, viên island, viền động theo trạng thái, 6 kiểu bóng tín hiệu, chuyển ảnh sang Tk.

Mọi hình vẽ bằng pet_tracker.vector (khử răng cưa, Python thuần) thành hàng pixel RGBA, rồi:
  - Windows: trộn sẵn lên màu nền (panel) hoặc màu key trong suốt (cửa sổ island / bóng) -> PhotoImage.put
  - macOS: trộn sẵn lên màu nền đặc (panel; island và bóng tín hiệu là cửa sổ nền đặc cắt bằng CALayer). Ảnh trên
    Canvas nền systemTransparent không hiện (Tk 8.6), nên bóng mascot vẽ bằng polygon / line của Canvas (draw_items).
Nguồn hình: docs/site/assets/wisp-ui.js. Ảnh được cache theo khoá; hàm ở đây không giữ tham chiếu Tk.
"""
from __future__ import annotations

import base64
import math
import tkinter as tk

from .. import platform as plat
from .. import render, vector

ALPHA = plat.transparent_key() is None  # macOS: alpha thật

# icon nét 24x24, giống P trong wisp-ui.js
ICONS = {
    "bell": '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    "run": '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    "done": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "idle": '<path d="M19.5 14.5A8 8 0 1 1 9.5 4.5a6.5 6.5 0 0 0 10 10z"/>',
    "gear": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "open": '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v6H4V6h6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>', "chev": '<path d="M9 6l6 6-6 6"/>', "back": '<path d="M15 6l-6 6 6 6"/>',
    "more": '<circle cx="5" cy="12" r="1.3" fill="C"/><circle cx="12" cy="12" r="1.3" fill="C"/><circle cx="19" cy="12" r="1.3" fill="C"/>',
    "dl": '<path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/>',
    "up": '<path d="M12 20V9"/><path d="M7 14l5-5 5 5"/><path d="M5 4h14"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><path d="M12 7.5v.1"/>',
    "mute": '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 9l4 6M21 9l-4 6"/>',
    "sound": '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 8a5 5 0 0 1 0 8"/>',
    "exit": '<path d="M10 4H5v16h5"/><path d="M14 8l4 4-4 4"/><path d="M18 12H9"/>',
    "trash": '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
    "branch": '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="7" r="2"/><path d="M6 7v10"/><path d="M18 9c0 5-6 4-11 8.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>', "swap": '<path d="M4 8h13l-3-3"/><path d="M20 16H7l3 3"/>',
    "power": '<path d="M12 3v8"/><path d="M6.3 7a8 8 0 1 0 11.4 0"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>', "term": '<path d="M4 6l6 6-6 6"/><path d="M12 18h8"/>',
    "check": '<path d="M4 12.5l4 4L20 5"/>',
}


# ---------------------------------------------------------------- RGBA -> Tk
def _flatten(rows, bg):
    """Trộn ảnh RGBA lên nền đặc bg (hex) -> hàng màu hex."""
    br, bgc, bb = render.hex2rgb(bg)
    out = []
    for row in rows:
        o = []
        for r, g, b, a in row:
            if a >= 255:
                o.append("#%02x%02x%02x" % (r, g, b))
            elif a <= 0:
                o.append(bg)
            else:
                k = a / 255.0
                o.append("#%02x%02x%02x" % (int(r * k + br * (1 - k) + .5), int(g * k + bgc * (1 - k) + .5),
                                             int(b * k + bb * (1 - k) + .5)))
        out.append(o)
    return out


def _keyed(rows, key, fringe):
    """Cho cửa sổ trong suốt bằng color key (Windows): pixel gần trong suốt -> key, mép trộn với màu fringe."""
    fr, fg, fb = render.hex2rgb(fringe)
    out = []
    for row in rows:
        o = []
        for r, g, b, a in row:
            if a < 102:
                o.append(key)
            elif a >= 250:
                o.append("#%02x%02x%02x" % (r, g, b))
            else:
                k = a / 255.0
                o.append("#%02x%02x%02x" % (int(r * k + fr * (1 - k) + .5), int(g * k + fg * (1 - k) + .5),
                                             int(b * k + fb * (1 - k) + .5)))
        out.append(o)
    return out


def to_photo(master, rows, bg=None, fringe="#0d0d11"):
    """PhotoImage từ hàng RGBA. bg: màu nền đặc phía sau (panel); None: cửa sổ trong suốt (island, bóng)."""
    if not rows or not rows[0]:
        return tk.PhotoImage(master=master, width=1, height=1)
    if ALPHA and not bg:  # macOS, nền có màu đặc: put() như Windows (đường đã chạy ổn ở 0.1.8 trong panel bo góc)
        return tk.PhotoImage(master=master, data=base64.b64encode(render.png_bytes(rows)).decode("ascii"), format="png")
    hexrows = _flatten(rows, bg) if bg else _keyed(rows, plat.transparent_key(), fringe)
    img = tk.PhotoImage(master=master, width=len(rows[0]), height=len(rows))
    img.put(render.to_photo_data(hexrows))
    return img


# ---------------------------------------------------------------- icon
def _icon_svg(name: str, color: str, sw: float) -> str:
    import re

    def style(m):
        tag = m.group(0)
        if 'fill="C"' in tag:  # chấm đặc (icon ⋯)
            return tag.replace('fill="C"', f'fill="{color}"')
        return tag[:-2] + f' fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'

    return re.sub(r"<(?:path|circle|rect)\b[^>]*/>", style, ICONS.get(name, ""))


def icon_rows(name: str, px: int, color: str, sw: float = 1.9) -> list:
    return vector.rasterize(vector.parse(_icon_svg(name, color, sw)), px, px, vector.affine(scale=px / 24.0))


def icon_items(name: str, color: str, sw: float = 1.9) -> list:
    """Icon dạng vector.items (khung 24x24) để vẽ bằng draw_items."""
    return vector.items(_icon_svg(name, color, sw))


# ---------------------------------------------------------------- vẽ vector thẳng lên Canvas (macOS)
def _flat(pts) -> list:
    return [v for xy in pts for v in xy]


def draw_items(c, its, m, tag) -> list:
    """Vẽ its (vector.items) lên Canvas c theo ma trận m: vùng tô = polygon, nét = line đầu tròn. Trả [(item, điểm
    gốc)] để move_items đổi dáng mà không tạo lại item. Bỏ qua opacity (Canvas không có alpha)."""
    k = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
    out = []
    for it in its:
        col = "#%02x%02x%02x" % it[2]
        if it[0] == "fill":
            for p in it[1]:
                out.append((c.create_polygon(*_flat(vector.transform(m, p)), fill=col, outline="", tags=tag), p))
            continue
        for p, closed in it[1]:
            pts = p + p[:1] if closed else p
            if len(pts) < 2:
                continue
            i = c.create_line(*_flat(vector.transform(m, pts)), fill=col, width=max(1.0, it[4] * k),
                              capstyle="round" if it[5] == "round" else "butt", joinstyle="round", tags=tag)
            out.append((i, pts))
    return out


def move_items(c, handle, m) -> None:
    for i, p in handle:
        c.coords(i, *_flat(vector.transform(m, p)))


def pill(c, x0, y0, x1, y1, fill, border=None, tag=None) -> None:
    """Viên thuốc bằng oval + rectangle (không dùng ảnh), viền 1px nếu có border."""
    for inset, col in ((0, border), (1 if border else 0, fill)):
        if col is None:
            continue
        a, b, cc, d = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        r = (d - b) / 2
        c.create_oval(a, b, a + 2 * r, d, fill=col, outline="", tags=tag)
        c.create_oval(cc - 2 * r, b, cc, d, fill=col, outline="", tags=tag)
        c.create_rectangle(a + r, b, cc - r, d, fill=col, outline="", tags=tag)


# ---------------------------------------------------------------- hình cơ bản (SDF)
def _cov(d: float) -> float:
    return 0.0 if d >= 0.5 else 1.0 if d <= -0.5 else 0.5 - d


def sd_round_rect(px, py, w, h, r):
    """Khoảng cách có dấu tới hình chữ nhật bo góc r (âm = bên trong)."""
    qx = abs(px - w / 2) - (w / 2 - r)
    qy = abs(py - h / 2) - (h / 2 - r)
    ox, oy = max(qx, 0.0), max(qy, 0.0)
    return math.hypot(ox, oy) + min(max(qx, qy), 0.0) - r


def shape_rows(w: int, h: int, r: float, fill: str, border: str | None = None, bw: float = 1.0) -> list:
    """Hình bo góc (r = h/2: viên thuốc, r = w/2 = h/2: tròn) tô fill, viền mảnh border."""
    f = render.hex2rgb(fill)
    b = render.hex2rgb(border) if border else None
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            d = sd_round_rect(x + .5, y + .5, w, h, r)
            a = _cov(d)
            if a <= 0:
                row.append((0, 0, 0, 0))
                continue
            col = f
            if b is not None:
                k = _cov(-(d + bw))  # phần viền: từ mép vào trong bw pixel
                if k > 0:
                    col = render.mix(f, b, k)
            row.append((int(col[0] + .5), int(col[1] + .5), int(col[2] + .5), int(255 * a + .5)))
        out.append(row)
    return out


# ---------------------------------------------------------------- viền động theo trạng thái
def _band(w: int, h: int, r: float, bw: float) -> list:
    """Các pixel thuộc dải viền (bề dày bw, bên trong mép): (x, y, độ phủ, góc 0..1 tính từ tâm, chiều kim đồng hồ từ 12h)."""
    out = []
    cx, cy = w / 2, h / 2
    for y in range(h):
        for x in range(w):
            d = sd_round_rect(x + .5, y + .5, w, h, r)
            if d > 0.5 or d < -bw - 0.5:
                continue
            c = _cov(d) * (1.0 - _cov(d + bw))
            if c <= 0.01:
                continue
            ang = (math.atan2(x + .5 - cx, -(y + .5 - cy)) / (2 * math.pi)) % 1.0
            out.append((x, y, c, ang))
    return out


_STOPS = (0.0, 0.2, 0.35, 0.5, 0.7, 0.85, 1.0)


def _conic(c1, c2, c3, t):
    cols = (c1, c2, c3, c1, c2, c3, c1)
    for i in range(6):
        if t <= _STOPS[i + 1]:
            k = (t - _STOPS[i]) / (_STOPS[i + 1] - _STOPS[i])
            return render.mix(cols[i], cols[i + 1], k)
    return c1


def border_frames(base: list, w: int, h: int, r: float, bw: float, state: str, P: dict, n: int = 24) -> list:
    """n khung hình: ảnh base (RGBA) + dải viền gradient xoay vòng theo trạng thái (giống .ab trong wisp-ui.css).
    wait: lửa + đốm sáng chạy ngược; quota: đỏ + nhấp nháy. Khung cuối nối liền khung đầu."""
    c1, c2, c3, _ = P["ab"][state if state in P["ab"] else "idle"]
    c1, c2, c3 = render.hex2rgb(c1), render.hex2rgb(c2), render.hex2rgb(c3)
    band = _band(w, h, r, bw)
    frames = []
    for i in range(n):
        ph = i / n
        pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(2 * math.pi * ph * 2)) if state == "quota" else 1.0
        img = [list(row) for row in base]
        for x, y, c, ang in band:
            col = _conic(c1, c2, c3, (ang - ph) % 1.0)
            if state == "wait":  # hai đốm sáng chạy ngược chiều, nhanh hơn 1.6 lần
                for spot in ((-1.6 * ph) % 1.0, (-1.6 * ph + 0.5) % 1.0):
                    dd = min(abs(ang - spot), 1 - abs(ang - spot))
                    if dd < 0.08:
                        col = render.mix(col, (255, 240, 180), 0.9 * (1 - dd / 0.08))
            k = c * pulse
            pr, pg, pb, pa = img[y][x]
            if pa == 0:
                img[y][x] = (int(col[0]), int(col[1]), int(col[2]), int(255 * k))
            else:
                img[y][x] = (int(pr + (col[0] - pr) * k), int(pg + (col[1] - pg) * k), int(pb + (col[2] - pb) * k), pa)
        frames.append(img)
    return frames


class Animated:
    """Ảnh base + viền động: dựng từng khung khi cần (lười), giữ PhotoImage đã dựng.
    Windows: chỉ thay pixel dải viền trên hàng hex của base (nhanh). macOS: PNG từng khung.
    bg: màu nền đặc phía sau (panel) hoặc None (cửa sổ trong suốt)."""

    def __init__(self, master, base: list, r: float, bw: float, state: str, P: dict, bg=None, n: int = 24,
                 fringe="#0d0d11"):
        self.master, self.base, self.state, self.P, self.bg, self.n = master, base, state, P, bg, n
        self.h, self.w = len(base), len(base[0]) if base else 0
        self.band = _band(self.w, self.h, r, bw) if state else []
        self.frames: dict = {}
        self.fringe = fringe
        self.alpha = ALPHA and not bg  # nền đặc (macOS: island, bóng tín hiệu): trộn sẵn rồi put() như Windows
        if not self.alpha:
            self.base_hex = _flatten(base, bg) if bg else _keyed(base, plat.transparent_key(), fringe)
        self.static = None

    def still(self):
        """Ảnh không có viền động (giảm chuyển động / chưa có trạng thái)."""
        if self.static is None:
            self.static = self.frame(0) if self.state else to_photo(self.master, self.base, self.bg, self.fringe)
        return self.static

    def frame(self, i: int):
        i %= self.n
        img = self.frames.get(i)
        if img is not None:
            return img
        c1, c2, c3, _ = self.P["ab"].get(self.state, self.P["ab"]["idle"])
        c1, c2, c3 = render.hex2rgb(c1), render.hex2rgb(c2), render.hex2rgb(c3)
        ph = i / self.n
        pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(4 * math.pi * ph)) if self.state == "quota" else 1.0
        spots = ((-1.6 * ph) % 1.0, (-1.6 * ph + 0.5) % 1.0) if self.state == "wait" else ()
        changes = []
        for x, y, c, ang in self.band:
            col = _conic(c1, c2, c3, (ang - ph) % 1.0)
            for spot in spots:
                dd = min(abs(ang - spot), 1 - abs(ang - spot))
                if dd < 0.08:
                    col = render.mix(col, (255, 240, 180), 0.9 * (1 - dd / 0.08))
            br, bgc, bb, ba = self.base[y][x]
            k = c * pulse
            if ba == 0:
                px = (int(col[0]), int(col[1]), int(col[2]), int(255 * k))
            else:
                px = (int(br + (col[0] - br) * k), int(bgc + (col[1] - bgc) * k), int(bb + (col[2] - bb) * k), ba)
            changes.append((x, y, px))
        if self.alpha:
            rows = [list(r) for r in self.base]
            for x, y, px in changes:
                rows[y][x] = px
            img = to_photo(self.master, rows)
        else:
            rows = [list(r) for r in self.base_hex]
            key = plat.transparent_key()
            for x, y, px in changes:
                one = _flatten([[px]], self.bg)[0][0] if self.bg else _keyed([[px]], key, self.fringe)[0][0]
                rows[y][x] = one
            img = tk.PhotoImage(master=self.master, width=self.w, height=self.h)
            img.put(render.to_photo_data(rows))
        self.frames[i] = img
        return img


# ---------------------------------------------------------------- bóng tín hiệu (6 kiểu)
SIGNALS = ("s01", "s02", "s05", "s08", "s10", "s11")


def _polar(cx, cy, r, a):
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _arc_d(cx, cy, r, a0, a1):
    x0, y0 = _polar(cx, cy, r, a0)
    x1, y1 = _polar(cx, cy, r, a1)
    return f"M{x0:.2f} {y0:.2f}A{r} {r} 0 {1 if a1 - a0 > math.pi else 0} 1 {x1:.2f} {y1:.2f}"


def signal_svg(style: str, pct: float, col: str, P: dict, D: float = 88.0) -> str:
    """SVG (khung D x D) phần viền / thanh quota của bóng tín hiệu. Giống SIG trong wisp-ui.js."""
    c0, a0 = D / 2, -math.pi / 2
    p = max(0.0, min(100.0, pct or 0.0))
    tr = P["track"]

    def ring(r, w, cap="round"):
        s = f'<circle cx="{c0}" cy="{c0}" r="{r}" fill="none" stroke="{tr}" stroke-width="{w}"/>'
        if p > 0:
            if p >= 99.9:
                s += f'<circle cx="{c0}" cy="{c0}" r="{r}" fill="none" stroke="{col}" stroke-width="{w}"/>'
            else:
                s += f'<path d="{_arc_d(c0, c0, r, a0, a0 + 2 * math.pi * p / 100)}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="{cap}"/>'
        return s

    if style == "s02":
        x, y = _polar(c0, c0, 36, a0 + 2 * math.pi * p / 100)
        return ring(36, 2.5) + f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5.5" fill="{P["disc"]}"/><circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="{col}"/>'
    if style == "s05":
        n, k = 48, round(p / 100 * 48)
        out = []
        for i in range(n):
            a = a0 + i * 2 * math.pi / n
            x1, y1 = _polar(c0, c0, 31, a)
            x2, y2 = _polar(c0, c0, 38, a)
            out.append(f'<path d="M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}" stroke="{col if i < k else tr}" stroke-width="2" stroke-linecap="round" fill="none"/>')
        return "".join(out)
    if style == "s08":  # mực nước: cắt theo hình tròn ở bước rasterize (clip_circle)
        h = D - 8
        y = 4 + h * (1 - p / 100)
        wave = f"M0 {y:.2f}q11 -5 22 0t22 0t22 0t22 0"
        return (f'<path d="{wave}V{D}H0z" fill="{col}" opacity=".22"/>'
                f'<path d="{wave}" stroke="{col}" stroke-width="2" fill="none"/>')
    if style == "s10":
        n, k = 24, round(p / 100 * 24)
        out = []
        for i in range(n):
            x, y = _polar(c0, c0, 35, a0 + i * 2 * math.pi / n)
            out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{3.2 if i < k else 2.2}" fill="{col if i < k else tr}"/>')
        return "".join(out)
    if style == "s11":  # bo vuông: thanh chạy theo mép, bắt đầu từ giữa cạnh trên
        x0, s, rr = 7.0, D - 14, 22.0
        L = 4 * (s - 2 * rr) + 2 * math.pi * rr
        pts = _squircle_path(x0, s, rr)
        done = []
        acc = 0.0
        target = L * p / 100
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            seg = math.hypot(xb - xa, yb - ya)
            if acc + seg >= target:
                k = (target - acc) / seg if seg else 0
                done.append((xa + (xb - xa) * k, ya + (yb - ya) * k))
                break
            done.append((xb, yb))
            acc += seg
        track = "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "z"
        out = f'<path d="{track}" fill="none" stroke="{tr}" stroke-width="5"/>'
        if p > 0 and len(done) > 1:
            out += f'<path d="M{pts[0][0]:.2f} {pts[0][1]:.2f}' + "".join(f"L{x:.2f} {y:.2f}" for x, y in done) + f'" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
        return out
    return ring(36, 5)  # s01


def _squircle_path(x0, s, r):
    """Mép hình vuông bo góc, đi chiều kim đồng hồ từ giữa cạnh trên."""
    x1 = x0 + s
    pts = [(x0 + s / 2, x0)]
    corners = ((x1 - r, x0 + r, -90), (x1 - r, x1 - r, 0), (x0 + r, x1 - r, 90), (x0 + r, x0 + r, 180))
    for cx, cy, a in corners:
        for i in range(10):
            t = math.radians(a + 9 * i)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    pts.append((x0 + s / 2, x0))
    return pts


def signal_rows(style: str, pct: float, col: str, P: dict, px: int) -> list:
    """Đĩa bóng + viền / thanh quota, cỡ px x px. Kiểu s11 là hình vuông bo góc."""
    sq = style == "s11"
    rad = px * (26 / 88) if sq else px / 2
    base = shape_rows(px, px, rad, P["disc"], P["discBd"], 1.0)
    over = vector.rasterize(vector.parse(signal_svg(style, pct, col, P)), px, px, vector.affine(scale=px / 88.0))
    if style == "s08":  # cắt mực nước theo hình tròn
        for y, row in enumerate(over):
            for x, (r, g, b, a) in enumerate(row):
                if a:
                    k = _cov(sd_round_rect(x + .5, y + .5, px, px, px / 2) + 4 * px / 88)
                    row[x] = (r, g, b, int(a * k))
    out = []
    for brow, orow in zip(base, over):
        row = []
        for (br, bg, bb, ba), (r, g, b, a) in zip(brow, orow):
            if a <= 0 or ba <= 0:
                row.append((br, bg, bb, ba))
            else:
                k = a / 255.0
                row.append((int(r * k + br * (1 - k)), int(g * k + bg * (1 - k)), int(b * k + bb * (1 - k)), ba))
        out.append(row)
    return out


def shape_radius(style: str, px: int) -> float:
    return px * (26 / 88) if style == "s11" else px / 2
