"""S7: nối Control room vào ui.app. Hàm thuần safe_log, find_live_session; helper nối dây gọi trên self giả;
mục popup trong menus. Không cần Tk display (phần dựng Tk thật tự bỏ qua khi không có display)."""
import queue
import sys
import time
import types
import unittest
from types import SimpleNamespace
from unittest import mock

# Import config/org trước stub tkinter: patch.dict gỡ mọi module import trong lúc stub khỏi sys.modules.
from pet_tracker import config, org  # noqa: F401

try:
    import tkinter  # noqa: F401
    from pet_tracker import i18n, theme
    from pet_tracker.ui import app as ui
    from pet_tracker.ui.menus import Menus
except ImportError:
    # Python không có _tkinter: ui chỉ dùng tk trong thân hàm nên stub đủ để import.
    with mock.patch.dict(sys.modules, tkinter=mock.MagicMock(), **{"tkinter.font": mock.MagicMock()}):
        from pet_tracker import i18n, theme
        from pet_tracker.ui import app as ui
        from pet_tracker.ui.menus import Menus


class _Stub:
    """self giả: thuộc tính chưa đặt trả Mock. Hàm của ui được gắn vào bằng _bind."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        m = mock.Mock()
        setattr(self, name, m)
        return m


def _bind(stub, *names):
    for n in names:
        setattr(stub, n, types.MethodType(getattr(ui.App, n), stub))
    return stub


def _live(sid, **extra):
    return {"session_id": sid, "name": f"s-{sid}", "pid": 1, **extra}


FONTS = {"meta": "F1", "body": "F2", "body_b": "F3", "title": "F4", "big": "F5"}


def _kit(scale=1.0):
    return SimpleNamespace(P=theme.DARK, f=dict(FONTS), S=scale)


def _panel(visible=False):
    return SimpleNamespace(visible=visible, hide=mock.Mock(), show=mock.Mock())


def _room_cls(cls, bg=None):
    """ControlRoom giả: th là dict thật (App so sánh màu nền khi mở lại)."""
    cls.return_value.th = {"bg": bg or theme.DARK["bg"]}
    return cls


class SafeLogTest(unittest.TestCase):
    def test_plain_ascii_unchanged(self):
        self.assertEqual(ui.safe_log("hello world"), "hello world")

    def test_control_and_escape_chars_are_escaped(self):
        out = ui.safe_log("a\nb\r\x1b[31mc\x00\x7f")
        self.assertTrue(all(32 <= ord(c) < 127 for c in out), repr(out))
        self.assertNotIn("\n", out)
        self.assertIn("\\n", out)

    def test_non_ascii_is_escaped(self):
        out = ui.safe_log("đang chạy")
        self.assertTrue(out.isascii(), out)
        self.assertIn("\\u0111", out)

    def test_capped_at_200_chars(self):
        self.assertEqual(len(ui.safe_log("x" * 500)), 200)
        self.assertEqual(len(ui.safe_log("\x01" * 300)), 200)

    def test_non_str_input(self):
        self.assertEqual(ui.safe_log(ValueError("boom")), "boom")
        self.assertEqual(ui.safe_log(None), "None")

    def test_quotes_do_not_leak_wrapper(self):
        self.assertEqual(ui.safe_log("it's"), "it's")


class FindLiveSessionTest(unittest.TestCase):
    def test_found_returns_same_live_dict(self):
        live = _live("s1")
        found = ui.find_live_session([_live("s0"), live], "s1")
        self.assertIs(found, live)

    def test_missing_returns_none(self):
        self.assertIsNone(ui.find_live_session([_live("s1")], "s2"))
        self.assertIsNone(ui.find_live_session([], "s1"))

    def test_wrong_type_returns_none(self):
        sessions = [_live("s1")]
        for bad in (None, 5, b"s1", ["s1"], {"s1": 1}):
            self.assertIsNone(ui.find_live_session(sessions, bad), repr(bad))

    def test_long_id_returns_none(self):
        sessions = [_live("x" * 65)]
        self.assertIsNone(ui.find_live_session(sessions, "x" * 65))
        self.assertIsNotNone(ui.find_live_session([_live("x" * 64)], "x" * 64))

    def test_duplicate_ids_return_none(self):
        # hai session cùng id là mơ hồ: không focus cái nào
        first, second = _live("d", name="first"), _live("d", name="second")
        self.assertIsNone(ui.find_live_session([first, second], "d"))
        self.assertIsNone(ui.find_live_session([first, _live("x"), second], "d"))

    def test_none_or_odd_sessions_return_none(self):
        self.assertIsNone(ui.find_live_session(None, "s1"))
        self.assertIsNone(ui.find_live_session({"session_id": "s1"}, "s1"))
        self.assertIsNone(ui.find_live_session("s1", "s1"))

    def test_skips_non_dict_entries(self):
        live = _live("s1")
        self.assertIs(ui.find_live_session([None, "s1", live], "s1"), live)


class FocusFromControlRoomTest(unittest.TestCase):
    def _stub(self, snap):
        stub = _bind(_Stub(), "_focus_from_control_room")
        stub.snap = snap
        stub.focus_session = mock.Mock()
        return stub

    def test_found_focuses_live_dict(self):
        live = _live("s1")
        stub = self._stub({"sessions": [live]})
        stub._focus_from_control_room("s1")
        stub.focus_session.assert_called_once()
        self.assertIs(stub.focus_session.call_args.args[0], live)

    def test_not_found_does_nothing(self):
        stub = self._stub({"sessions": [_live("s1")]})
        stub._focus_from_control_room("nope")
        stub.focus_session.assert_not_called()

    def test_bad_id_does_nothing(self):
        stub = self._stub({"sessions": [_live("s1")]})
        stub._focus_from_control_room(7)
        stub._focus_from_control_room("s" * 65)
        stub.focus_session.assert_not_called()

    def test_no_snapshot_does_nothing(self):
        for snap in (None, {}, {"sessions": None}):
            stub = self._stub(snap)
            stub._focus_from_control_room("s1")
            stub.focus_session.assert_not_called()


class RenderHelperTest(unittest.TestCase):
    def test_render_passes_snap(self):
        stub = _bind(_Stub(), "_render_control_room")
        stub.control_room = mock.Mock()
        stub.snap = {"sessions": []}
        stub._render_control_room()
        stub.control_room.render.assert_called_once_with({"sessions": []})

    def test_render_exception_is_swallowed_and_logged(self):
        stub = _bind(_Stub(), "_render_control_room")
        stub.control_room = mock.Mock()
        stub.control_room.render.side_effect = RuntimeError("bad\n\x1b")
        stub.snap = {}
        with mock.patch.object(ui, "log") as log:
            stub._render_control_room()
        log.assert_called_once()
        msg = log.call_args.args[0]
        self.assertIn("RuntimeError", msg)
        self.assertTrue(msg.isascii() and "\n" not in msg, msg)

    def test_render_without_control_room_is_noop(self):
        stub = _bind(_Stub(), "_render_control_room")
        stub.control_room = None
        stub.snap = {}
        stub._render_control_room()  # không ném lỗi


class CloseHelperTest(unittest.TestCase):
    def test_close_without_control_room_is_noop(self):
        stub = _bind(_Stub(), "_close_control_room")
        stub.control_room = None
        stub._close_control_room()

    def test_close_exception_is_swallowed(self):
        stub = _bind(_Stub(), "_close_control_room")
        stub.control_room = mock.Mock()
        stub.control_room.close.side_effect = RuntimeError("tk gone")
        with mock.patch.object(ui, "log") as log:
            stub._close_control_room()
        log.assert_called_once()

    def _quit_stub(self):
        stub = _bind(_Stub(), "quit", "_close_control_room")
        stub.collector = mock.Mock()
        stub.hook_server = mock.Mock()
        return stub

    def test_quit_tolerates_no_control_room_and_still_destroys(self):
        stub = self._quit_stub()
        stub.control_room = None
        ui.App.quit(stub)
        stub.root.destroy.assert_called_once()

    def test_quit_survives_close_failure_and_still_destroys(self):
        stub = self._quit_stub()
        stub.control_room = mock.Mock()
        stub.control_room.close.side_effect = RuntimeError("boom")
        with mock.patch.object(ui, "log"):
            ui.App.quit(stub)
        stub.control_room.close.assert_called_once()
        stub.root.destroy.assert_called_once()

    def test_quit_closes_room_before_destroy(self):
        stub = self._quit_stub()
        stub.control_room = mock.Mock()
        order = []
        stub.control_room.close.side_effect = lambda: order.append("close")
        stub.root.destroy.side_effect = lambda: order.append("destroy")
        ui.App.quit(stub)
        self.assertEqual(order, ["close", "destroy"])


class OpenControlRoomTest(unittest.TestCase):
    def _stub(self, snap=None, panel_visible=False):
        stub = _bind(_Stub(), "_open_control_room", "_control_room_theme", "_focus_from_control_room",
                     "_close_control_room")
        stub.control_room = None
        stub.kit = _kit()
        stub.state = {}
        stub.snap = snap
        stub.panel = _panel(panel_visible)
        stub.root = mock.Mock()
        stub.toast_info = mock.Mock()
        return stub

    def test_theme_has_all_keys_and_maps_palette(self):
        stub = self._stub()
        theme_ = stub._control_room_theme()
        for key in ("bg", "surface", "line", "fg", "fg2", "muted", "faint", "green", "yellow", "red",
                    "accent", "sel", "f_xs", "f_sm", "f_smb", "f_title", "f_big", "scale", "top"):
            self.assertIn(key, theme_)
        self.assertEqual(theme_["fg"], theme.DARK["fg"])
        self.assertEqual(theme_["muted"], theme.DARK["mut"])
        self.assertEqual(theme_["surface"], theme.DARK["surf"])
        self.assertEqual(theme_["f_big"], "F5")
        self.assertEqual(theme_["scale"], 1.0)

    def test_theme_follows_light_palette(self):
        stub = self._stub()
        stub.kit.P = theme.LIGHT
        theme_ = stub._control_room_theme()
        self.assertEqual(theme_["bg"], theme.LIGHT["bg"])
        self.assertEqual(theme_["fg"], theme.LIGHT["fg"])

    def test_lazy_create_once_and_show_each_time(self):
        stub = self._stub()
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            _room_cls(cls)
            ui.App._open_control_room(stub)
            ui.App._open_control_room(stub)
        cls.assert_called_once()
        self.assertEqual(cls.return_value.show.call_count, 2)

    def test_constructor_wiring(self):
        stub = self._stub()
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "save_state") as save:
            ui.App._open_control_room(stub)
        args, kwargs = cls.call_args
        self.assertIs(args[0], stub.root)
        self.assertIsInstance(args[1], dict)
        self.assertIs(args[2], stub.state)
        self.assertIs(args[3], save)
        self.assertEqual(args[4], stub._focus_from_control_room)
        self.assertIs(kwargs["log"], ui._control_room_log)

    def test_control_room_log_is_ascii_capped(self):
        with mock.patch.object(ui, "log") as log:
            ui._control_room_log("\x1b[31m" + "đ" * 400)
        out = log.call_args.args[0]
        self.assertTrue(out.isascii())
        self.assertLessEqual(len(out), 200)

    def test_show_failure_is_logged_not_raised(self):
        stub = self._stub()
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log") as log:
            cls.return_value.show.side_effect = RuntimeError("tcl")
            ui.App._open_control_room(stub)
        log.assert_called_once()

    def test_render_before_show_when_snapshot_present(self):
        stub = self._stub(snap={"sessions": []})
        order = []
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            cls.return_value.render.side_effect = lambda s: order.append(("render", s))
            cls.return_value.show.side_effect = lambda: order.append("show")
            ui.App._open_control_room(stub)
        self.assertEqual(order, [("render", {"sessions": []}), "show"])

    def test_no_render_without_snapshot(self):
        stub = self._stub(snap=None)
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            ui.App._open_control_room(stub)
        cls.return_value.render.assert_not_called()
        cls.return_value.show.assert_called_once()

    def test_visible_panel_hidden_before_show(self):
        stub = self._stub(snap=None, panel_visible=True)
        order = []
        stub.panel.hide = mock.Mock(side_effect=lambda: order.append("hide"))
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            cls.return_value.show.side_effect = lambda: order.append("show")
            ui.App._open_control_room(stub)
        self.assertEqual(order, ["hide", "show"])

    def test_hidden_panel_not_hidden_again(self):
        stub = self._stub(snap=None, panel_visible=False)
        with mock.patch("pet_tracker.control_room.ControlRoom"), mock.patch.object(ui, "log"):
            ui.App._open_control_room(stub)
        stub.panel.hide.assert_not_called()

    def test_show_false_closes_resets_and_flashes(self):
        stub = self._stub(snap=None)
        bad, good = mock.Mock(), mock.Mock()
        bad.th = good.th = {"bg": theme.DARK["bg"]}
        bad.show.return_value = False
        good.show.return_value = True
        with mock.patch("pet_tracker.control_room.ControlRoom", side_effect=[bad, good]) as cls, \
                mock.patch.object(ui, "log"):
            ui.App._open_control_room(stub)
            self.assertIsNone(stub.control_room)
            bad.close.assert_called_once()
            stub.toast_info.assert_called_once()
            self.assertIn("Control room", stub.toast_info.call_args.args[0])
            stub.panel.show.assert_called_once()    # thông báo chỉ thấy được khi panel mở
            ui.App._open_control_room(stub)        # lần sau dựng lại từ đầu
            stub.toast_info.assert_called_once()    # thành công thì không báo lỗi nữa
            stub.panel.show.assert_called_once()
        self.assertEqual(cls.call_count, 2)
        self.assertIs(stub.control_room, good)
        good.show.assert_called_once()

    def test_show_true_does_not_flash(self):
        stub = self._stub(snap=None)
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            cls.return_value.show.return_value = True
            ui.App._open_control_room(stub)
        stub.toast_info.assert_not_called()
        self.assertIs(stub.control_room, cls.return_value)

    def test_failed_render_is_closed_and_reset(self):
        stub = self._stub(snap={"sessions": []})
        bad = mock.Mock()
        bad.render.side_effect = RuntimeError("bad")
        with mock.patch("pet_tracker.control_room.ControlRoom", return_value=bad), \
                mock.patch.object(ui, "log"):
            ui.App._open_control_room(stub)
        bad.close.assert_called_once()
        bad.show.assert_not_called()
        self.assertIsNone(stub.control_room)

    def test_theme_change_recreates_room_on_next_open(self):
        stub = self._stub(snap=None)
        old = mock.Mock()
        old.th = {"bg": theme.DARK["bg"]}
        old.show.return_value = True
        stub.control_room = old
        stub.kit.P = theme.LIGHT
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            _room_cls(cls, bg=theme.LIGHT["bg"])
            ui.App._open_control_room(stub)
        old.close.assert_called_once()
        cls.assert_called_once()
        self.assertIs(stub.control_room, cls.return_value)


class PopupItemTest(unittest.TestCase):
    """Mục 'Control room' trong popup chuột phải của island và bóng (cùng một menu island_menu)."""

    def setUp(self):
        prev_lang = i18n.lang()
        self.addCleanup(i18n.set_lang, prev_lang)
        i18n.set_lang("vi")  # nhãn tiếng Việt cố định, không phụ thuộc máy hay test chạy trước

    def _menu(self, display):
        app = mock.Mock()
        app.prefs = {"display": display}
        app.mute_until = 0.0
        app.update = None
        app.kit = SimpleNamespace(P=theme.DARK, px=lambda v: int(v))
        m = Menus(app)
        m.opened_at = 0.0
        m._new = mock.Mock(return_value=(mock.Mock(), mock.Mock()))
        m._item = mock.Mock()
        m._sep = mock.Mock()
        m._pad = mock.Mock()
        m._finish = mock.Mock()
        return m, app

    def test_menu_has_control_room_item_in_both_modes(self):
        for display in ("island", "bubble"):
            with self.subTest(display=display):
                m, app = self._menu(display)
                m.island_menu(10, 10)
                rows = [c for c in m._item.call_args_list if c.args[2] == "Control room"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].args[3], "giám sát")

    def test_item_closes_popup_then_opens_room(self):
        m, app = self._menu("island")
        m.close = mock.Mock()
        m.island_menu(10, 10)
        row = [c for c in m._item.call_args_list if c.args[2] == "Control room"][0]
        row.kwargs["cmd"]()  # act(): đóng popup rồi mở room
        m.close.assert_called()
        app._open_control_room.assert_called_once()


class FocusSessionLogTest(unittest.TestCase):
    """dòng log của focus_session không bị giả mạo bằng xuống dòng trong pid hoặc thông báo."""

    def _stub(self):
        stub = _bind(_Stub(), "focus_session")
        stub.toast_info = mock.Mock()
        stub.panel = _panel()
        return stub

    def test_pid_repr_and_message_escaped(self):
        stub = self._stub()
        sess = {"name": "n", "pid": "7\nFORGED"}
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.return_value = (True, "ok\nFORGED line\x1b[0m đ")
            ui.App.focus_session(stub, sess)
        msg = log.call_args.args[0]
        self.assertNotIn("\n", msg)
        self.assertIn("pid='7\\nFORGED'", msg)
        self.assertTrue(msg.isascii(), msg)

    def test_name_and_pid_quoted_so_spaces_are_unambiguous(self):
        stub = self._stub()
        sess = {"name": "my work", "pid": 7}
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.return_value = (True, "ok")
            ui.App.focus_session(stub, sess)
        self.assertIn("focus session name='my work' pid='7': ok=True", log.call_args.args[0])

    def test_name_and_pid_capped(self):
        stub = self._stub()
        sess = {"name": "n" * 1000, "pid": "p" * 1000}
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.return_value = (True, "ok")
            ui.App.focus_session(stub, sess)
        msg = log.call_args.args[0]
        self.assertIn("n" * 200, msg)
        self.assertNotIn("n" * 201, msg)
        self.assertIn("p" * 200, msg)
        self.assertNotIn("p" * 201, msg)

    def test_exception_text_escaped_in_log(self):
        stub = self._stub()
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.side_effect = RuntimeError("bad\nline")
            ui.App.focus_session(stub, {"name": "n", "pid": 1})
        msg = log.call_args.args[0]
        self.assertNotIn("\n", msg)
        self.assertTrue(msg.isascii(), msg)
        self.assertIn("ok=False", msg)


class LangChangeTest(unittest.TestCase):
    def test_language_change_drops_room_so_labels_refresh(self):
        stub = _bind(_Stub(), "set_pref", "_close_control_room", "lang_code")
        stub.prefs = {"lang": "vi"}
        stub.state = {}
        stub.lang_code = mock.Mock(return_value="en")
        room = mock.Mock()
        room.win = None
        stub.control_room = room
        with mock.patch.object(ui, "save_state"), mock.patch.object(ui, "log"), \
                mock.patch.object(ui.i18n, "set_lang") as set_lang:
            ui.App.set_pref(stub, "lang", "en")
        set_lang.assert_called_once()
        room.close.assert_called_once()
        self.assertIsNone(stub.control_room)


class AgentFieldLogTest(unittest.TestCase):
    """F3: mọi trường do agent viết đi vào log qua safe_log (xuống dòng, ký tự không phải ASCII bị escape)."""

    HOSTILE = {"session_id": "s\nFORGED", "name": "n\nFORGED đ", "pid": "7\n", "cwd": "/a\nb đ"}

    def _ops_stub(self):
        stub = _bind(_Stub(), "run_op")
        stub.busy_sids = set()
        stub.toast_info = mock.Mock()
        stub.cfg = {"claude_dir": "/x"}
        stub.ops_done = queue.Queue()
        return stub

    def test_run_op_log_line_is_escaped(self):
        stub = self._ops_stub()
        sess = dict(self.HOSTILE)

        class SyncThread:
            def __init__(self, target, **kw):
                self.target = target

            def start(self):
                self.target()

        with mock.patch.object(ui.threading, "Thread", SyncThread), \
                mock.patch.object(ui.session_ops, "close_session", return_value=(True, "ok\nFORGED đ")), \
                mock.patch.object(ui, "log") as log:
            ui.App.run_op(stub, sess, "close")
        msg = log.call_args.args[0]
        self.assertNotIn("\n", msg)
        self.assertTrue(msg.isascii(), msg)
        self.assertIn("pid='7\\n'", msg)
        self.assertIn("cwd='/a\\nb \\u0111'", msg)

    def test_resume_log_line_is_escaped(self):
        stub = _bind(_Stub(), "resume_closed")
        stub.forget_closed = mock.Mock()
        stub.toast_info = mock.Mock()
        c = {"name": "n\nFORGED đ", "session_id": "s\nX", "cwd": "/tmp"}
        with mock.patch.object(ui.os.path, "isdir", return_value=True), \
                mock.patch.object(ui.plat, "open_terminal", return_value=(False, "bad\nline")), \
                mock.patch.object(ui, "log") as log:
            ui.App.resume_closed(stub, c)
        msg = log.call_args.args[0]
        self.assertNotIn("\n", msg)
        self.assertTrue(msg.isascii(), msg)


class ThemeContrastTest(unittest.TestCase):
    """R3: trạng thái của Control room tách màu rõ trong cả hai bảng màu và chữ đạt 4.5:1 trên nền cửa sổ."""

    def _th(self, P):
        stub = _bind(_Stub(), "_control_room_theme")
        stub.kit = _kit()
        stub.kit.P = P
        return stub._control_room_theme()

    def test_states_distinct_and_readable_in_both_palettes(self):
        for P in (theme.DARK, theme.LIGHT):
            with self.subTest(palette=P["name"]):
                th = self._th(P)
                states = {k: th[k] for k in ("green", "yellow", "red", "muted", "faint")}
                self.assertEqual(len(set(states.values())), len(states), states)
                self.assertEqual(th["green"], P["ok"])          # đang chạy: màu thành công của bảng màu
                for k, col in states.items():
                    self.assertGreaterEqual(theme.contrast(col, th["surface"]), 4.5, (k, col))


class ThemeChangeTest(unittest.TestCase):
    """R4: đổi giao diện (thủ công hoặc theo hệ thống) đóng Control room đang mở, như đổi ngôn ngữ."""

    def _stub(self):
        stub = _bind(_Stub(), "set_pref", "_close_control_room", "lang_code")
        stub.prefs = {"lang": "vi", "theme": "dark"}
        stub.state = {}
        stub._rebuild = mock.Mock()
        stub._refresh_views = mock.Mock()
        stub.kit = _kit()
        stub.kit.set_palette = mock.Mock()
        room = mock.Mock()
        room.win = None
        stub.control_room = room
        return stub, room

    def test_manual_theme_change_closes_room(self):
        stub, room = self._stub()
        with mock.patch.object(ui, "save_state"), mock.patch.object(ui, "log"), \
                mock.patch.object(ui.theme, "palette", return_value=theme.LIGHT):
            ui.App.set_pref(stub, "theme", "light")
        room.close.assert_called_once()
        self.assertIsNone(stub.control_room)

    def test_system_theme_switch_in_pump_closes_room(self):
        stub = _bind(_Stub(), "_pump", "_close_control_room")
        stub.update_dirty = stub.update_ready = stub._want_show = False
        stub.ops_done = queue.Queue()
        stub.q = queue.Queue()
        stub.snap = None
        stub.panel = _panel(visible=False)
        stub.menus = SimpleNamespace(sheet=None)
        stub.prefs = {"theme": "system"}
        stub._last_theme_check = 0.0
        stub._sys_theme = "dark"
        stub._theme_name = mock.Mock(return_value="light")
        stub._render_control_room = mock.Mock()
        room = mock.Mock()
        room.win = None
        stub.control_room = room
        with mock.patch.object(ui.plat, "system_theme", return_value="light"):
            ui.App._pump(stub)
        room.close.assert_called_once()
        self.assertIsNone(stub.control_room)


class PumpRenderTest(unittest.TestCase):
    """_pump gọi render khi có snapshot mới, kể cả lúc panel ẩn; không có snapshot mới thì không gọi."""

    def _stub(self):
        stub = _bind(_Stub(), "_pump")
        stub.update_dirty = False
        stub.update_ready = False
        stub._want_show = False
        stub.ops_done = queue.Queue()
        stub.q = queue.Queue()
        stub.snap = None
        stub.panel = _panel(visible=False)
        stub.menus = SimpleNamespace(sheet=None)
        stub.prefs = {"theme": "dark"}
        stub._last_theme_check = time.time()
        stub._render_control_room = mock.Mock()
        return stub

    def test_render_runs_on_new_snapshot_with_panel_hidden(self):
        stub = self._stub()
        snap = {"sessions": [], "org": None}
        stub.q.put(snap)
        ui.App._pump(stub)
        self.assertIs(stub.snap, snap)
        stub._render_control_room.assert_called_once_with()
        stub.panel.show.assert_not_called()

    def test_no_render_without_new_snapshot(self):
        stub = self._stub()
        ui.App._pump(stub)
        stub._render_control_room.assert_not_called()


if __name__ == "__main__":
    unittest.main()
