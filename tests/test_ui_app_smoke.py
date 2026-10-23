"""Smoke Tk headless cho App thật: dựng App (không mainloop; hook, kiểm tra cập nhật, collector và cửa sổ neo bị
chặn), dựng card có worker running + stuck, cập nhật tại chỗ, mở / render / đóng Control room.

Bỏ qua khi không có Tk display. Không ghi state, không ghi log, không đụng mạng: save_state và log bị thay."""
import sys
import time
import unittest
from unittest import mock

from pet_tracker import org  # noqa: F401  (import trước stub tkinter, như các test khác)

try:
    # Không tạo Tk root lúc import: root đầu tiên của process chốt danh sách font, test_mac_session cần Archivo.
    import tkinter as real_tk
    import _tkinter  # noqa: F401
    from pet_tracker import theme
    from pet_tracker import control_room as cr
    from pet_tracker import i18n
    from pet_tracker.ui import app as ui
    from pet_tracker.ui.kit import register_fonts
    HAVE_TK = True
except Exception:  # thiếu _tkinter
    HAVE_TK = False

NOW = time.time()


def worker(kind, wid, state):
    """Worker thô như claude_data đưa vào org: running (mtime mới) hoặc stuck (im quá stuck_after_sec)."""
    quiet = NOW - (500 if state == "stuck" else 10)
    w = {"kind": kind, "id": wid, "tool_use_id": "tu-" + wid, "mtime": quiet, "started": NOW - 100,
         "last_activity": quiet, "tokens": 5, "open_tools": 0, "agent_calls": []}
    if kind == "subagent":
        w.update(agent_type="les-engineering", description="desc " + wid, depth=1, finished=False, notif_status=None)
    return w


def _no_hooks(app):
    """Thay _start_hooks: không mở cổng hook, trạng thái hooks tắt."""
    app.hooks_status, app.hooks_error, app.hook_server = "off", None, None


def session(workers):
    return {"session_id": "s1", "name": "work", "cwd": "/w/proj", "status": "busy", "state": "run",
            "wait_kind": None, "has_transcript": True, "model": "claude-opus-4", "effort": None,
            "git_branch": "main", "entrypoint": "cli", "started_at": NOW - 100, "last_activity": NOW - 5,
            "state_since": NOW - 5, "context_tokens": 10, "context_limit": 100, "context_pct": 10.0,
            "totals": {"input": 1, "output": 2, "cache_create": 0, "cache_read": 0, "messages": 3},
            "subagents": sum(1 for w in workers if w["kind"] == "subagent"), "todo": None, "detail": "",
            "tool": "", "last_msg": "", "git": {"top": "/w/proj", "common": "/w/proj/.git", "branch": "main",
                                                 "dirty": 0, "done": False, "upstream": None, "ahead": 0,
                                                 "linked": False, "ignored": []},
            "workers": workers, "agent_calls": []}


def snapshot(workers):
    sessions = [session(workers)]
    cfg = {"agent_prefixes": ["les-"], "stuck_after_sec": 120}
    return {"ts": NOW, "sessions": sessions, "org": org.build(sessions, cfg, NOW), "quota": {}, "account": {},
            "usage": {}}


@unittest.skipUnless(HAVE_TK, "không có Tk/display")
class AppSmokeTest(unittest.TestCase):
    def setUp(self):
        prev_lang = i18n.lang()
        self.addCleanup(i18n.set_lang, prev_lang)  # App() đặt ngôn ngữ theo máy; trả lại cho test khác
        patches = [
            mock.patch.object(ui.plat, "init_process"),
            mock.patch.object(ui.App, "_start_hooks", _no_hooks),
            mock.patch.object(ui.App, "_start_update_checker"),
            mock.patch.object(ui.App, "_show_anchor"),
            mock.patch.object(ui.App, "_poll_right_click"),
            mock.patch.object(ui.Collector, "start"),
            mock.patch.object(ui, "log"),
            mock.patch.object(ui, "save_state"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        register_fonts()  # Archivo trước root đầu tiên: Tk chốt danh sách font lúc đó (R1)
        try:
            self.app = ui.App()
        except real_tk.TclError as e:  # không có display
            self.skipTest(f"không có Tk display: {e}")
        self.addCleanup(self._teardown)
        self.app.root.withdraw()
        self.app.toast_info = mock.Mock()   # không dựng cửa sổ thông báo thật

    def _teardown(self):
        try:
            self.app._close_control_room()
        finally:
            self.app.root.destroy()

    def card(self, sid="s1"):
        return self.app.panel.cards[sid][0]

    def test_card_badge_patches_in_place_with_running_and_stuck(self):
        app, P = self.app, self.app.kit.P
        app.snap = snapshot([worker("subagent", "a", "running"), worker("subagent", "b", "stuck"),
                             worker("bgtask", "t", "running")])
        app.panel.render(force=True)
        refs = self.card()
        self.assertEqual(refs["workers"].cget("text"), "2 agents · 1 task")
        self.assertEqual(refs["workers"].cget("fg"), P["warn"])

        built = app.panel.cards["s1"][0]
        app.snap = snapshot([worker("subagent", "a", "running")])
        app.panel.render()
        self.assertIs(self.card(), built)            # chỉ số đổi: vẫn cùng card, sửa chữ tại chỗ
        self.assertEqual(refs["workers"].cget("text"), "1 agent")
        self.assertEqual(refs["workers"].cget("fg"), P["mut"])

    def test_open_render_close_control_room(self):
        app = self.app
        app.snap = snapshot([worker("subagent", "a", "running"), worker("subagent", "b", "stuck")])
        app.panel.render(force=True)
        app._open_control_room()
        room = app.control_room
        self.assertIsNotNone(room)
        self.assertIsNotNone(room.win)
        rows = room.tree.get_children("")
        self.assertTrue(rows)
        app.snap = snapshot([worker("subagent", "a", "running")])
        app._render_control_room()
        self.assertIs(room._org, app.snap["org"])
        app._close_control_room()
        self.assertIsNone(room.win)
        self.assertIsNotNone(app.control_room)       # lần mở sau dùng lại đối tượng, dựng lại cửa sổ

    def test_control_room_theme_follows_app_palette(self):
        app = self.app
        self.assertEqual(app._control_room_theme()["bg"], app.kit.P["bg"])
        app.kit.set_palette(theme.LIGHT)
        self.assertEqual(app._control_room_theme()["bg"], theme.LIGHT["bg"])
        app.kit.set_palette(theme.DARK)

    def test_real_build_failure_flashes_and_retry_builds(self):
        app = self.app
        app.snap = {"sessions": [], "org": None}
        app.panel.show = mock.Mock()
        with mock.patch.object(cr.ControlRoom, "_style", side_effect=cr.tk.TclError("forced")):
            app._open_control_room()
        self.assertIsNone(app.control_room)
        app.toast_info.assert_called_once()
        self.assertIn("Control room", app.toast_info.call_args.args[0])
        app.panel.show.assert_called_once()
        app._open_control_room()
        room = app.control_room
        self.assertIsNotNone(room)
        self.assertIsNotNone(room.tree)                 # org None: cây rỗng, cửa sổ và cây đã dựng thật
        self.assertTrue(room.win.winfo_exists())
        app.toast_info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
