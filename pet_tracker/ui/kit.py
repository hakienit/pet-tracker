"""Bộ widget dùng chung: font Archivo theo pixel, ảnh có cache, nhãn, nút, công tắc, thanh, card bo góc,
và bộ chạy animation (một nhịp cho mọi viền động trên màn hình)."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import font as tkfont

from .. import platform as plat
from .. import render, theme
from ..assets import asset_path
from . import gfx

_FONTS_DONE = False


def register_fonts() -> bool:
    """Nạp Archivo (assets/fonts) cho process, một lần. False nếu không nạp được (dùng font hệ thống)."""
    global _FONTS_DONE
    if _FONTS_DONE:
        return True
    ok = all(plat.register_font(asset_path("fonts", f"Archivo-{w}.ttf"))
             for w in ("Regular", "SemiBold", "Bold", "ExtraBold"))
    _FONTS_DONE = ok
    return ok


class Animator:
    """Gọi lại từng animation đang hiển thị mỗi nhịp (40 ms). Tắt hẳn khi giảm chuyển động."""

    def __init__(self, root, tick_ms: int = 40):
        self.root, self.tick_ms = root, tick_ms
        self.items: dict = {}   # khoá -> hàm(t) (trả False để tự gỡ)
        self.enabled = True
        self._job = None

    def add(self, key, fn) -> None:
        self.items[key] = fn
        if self._job is None and self.enabled:
            self._job = self.root.after(self.tick_ms, self._tick)

    def remove(self, key) -> None:
        self.items.pop(key, None)

    def _tick(self) -> None:
        self._job = None
        if not self.enabled or not self.items:
            return
        t = time.time()
        for k, fn in list(self.items.items()):
            try:
                if fn(t) is False:
                    self.items.pop(k, None)
            except tk.TclError:  # widget đã bị huỷ
                self.items.pop(k, None)
        if self.items:
            self._job = self.root.after(self.tick_ms, self._tick)


class Kit:
    def __init__(self, root, S: float):
        self.root, self.S = root, S
        self.P = theme.DARK
        self.cache: dict = {}
        self.anim = Animator(root)
        self._fonts()

    # ---------------------------------------------------------------- thang đo
    def px(self, v: float) -> int:
        return int(round(v * self.S))

    def set_palette(self, P: dict) -> None:
        self.P = P
        self.cache.clear()

    # ---------------------------------------------------------------- font
    def _fonts(self) -> None:
        loaded = register_fonts()
        fams = set(tkfont.families(self.root))

        def pick(*names):
            return next((n for n in names if n in fams), "TkDefaultFont")

        text = "Archivo" if loaded and "Archivo" in fams else pick("Segoe UI Variable Text", "Segoe UI", ".AppleSystemUIFont",
                                                                  "Helvetica Neue")
        semi = "Archivo SemiBold" if loaded and "Archivo SemiBold" in fams else text
        heavy = "Archivo ExtraBold" if loaded and "Archivo ExtraBold" in fams else text
        mono = pick("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "Courier New")
        F = tkfont.Font
        sz = lambda v: -max(1, self.px(v))  # noqa: E731  (size âm = pixel, giống nhau trên Windows và macOS)
        T = theme.TYPE
        self.f = {
            "meta": F(family=text, size=sz(T["meta"])), "meta_b": F(family=semi, size=sz(T["meta"])),
            "body": F(family=text, size=sz(T["body"])), "body_b": F(family=semi, size=sz(T["body"])),
            "body_x": F(family=text, size=sz(T["body"]), weight="bold"),
            "title": F(family=text, size=sz(T["title"]), weight="bold"),
            "head": F(family=heavy, size=sz(T["head"])), "num": F(family=text, size=sz(T["num"]), weight="bold"),
            "big": F(family=heavy, size=sz(T["big"])), "lamp": F(family=text, size=sz(T["body"]), weight="bold"),
            "small_b": F(family=text, size=sz(10.5), weight="bold"),
            "mono": F(family=mono, size=sz(12.5)), "mono_s": F(family=mono, size=sz(12)),
        }

    # ---------------------------------------------------------------- ảnh
    def image(self, key, rows_fn, bg=None):
        k = (key, bg, self.P["name"])
        img = self.cache.get(k)
        if img is None:
            if len(self.cache) > 600:
                self.cache.clear()
            img = self.cache[k] = gfx.to_photo(self.root, rows_fn(), bg, self.P["fringe"])
        return img

    def icon(self, name: str, size: float, color: str, bg=None, sw: float = 1.9):
        n = self.px(size)
        return self.image(("icon", name, n, color, sw), lambda: gfx.icon_rows(name, n, color, sw), bg)

    def rounded(self, w: int, h: int, r: float, fill: str, border=None, bg=None):
        return self.image(("rr", w, h, round(r, 1), fill, border), lambda: gfx.shape_rows(w, h, r, fill, border), bg)

    # ---------------------------------------------------------------- widget
    def lbl(self, parent, text="", role="body", fg=None, **kw):
        kw.setdefault("anchor", "w")
        kw.setdefault("bg", parent["bg"])
        kw.setdefault("padx", 0)
        kw.setdefault("pady", 0)
        return tk.Label(parent, text=text, font=self.f[role], fg=fg or self.P["fg"], bd=0, **kw)

    def ellipsis(self, text: str, role: str, max_px: int) -> str:
        font = self.f[role]
        if font.measure(text) <= max_px:
            return text
        while text and font.measure(text + "…") > max_px:
            text = text[:-1]
        return text + "…"

    def icon_btn(self, parent, name: str, cmd, size: float = 17, color=None, hover=None, label=None):
        """Nút chỉ có icon, vùng bấm tối thiểu 32 px. label: chữ cho tooltip trạng thái (chưa dùng)."""
        P = self.P
        color, hover = color or P["mut"], hover or P["fg"]
        bg = parent["bg"]
        b = tk.Label(parent, image=self.icon(name, size, color, bg), bg=bg, cursor="hand2", bd=0,
                     width=self.px(32), height=self.px(32))
        b.bind("<Enter>", lambda e: b.configure(image=self.icon(name, size, hover, bg)))
        b.bind("<Leave>", lambda e: b.configure(image=self.icon(name, size, color, bg)))
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def button(self, parent, text: str, cmd, fill=None, fg=None, icon=None, outline=False, role="body_x"):
        """Nút bo góc. outline=True: nền trong suốt, viền mảnh."""
        P = self.P
        bg = parent["bg"]
        fill = fill or P["run"]
        fg = fg or (P["fg2"] if outline else P["btnFg"])
        font = self.f[role]
        ipx = self.px(14) if icon else 0
        gap = self.px(6) if icon else 0
        w = font.measure(text) + self.px(24) + ipx + gap
        h = max(self.px(32), font.metrics("linespace") + self.px(12))
        r = self.px(9)
        if outline:
            norm = self.rounded(w, h, r, bg, P["line"], bg)
            hov = self.rounded(w, h, r, P["hover"], P["line"], bg)
        else:
            norm = self.rounded(w, h, r, fill, None, bg)
            hov = self.rounded(w, h, r, render.rgb2hex(render.mix(render.hex2rgb(fill), (255, 255, 255), 0.14)), None, bg)
        c = tk.Canvas(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        it = c.create_image(0, 0, anchor="nw", image=norm)
        x = self.px(12)
        if icon:
            c.create_image(x, h / 2, anchor="w", image=self.icon(icon, 14, fg, fill))
            x += ipx + gap
        c.create_text(x, h / 2, text=text, anchor="w", fill=fg, font=font)
        c._imgs = (norm, hov)
        c.bind("<Enter>", lambda e: c.itemconfigure(it, image=hov))
        c.bind("<Leave>", lambda e: c.itemconfigure(it, image=norm))
        c.bind("<Button-1>", lambda e: cmd())
        return c

    def switch(self, parent, on: bool, cmd):
        P = self.P
        bg = parent["bg"]
        w, h = self.px(36), self.px(22)
        c = tk.Canvas(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        c.create_image(0, 0, anchor="nw", image=self.rounded(w, h, h / 2, P["on"] if on else P["off"], None, bg))
        k = self.px(16)
        kx = w - self.px(3) - k if on else self.px(3)
        c.create_image(kx, self.px(3), anchor="nw",
                       image=self.rounded(k, k, k / 2, "#ffffff", None, P["on"] if on else P["off"]))
        c.bind("<Button-1>", lambda e: cmd(not on))
        return c

    def segmented(self, parent, options: list, index: int, cmd):
        """Nhóm nút chọn một (giao diện, kiểu hiển thị…)."""
        P = self.P
        f = tk.Frame(parent, bg=P["seg"], padx=self.px(2), pady=self.px(2))
        for i, text in enumerate(options):
            on = i == index
            b = tk.Label(f, text=text, font=self.f["meta_b"], bg=P["segOn"] if on else P["seg"],
                         fg=P["fg"] if on else P["mut"], padx=self.px(9), pady=self.px(4), cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, i=i: cmd(i))
        return f

    def bar(self, parent, pct: float, color: str, width: int, height: float = 5):
        h = max(3, self.px(height))
        frac = max(0.0, min(100.0, pct or 0)) / 100.0
        bg = parent["bg"]
        img = self.image(("bar", width, h, round(frac, 3), color, self.P["track"]),
                         lambda: render.capsule_rows(width, h, frac, color, self.P["track"], bg, rgba=True), bg)
        c = tk.Canvas(parent, width=width, height=h, bg=bg, highlightthickness=0, bd=0)
        c.create_image(0, 0, anchor="nw", image=img)
        c._img = img
        return c

    def card(self, parent, fill: str, border=None, r: float = 12, padx: float = 12, pady: float = 10, width=None,
             state=None):
        """Card bo góc: (canvas ngoài, frame trong). Ảnh nền vẽ lại khi kích thước đổi.
        state: "wait" / "run"… thì viền chạy animation (gfx.Animated)."""
        bg = parent["bg"]
        outer = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, height=1, width=width or 1)
        inner = tk.Frame(outer, bg=fill)
        px_, py_ = self.px(padx), self.px(pady)
        bgi = outer.create_image(0, 0, anchor="nw")
        win = outer.create_window(px_, py_, anchor="nw", window=inner)
        rr = self.px(r)
        last = {}

        def relayout(_e=None):
            w = width or outer.winfo_width()
            if w <= 1:
                return
            h = inner.winfo_reqheight() + 2 * py_
            if last.get("wh") == (w, h):
                return
            last["wh"] = (w, h)
            outer.configure(height=h)
            outer.itemconfigure(win, width=max(1, w - 2 * px_))
            if state and self.anim.enabled:
                key = ("card", w, h, fill, state, self.P["name"])
                a = self.cache.get(key)
                if a is None:
                    base = gfx.shape_rows(w, h, rr, fill, border)
                    a = self.cache[key] = gfx.Animated(self.root, base, rr, self.px(1.5), state, self.P, bg=bg, n=12)
                period = self.P["ab"][state][3]
                outer.itemconfigure(bgi, image=a.frame(0))
                self.anim.add(("card", id(outer)), lambda t, a=a, p=period: outer.winfo_exists() and (
                    outer.itemconfigure(bgi, image=a.frame(int(t / p * a.n))) or True))
            else:
                outer.itemconfigure(bgi, image=self.rounded(w, h, rr, fill, border, bg))

        inner.bind("<Configure>", relayout, add="+")
        outer.bind("<Configure>", relayout, add="+")
        outer._relayout = relayout
        return outer, inner
