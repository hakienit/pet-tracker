"""Test pet_tracker.control_room: hàm thuần (làm sạch, flatten, chữ ký, hình học) và một smoke test Tk nếu có display."""
import ast
import json
import re
import time
import unittest
from pathlib import Path
from unittest import mock

from pet_tracker import control_room as cr
from pet_tracker import org
from pet_tracker.i18n import t

NOW = 10_000.0
CFG = {"agent_prefixes": ["les-"], "stuck_after_sec": 120}
HOSTILE = "x{y}\\z $a [b] %c \"q\" ;'"


def sess(sid="s1", **kw):
    s = {"session_id": sid, "started_at": 1000.0, "cwd": "/w/proj", "name": "main work", "status": "busy",
         "model": "opus", "git": {"top": "/w/proj", "common": "/w/proj/.git", "branch": "main"},
         "totals": {"input": 10, "output": 20, "cache_create": 0, "cache_read": 0, "messages": 3},
         "agent_calls": [], "workers": []}
    s.update(kw)
    return s


def sub(id, **kw):
    w = {"kind": "subagent", "id": id, "tool_use_id": "tu-" + id, "agent_type": "les-engineering",
         "description": "desc " + id, "depth": 1, "finished": False, "notif_status": None, "mtime": NOW - 10,
         "started": NOW - 100, "last_activity": NOW - 10, "tokens": 5, "open_tools": 0, "agent_calls": []}
    w.update(kw)
    return w


def bg(id, **kw):
    w = {"kind": "bgtask", "id": id, "tool_use_id": "tb-" + id, "started": NOW - 50, "status": None}
    w.update(kw)
    return w


def sample_sessions():
    """s1: A (engineering) cha của C (qa), B (review), một bgtask; s2: worktree khác cùng project."""
    s1 = sess(agent_calls=["tu-A", "tu-B"], workers=[
        sub("A", agent_calls=["tu-c"]),
        sub("C", agent_type="hba:qa-engineer", tool_use_id="tu-c"),
        sub("B", agent_type="les-review", notif_status="completed"),
        bg("T1"),
    ])
    s2 = sess("s2", name="feature work", cwd="/w/wt-feat",
              git={"top": "/w/wt-feat", "common": "/w/proj/.git", "branch": "feat"})
    return [s1, s2]


def build(sessions=None, now=NOW):
    return org.build(sample_sessions() if sessions is None else sessions, CFG, now)


def rows_of(sessions=None, now=NOW):
    return cr.flatten(build(sessions, now), now)


class SanitizeTest(unittest.TestCase):
    def test_strips_controls_and_bidi(self):
        bad = "\x00\x01\x07\x1b\x7f\x80\x9f​‎‏‪‮⁦⁩؜﻿\ud800"
        out = cr.sanitize("a" + bad + "b")
        self.assertEqual(out, "ab")

    def test_newlines_and_tabs_become_space(self):
        self.assertEqual(cr.sanitize("a\nb\r\nc\td e f"), "a b  c d e f".replace("  ", "  "))
        self.assertNotRegex(cr.sanitize("a\nb\r\nc\td e f"), "[\n\r\t  ]")

    def test_cut_length(self):
        out = cr.sanitize("x" * 5000, 50)
        self.assertLessEqual(len(out), 50)
        self.assertTrue(out.endswith("…"))
        self.assertEqual(cr.sanitize("x" * 50, 50), "x" * 50)

    def test_keeps_normal_unicode(self):
        for s in ("Đang chạy việc nền", "日本語のタスク", "naïve café", "emoji \U0001f600 ok"):
            self.assertEqual(cr.sanitize(s), s)

    def test_tcl_special_unchanged(self):
        self.assertEqual(cr.sanitize(HOSTILE), HOSTILE)
        for s in ("{", "}", "\\", "$", "[", "%", "{}", "}{", "$(x)", "[exec id]", "%W", "\\n", "{a b"):
            self.assertEqual(cr.sanitize(s), s)

    def test_non_str(self):
        for v in (None, 5, 1.5, ["a"], {"a": 1}, b"x", True):
            self.assertEqual(cr.sanitize(v), "")

    def test_only_junk_gives_empty(self):
        self.assertEqual(cr.sanitize("‮\x00 \n"), "")


class FormatTest(unittest.TestCase):
    def test_elapsed(self):
        f = cr.fmt_elapsed
        self.assertEqual(f(None), "")
        self.assertEqual(f(-5), "")
        self.assertEqual(f(float("nan")), "")
        self.assertEqual(f(0), "0s")
        self.assertEqual(f(59.9), "59s")
        self.assertEqual(f(125), "2m05s")
        self.assertEqual(f(3 * 3600 + 120), "3h02m")
        self.assertEqual(f(2 * 86400 + 5 * 3600), "2d05h")

    def test_tokens(self):
        self.assertEqual(cr.fmt_tokens(0), "0")
        self.assertEqual(cr.fmt_tokens(999), "999")
        self.assertEqual(cr.fmt_tokens(1500), "1.5k")
        self.assertEqual(cr.fmt_tokens(2_500_000), "2.5M")
        self.assertEqual(cr.fmt_tokens(None), "")

    def test_summary_counts(self):
        sc = cr.summary_counts(build())
        self.assertEqual(sc["projects"], 1)
        self.assertEqual(sc["teams"], 2)
        self.assertEqual(sc["subagents"], 2)   # A, C running; B done
        self.assertEqual(sc["tasks"], 1)
        self.assertEqual(sc["stuck"], 0)
        stuck = cr.summary_counts(build([sess(workers=[sub("Z", mtime=NOW - 500, last_activity=NOW - 500,
                                                           started=NOW - 600)])]))
        self.assertEqual(stuck["stuck"], 1)

    def test_summary_counts_junk(self):
        for bad in (None, {}, [], "x", {"projects": 5, "counts": []}, {"projects": [1, None], "counts": {"subagent": 3}}):
            sc = cr.summary_counts(bad)
            self.assertEqual(set(sc), {"projects", "teams", "subagents", "tasks", "stuck"})
            self.assertTrue(all(isinstance(v, int) for v in sc.values()))

    def test_summary_counts_clamped(self):
        sc = cr.summary_counts({"counts": {"subagent": {"running": 10**30, "stuck": 10**30},
                                           "bgtask": {"running": 7}}})
        self.assertEqual(sc["subagents"], 10**6)
        self.assertEqual(sc["stuck"], 10**6)
        self.assertEqual(sc["tasks"], 7)
        self.assertEqual(cr.summary_counts({"counts": {"subagent": {"stuck": float("inf")}}})["stuck"], 0)

    def test_counts_text(self):
        self.assertEqual(cr.counts_text(2, 1), "2 agent · 1 task")
        self.assertEqual(cr.counts_text(0, 0), "")
        self.assertEqual(cr.counts_text(2, 0, 1), "2 agent (1 treo)")
        self.assertEqual(cr.counts_text(0, 3), "3 task")


class FlattenTest(unittest.TestCase):
    def test_tree_shape(self):
        rows = rows_of()
        s1 = [r for r in rows if r["kind"] == "session" and r["session_id"] == "s1"][0]
        under = [(r["kind"], r["name"]) for r in rows if r["parent"] == s1["key"]]
        self.assertEqual(under, [("dept", "engineering"), ("dept", "review"), ("dept", "Task nền")])
        by_key = {r["key"]: r for r in rows}
        a = [r for r in rows if r["kind"] == "subagent" and r["name"] == "desc A"][0]
        c = [r for r in rows if r["kind"] == "subagent" and r["name"] == "desc C"][0]
        self.assertEqual(by_key[a["parent"]]["kind"], "dept")
        self.assertEqual(c["parent"], a["key"])       # con lồng dưới cha
        kinds = [r["kind"] for r in rows]
        self.assertEqual(kinds[:3], ["project", "team", "session"])
        self.assertEqual(kinds.count("project"), 1)
        self.assertEqual(kinds.count("team"), 2)
        self.assertEqual(kinds.count("bgtask"), 1)

    def test_team_label_has_worktree_and_branch(self):
        names = [r["name"] for r in rows_of() if r["kind"] == "team"]
        self.assertEqual(names, ["proj · main", "wt-feat · feat"])

    def test_parent_before_child_and_keys_unique(self):
        rows = rows_of()
        seen = set()
        for r in rows:
            self.assertNotIn(r["key"], seen)
            self.assertTrue(r["parent"] is None or r["parent"] in seen)
            seen.add(r["key"])

    def test_duplicate_worker_ids_get_unique_keys(self):
        rows = rows_of([sess(workers=[sub("D"), sub("D"), bg("D"), bg("D")])])
        keys = [r["key"] for r in rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len([r for r in rows if r["kind"] in ("subagent", "bgtask")]), 4)

    def test_many_duplicate_ids_fast_capped_and_unique(self):
        o = build([sess(workers=[sub("D") for _ in range(5000)])])
        t0 = time.perf_counter()
        rows = cr.flatten(o, NOW)
        self.assertLess(time.perf_counter() - t0, 2.0)
        keys = [r["key"] for r in rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(rows), 2 + 2000)        # project, team + 2000 dòng cho một session
        more = rows[-1]
        self.assertEqual((more["kind"], more["state"]), ("more", ""))
        self.assertEqual(more["name"], t("cr.more", n=3003))  # 5000 subagent, giữ 1997
        self.assertEqual(more["ag"], 3003)            # 3003 dòng đang chạy bị gộp vẫn được cộng cho cha
        self.assertEqual(len([r for r in rows if r["kind"] == "subagent"]), 1997)

    def test_duplicate_session_ids(self):
        rows = rows_of([sess("dup"), sess("dup")])
        keys = [r["key"] for r in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_state_and_tag_are_enum_only(self):
        for r in rows_of():
            self.assertIn(r["state"], ("", *cr.STATE_LABEL))
            self.assertIn(cr.row_tag(r), (None, *cr.STATE_TAG.values()))

    def test_hostile_strings_cleaned_and_kept_out_of_structure(self):
        evil = "‮evil\n\x00" + HOSTILE
        rows = rows_of([sess(name=evil, status=evil, workers=[
            sub("w" + evil, description=evil, agent_type=evil, state=evil)])])
        pat = re.compile("[\x00-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩؜﻿]")
        for r in rows:
            for v in (r["name"], r["summary"], r["status"], r["elapsed"], r["ago"]):
                self.assertIsNone(pat.search(v), v)
            for a, b in r["detail"]:
                self.assertIsNone(pat.search(b), b)
        self.assertTrue(any(HOSTILE in r["name"] for r in rows))

    def test_cycle_does_not_hang_or_drop(self):
        o = build([sess(workers=[sub("A"), sub("B")])])
        ws = o["projects"][0]["teams"][0]["sessions"][0]["workers"]
        ws[0]["parent"], ws[1]["parent"] = "B", "A"      # org không tạo ra vòng; module vẫn phải chịu được
        rows = cr.flatten(o, NOW)
        self.assertEqual(len([r for r in rows if r["kind"] == "subagent"]), 2)

    def test_junk_input(self):
        junk = (None, 5, "x", [], {}, {"projects": "x"}, {"projects": [None, 3, {"teams": 7}]},
                {"projects": [{"name": 1, "teams": [{"sessions": [None, {"workers": "x"}, {"workers": [5, {}]}]}]}]})
        for j in junk:
            self.assertIsInstance(cr.flatten(j, NOW), list)
        self.assertEqual(cr.flatten(None, NOW), [])
        self.assertIsInstance(cr.flatten(build(), None), list)

    def test_rows_json_safe(self):
        json.dumps(rows_of())

    def test_elapsed_and_ago(self):
        rows = rows_of()
        a = [r for r in rows if r["name"] == "desc A"][0]
        self.assertEqual(a["elapsed"], "1m40s")
        self.assertEqual(a["ago"], "10s")
        self.assertEqual(a["tokens"], 5)
        done = [r for r in rows if r["name"] == "desc B"][0]
        self.assertEqual(done["state"], "done")
        self.assertEqual(done["elapsed"], "1m30s")      # last_activity - started

    def test_group_summary(self):
        eng = [r for r in rows_of() if r["kind"] == "dept" and r["name"] == "engineering"][0]
        self.assertEqual(eng["summary"], "2 agent")

    def test_subagent_detail_shows_type(self):
        # org.build xuất khoá "type"; dòng "Loại agent" phải đọc khoá đó
        a = [r for r in rows_of() if r["kind"] == "subagent" and r["name"] == "desc A"][0]
        self.assertIn((t("cr.f.agent_type"), "les-engineering"), a["detail"])

    def test_empty_description_names_row_by_type(self):
        sessions = [sess(workers=[sub("A", description="")])]
        rows = [r for r in rows_of(sessions) if r["kind"] == "subagent"]
        self.assertEqual([r["name"] for r in rows], ["les-engineering"])
        self.assertNotEqual(rows[0]["name"], t("cr.anon_subagent"))


class SignatureTest(unittest.TestCase):
    def sigs(self, sessions=None, now=NOW):
        rows = rows_of(sessions, now)
        return cr.struct_sig(rows), cr.live_sig(rows)

    def test_stable_for_same_input(self):
        self.assertEqual(self.sigs(), self.sigs())

    def test_tokens_only_change_live(self):
        base = self.sigs()
        s = sample_sessions()
        s[0]["workers"][0]["tokens"] = 99999
        new = self.sigs(s)
        self.assertEqual(new[0], base[0])
        self.assertNotEqual(new[1], base[1])

    def test_last_activity_only_changes_live(self):
        base = self.sigs()
        s = sample_sessions()
        s[0]["workers"][0]["last_activity"] = NOW - 3
        s[0]["workers"][0]["mtime"] = NOW - 3
        new = self.sigs(s)
        self.assertEqual(new[0], base[0])
        self.assertNotEqual(new[1], base[1])

    def test_time_passing_only_changes_live(self):
        base = self.sigs()
        new = self.sigs(now=NOW + 30)
        self.assertEqual(new[0], base[0])
        self.assertNotEqual(new[1], base[1])

    def test_session_status_only_changes_live(self):
        base = self.sigs()
        s = sample_sessions()
        s[0]["status"] = "idle"
        new = self.sigs(s)
        self.assertEqual(new[0], base[0])
        self.assertNotEqual(new[1], base[1])

    def test_state_change_changes_struct(self):
        base = self.sigs()
        s = sample_sessions()
        s[0]["workers"][3]["status"] = "completed"       # bgtask xong
        self.assertNotEqual(self.sigs(s)[0], base[0])
        s = sample_sessions()
        s[0]["workers"][0]["notif_status"] = "failed"
        self.assertNotEqual(self.sigs(s)[0], base[0])

    def test_shape_and_name_change_struct(self):
        base = self.sigs()
        s = sample_sessions()
        s[0]["workers"].append(sub("N"))
        self.assertNotEqual(self.sigs(s)[0], base[0])
        s = sample_sessions()
        s[0]["workers"][0]["description"] = "other"
        self.assertNotEqual(self.sigs(s)[0], base[0])
        s = sample_sessions()
        s[1]["git"]["branch"] = "renamed"
        self.assertNotEqual(self.sigs(s)[0], base[0])

    def test_hashable(self):
        hash(self.sigs())


class GeometryTest(unittest.TestCase):
    SCREEN, DEFAULT, MIN = (1440, 900), (960, 600), (640, 380)

    def clamp(self, saved, top=0):
        return cr.clamp_geometry(saved, self.SCREEN, self.DEFAULT, self.MIN, top)

    def test_valid_kept(self):
        self.assertEqual(self.clamp({"w": 800, "h": 500, "x": 100, "y": 50}), (800, 500, 100, 50))

    def test_offscreen_pulled_back(self):
        w, h, x, y = self.clamp({"w": 800, "h": 500, "x": 5000, "y": -300})
        self.assertEqual((x, y), (1440 - 800, 0))
        w, h, x, y = self.clamp({"w": 800, "h": 500, "x": -9000, "y": 9000})
        self.assertEqual((x, y), (0, 900 - 500))

    def test_top_margin(self):
        self.assertEqual(self.clamp({"w": 800, "h": 500, "x": 0, "y": 0}, top=30)[3], 30)

    def test_size_clamped(self):
        w, h, x, y = self.clamp({"w": 99999, "h": 99999, "x": 0, "y": 0}, top=30)
        self.assertEqual((w, h), (1440, 870))
        w, h, *_ = self.clamp({"w": 10, "h": 10, "x": 0, "y": 0})
        self.assertEqual((w, h), self.MIN)

    def test_garbage_gives_centered_default(self):
        for bad in (None, 5, "x", [], {}, {"w": "a", "h": None, "x": 1.5, "y": True}, {"w": True}):
            w, h, x, y = self.clamp(bad)
            self.assertEqual((w, h), self.DEFAULT, bad)
            self.assertEqual((x, y), ((1440 - 960) // 2, (900 - 600) // 2), bad)

    def test_huge_ints(self):
        w, h, x, y = self.clamp({"w": 10**30, "h": 10**30, "x": 10**30, "y": -10**30})
        self.assertTrue(0 <= x <= 1440 - w and 0 <= y <= 900 - h)


class ConfigTest(unittest.TestCase):
    """Không cần Tk: __init__ chỉ lưu tham số, không đụng root."""

    def room(self, theme=None, focus=None, log=None):
        return cr.ControlRoom(None, theme or {}, {}, lambda st: None, focus or (lambda sid: None), log=log)

    def test_scale_clamped(self):
        self.assertEqual(self.room({"scale": 100}).S, 4.0)
        self.assertEqual(self.room({"scale": 0.01}).S, 0.5)
        self.assertEqual(self.room({"scale": 1.5}).S, 1.5)
        for bad in (None, "x", 0, -2, float("nan"), float("inf"), True):
            self.assertEqual(self.room({"scale": bad}).S, 1.0, bad)

    def test_focus_error_is_logged_short(self):
        msgs = []

        def boom(sid):
            raise ValueError("boom " + "x" * 1000)

        room = self.room(focus=boom, log=msgs.append)
        room._rows = {"i1": {"kind": "session", "session_id": "s1"}}
        room._activate("i1")
        self.assertEqual(len(msgs), 1)
        self.assertIsInstance(msgs[0], str)
        self.assertIn("boom", msgs[0])
        self.assertLess(len(msgs[0]), 300)

    def test_focus_error_without_log_is_silent(self):
        def boom(sid):
            raise ValueError("boom")

        room = self.room(focus=boom)
        room._rows = {"i1": {"kind": "session", "session_id": "s1"}}
        room._activate("i1")      # không ném lỗi


class SourceSafetyTest(unittest.TestCase):
    """Module không import ui/os/subprocess và không dùng eval/call (mọi chuỗi agent chỉ vào text=/values=)."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(cr.__file__).read_text(encoding="utf-8"))

    def test_imports(self):
        mods = set()
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(("." * n.level) + (n.module or ""))
        self.assertFalse(mods & {"os", "subprocess", "socket", "ctypes", "threading", "queue"}, mods)
        self.assertFalse(any(m.lstrip(".") in ("ui", "session_ops", "config", "platform") for m in mods), mods)

    def test_no_tcl_string_building(self):
        attrs = {n.attr for n in ast.walk(self.tree) if isinstance(n, ast.Attribute)}
        names = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)}
        self.assertFalse(attrs & {"eval", "call", "createcommand", "evalfile", "tk"}, attrs)
        self.assertFalse(names & {"eval", "exec"})

    def test_tag_names_fixed(self):
        for t in cr.STATE_TAG.values():
            self.assertRegex(t, r"^st_[a-z]+$")


# ---------------------------------------------------------------- Tk smoke test
def _register_fonts_first():
    """Archivo phải đăng ký trước root Tk đầu tiên của process: Tk chốt danh sách font lúc đó, root tạo trước thì
    test_mac_session (chạy sau) không thấy Archivo."""
    try:
        from pet_tracker.ui.kit import register_fonts
        register_fonts()
    except ImportError:     # không có Tk: test Tk sẽ tự bỏ qua
        pass


def _make_root():
    if cr.tk is None:
        return None
    try:
        _register_fonts_first()
        root = cr.tk.Tk()
    except Exception:       # TclError: không có display
        return None
    root.withdraw()
    return root


class TkSmokeTest(unittest.TestCase):
    def setUp(self):
        self.root = _make_root()
        if self.root is None:
            self.skipTest("không có Tk/display")
        self.state, self.saved, self.focused = {}, [], []
        self.room = cr.ControlRoom(self.root, {}, self.state, lambda st: self.saved.append(dict(st)),
                                   self.focused.append)

    def tearDown(self):
        self.room.close()
        self.root.destroy()

    def snap(self, sessions=None, now=NOW):
        return {"org": build(sessions, now), "sessions": []}

    def iid_of(self, kind, name=None):
        for iid, r in self.room._rows.items():
            if r["kind"] == kind and (name is None or r["name"] == name):
                return iid
        raise AssertionError((kind, name))

    def test_render_live_only_does_not_rebuild(self):
        room, tree = self.room, None
        room.show()
        tree = room.tree
        room.render(self.snap(), now=NOW)
        base = room._rebuilds
        iids = set(room._rows)
        self.assertTrue(all(re.fullmatch(r"i\d+", i) for i in tree.get_children("")))
        for iid in iids:
            self.assertRegex(iid, r"^i\d+$")
            self.assertLessEqual(set(tree.item(iid, "tags")), set(cr.STATE_TAG.values()))
        # chọn subagent A rồi thu gọn một nhánh
        a = self.iid_of("subagent", "desc A")
        tree.selection_set(a)
        room.root.update()          # <<TreeviewSelect>> đi qua hàng đợi sự kiện
        before = tree.set(a, "live")
        s = sample_sessions()
        s[0]["workers"][0]["tokens"] = 123456
        room.render({"org": build(s, NOW + 5), "sessions": []}, now=NOW + 5)
        self.assertEqual(room._rebuilds, base)               # chỉ live đổi: không dựng lại
        self.assertEqual(set(room._rows), iids)
        self.assertEqual(tree.selection(), (a,))
        self.assertNotEqual(tree.set(a, "live"), before)
        self.assertIn("123k", tree.set(a, "live"))

    def test_struct_change_rebuilds_keeps_selection_and_collapse(self):
        room = self.room
        room.show()
        room.render(self.snap(), now=NOW)
        base = room._rebuilds
        tree = room.tree
        a = self.iid_of("subagent", "desc A")
        tree.selection_set(a)
        sess_iid = self.iid_of("session", "feature work")
        tree.item(sess_iid, open=False)
        s = sample_sessions()
        s[0]["workers"][3]["status"] = "completed"
        room.render({"org": build(s, NOW), "sessions": []}, now=NOW)
        self.assertEqual(room._rebuilds, base + 1)
        new_a = self.iid_of("subagent", "desc A")
        self.assertNotEqual(new_a, a)                        # iid mới, bộ đếm tăng
        self.assertEqual(tree.selection(), (new_a,))
        self.assertFalse(bool(int(tree.item(self.iid_of("session", "feature work"), "open"))))

    def test_hostile_strings_displayed_literally(self):
        room = self.room
        room.show()
        evil = HOSTILE + " [exec id] ${x}"
        room.render(self.snap([sess(name=evil, status=evil, workers=[sub("w", description=evil)])]), now=NOW)
        tree = room.tree
        sid = self.iid_of("session")
        self.assertEqual(tree.item(sid, "text"), cr.sanitize(evil, cr.MAX_NAME))
        self.assertIn(cr.sanitize(evil, cr.MAX_STATUS), tree.set(sid, "live"))
        w = self.iid_of("subagent")
        self.assertEqual(tree.item(w, "text"), cr.sanitize(evil, cr.MAX_NAME))
        tree.selection_set(w)
        room.root.update()
        self.assertIn(HOSTILE, room._detail.get())

    def test_tcl_specials_roundtrip_through_tree(self):
        """Chuỗi toàn ký tự đặc biệt của Tcl đi vào text=/values= và đọc lại nguyên vẹn, không lỗi, không bị thực thi."""
        specials = ["{", "}", "{}", "}{", "\\", "\\{", '"abc', '"', "a b {", "$x", "[exec id]", "%W", ";", "-text",
                    "$(x) {a} [b] \\n"]
        room = self.room
        room.show()
        for sp in specials:
            room.render(self.snap([sess(name=sp, status=sp, workers=[sub("w", description=sp)])]), now=NOW)
            for kind in ("session", "subagent"):
                iid = self.iid_of(kind)
                self.assertEqual(str(room.tree.item(iid, "text")), sp, sp)
            self.assertIn(cr.sanitize(sp, cr.MAX_STATUS), str(room.tree.set(self.iid_of("session"), "live")), sp)
            room.tree.selection_set(self.iid_of("subagent"))
            room.root.update()
            self.assertIn(sp, room._detail.get())

    def test_click_session_focuses_others_readonly(self):
        room = self.room
        room.show()
        room.render(self.snap(), now=NOW)
        room._activate(self.iid_of("subagent", "desc A"))
        room._activate(self.iid_of("bgtask"))
        room._activate(self.iid_of("project"))
        room._activate("nope")
        self.assertEqual(self.focused, [])
        room._activate(self.iid_of("session", "feature work"))
        self.assertEqual(self.focused, ["s2"])

    def test_destroyed_window_recovers(self):
        room = self.room
        room.show()
        room.render(self.snap(), now=NOW)
        room.win.destroy()                           # đóng không qua close()
        self.assertIsNone(room.win)
        room.render(self.snap(), now=NOW)            # không ném TclError
        room.show()                                  # mở lại và dựng cây mới
        self.assertIsNotNone(room.win)
        self.assertTrue(room.tree.get_children(""))
        self.assertTrue(room._rows)

    def test_single_click_selects_only_double_click_activates(self):
        room = self.room
        room.show()
        room.render(self.snap(), now=NOW)
        self.assertFalse(room.tree.bind("<ButtonRelease-1>"))    # bấm đơn không còn kích hoạt
        self.assertTrue(room.tree.bind("<Double-1>"))
        self.assertTrue(room.tree.bind("<Return>"))
        room.tree.selection_set(self.iid_of("session", "main work"))
        room.root.update()
        self.assertEqual(self.focused, [])

    def test_render_before_show_fills_first_open(self):
        room = self.room
        room.render(self.snap(), now=NOW)            # trước khi có cửa sổ: chỉ lưu org
        self.assertIsNone(room.win)
        room.show()
        self.assertTrue(room.tree.get_children(""))  # lần mở đầu đã có dữ liệu, không chờ snapshot sau
        self.iid_of("session", "main work")

    def test_failed_build_resets_then_show_recovers(self):
        msgs = []
        room = cr.ControlRoom(self.root, {}, self.state, lambda st: None, self.focused.append, log=msgs.append)
        try:
            room.render(self.snap(), now=NOW)
            real_style = room._style
            calls = []

            def flaky_style():
                calls.append(1)
                if len(calls) == 1:
                    raise cr.tk.TclError("forced")
                return real_style()

            before = set(self.root.winfo_children())
            with mock.patch.object(room, "_style", side_effect=flaky_style):
                self.assertFalse(room.show())        # lỗi được ghi log, không ném ra; trả False
            self.assertIsNone(room.win)
            self.assertIsNone(room.tree)
            self.assertEqual(set(self.root.winfo_children()) - before, set())   # Toplevel đã bị huỷ
            self.assertEqual(len(msgs), 1)
            self.assertIn("forced", msgs[0])
            room.render(self.snap(), now=NOW)        # không ném, không log thêm
            self.assertEqual(len(msgs), 1)
            self.assertTrue(room.show())             # lần sau dựng được cây; trả True
            self.assertIsNotNone(room.tree)
            self.assertTrue(room.tree.get_children(""))
            self.assertEqual(len(msgs), 1)
        finally:
            room.close()

    def test_show_returns_true_on_first_open_and_on_reraise(self):
        room = self.room
        self.assertIs(room.show(), True)     # dựng mới
        self.assertIs(room.show(), True)     # đã có cửa sổ: đưa lên trước

    def test_show_rebuilds_when_tree_missing(self):
        room = self.room
        room.show()
        room.render(self.snap(), now=NOW)
        old_win = room.win
        room.tree = None                             # cửa sổ còn nhưng cây mất
        room.show()
        self.assertIsNotNone(room.tree)
        self.assertIsNot(room.win, old_win)
        self.assertTrue(room.tree.get_children(""))

    def test_no_org_and_junk_snapshots(self):
        room = self.room
        room.show()
        for snap in (None, {}, {"org": None}, {"org": "x"}, {"org": {"projects": [None]}}, 5):
            room.render(snap)
        room.render(self.snap(), now=NOW)
        self.assertTrue(room._rows)
        room.render({"org": None})
        self.assertFalse(room._rows)

    def test_close_saves_geometry_and_reopen(self):
        room = self.room
        room.show()
        room.render(self.snap(), now=NOW)
        room.root.update()
        room.close()
        g = self.state[cr.GEOMETRY_KEY]
        self.assertEqual(set(g), {"w", "h", "x", "y"})
        self.assertTrue(all(type(v) is int for v in g.values()))
        self.assertTrue(self.saved)
        self.assertIsNone(room.win)
        room.close()                                         # đóng lần hai không lỗi
        room.render(self.snap(), now=NOW)                    # render khi đóng không lỗi
        room.show()
        self.assertTrue(room._rows)                          # mở lại dựng từ snapshot cuối
        room.show()                                          # show lần hai chỉ raise


if __name__ == "__main__":
    unittest.main()
