"""Test pet_tracker.viewer_payload (S2b của plan Board + viewer 3D): bộ chuyển đổi Layout -> payload của viewer 3D.

Mã test C1..C16 theo docs/specs/2026-10-30-3d-viewer-design.md, mục "Kiểm thử" (phần C10 về `ViewerServer.start()` và
V29 thuộc S3a-1). Fixture dựng bằng `org.build` qua helper của tests/test_office.py; Layout dựng tay chỉ cho C3, C14, C16.
"""
import ast
import copy
import hashlib
import hmac
import json
import re
import secrets
import unittest
import zlib
from pathlib import Path
from unittest import mock

from pet_tracker import mascots, office, org, theme
from pet_tracker import viewer_payload as vp
from tests.test_office import NOW, S, bg, big_org, org_of, sub

ROOT = Path(__file__).resolve().parents[1]
LCFG = {"board_max_desks": 48, "board_max_workers": 12}
KEY = b"k" * 16
IDS = [m["id"] for m in mascots.all_mascots()]
HEX = re.compile(r"^#[0-9a-f]{6}$")
KINDS = {"project", "team", "session", "subagent", "bgtask", "overflow"}
NODE_KEYS = {"key", "kind", "parent", "x", "y", "w", "h", "state", "label", "sub", "mascot", "alert", "count", "counts"}
TOP_KEYS = {"schema", "bounds", "palette", "legend", "more", "hidden", "nodes", "live"}
PALETTE_KEYS = {"bg", "floor", "team", "line", "fg", "warn", "danger"}
DESK_ST = tuple(office.STATE_STYLE["desk"])
WORKER_ST = tuple(office.STATE_STYLE["worker"])
POISON = ("<img src=x onerror=alert(1)>{ } \\ [ $ %\n\u202eRTL\u200bZW\x07\x9f" + "x" * 10_000)


def pay(layout, o, th=theme.DARK, ids=IDS, key=KEY):
    return vp.viewer_payload(layout, o, th, ids, key)


def lay(o, cfg=LCFG, prev=None):
    return office.office_layout(o, cfg, prev)


def clean(s, n):
    return org._CTRL.sub("", s)[:n]


def by_kind(p, kind):
    return [n for n in p["nodes"] if n["kind"] == kind]


def walk_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_keys(v)


def json_types_only(x):
    if isinstance(x, dict):
        return all(isinstance(k, str) and json_types_only(v) for k, v in x.items())
    if isinstance(x, list):
        return all(json_types_only(v) for v in x)
    return x is None or isinstance(x, (str, int, float, bool))


def lkeys(layout):
    """Đếm nút Layout theo kind của payload."""
    c = dict.fromkeys(KINDS, 0)
    for f in layout["floors"]:
        c["project"] += 1
        for cl in f["clusters"]:
            c["team"] += 1
            for d in cl["desks"]:
                c["session"] += 1
                c["subagent"] += len(d["workers"])
                c["bgtask"] += len(d["devices"])
                c["overflow"] += d["more"]["n"] > 0
    c["overflow"] += layout["more"]["desks"] > 0
    return c


def small_org():
    """Hai project; bàn s1 có 14 subagent (2 vào `more`), 2 stuck, 2 bgtask; s3 (bắt đầu muộn nhất) không vẽ vì trần 3 bàn
    và có subagent stuck."""
    subs1 = [sub("a%d" % i, st="stuck" if i < 2 else "running", dept=("engineering", "qa", "review", "ops")[i % 4])
             for i in range(14)]
    return org_of([
        S("s1", started=1000, top="/w/p1", root="/w/p1", workers=subs1 + [bg("b1"), bg("b2", st="done")]),
        S("s2", started=1001, top="/w/p2/wt", root="/w/p2", state="run", workers=[sub("c1", dept="qa")]),
        S("s4", started=1002, top="/w/p1-wt2", root="/w/p1"),
        S("s3", started=1003, top="/w/p2", root="/w/p2", workers=[sub("z1", st="stuck")]),
    ])


SMALL_CFG = {"board_max_desks": 3, "board_max_workers": 12}


# ---------------------------------------------------------------- Layout dựng tay (C3, C14, C16)
def hdesk(key, x=1, y=1, state="idle", workers=(), devices=(), more=None, alert=0, seed=7):
    return {"key": key, "session_id": "", "slot": 0, "x": x, "y": y, "w": 2, "h": 2, "name": "d", "state": state,
            "seed": seed, "alert": {"stuck": alert}, "ref": [0, 0, 0], "workers": list(workers), "devices": list(devices),
            "more": more or {"n": 0, "counts": {}}}


def hworker(key, x=0, y=0, state="running"):
    return {"key": key, "id": "w", "department": "eng", "slot": 0, "lane": 0, "x": x, "y": y, "state": state,
            "seed": 3, "ref": [0, 0, 0, 0]}


def hdevice(key, x=2, y=1, state="running"):
    return {"key": key, "id": "b", "slot": 0, "x": x, "y": y, "state": state, "ref": [0, 0, 0, 0]}


def hfloor(level, key=None, desks=None, h=10):
    key = key or "p:/r%r" % (level,)
    desks = [hdesk(key + "/t:/x/s:a")] if desks is None else desks
    return {"key": key, "level": level, "name": "f", "root": "/r", "w": 30, "h": h, "ref": [0],
            "clusters": [{"key": key + "/t:/x", "slot": 0, "top": "/x", "branch": "main", "x": 0, "y": 0, "w": 15,
                          "h": 10, "ref": [0, 0], "desks": desks}]}


def hlayout(floors, more=None, styles=None):
    return {"version": 1, "limits": {"desks": 48, "workers": 12, "devices": 3},
            "styles": copy.deepcopy(office.STATE_STYLE) if styles is None else styles, "floors": floors,
            "more": more or {"desks": 0, "stuck_desks": 0}}


class C1Pure(unittest.TestCase):
    def test_no_forbidden_imports(self):
        tree = ast.parse((ROOT / "pet_tracker" / "viewer_payload.py").read_text(encoding="utf-8"))
        bad = {"tkinter", "os", "subprocess", "pathlib", "socket", "http", "threading"}
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                names.add(n.module.split(".")[0])
        self.assertFalse(names & bad, names & bad)

    def test_inputs_not_mutated_and_json_only(self):
        for o, cfg in ((big_org(), LCFG), (small_org(), SMALL_CFG)):
            l = lay(o, cfg)
            th, ids = copy.deepcopy(theme.DARK), list(IDS)
            snap = copy.deepcopy((l, o, th, ids))
            out = pay(l, o, th, ids)
            self.assertEqual((l, o, th, ids), snap)
            self.assertTrue(json_types_only(out))
            json.dumps(out, allow_nan=False)

    def test_bad_numbers_become_null(self):
        o = small_org()
        l = lay(o, SMALL_CFG)
        w = o["projects"][0]["teams"][0]["sessions"][0]["workers"][0]
        w.update(started=float("nan"), last_activity=float("inf"))
        o["projects"][0]["teams"][0]["sessions"][0]["workers"][14]["started"] = float("-inf")
        out = pay(l, o)
        json.dumps(out, allow_nan=False)
        self.assertTrue(any(v.get("started") is None and v.get("last_activity") is None for v in out["live"].values()))
        w["tokens"] = float("inf")
        out = pay(l, o)
        self.assertTrue(all(isinstance(v.get("tokens", 0), int) and v.get("tokens", 0) >= 0
                            for v in out["live"].values()))
        json.dumps(out, allow_nan=False)

    def test_tokens_clamped(self):
        big = 2 ** 53 - 1
        raw = sub("a1")
        raw["tokens"] = 1e308                      # org.build đổi thành int 309 chữ số
        o = org_of([S("s1", workers=[raw, sub("a2")])])
        o["projects"][0]["teams"][0]["sessions"][0]["workers"][1]["tokens"] = 10 ** 5000   # > 4300 chữ số
        out = pay(lay(o), o)
        self.assertEqual(sorted(v["tokens"] for v in out["live"].values()), [big, big])
        json.loads(json.dumps(out, allow_nan=False))


class C2Flatten(unittest.TestCase):
    def check(self, l, out):
        got = dict.fromkeys(KINDS, 0)
        for n in out["nodes"]:
            got[n["kind"]] += 1
        self.assertEqual(got, lkeys(l))
        seen = {}
        want = {"project": None, "team": "project", "session": "team", "subagent": "session", "bgtask": "session"}
        for n in out["nodes"]:
            if n["parent"] is not None:
                self.assertIn(n["parent"], seen)
            pk = None if n["parent"] is None else seen[n["parent"]]
            if n["kind"] == "overflow":
                self.assertIn(pk, (None, "session"))
            else:
                self.assertEqual(pk, want[n["kind"]], n["kind"])
            if n["kind"] in ("subagent", "bgtask"):
                self.assertEqual((n["w"], n["h"]), (1, 1))
            seen[n["key"]] = n["kind"]
            if "alert" in n:
                self.assertTrue(n["kind"] == "session" or (n["kind"] == "overflow" and n["parent"] is None))

    def test_big(self):
        l = lay(big_org())
        self.check(l, pay(l, big_org()))

    def test_overflow(self):
        o = small_org()
        l = lay(o, SMALL_CFG)
        self.assertEqual(l["more"], {"desks": 1, "stuck_desks": 1})
        out = pay(l, o)
        self.check(l, out)
        desk_of = {n["key"]: n for n in by_kind(out, "session")}
        dov = [n for n in by_kind(out, "overflow") if n["parent"] is not None]
        self.assertEqual(len(dov), 1)
        d = desk_of[dov[0]["parent"]]
        self.assertEqual((dov[0]["x"], dov[0]["y"], dov[0]["w"], dov[0]["h"]), (d["x"], d["y"], d["w"], d["h"]))
        self.assertEqual(dov[0]["count"], 2)
        self.assertEqual(sum(dov[0]["counts"].values()), 2)
        self.assertTrue(set(dov[0]["counts"]) <= set(WORKER_ST))
        g = [n for n in by_kind(out, "overflow") if n["parent"] is None]
        self.assertEqual(len(g), 1)
        self.assertNotIn("counts", g[0])
        self.assertEqual((g[0]["count"], g[0]["alert"]), (1, 1))
        self.assertIs(out["nodes"][-1], g[0])
        self.assertEqual(out["more"], {"desks": 1, "stuck_desks": 1})
        kinds = [n["kind"] for n in out["nodes"]]
        # project trước team trước session trước subagent/bgtask/overflow của nó
        self.assertEqual(kinds[:3], ["project", "team", "session"])


class C3Absolute(unittest.TestCase):
    PITCH = office.FLOOR_CLUSTER_COLS * office.CLUSTER_W + vp.FLOOR_GAP

    def xs(self, out):
        return sorted(n["x"] for n in by_kind(out, "project"))

    def test_pitch_constant(self):
        self.assertEqual(vp.FLOOR_GAP, 6)
        self.assertEqual(self.PITCH, 36)

    def test_offsets(self):
        f0 = hfloor(0, desks=[hdesk("p:a/t:/x/s:a", x=6, y=1, workers=[hworker("w", 5, 0)])])
        f1 = hfloor(1, desks=[hdesk("p:b/t:/x/s:a", x=6, y=6, workers=[hworker("w2", 5, 5)],
                                    devices=[hdevice("dv", 7, 6)])])
        f3 = hfloor(3)
        out = pay(hlayout([f0, f1, f3]), None)
        s = [n for n in by_kind(out, "session")]
        self.assertEqual([(n["x"], n["y"]) for n in s], [(6, 1), (self.PITCH + 6, 6), (3 * self.PITCH + 1, 1)])
        self.assertEqual([(n["x"], n["y"]) for n in by_kind(out, "subagent")], [(5, 0), (self.PITCH + 5, 5)])
        self.assertEqual([(n["x"], n["y"]) for n in by_kind(out, "bgtask")], [(self.PITCH + 7, 6)])
        self.assertEqual(self.xs(out), [0, self.PITCH, 3 * self.PITCH])
        # mọi nút của sàn 1 (cả project, team) = toạ độ cục bộ của Layout dựng tay + 36 theo x
        cl, d = f1["clusters"][0], f1["clusters"][0]["desks"][0]
        local = [("project", 0, 0, f1["w"], f1["h"]), ("team", cl["x"], cl["y"], cl["w"], cl["h"]),
                 ("session", d["x"], d["y"], 2, 2), ("subagent", 5, 5, 1, 1), ("bgtask", 7, 6, 1, 1)]
        fkey = next(n["key"] for n in out["nodes"] if n["kind"] == "project" and n["x"] == self.PITCH)
        tree, keys = [], {fkey}
        for n in out["nodes"]:
            if n["key"] == fkey or n["parent"] in keys:
                keys.add(n["key"])
                tree.append((n["kind"], n["x"], n["y"], n["w"], n["h"]))
        self.assertEqual(tree, [(k, self.PITCH + x, y, w, h) for k, x, y, w, h in local])
        # thứ tự đầu vào sai vẫn ra cùng toạ độ
        rev = pay(hlayout([f3, f1, f0]), None)
        self.assertEqual(sorted((n["x"], n["y"], n["kind"]) for n in rev["nodes"]),
                         sorted((n["x"], n["y"], n["kind"]) for n in out["nodes"]))

    def test_bad_levels_no_overlap(self):
        for bad in ("1", -1, True, None, 1.0, 0):
            floors = [hfloor(0, key="p:a"), hfloor(1, key="p:b"), hfloor(bad, key="p:c")]
            out = pay(hlayout(floors), None)
            self.assertEqual(self.xs(out), [0, self.PITCH, 2 * self.PITCH], bad)

    def test_duplicate_level_after_valid(self):
        key = lambda s: vp.hmac.digest(KEY, s.encode(), "sha256").hex()[:16]
        # sàn trùng đứng sau hoặc đứng trước sàn hợp lệ: sàn level 1 duy nhất luôn giữ x = PITCH
        for levels, want in (((0, 1, 0), {"p:a": 0, "p:b": self.PITCH, "p:c": 2 * self.PITCH}),
                             ((0, 0, 1), {"p:a": 0, "p:c": self.PITCH, "p:b": 2 * self.PITCH})):
            floors = [hfloor(lv, key=k) for lv, k in zip(levels, ("p:a", "p:b", "p:c"))]
            x = {n["key"]: n["x"] for n in by_kind(pay(hlayout(floors), None), "project")}
            self.assertEqual({k: x[key(k)] for k in want}, want, levels)

    def test_global_overflow_position(self):
        out = pay(hlayout([hfloor(0), hfloor(3)], more={"desks": 2, "stuck_desks": 0}), None)
        g = out["nodes"][-1]
        self.assertEqual((g["kind"], g["x"], g["y"], g["w"], g["h"]), ("overflow", 4 * self.PITCH, 0, 2, 2))
        self.assertNotIn("alert", g)


class C4Bounds(unittest.TestCase):
    def test_bounds(self):
        for o, cfg in ((big_org(), LCFG), (small_org(), SMALL_CFG)):
            out = pay(lay(o, cfg), o)
            ns = out["nodes"]
            self.assertEqual(out["bounds"], {"w": max(n["x"] + n["w"] for n in ns), "h": max(n["y"] + n["h"] for n in ns)})
            for n in ns:
                self.assertTrue(0 <= n["x"] and n["x"] + n["w"] <= out["bounds"]["w"])
                self.assertTrue(0 <= n["y"] and n["y"] + n["h"] <= out["bounds"]["h"])
        o = small_org()
        g = pay(lay(o, SMALL_CFG), o)["nodes"][-1]
        self.assertEqual(pay(lay(o, SMALL_CFG), o)["bounds"]["w"], g["x"] + g["w"])

    def test_empty(self):
        out = pay(lay(org_of([])), org_of([]))
        self.assertEqual((out["bounds"], out["nodes"]), ({"w": 0, "h": 0}, []))


class C5Stable(unittest.TestCase):
    def pos(self, out):
        return {n["key"]: (n["x"], n["y"]) for n in out["nodes"]}

    def test_prev(self):
        a = S("a", started=1000, top="/p0/t0", root="/p0", workers=[sub("x1"), bg("y1")])
        b = S("b", started=1001, top="/p0/t1", root="/p0", workers=[sub("x2", dept="qa")])
        c = S("c", started=1002, top="/p1/t0", root="/p1", workers=[sub("x3")])
        d = S("d", started=1003, top="/p1/t0", root="/p1")
        e = S("e", started=999, top="/p0/t2", root="/p0", workers=[sub("x4")])   # cụm thứ 3: sàn 0 cao thêm
        steps = [[a, b, c], [a, b, c, d], [a, b, d], [a, b, d, e], [d, e, b, a, c]]
        prev, last = None, None
        for sessions in steps:
            o = org_of(sessions)
            l = lay(o, prev=prev)
            prev = l
            out = pay(l, o)
            cur = self.pos(out)
            if last is not None:
                for k in cur.keys() & last.keys():
                    self.assertEqual(cur[k], last[k], k)
            last = cur
        self.assertEqual(max(n["h"] for n in by_kind(out, "project")), 20)

    def test_same_input_same_nodes(self):
        o = big_org()
        l = lay(o)
        self.assertEqual(pay(l, o)["nodes"], pay(copy.deepcopy(l), copy.deepcopy(o))["nodes"])


class C6Legend(unittest.TestCase):
    def test_real(self):
        out = pay(lay(big_org()), big_org())
        lg = out["legend"]
        self.assertEqual(set(lg), {"desk", "worker"})
        self.assertEqual(tuple(lg["desk"]), DESK_ST)
        self.assertEqual(tuple(lg["worker"]), WORKER_ST)
        for part in ("desk", "worker"):
            for st, row in lg[part].items():
                src = office.STATE_STYLE[part][st]
                self.assertEqual(row, {"color": theme.DARK[src["color"]].lower(), "mood": src["mood"],
                                       "marker": src["marker"]})
                self.assertRegex(row["color"], HEX)
                self.assertIn(row["mood"], mascots.MOODS)
        self.assertEqual(set(out["palette"]), PALETTE_KEYS)
        src = {"bg": "bg", "floor": "surf", "team": "track", "line": "line", "fg": "fg", "warn": "warn",
               "danger": "danger"}
        self.assertEqual(out["palette"], {k: theme.DARK[v].lower() for k, v in src.items()})
        self.assertTrue(all(HEX.match(v) for v in out["palette"].values()))

    def test_idle_invalid_fallback(self):
        th = dict(theme.DARK, ok="javascript:alert(1)", idle="url(x)")
        out = pay(lay(org_of([])), None, th=th)
        self.assertEqual(out["legend"]["worker"]["running"]["color"], "#000000")
        self.assertEqual(out["legend"]["desk"]["idle"]["color"], "#000000")
        self.assertNotIn("url(", json.dumps(out))

    def test_fake_theme(self):
        th = dict(theme.DARK, ok="javascript:alert(1)", warn="#ABCDEF", bg="red")
        del th["mut"]
        out = pay(lay(org_of([])), None, th=th)
        lg = out["legend"]["worker"]
        self.assertEqual(lg["running"]["color"], th["idle"])
        self.assertEqual(lg["done"]["color"], th["idle"])
        self.assertEqual(lg["stuck"]["color"], "#abcdef")
        self.assertEqual(out["palette"]["bg"], th["idle"])
        self.assertNotIn("javascript", json.dumps(out))


class C7Labels(unittest.TestCase):
    def test_poison(self):
        o = org_of([S("s1", top="/w/p", root="/w/p", workers=[sub("a1")])])
        p = o["projects"][0]
        p["name"] = POISON
        p["teams"][0]["branch"] = POISON
        s = p["teams"][0]["sessions"][0]
        s["name"] = POISON
        s["workers"][0]["department"] = POISON
        s["workers"][0]["description"] = POISON
        l = lay(o)
        out = pay(l, o)
        for n in out["nodes"]:
            self.assertLessEqual(len(n["label"]), 60)
            self.assertLessEqual(len(n["sub"]), 120)
            self.assertFalse(org._CTRL.search(n["label"] + n["sub"]))
        k = {n["kind"]: n for n in out["nodes"]}
        self.assertEqual(k["project"]["label"], clean(POISON, 60))
        self.assertEqual(k["team"]["sub"], clean(POISON, 120))
        self.assertEqual(k["session"]["label"], clean(POISON, 60))
        self.assertEqual(k["subagent"]["label"], clean(POISON, 60))
        self.assertEqual(k["subagent"]["sub"], clean(POISON, 120))
        self.assertTrue(k["subagent"]["sub"].startswith("<img src=x onerror=alert(1)>{ } \\ [ $ %RTLZW"))

    def test_surrogate_invisible_clean_then_cut(self):
        o = org_of([S("s1", workers=[sub("a1")])])
        s = o["projects"][0]["teams"][0]["sessions"][0]
        s["name"] = "a\ud800b\udfffc\u00add\u180ee\u2060f\u2064g\ufff9h\U000e0001i\U000e007fj"
        s["workers"][0]["description"] = "\x01" * 1000 + "\u2061" * 1000 + "visible"   # sạch rồi mới cắt
        out = pay(lay(o), o)
        self.assertEqual(by_kind(out, "session")[0]["label"], "abcdefghij")
        self.assertEqual(by_kind(out, "subagent")[0]["sub"], "visible")
        json.dumps(out, ensure_ascii=False).encode("utf-8")

    def test_surrogate_in_layout_key(self):
        # E7: khoá Layout chứa surrogate lẻ vẫn băm được, đúng công thức surrogatepass
        o = org_of([S("s\ud800x", top="/w/\udc80p", root="/w/\udc80p", workers=[sub("a1")])])
        l = lay(o)
        k = l["floors"][0]["clusters"][0]["desks"][0]["key"]
        self.assertIn("\ud800", k)
        want = hmac.new(KEY, k.encode("utf-8", "surrogatepass"), hashlib.sha256).hexdigest()[:16]
        self.assertEqual(by_kind(pay(l, o), "session")[0]["key"], want)

    def test_sid_prefix_name_dropped(self):
        # claude_data đặt tên sid[:8] cho phiên chưa có tên: viewer không đưa phần session id ra trình duyệt
        o = org_of([S("abcdef0123456789", name="abcdef01"), S("s2", started=2000, name="real")])
        labels = sorted(n["label"] for n in by_kind(pay(lay(o), o), "session"))
        self.assertEqual(labels, ["", "real"])

    def test_sub_from_ref(self):
        o = org_of([S("s1", workers=[sub("a1"), bg("b1"), sub("a2")])])
        l = lay(o)
        out = pay(l, o)
        self.assertEqual(sorted(n["sub"] for n in by_kind(out, "subagent")), ["desc a1", "desc a2"])
        self.assertEqual([(n["label"], n["sub"]) for n in by_kind(out, "bgtask")], [("", "")])
        self.assertEqual([(n["label"], n["sub"]) for n in by_kind(out, "session")], [("n-s1", "")])
        for bad in ([0, 0, 0, 1], [0, 0, 0, 99], [9, 0, 0, 0], [0, 0, 0, -1], [0, 0, 0, "0"], [0, 0, 0, True],
                    [0, 0, 0], "0000", None, [0, 0, 0, 0.0]):
            l2 = copy.deepcopy(l)
            for w in l2["floors"][0]["clusters"][0]["desks"][0]["workers"]:
                w["ref"] = bad
            self.assertTrue(all(n["sub"] == "" for n in by_kind(pay(l2, o), "subagent")), bad)
        self.assertTrue(all(n["sub"] == "" for n in by_kind(pay(l, None), "subagent")))
        self.assertTrue(all(n["sub"] == "" for n in by_kind(pay(l, {"projects": [{"teams": 5}]}), "subagent")))

    def test_team_label(self):
        o = org_of([S("s1")])
        l = lay(o)
        cl = l["floors"][0]["clusters"][0]
        for top, want in (("/a/b/wt1/", "wt1"), ("C:\\x\\wt2\\", "wt2"), ("C:\\x/wt3", "wt3"), ("/", "/"),
                          ("plain", "plain"), ("", "")):
            cl["top"] = top
            team = by_kind(pay(l, o), "team")[0]
            self.assertEqual(team["label"], want, top)
        cl["branch"] = None
        self.assertEqual(by_kind(pay(l, o), "team")[0]["sub"], "")


class C8Mascot(unittest.TestCase):
    def test_mascot(self):
        self.assertTrue(IDS)
        o = org_of([S("same", top="/w/a", root="/w/r", workers=[sub("a1"), sub("a2", dept="qa"), bg("b")]),
                    S("same", top="/w/b", root="/w/r", workers=[sub("a3")])])
        l = lay(o)
        out = pay(l, o)
        desks = by_kind(out, "session")
        self.assertEqual(len(desks), 2)
        self.assertEqual(desks[0]["mascot"], desks[1]["mascot"])
        ldesks = [d for f in l["floors"] for c in f["clusters"] for d in c["desks"]]
        self.assertEqual(desks[0]["mascot"], IDS[office.mascot_index(ldesks[0]["seed"], len(IDS))])
        subs = {n["label"]: n["mascot"] for n in by_kind(out, "subagent")}
        eng = [n["mascot"] for n in by_kind(out, "subagent") if n["label"] == "engineering"]
        self.assertEqual(len(eng), 2)
        self.assertEqual(eng[0], eng[1])
        self.assertEqual(subs["qa"], IDS[office.mascot_index(zlib.crc32(b"qa") & 0xFFFFFFFF, len(IDS))])
        self.assertTrue(all("mascot" not in n for n in out["nodes"] if n["kind"] not in ("session", "subagent")))
        self.assertTrue(all(n["mascot"] in IDS for n in out["nodes"] if "mascot" in n))
        self.assertTrue(all("mascot" not in n for n in pay(l, o, ids=[])["nodes"]))


class C9Allowlist(unittest.TestCase):
    SID, ROOTP, TOPP = "sess-SECRET-77", "/home/user/secret-root", "/home/user/secret-root-wt/feature-x"

    def fixture(self):
        o = org_of([S(self.SID, started=1000, top=self.TOPP, root=self.ROOTP, name="Desk A",
                      workers=[sub("a%d" % i, dept=("engineering", "qa", "review", "ops")[i % 4]) for i in range(14)]
                      + [bg("b1"), bg("b2", st="done")]),
                    S("other-XYZ-1", started=1001, top=self.ROOTP, root=self.ROOTP, name="Desk B",
                      workers=[sub("q", st="stuck")])])
        cfg = {"board_max_desks": 1, "board_max_workers": 12}
        return o, lay(o, cfg)

    def test_allowlist(self):
        o, l = self.fixture()
        out = pay(l, o)
        self.assertEqual(set(out), TOP_KEYS)
        self.assertEqual(set(out["bounds"]), {"w", "h"})
        self.assertEqual(set(out["palette"]), PALETTE_KEYS)
        self.assertEqual(set(out["legend"]), {"desk", "worker"})
        self.assertTrue(set(out["legend"]["desk"]) <= set(DESK_ST))
        self.assertTrue(set(out["legend"]["worker"]) <= set(WORKER_ST))
        for part in out["legend"].values():
            for row in part.values():
                self.assertEqual(set(row), {"color", "mood", "marker"})
        self.assertEqual(set(out["more"]), {"desks", "stuck_desks"})
        self.assertEqual({n["kind"] for n in out["nodes"]}, KINDS)
        for n in out["nodes"]:
            self.assertTrue(set(n) <= NODE_KEYS, set(n) - NODE_KEYS)
            self.assertIn(n["kind"], KINDS)
            if "counts" in n:
                self.assertTrue(set(n["counts"]) <= set(WORKER_ST))
        lkeys_ = {n["key"] for n in out["nodes"] if n["kind"] in ("subagent", "bgtask")}
        self.assertTrue(out["live"])
        self.assertTrue(set(out["live"]) <= lkeys_)
        for k, v in out["live"].items():
            self.assertTrue(set(v) <= {"tokens", "started", "last_activity"})
        self.assertFalse(set(walk_keys(out)) & {"__proto__", "constructor", "prototype", "hasOwnProperty",
                                                 "ref", "seed", "limits", "session_id", "root", "top"})
        js = json.dumps(out)
        for secret in (self.SID, "other-XYZ-1", self.ROOTP, self.TOPP, "p:", "/s:", "/t:"):
            self.assertNotIn(secret, js)


class C10Key(unittest.TestCase):
    def test_key(self):
        o = big_org()
        l = lay(o)
        a = pay(l, o)
        keys = [n["key"] for n in a["nodes"]]
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{16}", k) for k in keys))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(a, pay(l, o))
        b = pay(l, o, key=b"z" * 16)
        self.assertTrue(set(keys).isdisjoint(n["key"] for n in b["nodes"]))
        # parent dùng cùng cách: cấu trúc cha-con giống hệt
        idx_a = {n["key"]: i for i, n in enumerate(a["nodes"])}
        idx_b = {n["key"]: i for i, n in enumerate(b["nodes"])}
        self.assertEqual([None if n["parent"] is None else idx_a[n["parent"]] for n in a["nodes"]],
                         [None if n["parent"] is None else idx_b[n["parent"]] for n in b["nodes"]])
        f = l["floors"][0]
        want = __import__("hmac").new(KEY, f["key"].encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        self.assertEqual(a["nodes"][0]["key"], want)
        rk = secrets.token_bytes(16)
        self.assertNotEqual(pay(l, o, key=rk)["nodes"][0]["key"], hashlib.sha256(f["key"].encode()).hexdigest()[:16])

    def test_key_secret_checked(self):
        l = lay(org_of([S("s1")]))
        for bad in (b"", b"k" * 15, "k" * 16, bytearray(16), None):
            with self.assertRaises(ValueError):
                pay(l, None, key=bad)
        pay(l, None, key=b"k" * 32)

    def test_overflow_keys(self):
        o = small_org()
        l = lay(o, SMALL_CFG)
        out = pay(l, o)
        h = lambda s: __import__("hmac").new(KEY, s.encode(), hashlib.sha256).hexdigest()[:16]
        ov = by_kind(out, "overflow")
        d = next(d for f in l["floors"] for c in f["clusters"] for d in c["desks"] if d["more"]["n"])
        self.assertEqual({n["key"] for n in ov}, {h(d["key"] + "/more"), h("more:desks")})

    def test_duplicate_layout_keys(self):
        o = org_of([S("dup", started=1000), S("dup", started=1001)])
        l = lay(o)
        lk = sorted(d["key"] for d in l["floors"][0]["clusters"][0]["desks"])
        self.assertEqual(lk[1], lk[0] + "#1")
        ks = [n["key"] for n in by_kind(pay(l, o), "session")]
        self.assertEqual(len(set(ks)), 2)

    def test_collision_keeps_first(self):
        o = org_of([S("s1", started=1000, name="first"), S("s2", started=1001, name="second")])
        l = lay(o)
        real = vp.hmac.digest

        def fake(key, msg, digest):
            return real(key, b"same" if b"/s:s" in msg else msg, digest)

        with mock.patch.object(vp.hmac, "digest", fake):
            out = pay(l, o)
        s = by_kind(out, "session")
        self.assertEqual([n["label"] for n in s], ["first"])
        self.assertEqual(len(out["nodes"]), 3)


class C11Alert(unittest.TestCase):
    def test_alert(self):
        o = org_of([S("s1", started=1000, workers=[sub("a", st="stuck"), sub("b", st="stuck"), sub("c")]),
                    S("s2", started=1001, top="/w/q", root="/w/q", workers=[sub("d")])])
        l = lay(o)
        out = pay(l, o)
        al = {n["label"]: n.get("alert") for n in by_kind(out, "session")}
        self.assertEqual(al, {"n-s1": 2, "n-s2": None})
        for bad in (-3, "2", None, True, 2.5, float("nan")):
            l2 = copy.deepcopy(l)
            for f in l2["floors"]:
                f["clusters"][0]["desks"][0]["alert"] = {"stuck": bad}
            self.assertTrue(all("alert" not in n for n in pay(l2, o)["nodes"]), bad)
        l2 = copy.deepcopy(l)
        l2["floors"][0]["clusters"][0]["desks"][0]["alert"] = "x"
        self.assertTrue(all("alert" not in n for n in by_kind(pay(l2, o), "session")))

    def test_global_overflow_alert(self):
        o = small_org()
        g = pay(lay(o, SMALL_CFG), o)["nodes"][-1]
        self.assertEqual(g["alert"], 1)
        l = lay(o, SMALL_CFG)
        for bad in (0, -1, "1", None):
            l["more"]["stuck_desks"] = bad
            self.assertNotIn("alert", pay(l, o)["nodes"][-1])


class C12Cap(unittest.TestCase):
    def test_cap(self):
        o = big_org(projects=2, teams=7, desks=74, subs=12, tasks=3)
        l = lay(o, {"board_max_desks": 200, "board_max_workers": 12})
        self.assertEqual(sum(lkeys(l).values()), 1200)
        self.assertEqual(vp.MAX_NODES, 1000)
        out = pay(l, o)
        with mock.patch.object(vp, "MAX_NODES", 10 ** 6):
            full = pay(l, o)
        self.assertEqual((len(out["nodes"]), out["hidden"]), (1000, 200))
        self.assertEqual((len(full["nodes"]), full["hidden"]), (1200, 0))
        self.assertEqual(out["nodes"], full["nodes"][:1000])
        seen = set()
        for n in out["nodes"]:
            self.assertTrue(n["parent"] is None or n["parent"] in seen)
            seen.add(n["key"])
        self.assertEqual(out["more"], full["more"])
        self.assertEqual(out["live"], {k: v for k, v in full["live"].items() if k in seen})


class C13Live(unittest.TestCase):
    def test_live(self):
        o = org_of([S("s1", workers=[sub("a1"), bg("b1")])])
        l = lay(o)
        out = pay(l, o)
        s, b = by_kind(out, "subagent")[0], by_kind(out, "bgtask")[0]
        self.assertEqual(out["live"][s["key"]], {"tokens": 5, "started": NOW - 100, "last_activity": NOW - 10})
        self.assertEqual(out["live"][b["key"]], {"started": NOW - 50})
        w = o["projects"][0]["teams"][0]["sessions"][0]["workers"]
        w[0].update(tokens=-4, started="x", last_activity=True)
        w[1]["started"] = [1]
        out2 = pay(l, o)
        self.assertEqual(out2["live"][s["key"]], {"tokens": 0, "started": None, "last_activity": None})
        self.assertEqual(out2["live"][b["key"]], {"started": None})
        w[0].update(tokens=99999, last_activity=NOW)
        self.assertEqual(pay(l, o)["nodes"], out["nodes"])


class C14Errors(unittest.TestCase):
    def test_value_error(self):
        for bad in (None, [], "x", 1, {}, hlayout([]) | {"version": 2}, hlayout([]) | {"version": "1"}):
            with self.assertRaises(ValueError):
                pay(bad, None)

    def test_bad_org_no_error(self):
        l = hlayout([hfloor(0)])
        for o in (None, [], "x", {"projects": "x"}, {"projects": [None]}, {"projects": [{"teams": [{"sessions": 1}]}]}):
            json.dumps(pay(l, o), allow_nan=False)


class C15Empty(unittest.TestCase):
    def test_empty(self):
        out = pay(office.office_layout(None, LCFG), None)
        self.assertEqual(out["schema"], 1)
        self.assertEqual((out["nodes"], out["bounds"], out["hidden"], out["live"]), ([], {"w": 0, "h": 0}, 0, {}))
        self.assertEqual(out["more"], {"desks": 0, "stuck_desks": 0})
        self.assertEqual((tuple(out["legend"]["desk"]), tuple(out["legend"]["worker"])), (DESK_ST, WORKER_ST))
        self.assertEqual(set(out["palette"]), PALETTE_KEYS)
        json.dumps(out, allow_nan=False)


class C16Enum(unittest.TestCase):
    BAD = ("constructor", "__proto__", "toString", "run ", None, 5, "RUN", ["run"])

    def test_states(self):
        for bad in self.BAD:
            d = hdesk("p:a/t:/x/s:a", state=bad, workers=[hworker("w", state=bad)], devices=[hdevice("v", state=bad)])
            out = pay(hlayout([hfloor(0, desks=[d])]), None)
            st = {n["kind"]: n["state"] for n in out["nodes"]}
            self.assertEqual(st, {"project": None, "team": None, "session": "idle", "subagent": "unknown",
                                  "bgtask": "unknown"}, bad)
        d = hdesk("p:a/t:/x/s:a", state="wait", workers=[hworker("w", state="failed")], devices=[hdevice("v", state="ended")])
        st = {n["kind"]: n["state"] for n in pay(hlayout([hfloor(0, desks=[d])]), None)["nodes"]}
        self.assertEqual((st["session"], st["subagent"], st["bgtask"]), ("wait", "failed", "ended"))

    def test_styles_and_counts(self):
        styles = copy.deepcopy(office.STATE_STYLE)
        styles["desk"]["constructor"] = {"color": "run", "mood": "run", "marker": None}
        styles["worker"]["__proto__"] = {"color": "run", "mood": "run", "marker": None}
        styles["__proto__"] = {}
        styles["desk"]["run"] = {"color": "run", "mood": "../../etc", "marker": "javascript:"}
        styles["worker"]["stuck"] = {"color": ["x"], "mood": None, "marker": "ring"}
        del styles["worker"]["done"]
        d = hdesk("p:a/t:/x/s:a", more={"n": 6, "counts": {"__proto__": 2, "constructor": 1, "running": 2, "stuck": -5,
                                                           "done": "x", "failed": True, "unknown": 1}})
        out = pay(hlayout([hfloor(0, desks=[d])], styles=styles), None)
        lg = out["legend"]
        self.assertEqual(tuple(lg["desk"]), DESK_ST)
        self.assertEqual(tuple(lg["worker"]), WORKER_ST)
        self.assertEqual(lg["desk"]["run"], {"color": theme.DARK["run"], "mood": "idle", "marker": None})
        self.assertEqual(lg["worker"]["stuck"], {"color": theme.DARK["idle"], "mood": "idle", "marker": "ring"})
        self.assertEqual(lg["worker"]["done"], {"color": theme.DARK["idle"], "mood": "idle", "marker": None})
        ov = by_kind(out, "overflow")[0]
        self.assertEqual(ov["count"], 6)
        self.assertEqual(ov["counts"], {"running": 2, "unknown": 4})
        self.assertNotIn('"__proto__"', json.dumps(out))
        self.assertFalse(set(walk_keys(out)) & {"__proto__", "constructor"})


if __name__ == "__main__":
    unittest.main()
