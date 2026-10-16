"""Menu nổi: chuột phải vào island / bóng, menu ⋯ của session. Thao tác không hoàn tác được dùng khối xác nhận
ngay trong menu (kiểu 01 đã chốt): tiêu đề, danh sách hậu quả, nút Huỷ / Xoá."""
from __future__ import annotations

import os
import time
import tkinter as tk

from .. import __version__, session_ops
from .. import platform as plat
from ..i18n import t
from . import fmt


class Menus:
    def __init__(self, app):
        self.app = app
        self.sheet = None

    # ---------------------------------------------------------------- khung
    def close(self) -> None:
        if self.sheet is not None:
            try:
                self.sheet.destroy()
            except tk.TclError:
                pass
            self.sheet = None
            self.app.mouse_reset()

    def _new(self):
        self.close()
        P = self.app.kit.P
        top = tk.Toplevel(self.app.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.0)
        top.configure(bg=P["menuBg"])
        body = tk.Frame(top, bg=P["menuBg"])
        body.pack(fill="both", expand=True)
        self.sheet = top
        return top, body

    def _finish(self, top, body, W: int, x: int, y: int) -> None:
        k = self.app.kit
        top.update_idletasks()
        h = body.winfo_reqheight()
        l, t_, r, b = plat.work_area(self.app.root, (x, y))
        m = k.px(8)
        sx = x - W - m if x + W + m > r else x + m
        sx = max(l + m, sx)
        sy = max(t_ + m, min(y - k.px(10), b - h - m))
        top.geometry(f"{W}x{h}+{sx}+{sy}")
        if not plat.round_corners(top, k.P["line"]):
            top.configure(bg=k.P["line"])
            body.pack_configure(padx=1, pady=1)
            top.geometry(f"{W + 2}x{h + 2}+{sx}+{sy}")
        top.bind("<Escape>", lambda e: self.close())
        top.focus_force()
        if not plat.GLOBAL_MOUSE:
            self.app.focus_for_dismiss(top)
        self.app.mouse_reset()

        def fade(a=0.0):
            if self.sheet is not top:
                return
            a = min(1.0, a + (0.34 if k.anim.enabled else 1.0))
            top.attributes("-alpha", a)
            if a < 1.0:
                self.app.root.after(14, lambda: fade(a))
        fade()

    def _item(self, body, icon, label, sub="", cmd=None, danger=False, enabled=True):
        k, P = self.app.kit, self.app.kit.P
        bg = P["menuBg"]
        row = tk.Frame(body, bg=bg, cursor="hand2" if enabled else "arrow")
        row.pack(fill="x", padx=k.px(6))
        fg = (P["danger"] if danger else P["fg"]) if enabled else P["dim"]
        ic_col = (P["danger"] if danger else P["mut"]) if enabled else P["dim"]
        ic = tk.Label(row, image=k.icon(icon, 16, ic_col, bg), bg=bg, width=k.px(28))
        ic.pack(side="left", pady=k.px(7))
        lb = k.lbl(row, label, "body", fg)
        lb.pack(side="left", fill="x", expand=True, padx=(k.px(4), 0))
        parts = [row, ic, lb]
        if sub:
            hs = k.lbl(row, k.ellipsis(sub, "meta", k.px(170)), "meta", P["mut"])
            hs.pack(side="right", padx=(k.px(8), k.px(10)))
            parts.append(hs)

        def paint(c):
            for p in parts:
                p.configure(bg=c)
            ic.configure(image=k.icon(icon, 16, ic_col, c))

        if enabled and cmd:
            for p in parts:
                p.bind("<Enter>", lambda e: paint(P["hover"]))
                p.bind("<Leave>", lambda e: paint(bg))
                p.bind("<Button-1>", lambda e: cmd())
        return row

    def _sep(self, body) -> None:
        k = self.app.kit
        tk.Frame(body, bg=k.P["line"], height=1).pack(fill="x", padx=k.px(12), pady=k.px(4))

    def _pad(self, body, h=6) -> None:
        tk.Frame(body, bg=self.app.kit.P["menuBg"], height=self.app.kit.px(h)).pack(fill="x")

    # ---------------------------------------------------------------- chuột phải island / bóng
    def island_menu(self, x: int, y: int) -> None:
        app = self.app
        top, body = self._new()

        def act(fn):
            return lambda: (self.close(), fn())

        self._pad(body)
        self._item(body, "refresh", t("isl.refresh"), cmd=act(app.refresh))
        self._item(body, "gear", t("isl.settings"), cmd=act(app.open_settings))
        to_bubble = app.prefs["display"] == "island"
        self._item(body, "swap", t("isl.to_bubble") if to_bubble else t("isl.to_island"),
                   cmd=act(lambda: app.set_pref("display", "bubble" if to_bubble else "island")))
        muted = app.mute_until > time.time()
        self._item(body, "sound" if muted else "mute", t("isl.unmute") if muted else t("isl.mute"),
                   cmd=act(app.toggle_mute))
        u = app.update or {}
        self._item(body, "dl", t("isl.check"), f"{u['version']}" if u.get("available") else f"v{__version__}",
                   cmd=act(app.check_update_now))
        self._sep(body)
        self._item(body, "power", t("isl.quit"), cmd=act(app.quit), danger=True)
        self._pad(body)
        self._finish(top, body, self.app.kit.px(270), x, y)

    # ---------------------------------------------------------------- menu ⋯ của session
    def session_menu(self, sess: dict, x: int, y: int) -> None:
        app, k = self.app, self.app.kit
        P = k.P
        top, body = self._new()
        W = k.px(340)
        self._session_head(body, sess, W)
        items = tk.Frame(body, bg=P["menuBg"])
        items.pack(fill="x")

        def act(fn):
            return lambda: (self.close(), fn())

        desktop = sess.get("entrypoint") == "claude-desktop"
        busy = sess.get("session_id") in app.busy_sids
        why_not = t("m.desktop") if desktop else (t("m.busy") if busy else "")
        ep = {"cli": "ep.cli", "claude-desktop": "ep.desktop", "vscode": "ep.vscode"}.get(sess.get("entrypoint"))
        self._item(items, "open", t("m.open"), t(ep) if ep else "", act(lambda: app.focus_session(sess)))
        self._item(items, "folder", t("m.folder"), "", act(lambda: app.open_path(sess.get("cwd"))),
                   enabled=bool(sess.get("cwd")) and os.path.isdir(sess.get("cwd") or ""))
        self._item(items, "copy", t("m.copy"), "", act(lambda: app.copy_text(sess.get("session_id"), t("m.copied"))))
        tot = sess.get("totals") or {}
        self._item(items, "info", t("m.details"), t("m.details.sub", msgs=tot.get("messages", 0), out=fmt.k(tot.get("output", 0)),
                                                    ep=t(ep) if ep else (sess.get("entrypoint") or "?")))
        self._sep(items)
        muted = sess.get("session_id") in app.prefs["muted"]
        self._item(items, "sound" if muted else "mute", t("m.unmute") if muted else t("m.mute"), "",
                   act(lambda: app.toggle_mute_session(sess.get("session_id"))))
        self._sep(items)

        def ask(op):
            return lambda: self._confirm(body, items, sess, op, W)

        ok = not desktop and not busy
        self._item(items, "exit", t("m.handoff"), why_not or t("m.handoff.sub"), ask("handoff"), enabled=ok)
        self._item(items, "x", t("m.close"), why_not or t("m.close.sub"), ask("close"), enabled=ok)
        self._item(items, "trash", t("m.delete"), why_not or t("m.delete.sub"), ask("delete"), danger=True, enabled=ok)
        st = sess.get("git")
        if st and st.get("linked"):
            why = session_ops.worktree_block_reason(sess, (app.snap or {}).get("sessions") or [])
            self._item(items, "branch", t("m.worktree"), why or why_not, ask("worktree"), danger=True,
                       enabled=ok and why is None)
        self._pad(body)
        self._finish(top, body, W, x, y)

    def _session_head(self, body, sess, W) -> None:
        k, P = self.app.kit, self.app.kit.P
        head = tk.Frame(body, bg=P["menuBg"], padx=k.px(16), pady=k.px(10))
        head.pack(fill="x")
        k.lbl(head, k.ellipsis(sess.get("name") or "?", "title", W - k.px(32)), "title").pack(fill="x")
        k.lbl(head, k.ellipsis(sess.get("cwd") or "", "meta", W - k.px(32)), "meta", P["mut"]).pack(fill="x")
        gtxt, gkind = session_ops.state_text(sess.get("git"))
        if gtxt:
            st = sess["git"]
            label = f"⎇ {'worktree' if st.get('linked') else (st.get('branch') or 'git')} · {gtxt}"
            k.lbl(head, k.ellipsis(label, "meta", W - k.px(32)), "meta", P["ok"] if gkind == "done" else P["warn"]).pack(fill="x")
        tk.Frame(body, bg=P["line"], height=1).pack(fill="x")
        self._pad(body, 4)

    def _confirm(self, body, items, sess, op: str, W: int) -> None:
        """Thay danh sách thao tác bằng khối xác nhận: tiêu đề, hậu quả, Huỷ / nút thực hiện."""
        app, k = self.app, self.app.kit
        P = k.P
        for w in items.winfo_children():
            w.destroy()
        name = sess.get("name") or "?"
        lines = []
        if op == "handoff":
            title, btn, col = t("cf.title_handoff", name=name), t("cf.handoff_btn"), P["run"]
            lines = [t("cf.handoff"), t("cf.kill"), t("cf.reopen")]
        elif op == "close":
            title, btn, col = t("cf.title_close", name=name), t("cf.close"), P["danger"]
            lines = [t("cf.kill"), t("cf.reopen")]
        elif op == "delete":
            size = 0
            try:
                size = os.path.getsize(sess.get("transcript") or "")
            except OSError:
                pass
            title, btn, col = t("cf.title", name=name), t("cf.delete"), P["danger"]
            lines = [t("cf.kill"), t("cf.transcript", size=_size(size)), t("cf.noreopen")]
        else:
            st = sess.get("git") or {}
            ign = st.get("ignored") or []
            title, btn, col = t("cf.title_wt", name=name), t("cf.delete_wt"), P["danger"]
            lines = [t("cf.kill"), t("cf.wt_dir", dir=os.path.basename((sess.get("cwd") or "").rstrip("/\\")))]
            if ign:
                lines.append(t("cf.wt_ignored", n=len(ign), items=", ".join(ign[:2]) + ("…" if len(ign) > 2 else "")))
            lines.append(t("cf.noreopen"))
        danger = col == P["danger"]
        fill = P["dangerBg"] if danger else P["runBg"]
        outer, c = k.card(items, fill, col, width=W - k.px(16), r=10, padx=12, pady=12)
        outer.pack(fill="x", padx=k.px(8), pady=(k.px(2), k.px(4)))
        r = tk.Frame(c, bg=fill)
        r.pack(fill="x")
        tk.Label(r, image=k.icon("trash" if danger else "exit", 16, col, fill), bg=fill).pack(side="left")
        k.lbl(r, title, "body_x", col, wraplength=W - k.px(80), justify="left").pack(side="left", padx=(k.px(8), 0))
        for ln in lines:
            k.lbl(c, "•  " + ln, "meta", P["fg2"], wraplength=W - k.px(60), justify="left").pack(fill="x", pady=(k.px(3), 0))
        b = tk.Frame(c, bg=fill)
        b.pack(fill="x", pady=(k.px(10), 0))
        k.button(b, btn, lambda: (self.close(), app.run_op(sess, op)), col,
                 fg="#ffffff" if danger or P["name"] == "light" else P["btnFg"]).pack(side="right")
        k.button(b, t("cf.cancel"), self.close, outline=True, role="body").pack(side="right", padx=(0, k.px(8)))
        self.sheet.update_idletasks()
        h = body.winfo_reqheight()
        g = self.sheet.geometry().split("+")
        self.sheet.geometry(f"{self.sheet.winfo_width()}x{h + (0 if plat.IS_WINDOWS else 2)}+{g[1]}+{g[2]}")


def _size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    return f"{max(1, n // 1024)} KB"
