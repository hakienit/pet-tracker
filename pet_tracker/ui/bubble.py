"""Bóng nổi kéo thả. Hai kiểu (Cài đặt → Bóng nổi):
- tín hiệu: đĩa + 1 trong 6 kiểu viền / thanh quota, giữa là % và ba đèn; viền động theo trạng thái.
- mascot: mascot chính là bóng, biểu cảm + chuyển động theo trạng thái, chip dưới chân (3 kiểu).
"""
from __future__ import annotations

import math
import time
import tkinter as tk

from .. import mascots
from .. import platform as plat
from ..config import save_state
from . import gfx

D_DESIGN = 88.0  # cỡ thiết kế của bóng tín hiệu trong wisp-ui.js


class Bubble:
    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        plat.make_transparent(self.win)
        self.canvas = tk.Canvas(self.win, bg="systemTransparent" if gfx.ALPHA else plat.transparent_key(),
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self.view = None
        self.anim = None
        self._drag = None
        self._moved = False
        self._mimgs: dict = {}
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        for ev in plat.RIGHT_CLICK_EVENTS:
            self.canvas.bind(ev, lambda e: app.menus.island_menu(e.x_root, e.y_root))
        self.win.withdraw()

    # ---------------------------------------------------------------- kích thước
    def size(self) -> int:
        return self.app.kit.px(self.app.cfg.get("bubble_size", 80))

    def box(self) -> tuple:
        """(rộng, cao) cửa sổ: bóng mascot cần chỗ cho cú nhảy, hiệu ứng và chip."""
        s = self.size()
        if self.app.prefs["bubble_type"] == "mascot":
            return int(s * 1.25), int(s * 1.5)
        return s, s

    # ---------------------------------------------------------------- dữ liệu -> hình
    def update(self, v: dict) -> None:
        p = self.app.prefs
        key = (p["bubble_type"], p["signal"], p["mascot"], p["hue"], p["chip"], p.get("custom_image"),
               None if v["pct"] is None else round(v["pct"]), v["pct_col"], tuple(v["counts"]), v["state"],
               v["update"], self.app.kit.P["name"], tuple(v.get("bars") or ()), v.get("wait_name"))
        if key == self.view:
            return
        self.view = key
        self.v = v
        w, h = self.box()
        self.canvas.configure(width=w, height=h)
        self._place()
        self.canvas.delete("all")
        if p["bubble_type"] == "mascot":
            self._build_mascot(v)
        else:
            self._build_signal(v)

    # ---- tín hiệu
    def _build_signal(self, v) -> None:
        k, P, p = self.app.kit, self.app.kit.P, self.app.prefs
        s = self.size()
        style = p["signal"] if p["signal"] in gfx.SIGNALS else "s01"
        state = v["state"]
        akey = ("sig", style, s, round(v["pct"] or 0), v["pct_col"], state, P["name"])
        a = k.cache.get(akey)
        if a is None:
            base = gfx.signal_rows(style, v["pct"] or 0, v["pct_col"], P, s)
            a = k.cache[akey] = gfx.Animated(self.app.root, base, gfx.shape_radius(style, s), k.px(3), state, P,
                                             fringe=P["fringe"])
        self.anim = a
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw", image=a.still())
        sc = s / k.S / D_DESIGN  # tỉ lệ so với cỡ thiết kế
        cx = cy = s / 2
        pct = "–" if v["pct"] is None else f"{v['pct']:.0f}%"
        import tkinter.font as tkfont
        fnum = tkfont.Font(family=k.f["big"].actual("family"), size=-k.px(19 * sc))
        flamp = tkfont.Font(family=k.f["lamp"].actual("family"), size=-k.px(9.5 * sc), weight="bold")
        self._fonts = (fnum, flamp)
        self.canvas.create_text(cx, cy - k.px(5 * sc), text=pct, fill=P["fg"], font=fnum)
        lamps = [("bell", P["wait"], v["counts"][0]), ("run", P["run"], v["counts"][1]), ("done", P["done"], v["counts"][2])]
        ic = max(6, k.px(9 * sc))
        widths = [ic + k.px(1) + flamp.measure(str(n)) for _, _, n in lamps]
        gap = k.px(3 * sc)
        x = cx - (sum(widths) + gap * 2) / 2
        y = cy + k.px(10 * sc)
        for (name, col, n), lw in zip(lamps, widths):
            color = col if n else P["dim"]
            self.canvas.create_image(x, y, anchor="w", image=k.icon(name, ic / k.S, color, None if gfx.ALPHA else P["disc"], 2.6))
            self.canvas.create_text(x + ic + k.px(1), y, text=str(n), anchor="w", fill=color, font=flamp,
                                    tags="lamp-run" if name == "run" and n else ())
            x += lw + gap
        if v["update"]:
            r = k.px(12 * sc)
            self.canvas.create_image(s - r * 2 + k.px(2), -k.px(1), anchor="nw",
                                     image=k.image(("upd-badge", r, P["upd"]), lambda: self._badge_rows(r * 2, P), None))
        period = P["ab"][state][3]
        if k.anim.enabled:
            k.anim.add("bubble", lambda t: self._frame_sig(t, period))
        else:
            k.anim.remove("bubble")

    def _badge_rows(self, d, P):
        rows = gfx.shape_rows(d, d, d / 2, P["upd"], P["disc"], max(1.0, d / 10))
        icon = gfx.icon_rows("dl", int(d * 0.55), "#ffffff", 2.6)
        o = (d - len(icon)) // 2
        for y, row in enumerate(icon):
            for x, (r, g, b, a) in enumerate(row):
                if a:
                    br, bg, bb, ba = rows[y + o][x + o]
                    kk = a / 255
                    rows[y + o][x + o] = (int(r * kk + br * (1 - kk)), int(g * kk + bg * (1 - kk)), int(b * kk + bb * (1 - kk)), ba)
        return rows

    def _frame_sig(self, t, period) -> bool:
        if not self.win.winfo_viewable() or self.app.prefs["bubble_type"] != "signal":
            return True
        self.canvas.itemconfigure(self.bg_item, image=self.anim.frame(int(t / period * self.anim.n)))
        return True

    # ---- mascot
    def _mascot_img(self, mood: str, sx=1.0, sy=1.0, rot=0.0):
        k, P, p = self.app.kit, self.app.kit.P, self.app.prefs
        size = int(self.size() * 72 / D_DESIGN)
        hue = mascots.hues()[p["hue"]] if 0 <= p["hue"] < len(mascots.hues()) else 0
        key = ("mb", p["mascot"], mood, size, P["name"], hue, round(sx, 2), round(sy, 2), round(rot, 1))
        return k.image(key, lambda: mascots.rows(p["mascot"], mood, size, P["name"], hue, sx=sx, sy=sy, rot=rot), None)

    def _build_mascot(self, v) -> None:
        k, P = self.app.kit, self.app.kit.P
        w, h = self.box()
        st = v["state"]
        self.mood = {"wait": "wait", "quota": "quota", "run": "run", "done": "done"}.get(st, "idle")
        size = int(self.size() * 72 / D_DESIGN)
        n = mascots.canvas_size(size)
        self.m_origin = ((w - n) / 2, h - n - k.px(12))
        self.m_item = self.canvas.create_image(*self.m_origin, anchor="nw", image=self._mascot_img(self.mood))
        self._chip(v, w, h)
        self._fx = []
        if k.anim.enabled:
            self._t0 = time.time()
            k.anim.add("bubble", self._frame_mascot)
        else:
            k.anim.remove("bubble")

    def _chip(self, v, w, h) -> None:
        k, P, p = self.app.kit, self.app.kit.P, self.app.prefs
        f = k.f["small_b"]
        parts = []  # (loại, nội dung, màu)
        pct = "–" if v["pct"] is None else f"{v['pct']:.0f}%"
        lamps = [("bell", P["wait"], v["counts"][0]), ("run", P["run"], v["counts"][1]), ("done", P["done"], v["counts"][2])]
        if p["chip"] == 1:
            parts.append(("t", pct, v["pct_col"]))
            if v["state"] == "wait" and v.get("wait_name"):
                parts += [("i", "bell", P["wait"]), ("t", k.ellipsis(v["wait_name"], "small_b", k.px(60)), P["wait"])]
            elif v["counts"][1]:
                parts.append(("t", f"▸{v['counts'][1]}", P["run"]))
            elif v["counts"][2]:
                parts.append(("t", f"✓{v['counts'][2]}", P["done"]))
        elif p["chip"] == 2:
            parts.append(("bars", v.get("bars") or (v["pct"] or 0, 0), None))
            for name, col, n in lamps:
                if n:
                    parts += [("i", name, col), ("t", str(n), col)]
        else:
            parts.append(("t", pct, v["pct_col"]))
            for name, col, n in lamps:
                if n:
                    parts += [("i", name, col), ("t", str(n), col)]
        ic, gap = k.px(10), k.px(3)
        width = sum(f.measure(c) if t == "t" else ic if t == "i" else k.px(22) for t, c, _ in parts) + gap * (len(parts) - 1)
        cw, ch = width + k.px(14), f.metrics("linespace") + k.px(4)
        x0, y0 = (w - cw) / 2, h - ch - k.px(1)
        self.canvas.create_image(x0, y0, anchor="nw", image=k.rounded(int(cw), int(ch), ch / 2, P["isl"], P["discBd"]))
        x, mid = x0 + k.px(7), y0 + ch / 2
        for t, c, col in parts:
            if t == "t":
                self.canvas.create_text(x, mid, text=c, anchor="w", fill=col, font=f)
                x += f.measure(c) + gap
            elif t == "i":
                self.canvas.create_image(x, mid, anchor="w", image=k.icon(c, 10, col, None if gfx.ALPHA else P["isl"], 2.6))
                x += ic + gap
            else:
                for i, val in enumerate(c):
                    yy = mid - k.px(3) + i * k.px(5)
                    bw = k.px(22)
                    self.canvas.create_rectangle(x, yy, x + bw, yy + k.px(3), fill=P["track"], outline="")
                    self.canvas.create_rectangle(x, yy, x + bw * max(0, min(100, val)) / 100, yy + k.px(3),
                                                 fill=self.app.level_color(val), outline="")
                x += k.px(22) + gap

    def _frame_mascot(self, t) -> bool:
        if not self.win.winfo_viewable() or self.app.prefs["bubble_type"] != "mascot":
            return True
        k, P = self.app.kit, self.app.kit.P
        mood, (ox, oy) = self.mood, self.m_origin
        S = k.S
        dx = dy = 0.0
        sx = sy = 1.0
        rot = 0.0
        if mood == "idle":      # lắc lư, 3.6 giây
            rot = round(3 * math.sin(2 * math.pi * t / 3.6) / 1.5) * 1.5
        elif mood == "run":     # đi tại chỗ, 0.9 giây
            ph = (t / 0.9) % 1
            dx = 4 * S * math.sin(2 * math.pi * ph)
            dy = -6 * S * abs(math.sin(2 * math.pi * ph))
            rot = 4.0 * round(math.sin(2 * math.pi * ph))
        elif mood == "wait":    # nhảy, 0.8 giây
            ph = (t / 0.8) % 1
            dy = -22 * S * max(0.0, math.sin(math.pi * min(1.0, ph / 0.75)))
            sx, sy = ((1.06, 0.94) if ph < 0.08 or ph > 0.9 else (0.95, 1.06) if ph < 0.2 else (1.0, 1.0))
        elif mood == "done":    # nhảy múa, 1.3 giây
            ph = (t / 1.3) % 1
            rot = 12.0 * round(math.sin(2 * math.pi * ph) * 2) / 2
            dy = -8 * S * abs(math.sin(2 * math.pi * ph))
        else:                   # gần hết quota: run
            ph = (t / 0.16) % 1
            dx = 2 * S * (1 if ph < 0.5 else -1)
            rot = 1.0 if ph < 0.5 else -1.0
        self.canvas.itemconfigure(self.m_item, image=self._mascot_img(mood, sx, sy, rot))
        self.canvas.coords(self.m_item, ox + dx, oy + dy)
        self._effects(t, mood)
        return True

    def _effects(self, t, mood) -> None:
        """zZ, bụi, sóng, pháo giấy, mồ hôi: item canvas, vị trí tính theo thời gian (không cần lưu trạng thái)."""
        c, k, P = self.canvas, self.app.kit, self.app.kit.P
        c.delete("fx")
        w, h = self.box()
        cx = w / 2
        top = self.m_origin[1]
        if mood == "idle":
            for i, d in enumerate((0.0, 1.2)):
                ph = ((t - d) / 2.4) % 1
                if ph < 0.85:
                    c.create_text(cx + k.px(22 + 10 * ph + 4 * i), top + k.px(12 - 26 * ph - 4 * i), text="z",
                                  fill=P["idle"], font=k.f["small_b"], tags="fx")
        elif mood == "run":
            for d in (0.0, 0.3, 0.6):
                ph = ((t - d) / 0.9) % 1
                r = k.px(2 + 3 * ph)
                x, y = cx - k.px(16 + 14 * ph), h - k.px(20 + 4 * ph)
                if ph < 0.8:
                    c.create_oval(x - r, y - r, x + r, y + r, fill=P["mut"], outline="", tags="fx")
        elif mood == "wait":
            for d in (0.0, 0.6):
                ph = ((t - d) / 1.2) % 1
                r = k.px(26 + 22 * ph)
                y = top + mascots.canvas_size(int(self.size() * 72 / D_DESIGN)) / 2
                if ph < 0.85:
                    c.create_oval(cx - r, y - r, cx + r, y + r, outline=P["wait"], width=max(1, k.px(2 * (1 - ph))),
                                  tags="fx")
            c.tag_lower("fx")
        elif mood == "done":
            for col, x, y, d in (("#ffd23f", 10, 18, 0.0), ("#3fd0a4", 70, 12, 0.3), ("#ff7eb6", 76, 44, 0.6),
                                 ("#58a6ff", 8, 50, 0.9)):
                ph = ((t - d) / 1.3) % 1
                if 0.1 < ph < 0.75:
                    s = k.px(3.5)
                    xx, yy = k.px(x) * w / k.px(92), k.px(y) - k.px(6) * ph
                    c.create_rectangle(xx - s, yy - s, xx + s, yy + s, fill=col, outline="", tags="fx")
        else:
            ph = (t / 1.1) % 1
            x, y = cx + k.px(24), top + k.px(18 + 22 * ph)
            r = k.px(3)
            if ph < 0.9:
                c.create_oval(x - r, y - r * 1.3, x + r, y + r * 1.3, fill="#7cc4ff", outline="", tags="fx")

    # ---------------------------------------------------------------- vị trí + kéo thả
    def _place(self) -> None:
        w, h = self.box()
        st = self.app.state
        if "x" in st and "y" in st:
            x, y = self._clamp(int(st["x"]), int(st["y"]))
        else:
            l, t, r, b = plat.work_area(self.app.root, None)
            x, y = r - w - self.app.kit.px(24), b - h - self.app.kit.px(24)
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    def _clamp(self, x, y) -> tuple:
        w, h = self.box()
        l, t, r, b = plat.work_area(self.app.root, (x + w // 2, y + h // 2))
        return max(l, min(x, r - w)), max(t, min(y, b - h))

    def _press(self, e):
        self._drag = (e.x_root, e.y_root, self.win.winfo_x(), self.win.winfo_y())
        self._moved = False

    def _motion(self, e):
        if not self._drag:
            return
        x0, y0, wx, wy = self._drag
        dx, dy = e.x_root - x0, e.y_root - y0
        if abs(dx) > 3 or abs(dy) > 3:
            self._moved = True
        if self._moved:
            self.win.geometry(f"+{wx + dx}+{wy + dy}")
            self.app.panel.place()

    def _release(self, e):
        if self._drag is None:
            return
        moved, self._drag = self._moved, None
        if moved:
            x, y = self._clamp(self.win.winfo_x(), self.win.winfo_y())
            self.win.geometry(f"+{x}+{y}")
            self.app.state["x"], self.app.state["y"] = x, y
            save_state(self.app.state)
            self.app.panel.place()
        else:
            self.app.toggle_panel()

    # ---------------------------------------------------------------- hiển thị
    def show(self) -> None:
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def hide(self) -> None:
        self.win.withdraw()
        self.app.kit.anim.remove("bubble")

    def anchor(self) -> tuple:
        w, h = self.box()
        return self.win.winfo_x(), self.win.winfo_y(), w, h

    def reset(self) -> None:
        self.view = None
