"""Island: viên thuốc ghim giữa mép trên màn hình. Trái: % quota. Phải: đèn cần bạn · đang chạy · xong, mũi tên
xanh khi có bản mới. Viền chạy theo trạng thái chung (states.headline). Đổi độ rộng có animation.
Windows: cửa sổ màu key. macOS: Canvas nền đặc màu island, cửa sổ cắt thành viên thuốc (plat.clip_round)."""
from __future__ import annotations

import math
import time
import tkinter as tk

from .. import platform as plat
from .. import render
from . import gfx


class Island:
    def __init__(self, app):
        self.app = app
        k = app.kit
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        plat.make_transparent(self.win)
        self.canvas = tk.Canvas(self.win, bg=k.P["isl"] if gfx.ALPHA else plat.transparent_key(),
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw")
        self.h = k.px(34)
        self.w = 0
        self.anim = None
        self.view = None
        self._tween = None
        self._clipped = False
        self.canvas.bind("<ButtonRelease-1>", lambda e: app.toggle_panel())
        for ev in plat.RIGHT_CLICK_EVENTS:
            self.canvas.bind(ev, lambda e: app.menus.island_menu(e.x_root, e.y_root))
        self.win.withdraw()

    # ---------------------------------------------------------------- dữ liệu -> hình
    def update(self, v: dict) -> None:
        """v: {pct, pct_col, counts, state, update}. Chỉ vẽ lại khi có gì đổi."""
        key = (v["pct"], v["pct_col"], tuple(v["counts"]), v["state"], v["update"], self.app.kit.P["name"])
        if key == self.view:
            return
        self.view = key
        k, P = self.app.kit, self.app.kit.P
        if gfx.ALPHA:
            self.canvas.configure(bg=P["isl"])  # đổi theme
        f_num, f_lamp = k.f["title"], k.f["lamp"]
        pad, gap = k.px(15), k.px(12)
        pct_txt = "–" if v["pct"] is None else f"{v['pct']:.0f}%"
        lamps = [("bell", P["wait"], v["counts"][0]), ("run", P["run"], v["counts"][1]), ("done", P["done"], v["counts"][2])]
        ic = k.px(14)
        lamp_w = [ic + k.px(4) + f_lamp.measure(str(n)) for _, _, n in lamps]
        w = pad * 2 + f_num.measure("100%") + gap + k.px(1) + gap + sum(lamp_w) + gap * (len(lamps) - 1)
        if v["update"]:
            w += gap + ic
        self._layout = (pct_txt, lamps, lamp_w, pad, gap, ic, v)
        self._resize(w)

    def _resize(self, w: int) -> None:
        if self.w and w != self.w and self.app.kit.anim.enabled:
            self._tween = (time.time(), self.w, w)
            self.app.kit.anim.add("island-tween", self._tween_step)
        else:
            self._apply_width(w)

    def _tween_step(self, t):
        if not self._tween:
            return False
        t0, a, b = self._tween
        k = min(1.0, (t - t0) / 0.2)
        e = 1 - (1 - k) ** 3  # ease-out
        cur = int(a + (b - a) * e)
        if k >= 1:
            self._tween = None
            self._apply_width(b)
            return False
        self._place(cur)
        P = self.app.kit.P
        self.canvas.itemconfigure(self.bg_item, image=self.app.kit.image(
            ("isl-plain", cur, self.h, P["isl"]), lambda: gfx.shape_rows(cur, self.h, self.h / 2, P["isl"],
                                                                         P["discBd"] if P["name"] == "light" else None),
            P["isl"] if gfx.ALPHA else None))
        self.canvas.delete("fg")
        return True

    def _apply_width(self, w: int) -> None:
        k, P = self.app.kit, self.app.kit.P
        self.w = w
        self._place(w)
        state = self._layout[6]["state"]
        akey = ("isl-anim", w, self.h, state, P["name"])
        a = k.cache.get(akey)
        if a is None:
            base = gfx.shape_rows(w, self.h, self.h / 2, P["isl"], P["discBd"] if P["name"] == "light" else None)
            a = k.cache[akey] = gfx.Animated(self.app.root, base, self.h / 2, k.px(2.5), state, P,
                                             bg=P["isl"] if gfx.ALPHA else None,
                                             fringe=P["fringe"])
        self.anim = a
        period = P["ab"][state][3]
        if k.anim.enabled:
            k.anim.add("island", lambda t: self._frame(t, period))
        else:
            self.canvas.itemconfigure(self.bg_item, image=a.still())
        self._draw_fg()

    def _frame(self, t, period) -> bool:
        if self.anim is None or not self.win.winfo_viewable():
            return True
        self.canvas.itemconfigure(self.bg_item, image=self.anim.frame(int(t / period * self.anim.n)))
        # đèn "đang chạy" thở nhẹ (1.6 giây một nhịp)
        if self._layout[1][1][2]:
            k = 0.5 + 0.5 * math.cos(2 * math.pi * t / 1.6)
            P = self.app.kit.P
            col = render.rgb2hex(render.mix(render.hex2rgb(P["isl"]), render.hex2rgb(P["run"]), 0.4 + 0.6 * k))
            self.canvas.itemconfigure("lamp-run", fill=col)
        return True

    def _draw_fg(self) -> None:
        c, k, P = self.canvas, self.app.kit, self.app.kit.P
        c.delete("fg")
        pct_txt, lamps, lamp_w, pad, gap, ic, v = self._layout
        mid = self.h / 2
        x = pad
        c.create_text(x, mid, text=pct_txt, anchor="w", fill=v["pct_col"], font=k.f["title"], tags="fg")
        x += k.f["title"].measure("100%") + gap
        c.create_line(x, mid - k.px(7), x, mid + k.px(7), fill=P["islSep"], tags="fg")
        x += k.px(1) + gap
        for (name, col, n), lw in zip(lamps, lamp_w):
            color = col if n else P["dim"]
            c.create_image(x, mid, anchor="w", image=k.icon(name, 14, color, P["isl"], 2.2),
                           tags="fg")
            c.create_text(x + ic + k.px(4), mid, text=str(n), anchor="w", fill=color, font=k.f["lamp"],
                          tags=("fg", "lamp-run") if name == "run" and n else "fg")
            x += lw + gap
        if v["update"]:
            c.create_image(x, mid, anchor="w", image=k.icon("dl", 14, P["upd"], P["isl"], 2.4),
                           tags="fg")

    def _place(self, w: int) -> None:
        l, t, r, _ = plat.work_area(self.app.root, None)
        x = (l + r - w) // 2
        y = t + self.app.kit.px(6)
        self.canvas.configure(width=w, height=self.h)
        self.win.geometry(f"{w}x{self.h}+{x}+{y}")
        self._clip()

    def _clip(self) -> None:
        """macOS: cắt cửa sổ thành viên thuốc. Chỉ làm được khi NSWindow đã có (cửa sổ từng hiện), nên thử lại tới khi
        được; bán kính không đổi khi island đổi rộng."""
        if gfx.ALPHA and not self._clipped:
            self._clipped = plat.clip_round(self.win, self.h / 2)

    # ---------------------------------------------------------------- hiển thị
    def show(self) -> None:
        self.win.deiconify()
        self.win.attributes("-topmost", True)
        self._clip()

    def hide(self) -> None:
        self.win.withdraw()
        self.app.kit.anim.remove("island")

    def anchor(self) -> tuple:
        """(x, y, w, h) của island trên màn hình, để đặt panel và thông báo ngay dưới."""
        return self.win.winfo_x(), self.win.winfo_y(), self.w, self.h

    def reset(self) -> None:
        """Đổi theme / cỡ chữ: vẽ lại từ đầu."""
        self.view, self.w, self.anim = None, 0, None
