"""S7: nối Control room vào ui. Hàm thuần safe_log, find_live_session; helper nối dây gọi trên self giả. Không cần Tk display."""
import queue
import sys
import types
import unittest
from unittest import mock

# Import config/org trước stub tkinter: patch.dict gỡ mọi module import trong lúc stub khỏi sys.modules.
from pet_tracker import config, org  # noqa: F401

try:
    import tkinter  # noqa: F401
    from pet_tracker import ui
except ImportError:
    # Python không có _tkinter: ui.py chỉ dùng tk trong thân hàm nên stub đủ để import.
    with mock.patch.dict(sys.modules, tkinter=mock.MagicMock(), **{"tkinter.font": mock.MagicMock()}):
        from pet_tracker import ui


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
        setattr(stub, n, types.MethodType(getattr(ui.PetApp, n), stub))
    return stub


def _live(sid, **extra):
    return {"session_id": sid, "name": f"s-{sid}", "pid": 1, **extra}


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

    def test_duplicate_ids_return_first_live_match(self):
        first, second = _live("d", name="first"), _live("d", name="second")
        self.assertIs(ui.find_live_session([first, second], "d"), first)

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
        stub._focus_session = mock.Mock()
        return stub

    def test_found_focuses_live_dict(self):
        live = _live("s1")
        stub = self._stub({"sessions": [live]})
        stub._focus_from_control_room("s1")
        stub._focus_session.assert_called_once()
        self.assertIs(stub._focus_session.call_args.args[0], live)

    def test_not_found_does_nothing(self):
        stub = self._stub({"sessions": [_live("s1")]})
        stub._focus_from_control_room("nope")
        stub._focus_session.assert_not_called()

    def test_bad_id_does_nothing(self):
        stub = self._stub({"sessions": [_live("s1")]})
        stub._focus_from_control_room(7)
        stub._focus_from_control_room("s" * 65)
        stub._focus_session.assert_not_called()

    def test_no_snapshot_does_nothing(self):
        for snap in (None, {}, {"sessions": None}):
            stub = self._stub(snap)
            stub._focus_from_control_room("s1")
            stub._focus_session.assert_not_called()


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

    def test_quit_tolerates_no_control_room_and_still_destroys(self):
        stub = _bind(_Stub(), "quit", "_close_control_room")
        stub.control_room = None
        ui.PetApp.quit(stub)
        stub.root.destroy.assert_called_once()

    def test_quit_survives_close_failure_and_still_destroys(self):
        stub = _bind(_Stub(), "quit", "_close_control_room")
        stub.control_room = mock.Mock()
        stub.control_room.close.side_effect = RuntimeError("boom")
        with mock.patch.object(ui, "log"):
            ui.PetApp.quit(stub)
        stub.control_room.close.assert_called_once()
        stub.root.destroy.assert_called_once()

    def test_quit_closes_room_before_destroy(self):
        stub = _bind(_Stub(), "quit", "_close_control_room")
        stub.control_room = mock.Mock()
        order = []
        stub.control_room.close.side_effect = lambda: order.append("close")
        stub.root.destroy.side_effect = lambda: order.append("destroy")
        ui.PetApp.quit(stub)
        self.assertEqual(order, ["close", "destroy"])


class OpenControlRoomTest(unittest.TestCase):
    def _stub(self):
        stub = _bind(_Stub(), "_open_control_room", "_control_room_theme", "_focus_from_control_room")
        stub.control_room = None
        stub.f_xs, stub.f_sm, stub.f_smb, stub.f_title, stub.f_big = "F1", "F2", "F3", "F4", "F5"
        stub.S = 1.5
        stub.state = {}
        stub.snap = None
        return stub

    def test_theme_has_all_keys_from_constants(self):
        theme = self._stub()._control_room_theme()
        for key in ("bg", "surface", "line", "fg", "fg2", "muted", "faint", "green", "yellow", "red",
                    "accent", "sel", "f_xs", "f_sm", "f_smb", "f_title", "f_big", "scale", "top"):
            self.assertIn(key, theme)
        self.assertEqual(theme["fg"], ui.FG)
        self.assertEqual(theme["f_big"], "F5")
        self.assertEqual(theme["scale"], 1.5)

    def test_lazy_create_once_and_show_each_time(self):
        stub = self._stub()
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            ui.PetApp._open_control_room(stub)
            ui.PetApp._open_control_room(stub)
        cls.assert_called_once()
        self.assertEqual(cls.return_value.show.call_count, 2)

    def test_constructor_wiring(self):
        stub = self._stub()
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls:
            ui.PetApp._open_control_room(stub)
        args, kwargs = cls.call_args
        self.assertIs(args[0], stub.root)
        self.assertIsInstance(args[1], dict)
        self.assertIs(args[2], stub.state)
        self.assertIs(args[3], ui.save_state)
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
            ui.PetApp._open_control_room(stub)
        log.assert_called_once()


class PopupItemTest(unittest.TestCase):
    def test_menu_has_control_room_item_that_opens_room(self):
        stub = _bind(_Stub(), "_bubble_menu", "_open_control_room")
        stub.S = 1.0
        stub._update = None
        stub.island = True
        stub._new_sheet = mock.Mock(return_value=(mock.Mock(), mock.Mock()))
        stub._sheet_row = mock.Mock()
        stub._close_sheet = mock.Mock()
        stub.control_room = None
        with mock.patch.object(ui, "tk"), mock.patch.object(ui, "plat") as plat, \
                mock.patch("pet_tracker.control_room.ControlRoom") as cls:
            plat.autostart_is_enabled.return_value = False
            ui.PetApp._bubble_menu(stub, 10, 10)
            rows = [c for c in stub._sheet_row.call_args_list if c.args[2] == "Control room"]
            self.assertEqual(len(rows), 1)
            rows[0].args[4]()  # on_click đã bọc act(): đóng popup rồi mở room
        stub._close_sheet.assert_called()
        cls.assert_called_once()
        cls.return_value.show.assert_called_once()


class OpenOrderTest(unittest.TestCase):
    """Rework S7: render trước show, ẩn panel topmost, dựng lỗi thì dọn và thử lại được."""

    def _stub(self, snap=None, panel_visible=False):
        stub = _bind(_Stub(), "_open_control_room", "_control_room_theme", "_focus_from_control_room",
                     "_close_control_room")
        stub.control_room = None
        stub.f_xs, stub.f_sm, stub.f_smb, stub.f_title, stub.f_big = "F1", "F2", "F3", "F4", "F5"
        stub.S = 1.0
        stub.state = {}
        stub.snap = snap
        stub.panel_visible = panel_visible
        stub.root = mock.Mock()
        return stub

    def test_render_before_show_when_snapshot_present(self):
        stub = self._stub(snap={"sessions": []})
        order = []
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            cls.return_value.render.side_effect = lambda s: order.append(("render", s))
            cls.return_value.show.side_effect = lambda: order.append("show")
            ui.PetApp._open_control_room(stub)
        self.assertEqual(order, [("render", {"sessions": []}), "show"])

    def test_no_render_without_snapshot(self):
        stub = self._stub(snap=None)
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            ui.PetApp._open_control_room(stub)
        cls.return_value.render.assert_not_called()
        cls.return_value.show.assert_called_once()

    def test_visible_panel_hidden_before_show(self):
        stub = self._stub(snap=None, panel_visible=True)
        order = []
        stub.hide_panel = mock.Mock(side_effect=lambda: order.append("hide"))
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            cls.return_value.show.side_effect = lambda: order.append("show")
            ui.PetApp._open_control_room(stub)
        self.assertEqual(order, ["hide", "show"])

    def test_hidden_panel_not_hidden_again(self):
        stub = self._stub(snap=None, panel_visible=False)
        stub.hide_panel = mock.Mock()
        with mock.patch("pet_tracker.control_room.ControlRoom"), mock.patch.object(ui, "log"):
            ui.PetApp._open_control_room(stub)
        stub.hide_panel.assert_not_called()

    def test_show_false_closes_resets_and_flashes(self):
        stub = self._stub(snap=None)
        stub._flash = mock.Mock()
        stub.show_panel = mock.Mock()
        bad, good = mock.Mock(), mock.Mock()
        bad.show.return_value = False
        good.show.return_value = True
        with mock.patch("pet_tracker.control_room.ControlRoom", side_effect=[bad, good]) as cls, \
                mock.patch.object(ui, "log"):
            ui.PetApp._open_control_room(stub)
            self.assertIsNone(stub.control_room)
            bad.close.assert_called_once()
            stub._flash.assert_called_once()
            self.assertIn("Control room", stub._flash.call_args.args[0])
            stub.show_panel.assert_called_once()    # thông báo chỉ thấy được khi panel mở
            ui.PetApp._open_control_room(stub)     # lần sau dựng lại từ đầu
            stub._flash.assert_called_once()        # thành công thì không báo lỗi nữa
            stub.show_panel.assert_called_once()
        self.assertEqual(cls.call_count, 2)
        self.assertIs(stub.control_room, good)
        good.show.assert_called_once()

    def test_show_true_does_not_flash(self):
        stub = self._stub(snap=None)
        stub._flash = mock.Mock()
        with mock.patch("pet_tracker.control_room.ControlRoom") as cls, mock.patch.object(ui, "log"):
            cls.return_value.show.return_value = True
            ui.PetApp._open_control_room(stub)
        stub._flash.assert_not_called()
        self.assertIs(stub.control_room, cls.return_value)


    def test_failed_render_is_closed_and_reset(self):
        stub = self._stub(snap={"sessions": []})
        bad = mock.Mock()
        bad.render.side_effect = RuntimeError("bad")
        with mock.patch("pet_tracker.control_room.ControlRoom", return_value=bad), \
                mock.patch.object(ui, "log"):
            ui.PetApp._open_control_room(stub)
        bad.close.assert_called_once()
        bad.show.assert_not_called()
        self.assertIsNone(stub.control_room)




def _tk_root_available():
    try:
        import tkinter
        r = tkinter.Tk()
        r.destroy()
        return True
    except Exception:
        return False



@unittest.skipUnless(_tk_root_available(), "không có Tk/display")
class RealFailingBuildTest(unittest.TestCase):
    """Dựng thật qua ControlRoom.show(): _style ném lỗi, show trả False, ui dọn và báo; lần sau dựng được."""

    def setUp(self):
        import tkinter
        self.root = tkinter.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.stub = _bind(_Stub(), "_open_control_room", "_control_room_theme", "_focus_from_control_room",
                          "_close_control_room")
        self.stub.control_room = None
        self.stub.f_xs = self.stub.f_sm = self.stub.f_smb = self.stub.f_title = self.stub.f_big = "TkDefaultFont"
        self.stub.S = 1.0
        self.stub.state = {}
        self.stub.snap = {"sessions": [], "org": None}
        self.stub.panel_visible = False
        self.stub.root = self.root
        self.stub._flash = mock.Mock()
        for p in (mock.patch.object(ui, "log"), mock.patch.object(ui, "save_state")):
            p.start()
            self.addCleanup(p.stop)

    def test_real_build_failure_flashes_and_retry_builds(self):
        from pet_tracker import control_room as cr
        with mock.patch.object(cr.ControlRoom, "_style", side_effect=cr.tk.TclError("forced")):
            ui.PetApp._open_control_room(self.stub)
        self.assertIsNone(self.stub.control_room)
        self.stub._flash.assert_called_once()
        self.assertIn("Control room", self.stub._flash.call_args.args[0])
        ui.PetApp._open_control_room(self.stub)
        room = self.stub.control_room
        self.assertIsNotNone(room)
        self.assertIsNotNone(room.tree)                 # org None: cây rỗng, nhưng cửa sổ và cây đã dựng thật
        self.assertTrue(room.win.winfo_exists())
        self.stub._flash.assert_called_once()
        room.close()


class FocusSessionLogTest(unittest.TestCase):
    """Rework S7: dòng log của _focus_session không bị giả mạo bằng xuống dòng trong pid hoặc thông báo."""

    def _stub(self):
        stub = _bind(_Stub(), "_focus_session")
        stub._flash = mock.Mock()
        stub.hide_panel = mock.Mock()
        return stub

    def test_pid_repr_and_message_escaped(self):
        stub = self._stub()
        sess = {"name": "n", "pid": "7\nFORGED"}
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.return_value = (True, "ok\nFORGED line\x1b[0m đ")
            ui.PetApp._focus_session(stub, sess)
        msg = log.call_args.args[0]
        self.assertNotIn("\n", msg)
        self.assertIn("pid='7\\nFORGED'", msg)
        self.assertTrue(msg.isascii(), msg)

    def test_name_and_pid_quoted_so_spaces_are_unambiguous(self):
        stub = self._stub()
        sess = {"name": "my work", "pid": 7}
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.return_value = (True, "ok")
            ui.PetApp._focus_session(stub, sess)
        self.assertIn("focus session name='my work' pid='7': ok=True", log.call_args.args[0])

    def test_name_and_pid_capped(self):
        stub = self._stub()
        sess = {"name": "n" * 1000, "pid": "p" * 1000}
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.return_value = (True, "ok")
            ui.PetApp._focus_session(stub, sess)
        msg = log.call_args.args[0]
        self.assertIn("n" * 200, msg)
        self.assertNotIn("n" * 201, msg)
        self.assertIn("p" * 200, msg)
        self.assertNotIn("p" * 201, msg)

    def test_exception_text_escaped_in_log(self):
        stub = self._stub()
        with mock.patch.object(ui, "plat") as plat, mock.patch.object(ui, "log") as log:
            plat.focus_session.side_effect = RuntimeError("bad\nline")
            ui.PetApp._focus_session(stub, {"name": "n", "pid": 1})
        msg = log.call_args.args[0]
        self.assertNotIn("\n", msg)
        self.assertTrue(msg.isascii(), msg)
        self.assertIn("ok=False", msg)


class PumpRenderTest(unittest.TestCase):
    """Rework S7: _pump gọi render khi có snapshot mới, kể cả lúc panel ẩn."""

    def _stub(self):
        stub = _bind(_Stub(), "_pump")
        stub._update_dirty = False
        stub._update_ready = False
        stub._want_show = False
        stub._ops_done = queue.Queue()
        stub.q = queue.Queue()
        stub.snap = None
        stub._sheet = None
        stub.panel_visible = False
        stub._lbtn_prev = False
        stub._modal = False
        stub._render_control_room = mock.Mock()
        return stub

    def test_render_runs_on_new_snapshot_with_panel_hidden(self):
        stub = self._stub()
        snap = {"sessions": [], "org": None}
        stub.q.put(snap)
        ui.PetApp._pump(stub)
        self.assertIs(stub.snap, snap)
        stub._render_control_room.assert_called_once_with()

    def test_no_render_without_new_snapshot(self):
        stub = self._stub()
        ui.PetApp._pump(stub)
        stub._render_control_room.assert_not_called()


if __name__ == "__main__":
    unittest.main()
