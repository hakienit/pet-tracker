"""Thông báo của Wisp: cửa sổ nhỏ thả xuống dưới island (hoặc cạnh bóng nổi), xếp chồng tối đa 3.
"Cần bạn" giữ tới khi xử lý; loại khác tự ẩn (mặc định 6 giây). Giống nhau trên Windows và macOS."""
from __future__ import annotations

import time
import tkinter as tk

from .. import platform as plat

MAX = 3


class Toasts:
    def __init__(self, app):
        self.app = app
        self.items: list = []  # {key, win, until}

    def show(self, key, kind: str, title: str, sub: str = "", actions=(), ttl: float | None = 6.0, mono=False,
             on_click=None) -> None:
        """kind: wait | run | done | danger | upd | info (chọn màu icon). actions: [(nhãn, hàm, chính?)]."""
        self.dismiss(key)
        app, k = self.app, self.app.kit
        P = k.P
        win = tk.Toplevel(app.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=P["surf"])
        body = tk.Frame(win, bg=P["surf"], padx=k.px(14), pady=k.px(12))
        body.pack(fill="both", expand=True)
        icon = {"wait": "bell", "done": "done", "danger": "trend", "upd": "dl", "run": "run"}.get(kind, "info")
        col = P.get(kind, P["fg2"]) if kind != "info" else P["fg2"]
        ic = tk.Label(body, image=k.icon(icon, 18, col, P["surf"], 2.2), bg=P["surf"])
        ic.pack(side="left", anchor="n", pady=(k.px(1), 0))
        col_f = tk.Frame(body, bg=P["surf"])
        col_f.pack(side="left", fill="x", expand=True, padx=(k.px(12), 0))
        W = k.px(340)
        k.lbl(col_f, k.ellipsis(title, "body_x", W - k.px(70)), "body_x").pack(fill="x")
        if sub:
            k.lbl(col_f, k.ellipsis(sub, "mono_s" if mono else "meta", W - k.px(70)), "mono_s" if mono else "meta",
                  P["mut"]).pack(fill="x", pady=(k.px(2), 0))
        if actions:
            r = tk.Frame(col_f, bg=P["surf"])
            r.pack(fill="x", pady=(k.px(8), 0))
            for label, fn, primary in actions:
                def run(fn=fn):
                    self.dismiss(key)
                    fn()
                if primary:
                    k.button(r, label, run, P[kind] if kind in P else P["run"],
                             fg="#ffffff" if P["name"] == "light" else P["btnFg"]).pack(side="left", padx=(0, k.px(8)))
                else:
                    k.button(r, label, run, outline=True, role="body").pack(side="left", padx=(0, k.px(8)))
        if on_click:
            for w in (body, ic, col_f) + tuple(col_f.winfo_children()):
                if not isinstance(w, tk.Canvas):
                    w.bind("<Button-1>", lambda e: (self.dismiss(key), on_click()))
        win.update_idletasks()
        win.geometry(f"{W}x{body.winfo_reqheight()}")
        if not plat.round_corners(win, P["line"]):
            win.configure(bg=P["line"])
            body.pack_configure(padx=1, pady=1)
        self.items.insert(0, {"key": key, "win": win, "until": time.time() + ttl if ttl else None})
        while len(self.items) > MAX:  # bỏ thông báo tự ẩn cũ nhất trước; "cần bạn" (không tự ẩn) giữ lại sau cùng
            old = next((i for i in reversed(self.items) if i["until"]), self.items[-1])
            self.items.remove(old)
            old["win"].destroy()
        self._layout()
        self._fade(win, 0.0)

    def _fade(self, win, a) -> None:
        try:
            a = min(1.0, a + (0.25 if self.app.kit.anim.enabled else 1.0))
            win.attributes("-alpha", a)
            if a < 1.0:
                self.app.root.after(16, lambda: self._fade(win, a))
        except tk.TclError:
            pass

    def dismiss(self, key) -> None:
        for it in [i for i in self.items if i["key"] == key]:
            self.items.remove(it)
            try:
                it["win"].destroy()
            except tk.TclError:
                pass
        self._layout()

    def has(self, key) -> bool:
        return any(i["key"] == key for i in self.items)

    def clear(self) -> None:
        for it in self.items:
            try:
                it["win"].destroy()
            except tk.TclError:
                pass
        self.items = []

    def tick(self) -> None:
        now = time.time()
        for it in [i for i in self.items if i["until"] and i["until"] < now]:
            self.dismiss(it["key"])

    def _layout(self) -> None:
        """Island: xếp xuống dưới island (panel đang mở thì đặt bên phải panel). Bóng: xếp lên trên / cạnh bóng."""
        if not self.items:
            return
        app, k = self.app, self.app.kit
        ax, ay, aw, ah = app.anchor()
        l, t_, r, b = plat.work_area(app.root, (ax + aw // 2, ay + ah // 2))
        gap = k.px(8)
        W = k.px(340)
        island = app.prefs["display"] == "island"
        if island:
            x = ax + (aw - W) // 2
            y = ay + ah + k.px(10)
            if app.panel.visible:
                x = app.panel.win.winfo_x() + app.panel.win.winfo_width() + gap
                y = app.panel.win.winfo_y()
                if x + W > r:
                    x = app.panel.win.winfo_x() - W - gap
        else:
            x = ax - W - gap if ax - W - gap > l else ax + aw + gap
            y = ay
        x = max(l + gap, min(x, r - W - gap))
        for it in self.items:
            w = it["win"]
            try:
                h = w.winfo_reqheight()
                if not island:
                    y = min(y, b - h - gap)
                w.geometry(f"+{int(x)}+{int(y)}")
                y += h + gap
            except tk.TclError:
                pass
