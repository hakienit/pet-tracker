"""Control room: giới hạn và an toàn (F1, F4, F5b) và nối Tk (R6). Phần Tk tự bỏ qua khi không có display."""
import unittest
from unittest import mock

from pet_tracker import control_room as cr
from pet_tracker import org
from pet_tracker.i18n import t

NOW = 10_000.0
CFG = {"agent_prefixes": ["les-"], "stuck_after_sec": 120}


def sess(sid="s1", **kw):
    s = {"session_id": sid, "started_at": 1000.0, "cwd": "/w/proj", "name": "main work", "status": "busy",
         "model": "opus", "git": {"top": "/w/proj", "common": "/w/proj/.git", "branch": "main"},
         "totals": {"input": 10, "output": 20, "cache_create": 0, "cache_read": 0, "messages": 3},
         "agent_calls": [], "workers": []}
    s.update(kw)
    return s


def sub(wid, **kw):
    w = {"kind": "subagent", "id": wid, "tool_use_id": "tu-" + wid, "agent_type": "les-engineering",
         "description": "desc " + wid, "depth": 1, "finished": False, "notif_status": None, "mtime": NOW - 10,
         "started": NOW - 100, "last_activity": NOW - 10, "tokens": 5, "open_tools": 0, "agent_calls": []}
    w.update(kw)
    return w


def rows_of(sessions):
    return cr.flatten(org.build(sessions, CFG, NOW), NOW)


class HugeNumberTest(unittest.TestCase):
    def test_helpers_treat_huge_int_as_missing(self):
        self.assertIsNone(cr._n(10 ** 400))
        self.assertEqual(cr._i(10 ** 400), 0)
        self.assertEqual(cr.fmt_tokens(10 ** 400), "")
        self.assertEqual(cr.fmt_elapsed(10 ** 400), "")

    def test_huge_numbers_do_not_empty_the_tree(self):
        bad = sess("bad", started_at=10 ** 400, totals={"input": 10 ** 400, "output": 10 ** 400},
                   workers=[sub("A", tokens=10 ** 400, started=10 ** 400, last_activity=10 ** 400)])
        rows = rows_of([bad, sess("good")])
        sessions = [r["session_id"] for r in rows if r["kind"] == "session"]
        self.assertEqual(sorted(sessions), ["bad", "good"])


class NameFallbackTest(unittest.TestCase):
    def test_fallback_name_from_hostile_id_is_sanitised(self):
        rows = rows_of([sess("\ud800‮abcdefghijklmnop", name="")])
        name = next(r["name"] for r in rows if r["kind"] == "session")
        self.assertNotIn("\ud800", name)
        self.assertNotIn("‮", name)
        self.assertLessEqual(len(name), 8)


class GlobalCapTest(unittest.TestCase):
    def test_global_row_cap_with_more_row(self):
        sessions = [sess("s%d" % i, workers=[sub("W%d_%d" % (i, j)) for j in range(1500)]) for i in range(4)]
        rows = rows_of(sessions)
        self.assertEqual(len(rows), cr.MAX_ROWS_TOTAL)
        more = rows[-1]
        self.assertEqual((more["kind"], more["parent"]), ("more", None))
        total = 4 * 1502 + 2                             # 4 session (mỗi cái: session + dept + 1500 subagent), project, team
        dropped = total - (cr.MAX_ROWS_TOTAL - 1)        # dòng '+N more' chiếm một chỗ
        self.assertEqual(more["name"], t("cr.more", n=dropped))
        self.assertEqual(more["ag"], dropped)            # các dòng bị cắt đều là subagent đang chạy
        keys = [r["key"] for r in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_small_tree_has_no_global_more_row(self):
        rows = rows_of([sess("a", workers=[sub("A")])])
        self.assertFalse(any(r["kind"] == "more" and r["parent"] is None for r in rows))


def _register_fonts_first():
    """Archivo phải đăng ký trước root Tk đầu tiên của process (Tk chốt danh sách font lúc đó)."""
    from pet_tracker.ui.kit import register_fonts
    register_fonts()


class StringVarMasterTest(unittest.TestCase):
    def setUp(self):
        try:
            _register_fonts_first()
            import tkinter as tk
            self.root = tk.Tk()
        except Exception:
            self.skipTest("không có Tk/display")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_string_vars_bound_to_room_window(self):
        import tkinter as tk
        real = tk.StringVar
        room = cr.ControlRoom(self.root, {}, {}, lambda st: None, lambda sid: None)
        with mock.patch.object(cr.tk, "StringVar", side_effect=lambda *a, **kw: real(*a, **kw)) as sv:
            room.show()
            self.addCleanup(room.close)
        self.assertGreaterEqual(sv.call_count, 2)
        for call in sv.call_args_list:
            self.assertIs(call.kwargs.get("master"), room.win, call)


if __name__ == "__main__":
    unittest.main()
