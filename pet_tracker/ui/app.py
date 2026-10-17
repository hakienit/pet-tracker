"""Wisp 0.2: điều phối. Thread collector (poll + hooks + quota + token trên máy) -> snapshot -> island / bóng nổi,
panel, thông báo và âm thanh. Tuỳ chọn người dùng ở state.json["prefs"] (config.load_prefs)."""
from __future__ import annotations

import base64
import os
import queue
import threading
import time
import tkinter as tk
import urllib.request

from .. import __version__, hooks, mascots, procenv, render, session_ops, sounds, theme, updater
from .. import i18n
from .. import platform as plat
from .. import states as S
from ..claude_data import ClaudeDataStore, account_info
from ..config import CONFIG_FILE, STATE_DIR, load_config, load_prefs, load_state, save_state
from ..i18n import t
from ..quota import fetch_api_usage, is_session_window
from ..quota_history import QuotaHistory
from ..usage_local import LocalUsage
from . import fmt, gfx
from .bubble import Bubble
from .island import Island
from .kit import Kit
from .menus import Menus
from .panel import Panel
from .toast import Toasts

LOG_FILE = STATE_DIR / "wisp.log"


def log(msg: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 1_000_000:
            LOG_FILE.write_text("", encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


# ================================================================ thread thu thập dữ liệu
class Collector(threading.Thread):
    def __init__(self, app, out: queue.Queue):
        super().__init__(daemon=True, name="collector")
        self.app = app
        self.cfg = app.cfg
        self.out = out
        self.store = ClaudeDataStore(self.cfg["claude_dir"])
        self.states = S.SessionStates()
        self.stop = threading.Event()
        self.kick = threading.Event()
        self.quota_kick = threading.Event()
        self.cmds: queue.Queue = queue.Queue()      # lệnh từ main thread (đã xem session…)
        self.events: queue.Queue | None = None      # sự kiện hooks (HookServer.events)
        self._git_cache: dict = {}
        self._git_stale: set = set()
        self._quota = None
        self._account = account_info(self.cfg["claude_dir"])
        self.history = QuotaHistory(STATE_DIR / "quota_history.jsonl")
        self.usage = LocalUsage(self.cfg["claude_dir"], STATE_DIR / "usage_daily.json")

    def refresh_now(self):
        self.quota_kick.set()
        self.kick.set()

    def start(self):
        super().start()
        threading.Thread(target=self._quota_loop, daemon=True, name="quota").start()
        threading.Thread(target=self._usage_loop, daemon=True, name="usage").start()

    def _usage_loop(self):
        while not self.stop.is_set():
            now = time.time()
            if self.usage.needs_build(now):
                try:
                    self.usage.build(now)
                    self.kick.set()
                except Exception as e:
                    log(f"usage build: {type(e).__name__}: {e}")
            self.stop.wait(600)

    def _quota_loop(self):
        fails = 0
        while not self.stop.is_set():
            interval = max(15.0, float(self.cfg["refresh_quota_sec"]))
            if not self.app.prefs.get("quota_api_enabled", True):
                self._quota = None
                self.quota_kick.wait(interval)
                self.quota_kick.clear()
                continue
            res = fetch_api_usage(self.cfg["claude_dir"])
            wait = interval
            if res.get("ok"):
                fails = 0
                now = time.time()
                self.history.add(res.get("windows"), now)
                self.history.annotate(res.get("windows"), now)
            else:
                fails += 1
                if res.get("status"):
                    wait = min(900.0, interval * 2 ** min(fails - 1, 4))
                    wait = max(wait, min(3600.0, float(res.get("retry_after") or 0)))
                log(f"quota: {res.get('error')} (lần {fails}, thử lại sau {wait:.0f}s)")
                prev = self._quota or {}
                if prev.get("windows") and time.time() - (prev.get("fetched_at") or 0) < 1800:
                    res = dict(prev, ok=True, stale_error=res.get("error"))
            self._quota = res
            self.kick.set()
            self.quota_kick.wait(wait)
            self.quota_kick.clear()

    def invalidate_git(self, cwd):
        self._git_stale.add(cwd)
        self.refresh_now()

    def _git_state(self, cwd, now):
        hit = self._git_cache.get(cwd)
        if hit is None or now - hit[0] > 30:
            hit = self._git_cache[cwd] = (now, session_ops.git_state(cwd))
        return hit[1]

    def run(self):
        while not self.stop.is_set():
            try:
                now = time.time()
                while True:  # sự kiện hooks và lệnh từ UI
                    try:
                        ev = self.events.get_nowait() if self.events else None
                    except queue.Empty:
                        ev = None
                    if ev is None:
                        break
                    self.states.apply(ev, now)
                while True:
                    try:
                        cmd, arg = self.cmds.get_nowait()
                    except queue.Empty:
                        break
                    if cmd == "seen":
                        self.states.mark_seen(arg, now)
                self.store.poll_all()
                sessions = self.store.active_sessions(self.cfg["context_windows"])
                while self._git_stale:
                    self._git_cache.pop(self._git_stale.pop(), None)
                for s in sessions:
                    s["git"] = self._git_state(s.get("cwd"), now)
                self.states.merge(sessions, now)
                self.out.put({
                    "ts": now, "sessions": sessions, "quota": self._quota, "account": self._account,
                    "usage": self.usage.totals(list(self.store.transcripts.values()), now),
                    "hooks_last": self.states.last_event,
                })
            except Exception as e:
                log(f"collector error: {type(e).__name__}: {e}")
                self.out.put({"ts": time.time(), "error": f"{type(e).__name__}: {e}"})
            self.kick.wait(float(self.cfg["refresh_sessions_sec"]))
            self.kick.clear()


# ================================================================ app
class App:
    def __init__(self):
        plat.init_process()
        self.cfg = load_config()
        self.state = load_state()
        self.prefs = load_prefs(self.state, self.cfg)
        i18n.set_lang(self.lang_code())
        self.q: queue.Queue = queue.Queue()
        self.ops_done: queue.Queue = queue.Queue()
        self.snap = None
        self.busy_sids: set = set()
        self.modal = False
        self.mute_until = 0.0
        self.settings_tab = "all"
        self._lbtn_prev = False
        self._want_show = False
        self._prev_states: dict | None = None
        self._quota_seen: dict = {}
        self._sys_theme = None
        self._last_theme_check = 0.0
        # cập nhật
        self.update = None
        self.update_dirty = False
        self.update_stage = None     # None | "dl" | "verify" | "install"
        self.update_progress = 0.0
        self.update_ready = False
        self._stage_dir = None
        self.update_checked_at = None
        self._update_kick = threading.Event()

        self.root = tk.Tk()
        self.root.withdraw()
        self.kit = Kit(self.root, plat.dpi_scale(self.root))
        self._apply_motion()
        self.kit.set_palette(theme.palette(self._theme_name()))
        self.menus = Menus(self)
        self.toasts = Toasts(self)
        self.island = Island(self)
        self.bubble = Bubble(self)
        self.panel = Panel(self)
        self._show_anchor()

        self.collector = Collector(self, self.q)
        self._start_hooks()
        self.collector.start()
        self._start_update_checker()
        self.root.bind_all("<MouseWheel>", lambda e: self.panel.wheel(e.delta, *plat.cursor_pos(self.root)))
        try:
            self.root.bind_all("<TouchpadScroll>", self._on_touchpad)
        except tk.TclError:
            pass
        log(f"start v{__version__} dpi={self.kit.S:.2f} lang={i18n.lang()} theme={self.kit.P['name']} "
            f"display={self.prefs['display']} hooks={self.hooks_status}")
        if self.cfg.get("config_error"):
            log(self.cfg["config_error"])
        self.root.after(200, self._pump)
        if plat.IS_MAC:
            self._poll_right_click()

    # ================================================================ tuỳ chọn
    def lang_code(self) -> str:
        p = self.prefs["lang"]
        return p if p in ("vi", "en") else plat.ui_language()

    def _theme_name(self) -> str:
        p = self.prefs["theme"]
        if p in ("dark", "light"):
            return p
        self._sys_theme = plat.system_theme()
        return self._sys_theme

    def _apply_motion(self) -> None:
        m = self.prefs["motion"]
        self.kit.anim.enabled = m == "on" or (m == "system" and not plat.reduce_motion())

    def set_pref(self, key: str, val) -> None:
        if self.prefs.get(key) == val:
            return
        self.prefs[key] = val
        self.state.setdefault("prefs", {})[key] = val
        save_state(self.state)
        log(f"pref {key}={val!r}")
        if key == "lang":
            i18n.set_lang(self.lang_code())
            self._rebuild()
        elif key == "theme":
            self.kit.set_palette(theme.palette(self._theme_name()))
            self._rebuild()
        elif key == "motion":
            self._apply_motion()
            self._rebuild()
        elif key == "display":
            self._show_anchor()
            self.panel.rebuild()
        elif key in ("quota_api_enabled",):
            self.collector.refresh_now()
        elif key == "update_check" and val:
            self._update_kick.set()
        self._refresh_views()

    def _rebuild(self) -> None:
        self.menus.close()
        self.toasts.clear()
        self.kit.anim.items.clear()
        self.island.reset()
        self.bubble.reset()
        self.panel.rebuild()
        self._refresh_views()

    def _refresh_views(self) -> None:
        self._draw_anchor()
        if self.panel.visible:
            self.panel.render()

    # ================================================================ island / bóng
    def _show_anchor(self) -> None:
        if self.prefs["display"] == "island":
            self.bubble.hide()
            self.island.show()
        else:
            self.island.hide()
            self.bubble.show()
        self._draw_anchor()

    def anchor(self) -> tuple:
        return (self.island if self.prefs["display"] == "island" else self.bubble).anchor()

    def quota_top(self):
        q = (self.snap or {}).get("quota") or {}
        if not (q.get("ok") and q.get("windows")):
            return None, None
        wins = [w for w in q["windows"] if w.get("active", True)] or q["windows"]
        return max(wins, key=lambda w: float(w["percent"])), wins

    def headline(self) -> str:
        top, _ = self.quota_top()
        return S.headline((self.snap or {}).get("sessions") or [], top["percent"] if top else None,
                          self.prefs["danger_percent"])

    def level_color(self, pct) -> str:
        return theme.level(pct, self.kit.P, self.prefs["warn_percent"], self.prefs["danger_percent"])

    def _anchor_view(self) -> dict:
        top, wins = self.quota_top()
        sessions = (self.snap or {}).get("sessions") or []
        c = S.counts(sessions)
        pct = float(top["percent"]) if top else None
        wait = next((s for s in sessions if s.get("state") == "wait"), None)
        bars = None
        if wins:
            five = next((w["percent"] for w in wins if is_session_window(w)), 0)
            week = next((w["percent"] for w in wins if not is_session_window(w)), 0)
            bars = (five, week)
        return {"pct": pct, "pct_col": self.level_color(pct), "counts": (c["wait"], c["run"], c["done"]),
                "state": self.headline(), "update": bool((self.update or {}).get("available")), "bars": bars,
                "wait_name": wait["name"] if wait else None}

    def _draw_anchor(self) -> None:
        v = self._anchor_view()
        if self.prefs["display"] == "island":
            self.island.update(v)
        else:
            self.bubble.update(v)

    def toggle_panel(self) -> None:
        if self.menus.sheet is not None:
            self.menus.close()
            return
        self.panel.toggle()

    def open_settings(self) -> None:
        if not self.panel.visible:
            self.panel.show()
        self.panel.go("settings")

    def toggle_lane(self, lane: str) -> None:
        cur = list(self.prefs["lanes_collapsed"])
        cur.remove(lane) if lane in cur else cur.append(lane)
        self.set_pref("lanes_collapsed", cur)

    def set_settings_tab(self, tab: str) -> None:
        self.settings_tab = tab
        self.panel.render()

    # ================================================================ mascot
    def _hue(self) -> float:
        hs = mascots.hues()
        return hs[self.prefs["hue"]] if 0 <= self.prefs["hue"] < len(hs) else 0

    def mascot_name(self) -> str:
        if self.prefs["mascot"] == "custom":
            return t("set.custom")
        m = mascots.get(self.prefs["mascot"])
        return (m or {}).get(i18n.lang(), "?")

    def mascot_photo(self, mood: str, size: float, bg):
        """Ảnh mascot đang chọn (hoặc ảnh riêng của người dùng) cỡ size (px logic) trên nền bg."""
        n = self.kit.px(size)
        custom = self.prefs.get("custom_image")
        if self.prefs["mascot"] == "custom" and custom:
            return self.kit.image(("custom", custom, n), lambda: _load_custom(custom, mascots.canvas_size(n)), bg)
        mid, P = self.prefs["mascot"], self.kit.P
        return self.kit.image(("mascot", mid, mood, n, self._hue()),
                              lambda: mascots.rows(mid, mood, n, P["name"], self._hue()), bg)

    def mascot_thumb(self, mid: str, size: float, bg):
        n = self.kit.px(size)
        return self.kit.image(("mthumb", mid, n, self._hue()), lambda: mascots.rows(mid, "run", n, self.kit.P["name"], self._hue()), bg)

    def signal_thumb(self, sid: str, size: float, bg):
        n, P = self.kit.px(size), self.kit.P
        return self.kit.image(("sthumb", sid, n), lambda: gfx.signal_rows(sid, 62, P["warn"], P, n), bg)

    def bubble_preview(self, state: str, size: float, bg):
        """Ảnh tĩnh của bóng hiện tại ở một trạng thái (trang Cài đặt → Bóng nổi)."""
        P, p = self.kit.P, self.prefs
        n = self.kit.px(size)
        if p["bubble_type"] == "mascot":
            mood = {"wait": "wait", "quota": "quota", "run": "run"}.get(state, "idle")
            return self.mascot_photo(mood, size * 0.8, bg)
        pct = 91 if state == "quota" else 12 if state == "idle" else 62
        col = self.level_color(pct)

        def rows():
            base = gfx.signal_rows(p["signal"], pct, col, P, n)
            a = gfx.Animated(self.root, base, gfx.shape_radius(p["signal"], n), self.kit.px(2.5), state, P, bg=bg, n=6)
            return base if not a.band else _apply_band(base, a, state, P)
        return self.kit.image(("bprev", p["signal"], state, n), rows, bg)

    def pick_custom_image(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.panel.win, filetypes=[("PNG / SVG", "*.png *.svg")])
        if not path:
            return
        self.prefs["custom_image"] = path
        self.state.setdefault("prefs", {})["custom_image"] = path
        self.set_pref("mascot", "custom")
        self.bubble.reset()
        self._refresh_views()

    # ================================================================ hooks
    def _start_hooks(self) -> None:
        tok = self.state.get("hook_token")
        if not tok:
            tok = self.state["hook_token"] = hooks.new_token()
            save_state(self.state)
        self.hook_url = hooks.hook_url(self.cfg["hook_port"], tok)
        self.hooks_error = None
        self.hook_server = hooks.HookServer(self.cfg["hook_port"], tok)
        if self.hook_server.start():
            self.collector.events = self.hook_server.events
            threading.Thread(target=self._hook_waker, daemon=True, name="hook-wake").start()
        else:
            self.hooks_error = self.hook_server.error
            log(f"hooks: {self.hooks_error}")
        self.hooks_status = hooks.status(self.cfg["claude_dir"], self.hook_url)
        if self.hooks_status == "stale" and self.state.get("hooks_enabled"):
            self._install_hooks(quiet=True)  # cổng / token đổi: sửa lại cho khớp

    def _hook_waker(self) -> None:
        """Có sự kiện thì đánh thức collector ngay (không chờ chu kỳ poll 3 giây)."""
        q = self.hook_server.events
        while not self.collector.stop.is_set():
            if q.qsize():
                self.collector.kick.set()
            time.sleep(0.15)

    def hooks_last_event(self):
        return (self.snap or {}).get("hooks_last") or None

    def hooks_prompt_needed(self) -> bool:
        return (not self.prefs["hooks_asked"] and self.hooks_status in ("off", "stale") and self.hooks_error is None)

    def _install_hooks(self, quiet=False) -> None:
        try:
            hooks.install(self.cfg["claude_dir"], self.hook_url)
            self.state["hooks_enabled"] = True
            save_state(self.state)
            if not quiet:
                self.toast_info(t("t.hooks_on"), kind="done")
        except hooks.HookConfigError as e:
            log(f"hooks install: {e}")
            self.toast_info(t("t.hooks_fail", err=e), kind="danger")
        self.hooks_status = hooks.status(self.cfg["claude_dir"], self.hook_url)

    def enable_hooks(self) -> None:
        self._install_hooks()
        self.set_pref("hooks_asked", True)
        self.panel.render(force=True)

    def dismiss_hooks_prompt(self) -> None:
        self.set_pref("hooks_asked", True)
        self.panel.render(force=True)

    def disable_hooks(self) -> None:
        try:
            hooks.uninstall(self.cfg["claude_dir"])
            self.state["hooks_enabled"] = False
            save_state(self.state)
            self.toast_info(t("t.hooks_off"))
        except hooks.HookConfigError as e:
            self.toast_info(t("t.hooks_fail", err=e), kind="danger")
        self.hooks_status = hooks.status(self.cfg["claude_dir"], self.hook_url)
        self.panel.render(force=True)

    def test_hooks(self) -> None:
        def work():
            try:
                ok = urllib.request.urlopen(self.hook_url + "/ping", timeout=3).status == 200
            except Exception:
                ok = False
            self.root.after(0, lambda: self.toast_info(t("t.hooks_test_ok") if ok else t("t.hooks_test_fail"),
                                                       kind="done" if ok else "danger"))
        threading.Thread(target=work, daemon=True).start()
        self.hooks_status = hooks.status(self.cfg["claude_dir"], self.hook_url)
        self.panel.render()

    # ================================================================ thông báo + âm thanh
    def toast_info(self, title: str, sub: str = "", kind: str = "info", ttl: float = 5.0) -> None:
        self.toasts.show(("info", time.time()), kind, title, sub, ttl=ttl)

    def _quiet_now(self) -> bool:
        if self.mute_until > time.time():
            return True
        if not self.prefs["quiet"]:
            return False
        now = time.strftime("%H:%M")
        a, b = self.prefs["quiet_from"], self.prefs["quiet_to"]
        return (a <= now or now < b) if a > b else (a <= now < b)

    def _sound(self, kind: str) -> None:
        if not self._quiet_now():
            sounds.play(kind)

    def toggle_mute(self) -> None:
        if self.mute_until > time.time():
            self.mute_until = 0.0
            self.toast_info(t("t.unmuted"))
        else:
            self.mute_until = time.time() + 3600
            self.toast_info(t("t.muted", clock=fmt.clock(self.mute_until)))

    def toggle_mute_session(self, sid) -> None:
        cur = list(self.prefs["muted"])
        cur.remove(sid) if sid in cur else cur.append(sid)
        self.set_pref("muted", cur)

    def _notify(self, snap: dict) -> None:
        sessions = snap.get("sessions") or []
        now_states = {s["session_id"]: s for s in sessions}
        prev = self._prev_states
        self._prev_states = {sid: s.get("state") for sid, s in now_states.items()}
        for key in [it["key"] for it in self.toasts.items if isinstance(it["key"], tuple) and it["key"][0] == "wait"]:
            if (now_states.get(key[1]) or {}).get("state") != "wait":
                self.toasts.dismiss(key)
        if prev is None:  # lần đầu: không báo những gì đã có sẵn
            self._quota_alerts(snap, first=True)
            return
        for sid, s in now_states.items():
            st, before = s.get("state"), prev.get(sid)
            if st == before or sid in self.prefs["muted"]:
                continue
            name = s.get("name") or "?"
            focus = lambda s=s: self.focus_session(s)  # noqa: E731
            if st == "wait":
                self._sound("wait")
                if not self.panel.visible:
                    title = t("t.wait_q", name=name) if s.get("wait_kind") == "question" else t("t.wait_perm", name=name)
                    sub = (f"{s.get('tool')}: " if s.get("tool") and s.get("wait_kind") == "permission" else "") + (s.get("detail") or "")
                    self.toasts.show(("wait", sid), "wait", title, sub, [(t("open"), focus, True), (t("t.later"), lambda: None, False)],
                                     ttl=None, mono=s.get("wait_kind") == "permission", on_click=focus)
            elif st == "done" and before in ("run", "wait") and self.prefs["notify_done"]:
                if self.prefs["sound_done"]:
                    self._sound("done")
                if not self.panel.visible:
                    self.toasts.show(("done", sid), "done", t("t.done", name=name), s.get("last_msg") or "",
                                     [(t("open"), focus, False)], ttl=6.0, on_click=focus)
            elif st == "error" and not self.panel.visible:
                self.toasts.show(("err", sid), "danger", t("t.error", name=name), s.get("detail") or "", ttl=8.0, on_click=focus)
        self._quota_alerts(snap)

    def _quota_alerts(self, snap: dict, first=False) -> None:
        q = snap.get("quota") or {}
        if not q.get("ok"):
            return
        for w in q.get("windows") or []:
            key = w["key"]
            pct = float(w["percent"])
            seen = self._quota_seen.setdefault(key, {"resets": w.get("resets_at"), "pct": pct, "said": set()})
            if w.get("resets_at") and seen["resets"] and abs(w["resets_at"] - seen["resets"]) > 300:
                if seen["pct"] >= 80 and pct < seen["pct"] and not first and self.prefs["quota_alerts"]:
                    self.toast_info(t("t.quota_reset", win=fmt.window_label(w)), kind="done")
                seen.update(resets=w["resets_at"], said=set())
            said = seen["said"]
            if not first and self.prefs["quota_alerts"]:
                for th in (80, 95):
                    if pct >= th > seen["pct"] and th not in said:
                        said.add(th)
                        self.toasts.show(("quota", key), "danger", t("t.quota_at", win=fmt.window_label(w), p=int(pct)), ttl=8.0)
                f = w.get("forecast")
                if f and f.get("before_reset") and "fc" not in said and pct >= 50:
                    said.add("fc")
                    self.toasts.show(("quota-fc", key), "danger", t("t.quota", win=fmt.window_label(w)),
                                     t("q.forecast", clock=fmt.clock(f["eta"]), left=fmt.left(w["resets_at"] - f["eta"])), ttl=8.0)
            else:
                said.update({th for th in (80, 95) if pct >= th})
            seen["pct"] = pct

    # ================================================================ thao tác session (giữ từ 0.1.7)
    def focus_session(self, sess: dict) -> None:
        try:
            ok, msg = plat.focus_session(sess)
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        log(f"focus session {sess.get('name')!r} pid={sess.get('pid')}: ok={ok} {msg}")
        self.collector.cmds.put(("seen", sess.get("session_id")))
        self.collector.kick.set()
        self.toasts.dismiss(("wait", sess.get("session_id")))
        if ok:
            self.panel.hide()
        else:
            self.toast_info(t("t.open_fail", err=msg), kind="danger")

    def run_op(self, sess: dict, op: str) -> None:
        name = sess.get("name") or "?"
        sid = sess.get("session_id")
        if sid in self.busy_sids:
            self.toast_info(t("t.op_busy", name=name), kind="danger")
            return
        self.busy_sids.add(sid)
        self.toast_info(t("t.op_handoff", name=name) if op == "handoff" else t("t.op_running", name=name), ttl=4)
        claude_dir = self.cfg["claude_dir"]

        def work():
            path = None
            try:
                ok, msg = True, ""
                if op == "handoff":
                    ok, msg = session_ops.write_handoff(sess, STATE_DIR / "handoffs")
                    path = msg if ok else None
                if ok:
                    ok, msg = session_ops.close_session(sess, claude_dir)
                    if ok and path:
                        msg = path
                if ok and op == "delete":
                    ok, msg = session_ops.delete_transcript(sess, claude_dir)
                elif ok and op == "worktree":
                    ok, msg = session_ops.remove_worktree(sess, claude_dir)
            except Exception as e:
                ok, msg = False, f"{type(e).__name__}: {e}"
            log(f"session op {op} {name!r} pid={sess.get('pid')} cwd={sess.get('cwd')!r}: ok={ok} {msg}")
            closed = None
            if ok and op in ("handoff", "close"):
                closed = {"session_id": sid, "name": name, "cwd": sess.get("cwd"),
                          "home_cwd": sess.get("home_cwd") or sess.get("cwd"), "closed_at": time.time(), "handoff": path}
            self.ops_done.put((sid, name, ok, msg, sess.get("cwd"), closed))

        threading.Thread(target=work, daemon=True, name=f"op-{op}").start()

    def closed_list(self) -> list:
        active = {s["session_id"] for s in (self.snap or {}).get("sessions") or []}
        return [c for c in self.state.get("closed_sessions") or [] if c.get("session_id") not in active]

    def forget_closed(self, sid) -> None:
        self.state["closed_sessions"] = [c for c in self.state.get("closed_sessions") or [] if c.get("session_id") != sid]
        save_state(self.state)
        self.panel.render()

    def resume_closed(self, c: dict) -> None:
        cwd = c.get("home_cwd") or c.get("cwd")
        if not cwd or not os.path.isdir(cwd):
            self.toast_info(t("t.resume_fail", name=c.get("name")), kind="danger")
            return
        try:
            ok, msg = plat.open_terminal(cwd, [session_ops.claude_command(), "--resume", c["session_id"]],
                                         f"resume: {(c.get('name') or '')[:40]}", procenv.clean_env())
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        log(f"resume {c.get('name')!r} sid={c.get('session_id')}: ok={ok} {msg}")
        if ok:
            self.forget_closed(c["session_id"])
        else:
            self.toast_info(f"{c.get('name')}: {msg}", kind="danger")

    def open_path(self, path) -> None:
        try:
            plat.open_path(path)
        except Exception as e:
            self.toast_info(f"{path}: {e}", kind="danger")

    def open_claude_dir(self) -> None:
        self.open_path(self.cfg["claude_dir"])

    def open_config(self) -> None:
        if not CONFIG_FILE.exists():
            try:
                CONFIG_FILE.write_text("{\n}\n", encoding="utf-8")
            except OSError:
                pass
        self.open_path(CONFIG_FILE)

    def open_log(self) -> None:
        self.open_path(LOG_FILE)

    def copy_text(self, text: str, done_msg: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text or "")
        self.toast_info(done_msg, kind="done", ttl=3)

    def refresh(self) -> None:
        self.collector.refresh_now()

    def tier_text(self, tier) -> str:
        if not tier:
            return ""
        x = tier.replace("default_", "").replace("claude_", "")
        return ("Max " + x[4:]) if x.startswith("max_") else x.replace("_", " ").title()

    # ================================================================ khởi động cùng máy
    def autostart_on(self) -> bool:
        try:
            return plat.autostart_is_enabled()
        except Exception:
            return False

    def toggle_autostart(self) -> None:
        try:
            if plat.autostart_is_enabled():
                plat.autostart_disable()
                msg = t("t.autostart_off")
            else:
                plat.autostart_enable()
                msg = t("t.autostart_on")
            self.toast_info(msg, kind="done")
        except Exception as e:
            log(f"autostart toggle failed: {e}")
            self.toast_info(t("t.autostart_fail", err=e), kind="danger")
        self.panel.render()

    # ================================================================ cập nhật (GitHub Releases)
    def _start_update_checker(self) -> None:
        api = self.cfg.get("update_api_url") or updater.API_LATEST

        def loop():
            self._update_kick.wait(8)
            while not self.collector.stop.is_set():
                manual = self._update_kick.is_set()
                self._update_kick.clear()
                if manual or self.prefs["update_check"]:
                    try:
                        info = updater.check(api)
                    except Exception as e:
                        info = {"ok": False, "available": False, "error": f"{type(e).__name__}: {e}"}
                    prev = self.update or {}
                    if prev.get("apply_error") and prev.get("version") == info.get("version"):
                        info["apply_error"] = prev["apply_error"]
                    info["manual"] = manual
                    self.update = info
                    if info.get("ok"):
                        self.update_checked_at = time.time()
                    self.update_dirty = True
                    log(f"update check: ok={info.get('ok')} available={info.get('available')} latest={info.get('tag')} "
                        f"err={info.get('error')}")
                hours = max(1.0, float(self.cfg.get("update_interval_hours") or 24))
                self._update_kick.wait(hours * 3600)

        threading.Thread(target=loop, daemon=True, name="update-check").start()

    def check_update_now(self) -> None:
        self.toast_info(t("upd.checking"), ttl=3)
        self._update_kick.set()

    def update_sig(self):
        u = self.update or {}
        return (u.get("version"), u.get("available"), u.get("apply_error"), self.update_stage,
                round(self.update_progress, 2) if self.update_stage == "dl" else None, self.update_checked_at)

    def update_banner_kind(self):
        u = self.update or {}
        if self.update_stage:
            return self.update_stage
        if u.get("apply_error"):
            return "err"
        if u.get("available"):
            return "avail" if updater.can_self_update() or not plat.IS_MAC else "mac"
        return None

    def open_release_page(self) -> None:
        self.open_path((self.update or {}).get("html_url") or updater.RELEASES_PAGE)

    def apply_update(self) -> None:
        u = self.update or {}
        if not u.get("available") or self.update_stage:
            return
        if not updater.can_self_update():
            self.open_release_page()
            self.toast_info(t("t.release_opened"))
            return
        u.pop("apply_error", None)
        self.update_stage, self.update_progress = "dl", 0.0
        self.update_dirty = True
        log(f"update: downloading {u.get('tag')}")

        def progress(f):
            self.update_progress = f
            if f >= 1.0:
                self.update_stage = "verify"
            self.update_dirty = True

        def work():
            try:
                self._stage_dir = updater.download_and_stage(u, progress=progress)
            except Exception as e:
                log(f"update: download failed: {e}")
                u["apply_error"] = str(e)
                self.update_stage = None
                self.update_dirty = True
                return
            self.update_stage = "install"
            self.update_dirty = True
            self.update_ready = True

        threading.Thread(target=work, daemon=True, name="update-download").start()

    def _finish_update(self) -> None:
        u = self.update or {}
        try:
            updater.launch_swap(self._stage_dir, updater.install_dir(), os.getpid(), env=procenv.clean_env())
        except Exception as e:
            log(f"update: launch swap failed: {e}")
            u["apply_error"] = str(e)
            self.update_stage = None
            self.update_dirty = True
            return
        log(f"update: installing {u.get('tag')} into {updater.install_dir()}, quitting")
        self.toast_info(t("t.installing"), kind="upd", ttl=10)
        self.root.after(400, self.quit)

    def _on_update_state(self) -> None:
        u = self.update or {}
        self._draw_anchor()
        if self.panel.visible:
            self.panel.render()
        if u.pop("manual", False):
            if u.get("available"):
                self.toast_info(t("t.update_found", v=u.get("version")), kind="upd")
                if not self.panel.visible:
                    self.panel.show()
            elif u.get("ok"):
                self.toast_info(t("t.latest", v=__version__), kind="done")
            else:
                self.toast_info(t("upd.check_fail", err=u.get("error")), kind="danger", ttl=8)

    # ================================================================ vòng lặp
    def request_show(self) -> None:
        self._want_show = True

    @staticmethod
    def float_top(win) -> None:
        """macOS: -topmost đặt lúc cửa sổ chưa dựng không có tác dụng (popup nằm dưới panel); đặt lại rồi nâng
        NSWindow lên trên bóng / island (level 25, xem plat.make_transparent)."""
        if not plat.IS_MAC:
            return
        win.attributes("-topmost", False)
        win.attributes("-topmost", True)
        win.lift()
        plat.set_level(win, 26)

    def _poll_right_click(self, prev: bool = False) -> None:
        """macOS: khi Wisp không phải app đang active, Tk nuốt cú chuột phải đầu tiên (chỉ để kích hoạt app).
        Đọc nút phải toàn cục và mở menu nếu con trỏ đang trên card session, island hoặc bóng."""
        down = plat.mouse_down(1)
        if down and not prev:
            x, y = plat.cursor_pos(self.root)
            sess = self._session_at(x, y) if self.panel.visible and self.menus.sheet is None else None
            anchor = self.island.win if self.prefs["display"] == "island" else self.bubble.win
            if sess is not None:
                self.menus.session_menu(sess, x, y)
            elif self.inside(anchor, x, y):
                self.menus.island_menu(x, y)
        self.root.after(50, self._poll_right_click, down)

    def _session_at(self, x: int, y: int):
        """Session của card nằm dưới (x, y) trong panel, hoặc None."""
        try:
            w = self.panel.win.winfo_containing(x, y)
        except (tk.TclError, KeyError):
            return None
        while w is not None:
            if hasattr(w, "_sess"):
                return w._sess
            w = w.master
        return None

    def mouse_reset(self) -> None:
        self._lbtn_prev = plat.mouse_down() if plat.GLOBAL_MOUSE else False

    @staticmethod
    def inside(win, x: int, y: int) -> bool:
        try:
            wx, wy = win.winfo_rootx(), win.winfo_rooty()
            return wx <= x <= wx + win.winfo_width() and wy <= y <= wy + win.winfo_height()
        except tk.TclError:
            return False

    def focus_for_dismiss(self, win) -> None:
        """macOS (không đọc được chuột toàn cục): đóng panel / menu khi app mất focus."""
        try:
            win.focus_force()
        except tk.TclError:
            pass
        if getattr(win, "_dismiss_bound", False):
            return
        win._dismiss_bound = True

        def check():
            try:
                focused = self.root.focus_get()
            except Exception:
                focused = None
            if self.modal or self.panel.resize:
                return
            if focused is not None:
                if self.menus.sheet is not None and focused.winfo_toplevel() is not self.menus.sheet:
                    self.menus.close()
                return
            if self.menus.sheet is not None:
                self.menus.close()
            elif self.panel.visible:
                self.panel.hide()

        win.bind("<FocusOut>", lambda e: self.root.after(150, check), add="+")

    def _on_touchpad(self, e) -> None:
        dy = int(e.delta) & 0xFFFF
        if dy >= 0x8000:
            dy -= 0x10000
        self.panel.wheel(dy, *plat.cursor_pos(self.root))

    def _pump(self) -> None:
        if self.update_dirty:
            self.update_dirty = False
            self._on_update_state()
        if self.update_ready:
            self.update_ready = False
            self._finish_update()
        if self._want_show:
            self._want_show = False
            if not self.panel.visible:
                self.panel.show()
            self.toast_info(t("t.running"), ttl=3)
        try:
            while True:
                sid, name, ok, msg, cwd, closed = self.ops_done.get_nowait()
                self.busy_sids.discard(sid)
                self.toast_info(t("t.op_ok", name=name) if ok else t("t.op_fail", name=name), msg, kind="done" if ok else "danger",
                                ttl=6 if ok else 10)
                if closed:
                    rest = [c for c in self.state.get("closed_sessions") or [] if c.get("session_id") != closed["session_id"]]
                    self.state["closed_sessions"] = [closed] + rest[:9]
                    save_state(self.state)
                self.collector.invalidate_git(cwd)
        except queue.Empty:
            pass
        got = None
        try:
            while True:
                got = self.q.get_nowait()
        except queue.Empty:
            pass
        if got is not None:
            self.snap = got
            self._notify(got)
            self._draw_anchor()
            if self.panel.visible:
                self.panel.render()
        now = time.time()
        if self.prefs["theme"] == "system" and now - self._last_theme_check > 10:
            self._last_theme_check = now
            if plat.system_theme() != self._sys_theme:
                self.kit.set_palette(theme.palette(self._theme_name()))
                self._rebuild()
        self.toasts.tick()
        if self.menus.sheet is not None:
            down = plat.mouse_down() if plat.GLOBAL_MOUSE else False
            if down and not self._lbtn_prev:
                x, y = plat.cursor_pos(self.root)
                if not self.inside(self.menus.sheet, x, y):
                    self.menus.close()
                    self._lbtn_prev = True
                    self.root.after(60, self._pump)
                    return
            self._lbtn_prev = down
        elif self.panel.visible:
            down = plat.mouse_down() if plat.GLOBAL_MOUSE else False
            if down and not self._lbtn_prev and not self.modal:
                x, y = plat.cursor_pos(self.root)
                anchor = self.island.win if self.prefs["display"] == "island" else self.bubble.win
                toast_hit = any(self.inside(it["win"], x, y) for it in self.toasts.items)
                if not (self.inside(self.panel.win, x, y) or self.inside(anchor, x, y) or toast_hit):
                    self.panel.hide()
            self._lbtn_prev = down
        self.root.after(60 if self.panel.visible or self.menus.sheet else 250, self._pump)

    def quit(self) -> None:
        self.collector.stop.set()
        self.collector.kick.set()
        try:
            self.hook_server.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def mainloop(self) -> None:
        self.root.report_callback_exception = lambda et, ev, tb: log(
            f"tk error: {et.__name__}: {ev} @ {__import__('traceback').format_tb(tb)[-1].strip()}")
        self.root.mainloop()


def _apply_band(base, a, state, P):
    """Khung giữa của viền động trộn vào ảnh tĩnh (ảnh xem trước trong Cài đặt)."""
    rows = [list(r) for r in base]
    c1, c2, c3, _ = P["ab"][state]
    c1, c2, c3 = render.hex2rgb(c1), render.hex2rgb(c2), render.hex2rgb(c3)
    for x, y, c, ang in a.band:
        col = gfx._conic(c1, c2, c3, ang)
        br, bg, bb, ba = rows[y][x]
        rows[y][x] = (int(br + (col[0] - br) * c), int(bg + (col[1] - bg) * c), int(bb + (col[2] - bb) * c), max(ba, int(255 * c)))
    return rows


def _load_custom(path: str, n: int) -> list:
    """Ảnh riêng của người dùng -> RGBA n x n. SVG: vẽ bằng vector.py (đủ cho hình đơn giản). PNG: thu nhỏ trung bình."""
    from .. import vector
    try:
        if path.lower().endswith(".svg"):
            import re
            src = open(path, encoding="utf-8").read()
            vb = re.search(r'viewBox="([^"]+)"', src)
            x0, y0, w, h = (float(v) for v in vb.group(1).replace(",", " ").split()) if vb else (0, 0, 64, 64)
            k = n / max(w, h)
            return vector.rasterize(vector.parse(src), n, n, vector.affine(scale=k, tx=-x0 * k, ty=-y0 * k))
        img = tk.PhotoImage(file=path)
        w, h = img.width(), img.height()
        step = max(1, int(max(w, h) / n))
        out = []
        for y in range(n):
            row = []
            for x in range(n):
                sx, sy = int(x * max(w, h) / n), int(y * max(w, h) / n)
                if sx >= w or sy >= h:
                    row.append((0, 0, 0, 0))
                    continue
                r, g, b = img.get(sx, sy)
                a = 0 if img.transparency_get(sx, sy) else 255
                row.append((r, g, b, a))
            out.append(row)
        del step
        return out
    except Exception as e:
        log(f"custom mascot {path}: {e}")
        return mascots.rows("m01", "run", int(n / (1 + 2 * mascots.PAD)))


def run(instance=None) -> None:
    app = App()
    if instance is not None:
        instance.listen(app.request_show)
    try:
        plat.autostart_refresh()
    except Exception as e:
        log(f"autostart refresh failed: {e}")
    if plat.IS_WINDOWS:
        from ..platform.win_single import legacy_running
        if legacy_running():
            log("legacy pet-tracker is still running")
            app.root.after(1500, lambda: app.toast_info(t("t.legacy"), kind="danger", ttl=20))
    app.mainloop()


__all__ = ["run", "App", "base64"]
