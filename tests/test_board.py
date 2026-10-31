"""Test phần thuần của pet_tracker.board (S2a-1 của plan Board + viewer 3D): không Tk, không display.

Danh sách theo docs/specs/2026-10-30-board-2-5d-design.md, mục "Kiểm thử" (`tests/test_board.py`).
Fixture dựng bằng `org.build` qua các hàm của tests/test_office.py.
"""
import ast
import copy
import random
import unittest
from pathlib import Path

from pet_tracker import board, control_room as cr, office
from pet_tracker.i18n import t
from tests.test_office import NOW, S, bg, org_of, sub

ROOT = Path(__file__).resolve().parents[1]
LCFG = {"board_max_desks": 48, "board_max_workers": 12}
HOSTILE = "a{b}c\\d[e]$f%g\nh\u202ei\u200bj"


def build(sessions, cfg=LCFG, now=NOW):
    o = org_of(sessions, now)
    return o, office.office_layout(o, cfg)


def one_floor(sessions, cfg=LCFG):
    o, l = build(sessions, cfg)
    return o, l, l["floors"][0]


def raw_sub(o, wid):
    for p in o["projects"]:
        for tm in p["teams"]:
            for s in tm["sessions"]:
                for w in s["workers"]:
                    if w["id"] == wid:
                        return w
    raise KeyError(wid)


def node(floor, kind, ident):
    for c in floor["clusters"]:
        for d in c["desks"]:
            if kind == "desk" and d["session_id"] == ident:
                return d
            for n in d["workers" if kind == "worker" else "devices"] if kind != "desk" else ():
                if n["id"] == ident:
                    return n
    raise KeyError(ident)


def clean(s):
    return "\n" not in s and "\u202e" not in s and "\u200b" not in s


class PaintOrder(unittest.TestCase):
    def setUp(self):
        self.o, self.l, self.f = one_floor([
            S("s1", workers=[sub("a"), sub("b", dept="qa"), bg("t1"), bg("t2", "done")]),
            S("s2", started=1001, workers=[sub("c", dept="ops"), bg("t3")])])

    def test_order(self):
        items = board.paint_order(self.f)
        rank = {"desk": 0, "device": 1, "mascot": 2, "worker": 2}
        keys = [(n["x"] + n["y"], n["x"], rank[k]) for k, n in items]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(items), 2 * 2 + 3 + 3)
        for d in (node(self.f, "desk", "s1"), node(self.f, "desk", "s2")):
            kinds = [k for k, n in items if n is d]
            self.assertEqual(kinds, ["desk", "mascot"])
            i_mascot = next(i for i, (k, n) in enumerate(items) if k == "mascot" and n is d)
            for dev in d["devices"]:
                self.assertLess(i_mascot, next(i for i, (k, n) in enumerate(items) if n is dev))

    def test_stable(self):
        a = [(k, n["key"]) for k, n in board.paint_order(self.f)]
        self.assertEqual(a, [(k, n["key"]) for k, n in board.paint_order(self.f)])
        f2 = copy.deepcopy(self.f)
        rnd = random.Random(1)
        for c in f2["clusters"]:
            rnd.shuffle(c["desks"])
            for d in c["desks"]:
                rnd.shuffle(d["workers"])
                rnd.shuffle(d["devices"])
        self.assertEqual(a, [(k, n["key"]) for k, n in board.paint_order(f2)])

    def test_empty(self):
        self.assertEqual(board.paint_order(None), [])


class Sigs(unittest.TestCase):
    def sigs(self, sessions, cfg=LCFG):
        o, l, f = one_floor(sessions, cfg)
        return (board.board_struct_sig(l, f), board.board_style_sig(l, f),
                board.board_live_sig(l, f, o, NOW, node(f, "desk", "s1")["key"]))

    def base(self, **kw):
        w = [sub("a", kw.get("a", "running")), bg("t1", kw.get("t1", "running"))]
        s = S("s1", workers=w, name=kw.get("name"))
        if "tokens" in kw:
            s["totals"]["output"] = kw["tokens"]
        return [s]

    def test_struct(self):
        st, sy, lv = self.sigs(self.base())
        self.assertEqual(st, self.sigs(self.base())[0])
        self.assertEqual(st, self.sigs(self.base(a="done", t1="failed"))[0])
        self.assertEqual(st, self.sigs(self.base(tokens=9999))[0])
        self.assertNotEqual(st, self.sigs(self.base(name="khác"))[0])
        self.assertNotEqual(st, self.sigs(self.base() + [S("s2", started=1001)])[0])
        # +N của bàn
        many = [S("s1", workers=[sub("w%d" % i, started=NOW - 100 + i) for i in range(13)])]
        more = [S("s1", workers=[sub("w%d" % i, started=NOW - 100 + i) for i in range(14)])]
        self.assertNotEqual(self.sigs(many)[0], self.sigs(more)[0])
        # +N bàn của Layout
        cap = {"board_max_desks": 1, "board_max_workers": 12}
        two = self.base() + [S("s2", started=1001)]
        self.assertNotEqual(self.sigs(two, cap)[0], self.sigs(two + [S("s3", started=1002)], cap)[0])

    def test_style(self):
        st, sy, lv = self.sigs(self.base())
        self.assertEqual(sy, self.sigs(self.base(tokens=9999))[1])
        self.assertNotEqual(sy, self.sigs(self.base(a="done"))[1])
        self.assertNotEqual(sy, self.sigs(self.base(t1="failed"))[1])
        self.assertNotEqual(sy, self.sigs([S("s1", state="run", workers=[sub("a"), bg("t1")])])[1])

    def test_style_alert_hidden_worker(self):
        cap = {"board_max_desks": 48, "board_max_workers": 1}
        a = self.sigs([S("s1", workers=[sub("a", started=NOW - 200), sub("b", started=NOW - 100)])], cap)
        b = self.sigs([S("s1", workers=[sub("a", started=NOW - 200), sub("b", "stuck", started=NOW - 100)])], cap)
        self.assertEqual(a[0], b[0])
        self.assertNotEqual(a[1], b[1])

    def hand(self, edit):
        o, l, f = one_floor(self.base())
        l2 = copy.deepcopy(l)
        edit(l2["floors"][0]["clusters"][0])
        return l, f, l2, l2["floors"][0]

    def test_struct_hand(self):
        def cl(c): c["branch"] = "khác"
        def seed(c): c["desks"][0]["seed"] += 1
        def wx(c): c["desks"][0]["workers"][0]["x"] += 1
        def wy(c): c["desks"][0]["workers"][0]["y"] += 1
        def ws(c): c["desks"][0]["workers"][0]["seed"] += 1
        def dx(c): c["desks"][0]["devices"][0]["x"] += 1
        def dy(c): c["desks"][0]["devices"][0]["y"] += 1
        for edit in (cl, seed, wx, wy, ws, dx, dy):
            l, f, l2, f2 = self.hand(edit)
            self.assertNotEqual(board.board_struct_sig(l, f), board.board_struct_sig(l2, f2), edit.__name__)

    def test_style_hand(self):
        def alert(c): c["desks"][0]["alert"]["stuck"] = 3
        def counts(c): c["desks"][0]["more"] = {"n": 1, "counts": {"stuck": 1}}
        def counts0(c): c["desks"][0]["more"] = {"n": 1, "counts": {"done": 1}}
        l, f, l2, f2 = self.hand(counts0)
        _, _, l3, f3 = self.hand(counts)
        self.assertEqual(board.board_struct_sig(l2, f2), board.board_struct_sig(l3, f3))
        self.assertNotEqual(board.board_style_sig(l2, f2), board.board_style_sig(l3, f3))
        l, f, l2, f2 = self.hand(alert)
        self.assertEqual(board.board_struct_sig(l, f), board.board_struct_sig(l2, f2))
        self.assertNotEqual(board.board_style_sig(l, f), board.board_style_sig(l2, f2))
        l2 = copy.deepcopy(l)
        l2["more"]["stuck_desks"] = 1
        self.assertNotEqual(board.board_style_sig(l, f), board.board_style_sig(l2, l2["floors"][0]))

    def test_live_nav(self):
        o, l = build([S("sa", top="/a", root="/a", workers=[sub("y")]), S("sb", top="/b", root="/b")])
        fa = l["floors"][0]
        key = node(fa, "desk", "sa")["key"]
        lv = board.board_live_sig(l, fa, o, NOW, key)
        o2 = copy.deepcopy(o)
        o2["projects"][0]["counts"]["subagent"]["running"] += 1
        self.assertNotEqual(lv, board.board_live_sig(l, fa, o2, NOW, key))
        l2 = copy.deepcopy(l)
        l2["floors"][1]["clusters"][0]["desks"][0]["alert"]["stuck"] = 1
        self.assertNotEqual(lv, board.board_live_sig(l2, l2["floors"][0], o, NOW, key))

    def test_live(self):
        st, sy, lv = self.sigs(self.base())
        self.assertEqual(lv, self.sigs(self.base())[2])
        st2, sy2, lv2 = self.sigs(self.base(tokens=9999))
        self.assertEqual((st, sy), (st2, sy2))
        self.assertNotEqual(lv, lv2)


class Floors(unittest.TestCase):
    def lay(self, a_workers=(), b_workers=()):
        return build([S("sa", top="/a", root="/a", workers=list(a_workers)),
                      S("sb", top="/b", root="/b", workers=list(b_workers))])[1]

    def test_default(self):
        self.assertEqual(board.pick_floor(self.lay())["key"], "p:/a")
        self.assertEqual(board.pick_floor(self.lay(b_workers=[sub("x")]))["key"], "p:/b")
        self.assertEqual(board.pick_floor(self.lay(b_workers=[bg("x")]))["key"], "p:/b")
        self.assertEqual(board.pick_floor(self.lay([sub("y", "stuck")], [sub("x")]))["key"], "p:/a")
        self.assertEqual(board.pick_floor(self.lay([sub("y")], [sub("x", "stuck")]))["key"], "p:/b")

    def test_default_folded_running(self):
        o, l = build([S("sa", top="/a", root="/a", workers=[sub("y", "done")]),
                      S("sb", top="/b", root="/b", workers=[sub("x")])], {"board_max_desks": 48, "board_max_workers": 0})
        self.assertEqual(l["floors"][1]["clusters"][0]["desks"][0]["workers"], [])
        self.assertEqual(board.pick_floor(l)["key"], "p:/b")

    def test_chosen(self):
        l = self.lay(b_workers=[sub("x", "stuck")])
        self.assertEqual(board.pick_floor(l, "p:/a")["key"], "p:/a")
        self.assertEqual(board.pick_floor(l, "p:/gone")["key"], "p:/b")
        self.assertIsNone(board.pick_floor(build([])[1], "p:/a"))
        self.assertIsNone(board.pick_floor(office.office_layout(None, LCFG)))

    def test_alerts(self):
        self.assertEqual(board.floor_alerts(self.lay()), {})
        l = self.lay([sub("y", "stuck"), sub("z", "stuck")], [sub("x")])
        self.assertEqual(board.floor_alerts(l), {"p:/a": 2})

    def test_nav(self):
        o, l = build([S("sa", top="/a", root="/a", workers=[sub("y", "stuck")]),
                      S("sb", top="/b", root="/b", workers=[sub("x"), bg("t")])])
        fa, fb = l["floors"]
        self.assertEqual(board.floor_nav(l, fb, o), (2, 2, "b", cr.counts_text(1, 1, 0), True))
        self.assertEqual(board.floor_nav(l, fa, o), (1, 2, "a", cr.counts_text(1, 0, 1), False))


class Detail(unittest.TestCase):
    def setUp(self):
        self.o, self.l, self.f = one_floor([S("s1", workers=[sub("a"), sub("b", "stuck", dept="qa"), bg("t1")])])

    def det(self, key):
        return board.node_detail(self.l, self.f, key, self.o, NOW)

    def test_desk(self):
        d = node(self.f, "desk", "s1")
        title, rows = self.det(d["key"])
        self.assertEqual(title, "n-s1")
        labels = [t(k) for k in ("cr.f.session", "cr.f.status", "cr.f.model", "cr.f.folder", "cr.f.branch",
                                  "cr.f.elapsed", "cr.f.last", "cr.f.tokens", "cr.f.workers")]
        self.assertEqual([k for k, _ in rows], labels)
        v = dict(rows)
        self.assertEqual(v[t("cr.f.session")], "s1")
        self.assertEqual(v[t("cr.f.tokens")], "30")
        self.assertEqual(v[t("cr.f.elapsed")], cr.fmt_elapsed(NOW - 1000))
        self.assertEqual(v[t("cr.f.workers")], cr.counts_text(2, 1, 1))
        s = self.o["projects"][0]["teams"][0]["sessions"][0]
        self.assertEqual(rows[:-1], cr.session_detail(s, NOW))

    def test_anon_desk(self):
        o, l, f = one_floor([S("s1", name="")])
        self.assertEqual(board.node_detail(l, f, node(f, "desk", "s1")["key"], o, NOW)[0], t("cr.anon_session"))
        self.assertEqual(board.desk_name(node(f, "desk", "s1")), t("cr.anon_session"))

    def test_subagent_same_as_tree(self):
        w = node(self.f, "worker", "b")
        title, rows = self.det(w["key"])
        self.assertEqual(title, "desc b")
        self.assertEqual(rows, cr.subagent_detail(raw_sub(self.o, "b"), NOW))
        tree = next(r for r in cr.flatten(self.o, NOW) if r["kind"] == "subagent" and r["key"].endswith("w:sub:b"))
        self.assertEqual(rows, tree["detail"])
        v = dict(rows)
        self.assertEqual(v[t("cr.f.agent_type")], "les-qa")
        self.assertEqual(v[t("cr.f.dept")], "qa")
        self.assertEqual(v[t("cr.f.status")], t("cr.st.stuck"))
        self.assertEqual(v[t("cr.f.depth")], "1")

    def test_device(self):
        w = node(self.f, "device", "t1")
        title, rows = self.det(w["key"])
        self.assertEqual(title, t("cr.bg_task", id="t1"))
        self.assertEqual([k for k, _ in rows],
                         [t("cr.f.task_id"), t("cr.f.status"), t("cr.f.elapsed"), t("cr.f.tool_use")])
        self.assertEqual(rows, cr.bgtask_detail(raw_sub(self.o, "t1"), NOW))
        tree = next(r for r in cr.flatten(self.o, NOW) if r["kind"] == "bgtask")
        self.assertEqual(rows, tree["detail"])
        self.assertEqual(dict(rows)[t("cr.f.tool_use")], "tb-t1")

    def test_desk_chip(self):
        cfg = {"board_max_desks": 48, "board_max_workers": 1}
        o, l, f = one_floor([S("s1", workers=[sub("a", started=NOW - 300), sub("b", "stuck", started=NOW - 200),
                                             sub("c", "failed", started=NOW - 100)])], cfg)
        d = node(f, "desk", "s1")
        self.assertEqual(d["more"]["n"], 2)
        title, rows = board.node_detail(l, f, board.chip_key(d), o, NOW)
        self.assertEqual(title, t("cr.board.more_detail"))
        self.assertEqual(rows, [(t("cr.st.stuck"), "1"), (t("cr.st.failed"), "1")])

    def test_unknown_chip_label(self):
        o, l, f = one_floor([S("s1")])
        d = node(f, "desk", "s1")
        d["more"] = {"n": 1, "counts": {"unknown": 1}}
        self.assertEqual(board.node_detail(l, f, board.chip_key(d), o, NOW)[1], [(t("cr.unknown"), "1")])

    def test_layout_chip(self):
        cap = {"board_max_desks": 1, "board_max_workers": 12}
        o, l, f = one_floor([S("s1"), S("s2", started=1001, workers=[sub("x", "stuck")]), S("s3", started=1002)], cap)
        title, rows = board.node_detail(l, f, board.MORE_DESKS_KEY, o, NOW)
        self.assertEqual(title, t("cr.board.more_desks", n=2))
        self.assertEqual(rows, [(t("cr.board.more_detail"), "2"), (t("cr.board.cap", n=1), None),
                                (t("cr.board.stuck_desks", n=1), None)])

    def test_chip_key_unique(self):
        o, l, f = one_floor([S("s1"), S("s1/+", started=1001)])
        d1, d2 = node(f, "desk", "s1"), node(f, "desk", "s1/+")
        self.assertEqual(d2["key"], d1["key"] + "/+")
        keys = [d1["key"], d2["key"], board.chip_key(d1), board.chip_key(d2), board.MORE_DESKS_KEY]
        self.assertEqual(len(set(keys)), 5)
        d1["more"] = {"n": 1, "counts": {"done": 1}}
        self.assertEqual(board.node_detail(l, f, d2["key"], o, NOW)[0], "n-s1/+")
        self.assertEqual(board.node_detail(l, f, board.chip_key(d1), o, NOW)[0], t("cr.board.more_detail"))

    def test_title_not_cut_at_24(self):
        o, l, f = one_floor([S("s1", name="x" * 60)])
        d = node(f, "desk", "s1")
        self.assertEqual(board.node_detail(l, f, d["key"], o, NOW)[0], "x" * 60)
        self.assertEqual(len(board.desk_name(d)), 24)

    def test_missing(self):
        self.assertIsNone(self.det("p:/nope"))
        self.assertIsNone(self.det(None))
        self.assertIsNone(board.node_detail(self.l, self.f, node(self.f, "desk", "s1")["key"], None, NOW))
        self.assertIsNone(board.node_detail(self.l, self.f, board.MORE_DESKS_KEY, self.o, NOW))

    def test_hostile(self):
        w = sub("a", dept="qa")
        w["description"] = HOSTILE
        s = S("s1", top="/w/" + HOSTILE, root="/w/proj", branch=HOSTILE, name=HOSTILE, workers=[w, bg(HOSTILE)])
        s["model"] = HOSTILE
        o, l, f = one_floor([s])
        d = node(f, "desk", "s1")
        out = [board.desk_name(d), board.cluster_label(f["clusters"][0]), *board.floor_nav(l, f, o)[2:4]]
        for key in (d["key"], d["workers"][0]["key"], d["devices"][0]["key"]):
            title, rows = board.node_detail(l, f, key, o, NOW)
            out += [title] + [x for r in rows for x in r]
        self.assertTrue(board.node_detail(l, f, d["devices"][0]["key"], o, NOW)[0].startswith(t("cr.bg_task", id="a{b}")))
        for x in out:
            self.assertIsInstance(x, str)
            self.assertTrue(clean(x), repr(x))
        self.assertIn("a{b}c\\d[e]$f%g", board.node_detail(l, f, d["key"], o, NOW)[0])
        self.assertLessEqual(len(board.desk_name(d)), 24)
        # org.py đã làm sạch; Board vẫn sanitize lại khi Layout mang chuỗi độc thô
        raw = board.desk_name(dict(d, name=HOSTILE))
        self.assertTrue(clean(raw), repr(raw))
        self.assertTrue(raw.startswith("a{b}c\\d[e]$f%g h"), repr(raw))
        self.assertTrue(clean(board.cluster_label(dict(f["clusters"][0], top=HOSTILE, branch=HOSTILE))))
        # chuỗi thô ghi thẳng vào org_out và Layout sau org.build: chỉ sanitize của Board chặn được
        pi, ti, si, wi = d["workers"][0]["ref"]
        ws = o["projects"][pi]["teams"][ti]["sessions"][si]["workers"]
        ws[wi]["description"] = HOSTILE
        ws[d["devices"][0]["ref"][3]]["id"] = HOSTILE
        f["name"] = HOSTILE
        raw = [board.node_detail(l, f, d["workers"][0]["key"], o, NOW)[0],
               board.node_detail(l, f, d["devices"][0]["key"], o, NOW)[0], board.floor_nav(l, f, o)[2]]
        for x in raw:
            self.assertTrue(clean(x), repr(x))


class Pure(unittest.TestCase):
    def test_no_io(self):
        tree = ast.parse((ROOT / "pet_tracker" / "board.py").read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                self.assertFalse({a.name.split(".")[0] for a in n.names} & {"os", "subprocess"})
            elif isinstance(n, ast.ImportFrom):
                self.assertNotIn((n.module or "").split(".")[0], {"os", "subprocess"})
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                self.assertNotIn(n.func.id, {"open", "exec", "eval", "__import__"})
            elif isinstance(n, ast.Name):
                self.assertNotIn(n.id, {"os", "subprocess"})


if __name__ == "__main__":
    unittest.main()
