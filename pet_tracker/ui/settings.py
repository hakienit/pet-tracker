"""Trang Cài đặt trong panel (view "settings"), trang con Bóng nổi ("bubble") và thư viện mascot ("mascots").
Mọi thay đổi lưu ngay vào state.json["prefs"] qua app.set_pref."""
from __future__ import annotations

import tkinter as tk

from .. import __version__, mascots
from ..i18n import t
from . import fmt, gfx

HUE_SW = ("#ff8a4c", "#ff5d5d", "#ff7eb6", "#a78bfa", "#58a6ff", "#3fd0c0", "#6fd08c", "#ffd23f")
CATS = ("all", "fire", "crit", "thing", "nature")


def build(panel, view: str) -> None:
    {"settings": _main, "bubble": _bubble, "mascots": _mascots}.get(view, _main)(panel)


# ---------------------------------------------------------------- khối dùng chung
def _group(panel, title: str):
    k, P = panel.app.kit, panel.app.kit.P
    wrap = tk.Frame(panel.content, bg=P["bg"])
    wrap.pack(fill="x", padx=(k.px(14), k.px(10)), pady=(k.px(4), k.px(10)))
    k.lbl(wrap, title, "meta_b", P["mut"]).pack(fill="x", padx=k.px(2), pady=(0, k.px(6)))
    outer, inner = k.card(wrap, P["surf"], P["line"], width=panel.inner_w(), padx=0, pady=2)
    outer.pack(fill="x")
    inner._rows = 0
    return inner


def _row(panel, g, label: str, control_fn=None, sub=None, on_click=None):
    k, P = panel.app.kit, panel.app.kit.P
    if g._rows:
        tk.Frame(g, bg=P["line"], height=1).pack(fill="x", padx=k.px(12))
    g._rows += 1
    r = tk.Frame(g, bg=P["surf"], padx=k.px(12), pady=k.px(8), cursor="hand2" if on_click else "")
    r.pack(fill="x")
    left = tk.Frame(r, bg=P["surf"])
    left.pack(side="left", fill="x", expand=True)
    k.lbl(left, label, "body").pack(fill="x")
    if sub:
        k.lbl(left, sub, "meta", P["mut"]).pack(fill="x")
    if control_fn:
        control_fn(r).pack(side="right")
    if on_click:
        for w in (r, left) + tuple(left.winfo_children()):
            w.bind("<Button-1>", lambda e: on_click())
    return r


def _value(panel, text: str, img=None):
    k, P = panel.app.kit, panel.app.kit.P

    def mk(parent):
        f = tk.Frame(parent, bg=parent["bg"])
        if img is not None:
            lb = tk.Label(f, image=img, bg=parent["bg"])
            lb._img = img
            lb.pack(side="left", padx=(0, k.px(6)))
        if text:
            k.lbl(f, text, "body", P["fg2"]).pack(side="left")
        tk.Label(f, image=k.icon("chev", 14, P["mut"], parent["bg"]), bg=parent["bg"]).pack(side="left", padx=(k.px(6), 0))
        return f
    return mk


def _seg(panel, options, current, values, pref):
    return lambda parent: panel.app.kit.segmented(parent, options, values.index(current) if current in values else 0,
                                                  lambda i: panel.app.set_pref(pref, values[i]))


def _switch(panel, pref):
    return lambda parent: panel.app.kit.switch(parent, bool(panel.app.prefs[pref]), lambda v: panel.app.set_pref(pref, v))


def _stepper(panel, pref, lo, hi):
    k, P = panel.app.kit, panel.app.kit.P

    def mk(parent):
        f = tk.Frame(parent, bg=P["line"], padx=1, pady=1)
        inner = tk.Frame(f, bg=P["surf"])
        inner.pack()
        v = int(panel.app.prefs[pref])
        for text, d in (("−", -5), (None, 0), ("+", 5)):
            if text is None:
                k.lbl(inner, f"{v}%", "body_b", anchor="center", width=5).pack(side="left")
                continue
            b = k.lbl(inner, text, "body_x", P["mut"], anchor="center", width=2, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, d=d: panel.app.set_pref(pref, max(lo, min(hi, v + d))))
        return f
    return mk


def _action(panel, g, icon: str, label: str, cmd, danger=False):
    k, P = panel.app.kit, panel.app.kit.P
    if g._rows:
        tk.Frame(g, bg=P["line"], height=1).pack(fill="x", padx=k.px(12))
    g._rows += 1
    col = P["danger"] if danger else P["fg"]
    r = tk.Frame(g, bg=P["surf"], padx=k.px(12), pady=k.px(9), cursor="hand2")
    r.pack(fill="x")
    ic = tk.Label(r, image=k.icon(icon, 16, P["danger"] if danger else P["mut"], P["surf"]), bg=P["surf"])
    ic.pack(side="left")
    lb = k.lbl(r, label, "body", col)
    lb.pack(side="left", padx=(k.px(10), 0))
    for w in (r, ic, lb):
        w.bind("<Button-1>", lambda e: cmd())
        w.bind("<Enter>", lambda e: [x.configure(bg=P["hover"]) for x in (r, ic, lb)])
        w.bind("<Leave>", lambda e: [x.configure(bg=P["surf"]) for x in (r, ic, lb)])


# ---------------------------------------------------------------- trang chính
def _main(panel) -> None:
    app, k = panel.app, panel.app.kit
    P, p = k.P, app.prefs
    g = _group(panel, t("set.general"))
    _row(panel, g, t("set.lang"), _seg(panel, ["Tiếng Việt", "English"], app.lang_code(), ["vi", "en"], "lang"))
    _row(panel, g, t("set.theme"), _seg(panel, [t("set.theme.system"), t("set.theme.dark"), t("set.theme.light")],
                                         p["theme"], ["system", "dark", "light"], "theme"))
    _row(panel, g, t("set.display"), _seg(panel, [t("set.display.island"), t("set.display.bubble")], p["display"],
                                           ["island", "bubble"], "display"))
    bub = (t("set.bubble.mascot") + " · " + app.mascot_name()) if p["bubble_type"] == "mascot" else \
        (t("set.bubble.signal") + " · " + t("sig." + p["signal"]))
    _row(panel, g, t("set.bubble"), _value(panel, bub), on_click=lambda: panel.go("bubble"))
    _row(panel, g, t("set.mascot"), _value(panel, "", app.mascot_photo("run", 26, P["surf"])), on_click=lambda: panel.go("mascots"))
    _row(panel, g, t("set.motion"), _seg(panel, [t("set.motion.system"), t("set.motion.on"), t("set.motion.off")],
                                          p["motion"], ["system", "on", "off"], "motion"))
    _row(panel, g, t("set.startup"), lambda parent: k.switch(parent, app.autostart_on(), lambda v: app.toggle_autostart()))

    g = _group(panel, t("set.notif"))
    _row(panel, g, t("set.sound_wait"), _switch(panel, "sound_wait"))
    _row(panel, g, t("set.sound_done"), _switch(panel, "sound_done"))
    _row(panel, g, t("set.notify_done"), _switch(panel, "notify_done"))
    _row(panel, g, t("set.quiet"), _switch(panel, "quiet"), sub=f"{p['quiet_from']} – {p['quiet_to']}")
    _row(panel, g, t("set.quota_alerts"), _switch(panel, "quota_alerts"), sub="80% · 95%")

    g = _group(panel, t("set.hooks"))
    hs = app.hooks_status
    dot = {"on": P["ok"], "stale": P["warn"], "error": P["danger"]}.get(hs, P["dim"])
    label = {"on": t("set.hooks.on"), "stale": t("set.hooks.stale"), "error": t("set.hooks.err")}.get(hs, t("set.hooks.off"))
    last = app.hooks_last_event()
    sub = t("set.hooks.port", p=app.cfg["hook_port"]) + " · " + (t("set.hooks.last", ago=fmt.ago_long(last)) if last else t("set.hooks.none"))
    if app.hooks_error:
        sub = app.hooks_error
    r = _row(panel, g, label, sub=sub)
    lab = r.winfo_children()[0].winfo_children()[0]
    lab.configure(text="  " + label, image=k.image(("dot", dot), lambda: gfx.shape_rows(k.px(8), k.px(8), k.px(4), dot), P["surf"]),
                  compound="left", padx=0)
    btns = tk.Frame(g, bg=P["surf"], padx=k.px(12), pady=k.px(8))
    btns.pack(fill="x")
    k.button(btns, t("set.hooks.test"), app.test_hooks, outline=True, role="body").pack(side="left")
    if hs == "on":
        k.button(btns, t("set.hooks.remove"), app.disable_hooks, outline=True, role="body").pack(side="left", padx=(k.px(8), 0))
    else:
        k.button(btns, t("set.hooks.enable"), app.enable_hooks, P["wait"]).pack(side="left", padx=(k.px(8), 0))

    g = _group(panel, t("set.quota"))
    _row(panel, g, t("set.warn"), _stepper(panel, "warn_percent", 10, 95))
    _row(panel, g, t("set.danger"), _stepper(panel, "danger_percent", 15, 100))
    _row(panel, g, t("set.api"), _switch(panel, "quota_api_enabled"))

    g = _group(panel, t("set.update"))
    box = tk.Frame(g, bg=P["surf"], padx=k.px(10), pady=k.px(8))
    box.pack(fill="x")
    g._rows += 1
    update_banner(panel, box, app.update_banner_kind() or "latest", width=panel.inner_w() - k.px(20))
    _row(panel, g, t("set.auto_update"), _switch(panel, "update_check"))
    _row(panel, g, t("set.check_now"), lambda parent: k.icon_btn(parent, "refresh", app.check_update_now, 15))

    g = _group(panel, t("set.adv"))
    _action(panel, g, "refresh", t("set.refresh"), app.refresh)
    _action(panel, g, "folder", t("set.open_claude"), app.open_claude_dir)
    _action(panel, g, "info", t("set.open_cfg"), app.open_config)
    _action(panel, g, "info", t("set.open_log"), app.open_log)
    _action(panel, g, "power", t("set.quit"), app.quit, danger=True)
    k.lbl(panel.content, f"Wisp v{__version__}", "meta", P["mut"], anchor="center").pack(fill="x", pady=(k.px(2), k.px(14)))


# ---------------------------------------------------------------- trang con Bóng nổi
def _bubble(panel) -> None:
    app, k = panel.app, panel.app.kit
    P, p = k.P, app.prefs
    g = _group(panel, t("set.bubble.preview"))
    prev = tk.Frame(g, bg=P["surf"], pady=k.px(8))
    prev.pack(fill="x")
    row = tk.Frame(prev, bg=P["surf"])
    row.pack()
    for st in ("idle", "run", "wait", "quota"):
        img = app.bubble_preview(st, 56, P["surf"])
        lb = tk.Label(row, image=img, bg=P["surf"])
        lb._img = img
        lb.pack(side="left", padx=k.px(4))
    segrow = tk.Frame(g, bg=P["surf"], padx=k.px(10), pady=k.px(8))
    segrow.pack(fill="x")
    k.segmented(segrow, [t("set.bubble.signal"), t("set.bubble.mascot")], 1 if p["bubble_type"] == "mascot" else 0,
                lambda i: app.set_pref("bubble_type", "mascot" if i else "signal")).pack(fill="x")
    if p["bubble_type"] == "signal":
        g = _group(panel, t("set.bubble.style"))
        grid = tk.Frame(g, bg=P["surf"], padx=k.px(6), pady=k.px(6))
        grid.pack(fill="x")
        for i, sid in enumerate(gfx.SIGNALS):
            grid.grid_columnconfigure(i % 3, weight=1, uniform="s")
            on = sid == p["signal"]
            cell = tk.Frame(grid, bg=P["waitBg"] if on else P["surf"], padx=k.px(4), pady=k.px(6), cursor="hand2",
                            highlightthickness=1, highlightbackground=P["wait"] if on else P["surf"])
            cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=k.px(2), pady=k.px(2))
            img = app.signal_thumb(sid, 52, cell["bg"])
            il = tk.Label(cell, image=img, bg=cell["bg"])
            il._img = img
            il.pack()
            tl = k.lbl(cell, t("sig." + sid), "meta", P["fg2"], anchor="center")
            tl.pack(fill="x")
            for w in (cell, il, tl):
                w.bind("<Button-1>", lambda e, sid=sid: app.set_pref("signal", sid))
        return
    g = _group(panel, t("set.mascot"))
    _mascot_grid(panel, g, mascots.all_mascots()[:11], more=True)
    _hues(panel, g)
    g = _group(panel, t("set.chip"))
    for i in range(3):
        on = i == p["chip"]
        r = tk.Frame(g, bg=P["hover"] if on else P["surf"], padx=k.px(10), pady=k.px(7), cursor="hand2")
        r.pack(fill="x")
        dot = tk.Label(r, image=k.image(("radio", on), lambda on=on: _radio_rows(k, P, on), r["bg"]), bg=r["bg"])
        dot.pack(side="left")
        lb = k.lbl(r, t(f"chip.{i}"), "body")
        lb.pack(side="left", padx=(k.px(8), 0))
        for w in (r, dot, lb):
            w.bind("<Button-1>", lambda e, i=i: app.set_pref("chip", i))


def _radio_rows(k, P, on):
    n = k.px(16)
    rows = gfx.shape_rows(n, n, n / 2, P["surf"], P["wait"] if on else P["mut"], max(1.5, k.px(2)))
    if on:
        m = k.px(7)
        inner = gfx.shape_rows(m, m, m / 2, P["wait"])
        o = (n - m) // 2
        for y, row in enumerate(inner):
            for x, px in enumerate(row):
                if px[3]:
                    rows[y + o][x + o] = px
    return rows


def _mascot_grid(panel, g, items, more=False, cols=6):
    app, k = panel.app, panel.app.kit
    P, p = k.P, app.prefs
    grid = tk.Frame(g, bg=P["surf"], padx=k.px(6), pady=k.px(6))
    grid.pack(fill="x")
    cells = [(m["id"], m) for m in items] + [("custom", None)]
    for i, (mid, m) in enumerate(cells):
        grid.grid_columnconfigure(i % cols, weight=1, uniform="m")
        on = mid == p["mascot"]
        cell = tk.Frame(grid, bg=P["waitBg"] if on else P["surf"], highlightthickness=1,
                        highlightbackground=P["wait"] if on else P["surf"], cursor="hand2")
        cell.grid(row=i // cols, column=i % cols, sticky="nsew", padx=k.px(2), pady=k.px(2))
        if mid == "custom":
            img = k.icon("up", 18, P["mut"], cell["bg"], 2)
            cmd = app.pick_custom_image
        else:
            img = app.mascot_thumb(mid, 34, cell["bg"])
            cmd = lambda mid=mid: app.set_pref("mascot", mid)  # noqa: E731
        lb = tk.Label(cell, image=img, bg=cell["bg"], pady=k.px(4))
        lb._img = img
        lb.pack()
        for w in (cell, lb):
            w.bind("<Button-1>", lambda e, cmd=cmd: cmd())
    if more:
        m = k.lbl(g, t("set.all_mascots", n=len(mascots.all_mascots())) + " ›", "meta_b", P["run"], cursor="hand2")
        m.pack(fill="x", padx=k.px(12), pady=(0, k.px(6)))
        m.bind("<Button-1>", lambda e: panel.go("mascots"))


def _hues(panel, g):
    app, k = panel.app, panel.app.kit
    P = k.P
    r = tk.Frame(g, bg=P["surf"], padx=k.px(12), pady=k.px(8))
    r.pack(fill="x")
    k.lbl(r, t("set.color"), "meta", P["mut"]).pack(side="left")
    box = tk.Frame(r, bg=P["surf"])
    box.pack(side="right")
    for i, c in enumerate(HUE_SW):
        on = i == app.prefs["hue"]
        n = k.px(20)
        img = k.image(("hue", i, on), lambda c=c, on=on: gfx.shape_rows(n, n, n / 2, c, P["fg"] if on else None, k.px(2)), P["surf"])
        b = tk.Label(box, image=img, bg=P["surf"], cursor="hand2")
        b.pack(side="left", padx=k.px(2))
        b.bind("<Button-1>", lambda e, i=i: app.set_pref("hue", i))


# ---------------------------------------------------------------- thư viện mascot
def _mascots(panel) -> None:
    app, k = panel.app, panel.app.kit
    P = k.P
    tabs = tk.Frame(panel.content, bg=P["bg"])
    tabs.pack(fill="x", padx=(k.px(14), k.px(10)), pady=(k.px(2), k.px(8)))
    for c in CATS:
        on = c == app.settings_tab
        b = k.lbl(tabs, t("cat." + c), "meta_b", P["fg"] if on else P["mut"], cursor="hand2",
                  bg=P["hover"] if on else P["bg"], padx=k.px(8), pady=k.px(4))
        b.pack(side="left", padx=(0, k.px(4)))
        b.bind("<Button-1>", lambda e, c=c: app.set_settings_tab(c))
    items = [m for m in mascots.all_mascots() if app.settings_tab == "all" or m["cat"] == app.settings_tab]
    g = _group(panel, t("set.mascot"))
    _mascot_grid(panel, g, items, cols=5)
    _hues(panel, g)


# ---------------------------------------------------------------- banner cập nhật
def update_banner(panel, parent, kind: str, width=None) -> None:
    app, k = panel.app, panel.app.kit
    P = k.P
    u = app.update or {}
    v = u.get("version") or ""
    if kind == "latest":
        r = tk.Frame(parent, bg=parent["bg"])
        r.pack(fill="x")
        tk.Label(r, image=k.icon("check", 18, P["ok"], parent["bg"], 2.4), bg=parent["bg"]).pack(side="left")
        col = tk.Frame(r, bg=parent["bg"])
        col.pack(side="left", padx=(k.px(10), 0))
        k.lbl(col, t("upd.latest"), "body_x").pack(anchor="w")
        k.lbl(col, t("upd.checked", v=__version__, clock=fmt.clock(app.update_checked_at) if app.update_checked_at else "–"),
              "meta", P["mut"]).pack(anchor="w")
        return
    err = kind == "err"
    fill = P["dangerBg"] if err else P["runBg"]
    border = P["danger"] if err else P["upd"]
    width = width or panel.inner_w()
    outer, c = k.card(parent, fill, border, width=width, state="update" if kind == "avail" else None)
    outer.pack(fill="x")
    r = tk.Frame(c, bg=fill)
    r.pack(fill="x")
    icon = {"err": "info", "verify": "shield", "install": "refresh"}.get(kind, "dl")
    tk.Label(r, image=k.icon(icon, 18, P["danger"] if err else P["upd"], fill, 2.2), bg=fill).pack(side="left")
    col = tk.Frame(r, bg=fill)
    col.pack(side="left", fill="x", expand=True, padx=(k.px(10), 0))
    titles = {"avail": t("upd.avail", v=v), "mac": t("upd.avail", v=v), "dl": t("upd.dl", v=v), "verify": t("upd.verify"),
              "install": t("upd.install", v=v), "err": t("upd.err")}
    subs = {"avail": t("upd.using", v=__version__), "mac": t("upd.mac"), "verify": "SHA256 + Ed25519",
            "install": t("upd.reopen"), "err": u.get("apply_error") or "",
            "dl": f"{int((app.update_progress or 0) * 100)}%"}
    k.lbl(col, titles[kind], "body_x").pack(anchor="w")
    sub = k.lbl(col, k.ellipsis(subs[kind], "meta", width - k.px(150)), "meta", P["mut"], cursor="hand2")
    sub.pack(anchor="w")
    if kind in ("avail", "mac"):
        sub.bind("<Button-1>", lambda e: app.open_release_page())
        k.button(r, t("upd.download") if kind == "mac" else t("upd.update"), app.apply_update, P["upd"],
                 fg="#ffffff" if P["name"] == "light" else P["btnFg"]).pack(side="right")
    if kind == "dl":
        k.bar(c, (app.update_progress or 0) * 100, P["upd"], width - k.px(24), 6).pack(fill="x", pady=(k.px(8), 0))
    if kind in ("verify", "install"):
        k.bar(c, 40, P["upd"], width - k.px(24), 6).pack(fill="x", pady=(k.px(8), 0))
    if err:
        rb = tk.Frame(c, bg=fill)
        rb.pack(fill="x", pady=(k.px(8), 0))
        k.button(rb, t("upd.retry"), app.apply_update, P["danger"], fg="#ffffff").pack(side="left")
        k.button(rb, t("upd.manual"), app.open_release_page, outline=True, role="body").pack(side="left", padx=(k.px(8), 0))
