"""Panel: header (mascot, đếm trạng thái, tài khoản), banner cập nhật, quota, token trên máy, làn session theo trạng
thái (thu / mở được), đã đóng gần đây. Trang Cài đặt và các trang con dựng trong cùng panel (settings.py)."""
from __future__ import annotations

import os
import tkinter as tk

from .. import platform as plat
from .. import render, session_ops
from .. import states as S
from ..config import save_state
from ..i18n import t
from . import fmt, gfx

LANES = ("wait", "run", "done", "idle")
EP = {"cli": "ep.cli", "claude-desktop": "ep.desktop", "sdk-ts": "ep.sdk", "sdk-py": "ep.sdk", "vscode": "ep.vscode"}
CARD_BG = {"wait": "waitBg", "error": "dangerBg", "run": "runBg", "done": "doneBg", "idle": "idleBg"}
STATE_ICON = {"wait": "bell", "run": "run", "done": "done", "idle": "idle", "closed": "exit"}


class Panel:
    def __init__(self, app):
        self.app = app
        self.visible = False
        self.view = "main"
        self._build_window()

    # ================================================================ khung
    def _build_window(self) -> None:
        app, k = self.app, self.app.kit
        P = k.P
        self.win = p = tk.Toplevel(app.root)
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        p.configure(bg=P["bg"])
        S_ = k.S
        self.pw_default = int(400 * S_)
        self.pw_min, self.pw_max = int(340 * S_), int(760 * S_)
        self.ph_min = int(260 * S_)
        self.pw = max(self.pw_min, min(self.pw_max, int(app.state.get("panel_w") or self.pw_default)))
        self.user_h = app.state.get("panel_h")
        self.body = tk.Frame(p, bg=P["bg"])
        self.body.pack(fill="both", expand=True)
        self.hdr = tk.Frame(self.body, bg=P["bg"])
        self.hdr.pack(side="top", fill="x")
        mid = tk.Frame(self.body, bg=P["bg"])
        mid.pack(side="top", fill="both", expand=True)
        self.bar_w = k.px(10)
        self.sbar = tk.Canvas(mid, width=self.bar_w, bg=P["bg"], highlightthickness=0, bd=0)
        self.sbar.pack(side="right", fill="y")
        self.scv = tk.Canvas(mid, bg=P["bg"], highlightthickness=0, bd=0, yscrollincrement=1)
        self.scv.pack(side="left", fill="both", expand=True)
        self.content = None
        self.content_win = None
        self.content_h = 1
        self.scrollable = False
        self.scroll_target = None
        self.thumb = (0, 0)
        self.thumb_drag = None
        self.hdr_key = None
        self.sig = {}
        self.parts = {}
        self.cards = {}
        self.rounded = False
        self.dwm_done = False
        self.resize = None
        self.scv.bind("<Configure>", lambda e: self._sync_scroll())
        self.sbar.bind("<Configure>", lambda e: self._update_thumb())
        self.sbar.bind("<ButtonPress-1>", self._sb_press)
        self.sbar.bind("<B1-Motion>", self._sb_motion)
        self.sbar.bind("<ButtonRelease-1>", lambda e: setattr(self, "thumb_drag", None))
        self._build_grip()
        p.withdraw()

    def rebuild(self) -> None:
        """Đổi theme / ngôn ngữ: dựng lại toàn bộ cửa sổ panel."""
        vis = self.visible
        self.app.kit.anim.items = {k: v for k, v in self.app.kit.anim.items.items() if not (isinstance(k, tuple) and k[0] == "card")}
        self.win.destroy()
        self._build_window()
        if vis:
            self.show()

    # ================================================================ hiển thị
    def toggle(self) -> None:
        self.hide() if self.visible else self.show()

    def show(self) -> None:
        self.render(force=True)
        self.win.attributes("-alpha", 0.0)
        self.place()
        self.win.deiconify()
        if not self.dwm_done:
            self.dwm_done = True
            self.rounded = plat.round_corners(self.win, self.app.kit.P["line"])
            if not self.rounded:
                self.win.configure(bg=self.app.kit.P["line"])
                self.body.pack_configure(padx=1, pady=1)
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.visible = True
        self.place()
        self._fade(1)
        if not plat.GLOBAL_MOUSE:
            self.app.focus_for_dismiss(self.win)

    def _fade(self, step: int) -> None:
        if not self.visible:
            return
        a = min(1.0, step * (0.25 if self.app.kit.anim.enabled else 1.0))
        try:
            self.win.attributes("-alpha", a)
        except tk.TclError:
            return
        if a < 1.0:
            self.app.root.after(16, lambda: self._fade(step + 1))

    def hide(self) -> None:
        self.app.menus.close()
        self.win.withdraw()
        self.visible = False
        if self.view != "main":
            self.view = "main"
            self.hdr_key = None
            self._new_content()

    def place(self) -> None:
        if not self.visible:
            return
        k = self.app.kit
        ph = self._layout()
        pw = self.pw
        ax, ay, aw, ah = self.app.anchor()
        l, t_, r, b = plat.work_area(self.app.root, (ax + aw // 2, ay + ah // 2))
        gap, margin = k.px(10), k.px(12)
        if self.app.prefs["display"] == "island":
            x = max(l + margin, min(ax + (aw - pw) // 2, r - margin - pw))
            self.win.geometry(f"{pw}x{ph}+{x}+{ay + ah + gap}")
            return
        x = ax - pw - gap
        if x < l + margin:
            x = ax + aw + gap
        if x + pw > r - margin:
            x = max(l + margin, r - margin - pw)
        y = max(t_ + margin, min(ay + ah - ph, b - margin - ph))
        self.win.geometry(f"{pw}x{ph}+{x}+{y}")

    def _layout(self) -> int:
        self.body.update_idletasks()
        k = self.app.kit
        ax, ay, aw, ah = self.app.anchor()
        l, t_, r, b = plat.work_area(self.app.root, (ax + aw // 2, ay + ah // 2))
        margin = k.px(12)
        max_h = (b - t_) - 2 * margin - (0 if self.rounded else 2)
        if self.app.prefs["display"] == "island":
            max_h -= ay - t_ + ah
        if self.user_h:
            max_h = max(self.ph_min, min(max_h, int(self.user_h)))
        hh = self.hdr.winfo_reqheight()
        ch = self.content.winfo_reqheight() if self.content else 1
        view = min(ch, max(k.px(140), max_h - hh))
        self.scv.configure(height=view, width=self.pw - self.bar_w - (0 if self.rounded else 2))
        self._sync_scroll()
        return hh + view + (0 if self.rounded else 2)

    # ================================================================ dựng nội dung
    def _new_content(self) -> None:
        P = self.app.kit.P
        old, old_win = self.content, self.content_win
        self.content = tk.Frame(self.scv, bg=P["bg"])
        cw = self.scv.winfo_width()
        cw = cw if cw > 1 else max(1, self.scv.winfo_reqwidth())
        self.content_win = self.scv.create_window(0, 0, anchor="nw", window=self.content, width=cw)
        if old_win is not None:
            self.scv.delete(old_win)
        if old is not None:
            old.destroy()
        self.sig, self.parts, self.cards = {}, {}, {}
        self.app.kit.anim.items = {k: v for k, v in self.app.kit.anim.items.items() if not (isinstance(k, tuple) and k[0] == "card")}

    def inner_w(self) -> int:
        return self.pw - 2 * self.app.kit.px(14) - self.bar_w + self.app.kit.px(4)

    def render(self, force: bool = False) -> None:
        app, k = self.app, self.app.kit
        hdr_key = (self.view, k.P["name"], self.pw, self._header_sig())
        if force or hdr_key != self.hdr_key:
            self.hdr_key = hdr_key
            for w in self.hdr.winfo_children():
                w.destroy()
            self._build_header()
        if self.view != "main":
            if force or self.content is None or self.sig.get("_view") != self._sub_sig():
                self._new_content()
                self.sig["_view"] = self._sub_sig()
                from . import settings
                settings.build(self, self.view)
            self._after_render()
            return
        if force or self.content is None or self.sig.get("_view") != "main":
            self._new_content()
            self.sig["_view"] = "main"
            for name in ("hooks", "notice", "update", "quota", "local") + tuple("lane-" + x for x in LANES) + ("closed",):
                self.parts[name] = tk.Frame(self.content, bg=k.P["bg"])
                self.parts[name].pack(fill="x", padx=(k.px(14), k.px(10)))
            tk.Frame(self.content, bg=k.P["bg"], height=k.px(14)).pack(fill="x")
        snap = app.snap or {}
        sessions = snap.get("sessions") or []
        sigs = {
            "hooks": app.hooks_prompt_needed(),
            "notice": (app.cfg.get("config_error"), snap.get("error")),
            "update": app.update_sig(),
            "quota": self._quota_sig(snap.get("quota") or {}),
            "local": tuple(snap.get("usage", {}).get(x) for x in ("today", "week", "month")),
            "closed": (tuple((c.get("session_id"), fmt.ago(c.get("closed_at"))) for c in app.closed_list()),
                       "closed" in app.prefs["lanes_collapsed"]),
        }
        lanes = {x: [] for x in LANES}
        for s in sessions:
            lanes["wait" if s.get("state") == "error" else s.get("state", "idle")].append(s)
        for lane in LANES:
            sigs["lane-" + lane] = (tuple(self._card_key(s)[0] for s in lanes[lane]), lane in app.prefs["lanes_collapsed"],
                                    bool(sessions), bool(snap.get("ts")))
        builders = {"hooks": self._b_hooks, "notice": self._b_notice, "update": self._b_update, "quota": self._b_quota,
                    "local": self._b_local, "closed": self._b_closed}
        for name, sg in sigs.items():
            if self.sig.get(name) == sg:
                if name.startswith("lane-"):
                    for s in lanes[name[5:]]:
                        self._patch_card(s)
                continue
            holder = self.parts[name]
            for w in holder.winfo_children():
                w.destroy()
            if name.startswith("lane-"):
                self._b_lane(holder, name[5:], lanes[name[5:]], sessions)
            else:
                builders[name](holder)
            self.sig[name] = sg
        self._after_render()

    def _after_render(self) -> None:
        tk.Misc.lift(self.grip)
        if self.visible:
            self.place()
        else:
            self._sync_scroll()

    def _sub_sig(self):
        p = self.app.prefs
        return (self.view, p["lang"], p["theme"], p["display"], p["bubble_type"], p["signal"], p["mascot"], p["hue"],
                p["chip"], p["motion"], p["sound_wait"], p["sound_done"], p["notify_done"], p["quiet"],
                p["quota_alerts"], p["warn_percent"], p["danger_percent"], p["quota_api_enabled"], p["update_check"],
                self.app.hooks_status, self.app.autostart_on(), self.app.update_sig(), self.app.settings_tab)

    # ================================================================ header
    def _header_sig(self):
        snap = self.app.snap or {}
        sess = snap.get("sessions") or []
        c = S.counts(sess)
        return (tuple(c.values()), self.app.headline(), (snap.get("account") or {}).get("email"), self.app.prefs["mascot"],
                self.app.prefs["hue"])

    def _build_header(self) -> None:
        app, k = self.app, self.app.kit
        P = k.P
        row = tk.Frame(self.hdr, bg=P["bg"])
        row.pack(fill="x", padx=(k.px(14), k.px(8)), pady=(k.px(12), k.px(10)))
        if self.view != "main":
            back = "main" if self.view == "settings" else "settings"
            k.icon_btn(row, "back", lambda: self.go(back), 18, P["fg"]).pack(side="left")
            title = t("set.title") if self.view == "settings" else t("set.bubble") if self.view == "bubble" else t("set.mascot")
            k.lbl(row, title, "head").pack(side="left", padx=(k.px(4), 0))
            for ev in plat.RIGHT_CLICK_EVENTS:
                row.bind(ev, lambda e: app.menus.island_menu(e.x_root, e.y_root))
            return
        mood = {"wait": "wait", "quota": "quota", "run": "run", "done": "done"}.get(app.headline(), "idle")
        img = app.mascot_photo(mood, 64, P["bg"])
        ml = tk.Label(row, image=img, bg=P["bg"], bd=0)
        ml._img = img
        ml.pack(side="left", padx=(0, k.px(12)))
        col = tk.Frame(row, bg=P["bg"])
        col.pack(side="left", fill="x", expand=True)
        k.lbl(col, "Wisp", "head").pack(fill="x")
        c = S.counts((app.snap or {}).get("sessions") or [])
        k.lbl(col, t("count", w=c["wait"], r=c["run"], d=c["done"], i=c["idle"]), "meta", P["fg2"]).pack(fill="x", pady=(k.px(3), 0))
        acct = (app.snap or {}).get("account") or {}
        sub = " · ".join(x for x in (acct.get("email"), app.tier_text(acct.get("tier"))) if x)
        if sub:
            k.lbl(col, k.ellipsis(sub, "meta", self.pw - k.px(170)), "meta", P["mut"]).pack(fill="x", pady=(k.px(2), 0))
        btns = tk.Frame(row, bg=P["bg"])
        btns.pack(side="right", anchor="n")
        k.icon_btn(btns, "gear", lambda: self.go("settings"), 18).pack()
        k.icon_btn(btns, "refresh", app.refresh, 17).pack()
        for w in (row, col, ml) + tuple(col.winfo_children()):
            for ev in plat.RIGHT_CLICK_EVENTS:
                w.bind(ev, lambda e: app.menus.island_menu(e.x_root, e.y_root))

    def go(self, view: str) -> None:
        self.view = view
        self.hdr_key = None
        self.render(force=True)
        self.scroll_to(0)

    # ================================================================ các phần của trang chính
    def _section_gap(self, parent, top=12):
        tk.Frame(parent, bg=self.app.kit.P["bg"], height=self.app.kit.px(top)).pack(fill="x")

    def _b_hooks(self, parent) -> None:
        if not self.app.hooks_prompt_needed():
            return
        k, P = self.app.kit, self.app.kit.P
        self._section_gap(parent, 2)
        outer, c = k.card(parent, P["waitBg"], P["wait"], width=self.inner_w(), state="wait")
        outer.pack(fill="x")
        k.lbl(c, t("hk.title"), "body_x").pack(fill="x")
        k.lbl(c, t("hk.body"), "meta", P["fg2"], wraplength=self.inner_w() - k.px(28), justify="left").pack(fill="x", pady=(k.px(4), k.px(8)))
        r = tk.Frame(c, bg=c["bg"])
        r.pack(fill="x")
        k.button(r, t("hk.yes"), self.app.enable_hooks, P["wait"]).pack(side="left")
        k.button(r, t("hk.no"), self.app.dismiss_hooks_prompt, outline=True).pack(side="left", padx=(k.px(8), 0))

    def _b_notice(self, parent) -> None:
        err = self.app.cfg.get("config_error") or (self.app.snap or {}).get("error")
        if not err:
            return
        k, P = self.app.kit, self.app.kit.P
        self._section_gap(parent, 2)
        outer, c = k.card(parent, P["dangerBg"], P["danger"], width=self.inner_w())
        outer.pack(fill="x")
        k.lbl(c, err, "meta", P["fg"], wraplength=self.inner_w() - k.px(28), justify="left").pack(fill="x")

    def _b_update(self, parent) -> None:
        from . import settings
        if self.app.update_banner_kind() is None:
            return
        self._section_gap(parent, 2)
        settings.update_banner(self, parent, self.app.update_banner_kind())

    def _quota_sig(self, q):
        wins = q.get("windows") or []
        return (q.get("ok"), q.get("error"), q.get("stale_error"),
                tuple((w["key"], round(w["percent"]), fmt.clock(w.get("resets_at")), fmt.left((w.get("resets_at") or 0) - __import__("time").time())
                       if w.get("resets_at") else "", (w.get("forecast") or {}).get("before_reset"),
                       fmt.clock((w.get("forecast") or {}).get("eta"))) for w in wins),
                self.app.prefs["warn_percent"], self.app.prefs["danger_percent"])

    def _b_quota(self, parent) -> None:
        import time
        app, k = self.app, self.app.kit
        P = k.P
        q = (app.snap or {}).get("quota")
        self._section_gap(parent, 10)
        outer, c = k.card(parent, P["surf"], P["line"], width=self.inner_w())
        outer.pack(fill="x")
        iw = self.inner_w() - k.px(24)
        if not q or not q.get("ok"):
            if not app.prefs["quota_api_enabled"]:
                msg = t("q.off")
            elif not q:
                msg = t("q.loading")
            else:
                msg = t("q.error", err=q.get("error"))
            k.lbl(c, msg, "meta", P["warn"] if q else P["mut"], wraplength=iw, justify="left").pack(fill="x")
            return
        wins = q.get("windows") or []
        if not wins:
            k.lbl(c, t("q.none"), "meta", P["mut"]).pack(fill="x")
        for i, w in enumerate(wins):
            if i:
                tk.Frame(c, bg=P["line"], height=1).pack(fill="x", pady=k.px(10))
            col = app.level_color(w["percent"])
            r1 = tk.Frame(c, bg=c["bg"])
            r1.pack(fill="x")
            k.lbl(r1, fmt.window_label(w), "body_x").pack(side="left", anchor="s")
            ra = w.get("resets_at")
            sub = t("q.reset_in", clock=fmt.clock(ra), left=fmt.left(ra - time.time())) if ra else ""
            k.lbl(r1, sub, "meta", P["mut"]).pack(side="left", anchor="s", padx=(k.px(8), 0), pady=(0, k.px(1)))
            k.lbl(r1, f"{w['percent']:.0f}%", "num", col).pack(side="right", anchor="s")
            k.bar(c, w["percent"], col, iw, 6).pack(fill="x", pady=(k.px(6), 0))
            f = w.get("forecast")
            if f and f.get("before_reset") and ra:
                r3 = tk.Frame(c, bg=c["bg"])
                r3.pack(fill="x", pady=(k.px(6), 0))
                tk.Label(r3, image=k.icon("trend", 14, P["warn"], c["bg"], 2.2), bg=c["bg"]).pack(side="left")
                k.lbl(r3, t("q.forecast", clock=fmt.clock(f["eta"]), left=fmt.left(ra - f["eta"])), "meta", P["warn"]).pack(
                    side="left", padx=(k.px(6), 0))
        if q.get("stale_error"):
            k.lbl(c, t("q.stale", err=q["stale_error"], clock=fmt.clock(q.get("fetched_at"))), "meta", P["warn"]).pack(
                fill="x", pady=(k.px(8), 0))

    def _b_local(self, parent) -> None:
        k, P = self.app.kit, self.app.kit.P
        u = (self.app.snap or {}).get("usage") or {}
        self._section_gap(parent, 10)
        outer, c = k.card(parent, P["surf"], P["line"], width=self.inner_w())
        outer.pack(fill="x")
        r = tk.Frame(c, bg=c["bg"])
        r.pack(fill="x")
        k.lbl(r, t("local.title"), "body_x").pack(side="left")
        k.lbl(r, t("local.note"), "meta", P["mut"]).pack(side="right")
        g = tk.Frame(c, bg=c["bg"])
        g.pack(fill="x", pady=(k.px(8), 0))
        for i, key in enumerate(("today", "week", "month")):
            g.grid_columnconfigure(i, weight=1, uniform="u")
            cell = tk.Frame(g, bg=c["bg"])
            cell.grid(row=0, column=i, sticky="w")
            k.lbl(cell, t("local." + key), "meta", P["mut"]).pack(anchor="w")
            v = u.get(key)
            k.lbl(cell, "…" if v is None else fmt.k(v), "num").pack(anchor="w", pady=(k.px(2), 0))

    # ---------------------------------------------------------------- làn session
    def _lane_header(self, parent, lane: str, n, color) -> None:
        k, P = self.app.kit, self.app.kit.P
        collapsed = lane in self.app.prefs["lanes_collapsed"]
        h = tk.Frame(parent, bg=P["bg"], cursor="hand2")
        h.pack(fill="x", pady=(k.px(12), k.px(6)))
        icon = tk.Label(h, image=k.icon(STATE_ICON[lane], 15, color, P["bg"], 2.2), bg=P["bg"])
        icon.pack(side="left")
        k.lbl(h, t("lane." + lane), "body_x", color).pack(side="left", padx=(k.px(6), 0))
        k.lbl(h, str(n), "body", P["mut"]).pack(side="left", padx=(k.px(6), 0))
        chev = tk.Label(h, image=k.icon("chev" if collapsed else "down", 15, P["mut"], P["bg"]), bg=P["bg"])
        chev.pack(side="right")
        for w in (h,) + tuple(h.winfo_children()):
            w.bind("<Button-1>", lambda e: self.app.toggle_lane(lane))

    def _b_lane(self, parent, lane: str, items: list, all_sessions: list) -> None:
        k, P = self.app.kit, self.app.kit.P
        if not all_sessions:
            if lane == "wait" and (self.app.snap or {}).get("ts"):
                self._section_gap(parent, 12)
                outer, c = k.card(parent, P["surf"], P["line"], width=self.inner_w(), pady=14)
                outer.pack(fill="x")
                k.lbl(c, t("no_sessions"), "meta", P["mut"], anchor="center").pack(fill="x")
            return
        if not items:
            return
        self._lane_header(parent, lane, len(items), P[lane])
        if lane in self.app.prefs["lanes_collapsed"]:
            return
        for i, s in enumerate(items):
            if i:
                tk.Frame(parent, bg=P["bg"], height=k.px(8)).pack(fill="x")
            self._build_card(parent, s)

    @staticmethod
    def _card_key(s: dict) -> tuple:
        git = session_ops.state_text(s.get("git"))
        struct = (s["session_id"], s.get("state"), s.get("wait_kind"), s["has_transcript"], s["name"], s["model"],
                  s.get("effort"), s.get("cwd"), s.get("git_branch"), s.get("entrypoint"), bool(s.get("todo")),
                  bool(git[0]))
        live = (fmt.ago(s.get("last_activity")), s.get("detail"), s.get("last_msg"), s["context_tokens"],
                s["context_limit"], s.get("todo"), git)
        return struct, live

    def _build_card(self, parent, s: dict) -> None:
        app, k = self.app, self.app.kit
        P = k.P
        st = s.get("state", "idle")
        fill = P[CARD_BG.get(st, "idleBg")]
        scol = P["danger"] if st == "error" else P.get(st, P["idle"])
        border = P["line"] if st == "idle" else render.rgb2hex(render.mix(render.hex2rgb(fill), render.hex2rgb(scol), 0.55))
        outer, c = k.card(parent, fill, border, width=self.inner_w(), state=st if st in ("wait", "run") else None)
        outer.pack(fill="x")
        outer._sess = s  # chuột phải khi app không active (macOS): app._poll_right_click tìm session qua card
        iw = self.inner_w() - k.px(24)
        refs = {}
        # dòng 1: tên · thời gian · model · effort · ⋯
        r1 = tk.Frame(c, bg=fill)
        r1.pack(fill="x")
        more = tk.Label(r1, image=k.icon("more", 17, P["mut"], fill), bg=fill, cursor="hand2", width=k.px(28))
        more.pack(side="right")
        meta = tk.Frame(r1, bg=fill)
        meta.pack(side="right", padx=(k.px(8), k.px(2)))
        refs["ago"] = k.lbl(meta, self._ago_text(s), "meta", P["mut"])
        refs["ago"].pack(side="left")
        from ..claude_data import short_model
        model = short_model(s["model"])
        if model != "?":
            k.lbl(meta, model, "meta", P["mut"]).pack(side="left")
        if s.get("effort"):
            k.lbl(meta, " · ", "meta", P["mut"]).pack(side="left")
            k.lbl(meta, s["effort"], "meta_b", P["fg2"]).pack(side="left")
        used = meta.winfo_reqwidth() + k.px(40)
        k.lbl(r1, k.ellipsis(s["name"], "title", iw - used), "title").pack(side="left")
        # dòng 2: việc đang làm
        mono_bg = P["code"]
        if st == "wait" and s.get("wait_kind") == "permission":
            box = tk.Frame(c, bg=mono_bg, padx=k.px(10), pady=k.px(6))
            box.pack(fill="x", pady=(k.px(6), 0))
            tool = s.get("tool") or ""
            refs["detail"] = k.lbl(box, k.ellipsis((f"{tool} › " if tool else "") + (s.get("detail") or t("wait.permission")),
                                                   "mono", iw - k.px(24)), "mono", P["codeFg"])
            refs["detail"].pack(fill="x")
        elif st in ("wait", "error"):
            txt = s.get("detail") or (t("wait.question") if st == "wait" else t("error"))
            refs["detail"] = k.lbl(c, txt, "body", P["fg2"] if st == "wait" else P["danger"], wraplength=iw, justify="left")
            refs["detail"].pack(fill="x", pady=(k.px(4), 0))
        elif st == "run" and (s.get("tool") or s.get("detail")):
            refs["detail"] = k.lbl(c, k.ellipsis(f"{s.get('tool') or ''} {s.get('detail') or ''}".strip(), "mono_s", iw),
                                   "mono_s", P["fg2"])
            refs["detail"].pack(fill="x", pady=(k.px(4), 0))
        elif st == "done" and s.get("last_msg"):
            refs["detail"] = k.lbl(c, k.ellipsis(s["last_msg"], "body", iw), "body", P["fg2"])
            refs["detail"].pack(fill="x", pady=(k.px(4), 0))
        # dòng 3: dự án · branch · việc a/b · git
        refs["where"] = k.lbl(c, k.ellipsis(self._where(s), "meta", iw), "meta", P["mut"])
        refs["where"].pack(fill="x", pady=(k.px(3), 0))
        # context
        r4 = tk.Frame(c, bg=fill)
        r4.pack(fill="x", pady=(k.px(6), k.px(4)))
        k.lbl(r4, t("ctx"), "meta", P["mut"]).pack(side="left")
        if s["has_transcript"]:
            ccol = app.level_color(s["context_pct"])
            refs["pct"] = k.lbl(r4, f"{s['context_pct']:.0f}%", "meta_b", ccol)
            refs["pct"].pack(side="right")
            refs["tok"] = k.lbl(r4, f"{fmt.k(s['context_tokens'])} / {fmt.k(s['context_limit'])}", "meta", P["fg2"])
            refs["tok"].pack(side="right", padx=(0, k.px(6)))
            refs["bar_parent"] = c
            refs["bar"] = k.bar(c, s["context_pct"], ccol, iw, 4)
            refs["bar"].pack(fill="x")
        else:
            k.lbl(r4, t("ctx.none"), "meta", P["mut"]).pack(side="right")
        if st == "wait":
            r5 = tk.Frame(c, bg=fill)
            r5.pack(fill="x", pady=(k.px(8), 0))
            k.button(r5, t("open"), lambda sess=s: app.focus_session(sess), P["wait"], icon="open").pack(side="left")
            ep = t(EP[s.get("entrypoint")]) if s.get("entrypoint") in EP else ""
            if ep:
                tk.Label(r5, image=k.icon("term", 13, P["mut"], fill, 2), bg=fill).pack(side="left", padx=(k.px(10), k.px(4)))
                k.lbl(r5, ep, "meta", P["mut"]).pack(side="left")
        open_ = lambda e, sess=s: app.focus_session(sess)  # noqa: E731
        menu = lambda e, sess=s: app.menus.session_menu(sess, e.x_root, e.y_root)  # noqa: E731
        self._bind_tree(outer, "<Button-1>", open_, skip=(more,))
        for ev in plat.RIGHT_CLICK_EVENTS:
            self._bind_tree(outer, ev, menu)
        more.bind("<Button-1>", menu)
        self.cards[s["session_id"]] = (refs, self._card_key(s)[1])

    def _ago_text(self, s) -> str:
        a = fmt.ago(s.get("state_since") or s.get("last_activity"))
        return f"{a} · " if a else ""

    @staticmethod
    def _where(s) -> str:
        cwd = (s.get("cwd") or "").rstrip("\\/")
        bits = [os.path.basename(cwd) or cwd]
        br = s.get("git_branch")
        if br and br != "HEAD":
            bits.append(br)
        if s.get("todo"):
            bits.append(t("task", a=s["todo"][0], b=s["todo"][1]))
        gtxt, _ = session_ops.state_text(s.get("git"))
        if gtxt:
            bits.append(gtxt)
        return " · ".join(b for b in bits if b)

    def _patch_card(self, s: dict) -> None:
        got = self.cards.get(s["session_id"])
        if not got:
            return
        refs, live = got
        new = self._card_key(s)[1]
        if new == live:
            return
        k, P = self.app.kit, self.app.kit.P
        iw = self.inner_w() - k.px(24)
        refs["ago"].configure(text=self._ago_text(s))
        if "detail" in refs and s.get("state") == "run":
            refs["detail"].configure(text=k.ellipsis(f"{s.get('tool') or ''} {s.get('detail') or ''}".strip(), "mono_s", iw))
        refs["where"].configure(text=k.ellipsis(self._where(s), "meta", iw))
        if "pct" in refs:
            ccol = self.app.level_color(s["context_pct"])
            refs["pct"].configure(text=f"{s['context_pct']:.0f}%", fg=ccol)
            refs["tok"].configure(text=f"{fmt.k(s['context_tokens'])} / {fmt.k(s['context_limit'])}")
            old = refs["bar"]
            refs["bar"] = k.bar(refs["bar_parent"], s["context_pct"], ccol, iw, 4)
            refs["bar"].pack(fill="x", after=old)
            old.destroy()
        self.cards[s["session_id"]] = (refs, new)

    def _bind_tree(self, w, ev, fn, skip=()):
        if w in skip:
            return
        w.bind(ev, fn)
        try:
            w.configure(cursor="hand2")
        except tk.TclError:
            pass
        for ch in w.winfo_children():
            if not isinstance(ch, tk.Canvas) or ev != "<Button-1>":  # nút (canvas) giữ hành động riêng
                self._bind_tree(ch, ev, fn, skip)

    # ---------------------------------------------------------------- đã đóng gần đây
    def _b_closed(self, parent) -> None:
        app, k = self.app, self.app.kit
        P = k.P
        items = app.closed_list()
        if not items:
            return
        self._lane_header(parent, "closed", len(items), P["mut"])
        if "closed" in app.prefs["lanes_collapsed"]:
            return
        outer, c = k.card(parent, P["surf"], P["line"], width=self.inner_w(), pady=4)
        outer.pack(fill="x")
        iw = self.inner_w() - k.px(24)
        for i, it in enumerate(items):
            if i:
                tk.Frame(c, bg=P["line"], height=1).pack(fill="x")
            row = tk.Frame(c, bg=P["surf"])
            row.pack(fill="x", pady=k.px(6))
            k.icon_btn(row, "x", lambda sid=it["session_id"]: app.forget_closed(sid), 14).pack(side="right")
            b = k.lbl(row, t("closed.reopen"), "meta_b", P["run"], cursor="hand2")
            b.pack(side="right", padx=(k.px(8), 0))
            b.bind("<Button-1>", lambda e, it=it: app.resume_closed(it))
            if it.get("handoff") and os.path.isfile(it["handoff"]):
                hb = k.lbl(row, t("closed.handoff"), "meta_b", P["done"], cursor="hand2")
                hb.pack(side="right", padx=(k.px(8), 0))
                hb.bind("<Button-1>", lambda e, f=it["handoff"]: app.open_path(f))
            left = tk.Frame(row, bg=P["surf"])
            left.pack(side="left", fill="x", expand=True)
            k.lbl(left, k.ellipsis(it.get("name") or "?", "body", iw - k.px(150)), "body").pack(anchor="w")
            where = os.path.basename((it.get("cwd") or "").rstrip("/\\")) or "?"
            k.lbl(left, f"{where} · " + t("closed.closed", ago=fmt.ago_long(it.get("closed_at"))), "meta", P["mut"]).pack(anchor="w")

    # ================================================================ cuộn (giữ từ bản 0.1.7)
    def view_h(self) -> int:
        h = self.scv.winfo_height()
        return h if h > 1 else max(1, self.scv.winfo_reqheight())

    def offset(self) -> float:
        return float(self.scv.canvasy(0))

    def _sync_scroll(self) -> None:
        if not self.content:
            return
        cw = self.scv.winfo_width()
        cw = cw if cw > 1 else max(1, self.scv.winfo_reqwidth())
        self.scv.itemconfigure(self.content_win, width=cw)
        ch = max(1, self.content.winfo_reqheight())
        self.content_h = ch
        vh = self.view_h()
        self.scrollable = ch > vh + 1
        self.scv.configure(scrollregion=(0, 0, cw, max(ch, vh)))
        if self.scroll_target is not None:
            self.scroll_target = max(0.0, min(self._max_off(), self.scroll_target))
            self._update_thumb()
        else:
            self.scroll_to(self.offset(), animate=False)

    def _max_off(self) -> float:
        return max(0.0, self.content_h - self.view_h())

    def scroll_to(self, off: float, animate: bool = False) -> None:
        off = max(0.0, min(self._max_off(), off))
        if animate and self.app.kit.anim.enabled:
            self.scroll_target = off
            self._animate_scroll()
            return
        self.scroll_target = None
        total = max(self.content_h, self.view_h())
        self.scv.yview_moveto(off / total if total else 0)
        self._update_thumb()

    def _animate_scroll(self) -> None:
        if self.scroll_target is None:
            return
        cur = self.offset()
        d = self.scroll_target - cur
        if abs(d) < 1.5:
            self.scroll_to(self.scroll_target)
            return
        total = max(self.content_h, self.view_h())
        self.scv.yview_moveto((cur + d * 0.35) / total)
        self._update_thumb()
        self.app.root.after(12, self._animate_scroll)

    def wheel(self, delta: float, x: int, y: int) -> None:
        if not delta or not self.visible or not self.scrollable or self.app.menus.sheet:
            return
        if not self.app.inside(self.win, x, y):
            return
        base = self.scroll_target if self.scroll_target is not None else self.offset()
        self.scroll_to(base - delta * plat.WHEEL_PX_PER_DELTA * self.app.kit.S, animate=True)

    def _update_thumb(self) -> None:
        sb, k, P = self.sbar, self.app.kit, self.app.kit.P
        sb.delete("all")
        self.thumb = (0, 0)
        if not self.scrollable or not self.content:
            return
        vh = self.view_h()
        pad = k.px(4)
        track = max(1, vh - 2 * pad)
        L = min(track, max(k.px(28), int(track * vh / max(self.content_h, 1))))
        mo = self._max_off()
        y0 = pad + int((track - L) * (self.offset() / mo if mo else 0))
        w = k.px(5 if self.thumb_drag else 4)
        img = k.rounded(w, L, w / 2, P["mut"] if self.thumb_drag else P["dim"], None, P["bg"])
        sb.create_image((self.bar_w - w) // 2, y0, anchor="nw", image=img)
        self.thumb = (y0, y0 + L)

    def _sb_press(self, e) -> None:
        if not self.scrollable:
            return
        y0, y1 = self.thumb
        if y0 <= e.y <= y1:
            self.thumb_drag = (e.y, self.offset())
        else:
            page = self.view_h() * 0.9
            self.scroll_to(self.offset() + (page if e.y > y1 else -page), animate=True)

    def _sb_motion(self, e) -> None:
        if not self.thumb_drag:
            return
        y_start, off0 = self.thumb_drag
        y0, y1 = self.thumb
        free = max(1, (self.view_h() - 2 * self.app.kit.px(4)) - (y1 - y0))
        self.scroll_to(off0 + (e.y - y_start) * self._max_off() / free)

    # ================================================================ resize (giữ từ bản 0.1.7)
    def _build_grip(self) -> None:
        k, P = self.app.kit, self.app.kit.P
        g = k.px(14)
        c = tk.Canvas(self.body, width=g, height=g, bg=P["bg"], highlightthickness=0, bd=0)
        self.grip = c
        step, r = max(3, k.px(4)), max(1, k.px(1))
        island = self.app.prefs["display"] == "island"
        for i in range(3):
            for j in range(3 - i):
                x, y = k.px(3) + j * step, k.px(3) + i * step
                if island:
                    y = g - 1 - y
                c.create_oval(x - r, y - r, x + r, y + r, fill=P["dim"], outline="", tags="dot")
        # tên con trỏ size_* chỉ có trên Windows: macOS báo "bad cursor spec" và app thoát ngay khi mở
        if plat.IS_WINDOWS:
            c.configure(cursor="size_ne_sw" if island else "size_nw_se")
        else:
            c.configure(cursor="bottom_left_corner" if island else "top_left_corner")
        inset = k.px(3) if plat.IS_MAC else 0  # góc panel bo tròn: dời tay nắm vào trong
        c.place(x=inset, y=-inset if island else inset, rely=1.0 if island else 0.0, anchor="sw" if island else "nw")
        c.bind("<Enter>", lambda e: c.itemconfigure("dot", fill=P["fg2"]))
        c.bind("<Leave>", lambda e: c.itemconfigure("dot", fill=P["dim"]))
        c.bind("<ButtonPress-1>", self._rz_start)
        c.bind("<B1-Motion>", self._rz_move)
        c.bind("<ButtonRelease-1>", self._rz_end)
        c.bind("<Double-Button-1>", self._rz_reset)

    def _rz_start(self, e) -> None:
        p = self.win
        self.resize = (e.x_root, e.y_root, p.winfo_width(), p.winfo_height(), p.winfo_x() + p.winfo_width(),
                       p.winfo_y() + p.winfo_height(), p.winfo_y())
        self.app.modal = True

    def _rz_move(self, e) -> None:
        if not self.resize:
            return
        x0, y0, w0, h0, right, bottom, top = self.resize
        l, t_, r, b = plat.work_area(self.app.root, (right - 1, bottom - 1))
        w = max(self.pw_min, min(self.pw_max, w0 - (e.x_root - x0), right - l))
        if self.app.prefs["display"] == "island":
            h = max(self.ph_min, min(h0 + (e.y_root - y0), b - top))
            self.win.geometry(f"{int(w)}x{int(h)}+{int(right - w)}+{int(top)}")
            return
        h = max(self.ph_min, min(h0 - (e.y_root - y0), bottom - t_))
        self.win.geometry(f"{int(w)}x{int(h)}+{int(right - w)}+{int(bottom - h)}")

    def _rz_end(self, e) -> None:
        if not self.resize:
            return
        self.resize = None
        self.app.modal = False
        self.pw = max(self.pw_min, min(self.pw_max, self.win.winfo_width()))
        self.user_h = self.win.winfo_height()
        self.app.state["panel_w"], self.app.state["panel_h"] = self.pw, self.user_h
        save_state(self.app.state)
        self.hdr_key = None
        self.render(force=True)

    def _rz_reset(self, e=None) -> None:
        self.resize = None
        self.app.modal = False
        self.pw, self.user_h = self.pw_default, None
        self.app.state.pop("panel_w", None)
        self.app.state.pop("panel_h", None)
        save_state(self.app.state)
        self.hdr_key = None
        self.render(force=True)


def lamp_icon(lane: str) -> str:
    return STATE_ICON.get(lane, "idle")


__all__ = ["Panel", "LANES", "gfx"]
