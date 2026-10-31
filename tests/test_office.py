"""Test pet_tracker.office (S1 của plan Board + viewer 3D): Layout thuần, không Tk, không đĩa ngoài file của repo.

Mã test T-L1..T-L17, T-S1 theo docs/specs/2026-10-30-board-2-5d-design.md, mục "Kiểm thử".
Fixture luôn dựng bằng `org.build(sessions_thô, cfg, now)` (worker thô có `agent_type`), không dựng tay dạng đầu ra,
trừ T-S1/T-L15/T-L2 cần ép state ngoài enum (sửa đầu ra thật của org.build tại chỗ).
"""
import ast
import copy
import json
import math
import platform
import random
import sys
import threading
import time
import unittest
import zlib
from pathlib import Path

from pet_tracker import config, mascots, office, org, theme

ROOT = Path(__file__).resolve().parents[1]
NOW = 10_000.0
CFG = {"agent_prefixes": ["les-"], "stuck_after_sec": 120}
LCFG = {"board_max_desks": 48, "board_max_workers": 12}
DEPTS = ("engineering", "qa", "review", "ops")
ENUM_W = ("running", "stuck", "done", "failed", "killed", "ended", "unknown")
LANE_CELLS = (((0, 0), (1, 0), (2, 0)), ((3, 0), (3, 1), (3, 2)), ((3, 3), (2, 3), (1, 3)), ((0, 3), (0, 2), (0, 1)))
DEVICE_CELLS = ((1, 0), (0, 1), (1, 1))


# ---------------------------------------------------------------- fixture thô -> org.build
def S(sid, started=1000.0, top="/w/proj", root="/w/proj", branch="main", state="idle", workers=(), name=None):
    return {"session_id": sid, "started_at": float(started), "cwd": top, "name": "n-" + sid if name is None else name,
            "status": "busy", "state": state, "model": "opus", "last_activity": NOW - 5,
            "git": {"top": top, "common": root + "/.git", "branch": branch},
            "totals": {"input": 10, "output": 20, "cache_create": 0, "cache_read": 0, "messages": 3},
            "agent_calls": [], "workers": list(workers)}


def sub(id, st="running", dept="engineering", started=None, last=None, agent_type=None):
    w = {"kind": "subagent", "id": id, "tool_use_id": "tu-" + id, "agent_type": agent_type or "les-" + dept,
         "description": "desc " + id, "depth": 1, "finished": False, "notif_status": None, "mtime": NOW - 10,
         "started": NOW - 100 if started is None else started, "last_activity": NOW - 10 if last is None else last,
         "tokens": 5, "open_tools": 0, "agent_calls": []}
    if st == "stuck":
        w["mtime"] = NOW - 1000
        if last is None:
            w["last_activity"] = NOW - 1000
    elif st in ("done", "failed", "killed"):
        w["notif_status"] = "completed" if st == "done" else st
    elif st != "running":
        raise ValueError(st)
    return w


def bg(id, st="running", started=None):
    w = {"kind": "bgtask", "id": id, "tool_use_id": "tb-" + id, "started": NOW - 50 if started is None else started,
         "status": None}
    if st in ("done", "failed", "killed"):
        w["status"] = "completed" if st == "done" else st
    elif st == "ended":
        w["started"] = 500.0  # < started_at của session (1000) nên org.build cho "ended"
    elif st != "running":
        raise ValueError(st)
    return w


def org_of(sessions, now=NOW):
    return org.build(list(sessions), CFG, now)


def lay(sessions_or_org, cfg=LCFG, prev=None, now=NOW):
    o = sessions_or_org if isinstance(sessions_or_org, dict) else org_of(sessions_or_org, now)
    return office.office_layout(o, cfg, prev)


# ---------------------------------------------------------------- fixture lớn (T-L12 và, sau này, Đ2)
def big_org(projects=2, teams=8, desks=48, subs=12, tasks=3, now=NOW):
    """`org.build` của session thô tổng hợp: `desks` session chia vòng quanh `projects` x `teams` team (tối đa 6 mỗi
    team), mỗi session `subs` subagent (phòng ban lấy vòng từ 4 `agent_type` `les-*`, state lấy vòng) và `tasks` bgtask."""
    if projects * teams * 6 < desks:
        raise ValueError("quá 6 session mỗi team")
    states = ("running", "stuck", "done", "failed", "killed")
    sessions = []
    for i in range(desks):
        pi, ti = (i % projects), (i // projects) % teams
        ws = []
        for j in range(subs):
            st = states[j % len(states)]
            ws.append({"kind": "subagent", "id": "a%d-%d" % (i, j), "tool_use_id": "tu%d-%d" % (i, j),
                       "agent_type": "les-" + DEPTS[j % len(DEPTS)], "description": "d", "depth": 1,
                       "finished": False, "notif_status": None if st in ("running", "stuck")
                       else ("completed" if st == "done" else st),
                       "mtime": now - (10 if st == "running" else 1000), "started": now - 2000 + j,
                       "last_activity": now - (10 if st == "running" else 1000), "tokens": j, "open_tools": 0,
                       "agent_calls": []})
        for j in range(tasks):
            ws.append({"kind": "bgtask", "id": "b%d-%d" % (i, j), "tool_use_id": "tb%d-%d" % (i, j),
                       "started": now - 50, "status": None if j % 2 == 0 else "completed"})
        top = "/p%d/wt%d" % (pi, ti)
        sessions.append(S("s%d" % i, started=1000.0 + i, top=top, root="/p%d" % pi, branch="b%d" % ti, workers=ws))
    return org.build(sessions, CFG, now)


def org_none(o, sids=(), wids=(), field="started"):
    """Đặt None tại chỗ cho `started_at` của session trong `sids` và `field` của worker trong `wids` (org.build không
    sinh None ở đây)."""
    for p in o["projects"]:
        for t in p["teams"]:
            for ss in t["sessions"]:
                if ss["session_id"] in sids:
                    ss["started_at"] = None
                for w in ss["workers"]:
                    if w["id"] in wids:
                        w[field] = None
    return o


# ---------------------------------------------------------------- tiện ích đọc Layout
def all_desks(l):
    return [(f, c, d) for f in l["floors"] for c in f["clusters"] for d in c["desks"]]


def by_sid(l):
    return {d["session_id"]: d for _, _, d in all_desks(l)}


def dpos(l):
    return {d["key"]: (f["level"], c["slot"], d["slot"], d["x"], d["y"]) for f, c, d in all_desks(l)}


def wpos(d):
    return {w["id"]: (w["lane"], w["slot"], w["x"], w["y"]) for w in d["workers"]}


def strip_ref(x):
    if isinstance(x, dict):
        return {k: strip_ref(v) for k, v in x.items() if k != "ref"}
    if isinstance(x, list):
        return [strip_ref(v) for v in x]
    return x


def all_keys(l):
    ks = []
    for f in l["floors"]:
        ks.append(f["key"])
        for c in f["clusters"]:
            ks.append(c["key"])
            for d in c["desks"]:
                ks.append(d["key"])
                ks += [w["key"] for w in d["workers"]] + [v["key"] for v in d["devices"]]
    return ks


def only_json(x):
    if isinstance(x, dict):
        return all(isinstance(k, str) and only_json(v) for k, v in x.items())
    if isinstance(x, list):
        return all(only_json(v) for v in x)
    return x is None or type(x) in (str, int, bool)


def rich_sessions(seed=1):
    """3 project, vài team, 2-6 session, worker nhiều phòng ban/state: không khoá trùng, thời gian khác nhau."""
    rnd = random.Random(seed)
    out, n = [], 0
    for p in ("a", "b", "c"):
        for t in ("x", "y", "z"):
            for _ in range(rnd.randint(2, 6)):
                n += 1
                ws = []
                for j in range(rnd.randint(0, 20)):
                    ws.append(sub("w%d-%d" % (n, j), st=rnd.choice(("running", "stuck", "done", "failed", "killed")),
                                  dept=rnd.choice(DEPTS + ("docs", "infra")), started=NOW - 5000 + n * 50 + j,
                                  last=NOW - rnd.randint(1, 4000)))
                for j in range(rnd.randint(0, 5)):
                    ws.append(bg("t%d-%d" % (n, j), st=rnd.choice(("running", "done", "failed", "killed", "ended")),
                                 started=None if rnd.random() < 0.5 else 600.0 + n * 7 + j))
                out.append(S("s%d" % n, started=1000.0 + rnd.randint(0, 5000) + n / 1000, top="/%s/%s" % (p, t),
                             root="/" + p, branch="br-" + t, state=rnd.choice(("idle", "run", "wait", "done", "error")),
                             workers=ws))
    return out


def shuffle_org(o, rnd):
    o = copy.deepcopy(o)
    rnd.shuffle(o["projects"])
    for p in o["projects"]:
        rnd.shuffle(p["teams"])
        for t in p["teams"]:
            rnd.shuffle(t["sessions"])
            for s in t["sessions"]:
                rnd.shuffle(s["workers"])
    return o


def check_geometry(tc, l):
    for f in l["floors"]:
        used = set()
        for c in f["clusters"]:
            for d in c["desks"]:
                block = {(d["x"] + i, d["y"] + j) for i in range(2) for j in range(2)}
                tc.assertTrue(all(0 <= x < f["w"] and 0 <= y < f["h"] for x, y in block), (f["key"], d["key"]))
                tc.assertFalse(block & used, d["key"])
                used |= block
                cells = [(v["x"], v["y"]) for v in d["devices"]]
                tc.assertEqual(len(set(cells)), len(cells))
                for cell in cells:
                    tc.assertIn(cell, block)
                    tc.assertNotEqual(cell, (d["x"], d["y"]))
        for c in f["clusters"]:
            for d in c["desks"]:
                for w in d["workers"]:
                    cell = (w["x"], w["y"])
                    tc.assertTrue(0 <= cell[0] < f["w"] and 0 <= cell[1] < f["h"])
                    tc.assertNotIn(cell, used, w["key"])
                    used.add(cell)


def check_promises(tc, l):
    lv = [f["level"] for f in l["floors"]]
    tc.assertEqual(lv, sorted(lv))
    tc.assertEqual(len(set(lv)), len(lv))
    lim = l["limits"]["desks"]
    for f in l["floors"]:
        tc.assertIs(type(f["level"]), int)
        tc.assertTrue(0 <= f["level"] <= lim - 1, f["level"])
        tc.assertEqual(f["w"], office.FLOOR_CLUSTER_COLS * office.CLUSTER_W)
        tc.assertEqual(f["w"], 30)
        tc.assertEqual(f["h"] % 10, 0)
        tc.assertTrue(10 <= f["h"] <= office.max_floor_h(lim), (f["h"], lim))


# ================================================================ T-L1
class PurityTest(unittest.TestCase):
    def test_json_roundtrip_only_lists(self):
        o = org_of(rich_sessions())
        l1 = office.office_layout(o, LCFG)
        l2 = office.office_layout(o, LCFG, l1)
        for l in (l1, l2, office.office_layout(None, LCFG)):
            self.assertEqual(json.loads(json.dumps(l)), l)
            self.assertTrue(only_json(l))

    def test_ast_imports(self):
        tree = ast.parse((ROOT / "pet_tracker" / "office.py").read_text(encoding="utf-8"))
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                names.add((n.module or "").split(".")[0])
        self.assertFalse(names & {"tkinter", "os", "subprocess", "pathlib"}, names)

    def test_inputs_not_mutated(self):
        o = org_of(rich_sessions())
        cfg = dict(LCFG)
        prev = office.office_layout(o, cfg)
        o2 = shuffle_org(o, random.Random(3))
        snap = (copy.deepcopy(o2), copy.deepcopy(cfg), copy.deepcopy(prev))
        office.office_layout(o2, cfg, prev)
        self.assertEqual((o2, cfg, prev), snap)


# ================================================================ T-L2
class RobustTest(unittest.TestCase):
    EMPTY_KEYS = {"version", "limits", "styles", "floors", "more"}

    def assert_empty(self, l):
        self.assertEqual(set(l), self.EMPTY_KEYS)
        self.assertEqual(l["version"], 1)
        self.assertEqual(l["floors"], [])
        self.assertEqual(l["more"], {"desks": 0, "stuck_desks": 0})
        self.assertEqual(l["limits"], {"desks": 48, "workers": 12, "devices": 3})

    def test_bad_org_gives_empty_layout(self):
        for bad in (None, {}, {"projects": 5}, {"projects": None}, [], "x", 5, {"projects": "abc"}):
            self.assert_empty(office.office_layout(bad, LCFG))
        self.assert_empty(office.office_layout({"projects": []}, LCFG))

    def test_broken_branches_dropped_no_raise(self):
        bad = {"projects": [
            5, None, "x", {"teams": 5}, {"root": "/r", "teams": [
                7, {"sessions": 3}, {"top": "/r", "sessions": [
                    "x", None,
                    {"session_id": 5, "workers": 9},
                    {"session_id": "\ud800", "started_at": float("nan"), "state": ["x"], "workers": []},
                    {"session_id": "ok", "started_at": "yesterday", "state": 12, "name": 7, "workers": [
                        None, 3, {"kind": "zzz"}, {"kind": "subagent", "state": None, "id": 5, "department": None},
                        {"kind": "bgtask", "state": ["x"], "started": "q"},
                        {"kind": "subagent", "state": "weird", "id": "w", "department": "d", "started": True,
                         "last_activity": "x"}]}]}]},
        ]}
        l = office.office_layout(bad, LCFG)
        self.assertEqual(json.loads(json.dumps(l)), l)
        d = by_sid(l)["ok"]
        self.assertEqual(d["state"], "idle")
        self.assertEqual(d["name"], "")
        self.assertEqual({w["state"] for w in d["workers"]}, {"unknown"})
        self.assertEqual([v["state"] for v in d["devices"]], ["unknown"])
        self.assertIn("", by_sid(l))  # session_id sai kiểu hoặc thiếu: bàn vẽ được, id rỗng
        check_geometry(self, l)

    def test_bad_cfg_and_prev(self):
        o = org_of([S("a"), S("b", started=500)])
        base = office.office_layout(o, LCFG)
        for cfg in (None, {}, "x", 5, [], {"board_max_desks": "x", "board_max_workers": None}):
            self.assertEqual(office.office_layout(o, cfg), base)
        for prev in (5, "x", [], {}, {"version": 2}, {"version": 1}, {"version": 1, "limits": LCFG},
                     {"version": 1, "limits": base["limits"], "floors": 5},
                     {"version": 1, "limits": base["limits"], "floors": [5, {"clusters": 3}, {"key": 3, "level": "x"},
                      {"key": "p:/w/proj", "level": 4, "clusters": [{"key": 1}, None, {"key": "p:/w/proj/t:/w/proj",
                       "slot": 9999, "desks": [3, {"key": "x", "slot": "q"}]}]}]}):
            l = office.office_layout(o, LCFG, prev)
            self.assertEqual(json.loads(json.dumps(l)), l)
            check_geometry(self, l)
            check_promises(self, l)
        for prev in (5, "x", [], {}, {"version": 2}, {"version": 1}):
            self.assertEqual(office.office_layout(o, LCFG, prev), base)

    def test_started_none_sorts_last(self):
        o = org_none(org_of([S("n", started=1), S("a", started=5), S("b", started=1)]), sids=("n",))
        self.assertEqual({k: d["slot"] for k, d in by_sid(office.office_layout(o, LCFG)).items()},
                         {"b": 0, "a": 1, "n": 2})
        self.assertEqual(sorted(by_sid(office.office_layout(o, {"board_max_desks": 2}))), ["a", "b"])
        o = org_none(org_of([S("a", workers=[sub("e1", started=5), sub("e0", started=9)])]), wids=("e0",))
        self.assertEqual(wpos(by_sid(office.office_layout(o, LCFG))["a"])["e0"][:2], (0, 1))


# ================================================================ T-L3
class DeterminismTest(unittest.TestCase):
    def test_same_input_same_output(self):
        o = org_of(rich_sessions())
        self.assertEqual(office.office_layout(o, LCFG), office.office_layout(o, LCFG))

    def test_shuffle_without_prev_same_layout_without_ref(self):
        o = org_of(rich_sessions())
        base = strip_ref(office.office_layout(o, LCFG))
        self.assertGreater(len(all_desks(base)), 10)
        for seed in range(8):
            sh = shuffle_org(o, random.Random(seed))
            self.assertEqual(strip_ref(office.office_layout(sh, LCFG)), base, seed)

    def test_shuffle_with_tight_caps_still_equal(self):
        o = org_of(rich_sessions(2))
        cfg = {"board_max_desks": 7, "board_max_workers": 4}
        base = strip_ref(office.office_layout(o, cfg))
        for seed in range(5):
            self.assertEqual(strip_ref(office.office_layout(shuffle_org(o, random.Random(seed)), cfg)), base)

    def test_duplicate_keys_no_raise_and_unique(self):
        ws = [sub("same"), sub("same"), sub("same", dept="qa"), bg("t"), bg("t")]
        ss = [S("dup", workers=ws), S("dup", started=1001), S("dup", started=1002, top="/w/other")]
        ss += [S("q", top="/w/proj"), S("q", root="/w/proj", top="/w/proj")]
        o = org_of(ss)
        o["projects"].append(copy.deepcopy(o["projects"][0]))  # hai project trùng root
        o["projects"][0]["teams"].append(copy.deepcopy(o["projects"][0]["teams"][0]))  # hai team trùng top
        l = office.office_layout(o, LCFG)
        ks = all_keys(l)
        self.assertEqual(len(ks), len(set(ks)))
        self.assertTrue(any(k.endswith("#1") for k in ks))
        self.assertEqual(json.loads(json.dumps(l)), l)
        check_geometry(self, l)


# ================================================================ T-L4
class DeskStabilityTest(unittest.TestCase):
    def test_valid_org(self):
        self.assertTrue(office.valid_org({"projects": []}))
        self.assertTrue(office.valid_org({"projects": [1]}))
        for bad in (None, {}, {"projects": 5}, {"projects": None}, [], "x"):
            self.assertFalse(office.valid_org(bad))

    def test_none_org_with_prev_gives_empty(self):
        prev = lay([S("a")])
        self.assertEqual(office.office_layout(None, LCFG, prev), office.office_layout(None, LCFG))
        self.assertEqual(office.office_layout(None, LCFG, prev)["floors"], [])

    def test_scripted_rounds(self):
        mk = lambda ids, **kw: [S(i, started=int(i[1:]) * 10, **kw) for i in ids]
        l0 = lay(mk(["s1", "s2", "s3", "s4", "s5"]))
        p0 = by_sid(l0)
        self.assertEqual([p0["s%d" % i]["slot"] for i in range(1, 6)], [0, 1, 2, 3, 4])
        # s2 đi, s6 đến, đảo thứ tự: bàn còn lại giữ x,y; s6 lấy ô trống thấp nhất (ô của s2)
        l1 = lay(mk(["s5", "s4", "s6", "s3", "s1"]), prev=l0)
        p1 = by_sid(l1)
        for i in (1, 3, 4, 5):
            self.assertEqual((p1["s%d" % i]["x"], p1["s%d" % i]["y"]), (p0["s%d" % i]["x"], p0["s%d" % i]["y"]))
        self.assertEqual((p1["s6"]["x"], p1["s6"]["y"], p1["s6"]["slot"]), (p0["s2"]["x"], p0["s2"]["y"], 1))
        # s1 và s4 đi, s7 s8 đến: lấy ô trống thấp nhất theo thứ tự started
        l2 = lay(mk(["s8", "s3", "s5", "s6", "s7"]), prev=l1)
        p2 = by_sid(l2)
        self.assertEqual([p2["s7"]["slot"], p2["s8"]["slot"]], [0, 3])
        for i in (3, 5, 6):
            self.assertEqual(p2["s%d" % i]["slot"], p1["s%d" % i]["slot"])
        # khoá cũ s2 trở lại: như session mới, không đẩy bàn khác
        l3 = lay(mk(["s2", "s3", "s5", "s6", "s7", "s8"]), prev=l2)
        p3 = by_sid(l3)
        self.assertEqual(p3["s2"]["slot"], 5)
        for i in (3, 5, 6, 7, 8):
            self.assertEqual(p3["s%d" % i]["slot"], p2["s%d" % i]["slot"])

    def test_random_walk_keeps_every_present_desk(self):
        rnd = random.Random(42)
        teams = [("/p1", "/p1/a"), ("/p1", "/p1/b"), ("/p2", "/p2/a"), ("/p2", "/p2/b"), ("/p3", "/p3/a")]
        pool = {}
        for n in range(30):
            root, top = teams[n % len(teams)]
            pool["s%d" % n] = S("s%d" % n, started=rnd.randint(1, 9999), top=top, root=root)
        present, prev, prev_pos = {}, None, {}
        for rd in range(60):
            for sid in rnd.sample(sorted(pool), rnd.randint(0, 6)):
                if sid in present and rnd.random() < 0.6:
                    del present[sid]
                else:
                    present[sid] = pool[sid]
            ss = list(present.values())
            rnd.shuffle(ss)
            l = lay(ss, prev=prev)
            pos = dpos(l)
            self.assertEqual({d["session_id"] for _, _, d in all_desks(l)}, set(present))
            for k, v in pos.items():
                if k in prev_pos:
                    self.assertEqual(v, prev_pos[k], (rd, k))
            check_geometry(self, l)
            check_promises(self, l)
            prev, prev_pos = l, pos

    def test_caller_rule_invalid_keeps_prev(self):
        ss = [S("s1", started=300), S("s2", started=100, top="/w/proj/b")]
        l0 = lay([ss[0]])
        l1 = lay(ss, prev=l0)
        prev = l1
        for o in (None, {}, {"projects": 5}):  # luật nơi gọi: org hỏng thì không gọi, không thay prev
            if office.valid_org(o):
                prev = office.office_layout(o, LCFG, prev)
        l2 = lay(ss, prev=prev)
        self.assertEqual(dpos(l2), dpos(l1))

    def test_empty_projects_releases_slots(self):
        ss = [S("s1", started=300), S("s2", started=100)]
        l0 = lay([ss[0]])
        l1 = lay(ss, prev=l0)
        self.assertEqual((by_sid(l1)["s1"]["slot"], by_sid(l1)["s2"]["slot"]), (0, 1))
        empty = office.office_layout({"projects": []}, LCFG, l1)
        self.assertEqual(empty["floors"], [])
        l2 = lay(ss, prev=empty)
        self.assertEqual((by_sid(l2)["s2"]["slot"], by_sid(l2)["s1"]["slot"]), (0, 1))  # theo bước 2: started 100 trước
        self.assertEqual(l2, lay(ss))

    def test_worktree_change_releases_old_desk(self):
        l0 = lay([S("s1", started=1, top="/w/a"), S("s2", started=2, top="/w/a")])
        l1 = lay([S("s1", started=1, top="/w/b"), S("s2", started=2, top="/w/a")], prev=l0)
        self.assertEqual(by_sid(l1)["s2"]["slot"], by_sid(l0)["s2"]["slot"])
        self.assertEqual(by_sid(l1)["s1"]["slot"], 0)  # cụm /w/b mới, bàn đầu
        l2 = lay([S("s3", started=3, top="/w/a")], prev=l1)  # s1 rời /w/a trước đó: pod 0 của /w/a đã trống
        self.assertEqual(by_sid(l2)["s3"]["slot"], 0)


# ================================================================ T-L5
class WorkerStabilityTest(unittest.TestCase):
    def test_add_remove_other_workers_no_shift(self):
        w0 = [sub("e1", started=1), sub("e2", started=2), sub("q1", dept="qa", started=3), bg("t1", started=5900.0 + 99)]
        l0 = lay([S("a", workers=w0), S("b", started=2000)])
        a0, b0 = wpos(by_sid(l0)["a"]), by_sid(l0)["b"]
        w1 = [sub("e1", started=1), sub("q1", dept="qa", started=3), sub("r1", dept="review", started=9)]
        l1 = lay([S("a", workers=w1), S("b", started=2000)], prev=l0)
        a1 = wpos(by_sid(l1)["a"])
        self.assertEqual(a1["e1"], a0["e1"])
        self.assertEqual(a1["q1"], a0["q1"])
        self.assertEqual((by_sid(l1)["a"]["x"], by_sid(l1)["a"]["y"]), (by_sid(l0)["a"]["x"], by_sid(l0)["a"]["y"]))
        self.assertEqual((by_sid(l1)["b"]["x"], by_sid(l1)["b"]["y"]), (b0["x"], b0["y"]))

    def test_empty_lane_loses_owner_and_is_reused(self):
        l0 = lay([S("a", workers=[sub("e1", started=1), sub("q1", dept="qa", started=2)])])
        a0 = wpos(by_sid(l0)["a"])
        self.assertEqual((a0["e1"][0], a0["q1"][0]), (0, 1))
        l1 = lay([S("a", workers=[sub("q1", dept="qa", started=2), sub("r1", dept="review", started=3)])], prev=l0)
        a1 = wpos(by_sid(l1)["a"])
        self.assertEqual(a1["q1"], a0["q1"])
        self.assertEqual(a1["r1"][:2], (0, 0))  # lane 0 hết chủ, ô 0 của lane không chủ thấp nhất

    def test_lane_keeps_owner_while_worker_remains(self):
        es = [sub("e%d" % i, started=i) for i in range(1, 5)]
        l0 = lay([S("a", workers=es)])
        self.assertEqual({k: v[:2] for k, v in wpos(by_sid(l0)["a"]).items()},
                         {"e1": (0, 0), "e2": (0, 1), "e3": (0, 2), "e4": (1, 0)})
        l1 = lay([S("a", workers=[es[3], sub("e5", started=5)])], prev=l0)
        a1 = wpos(by_sid(l1)["a"])
        self.assertEqual(a1["e4"][:2], (1, 0))
        self.assertEqual(a1["e5"][:2], (1, 1))  # a: ô trống thấp nhất trong lane do phòng ban sở hữu


# ================================================================ T-L6
class LaneRulesTest(unittest.TestCase):
    def test_same_department_same_lane_second_department_other_lane(self):
        ws = [sub("e%d" % i, started=i) for i in range(3)] + [sub("q0", dept="qa", started=10)]
        a = wpos(by_sid(lay([S("a", workers=ws)]))["a"])
        self.assertEqual({a["e0"][0], a["e1"][0], a["e2"][0]}, {0})
        self.assertEqual(sorted(a[k][1] for k in ("e0", "e1", "e2")), [0, 1, 2])
        self.assertEqual(a["q0"][0], 1)

    def test_more_than_three_takes_extra_lane(self):
        ws = [sub("e%d" % i, started=i) for i in range(7)]
        a = wpos(by_sid(lay([S("a", workers=ws)]))["a"])
        self.assertEqual(sorted({v[0] for v in a.values()}), [0, 1, 2])
        self.assertEqual(len(a), 7)

    def test_fifth_department_goes_to_more(self):
        ws = [sub("d%d" % i, dept="dept%d" % i, started=i) for i in range(5)]
        d = by_sid(lay([S("a", workers=ws)]))["a"]
        self.assertEqual(sorted(w["id"] for w in d["workers"]), ["d0", "d1", "d2", "d3"])
        self.assertEqual(d["more"], {"n": 1, "counts": {"running": 1}})

    def test_4c_replaces_oldest_finished_in_own_lane(self):
        base = [sub("ea", started=1), sub("q", dept="qa", started=2), sub("r", dept="review", started=3),
                sub("o", dept="ops", started=4), sub("ed1", "done", started=5, last=50),
                sub("ed2", "done", started=6, last=10)]
        l0 = lay([S("a", workers=base)])
        a0 = wpos(by_sid(l0)["a"])
        self.assertEqual({a0[k][0] for k in ("ea", "ed1", "ed2")}, {0})
        l1 = lay([S("a", workers=base + [sub("en", started=7)])], prev=l0)
        d = by_sid(l1)["a"]
        a1 = wpos(d)
        self.assertNotIn("ed2", a1)
        self.assertEqual(a1["en"], a0["ed2"])
        for k in ("ea", "ed1", "q", "r", "o"):
            self.assertEqual(a1[k], a0[k])
        self.assertEqual(d["more"], {"n": 1, "counts": {"done": 1}})

    def test_4d_frees_lowest_all_finished_lane_only(self):
        base = [sub("d1a", started=1), sub("d1b", started=2), sub("d1c", started=3),
                sub("d4", dept="d4", started=4), sub("d2", "done", dept="d2", started=5),
                sub("d3", "done", dept="d3", started=6)]
        l0 = lay([S("a", workers=base)])
        a0 = wpos(by_sid(l0)["a"])
        self.assertLess(a0["d2"][0], a0["d3"][0])
        l1 = lay([S("a", workers=base + [sub("d5", dept="d5", started=7)])], prev=l0)
        d = by_sid(l1)["a"]
        a1 = wpos(d)
        self.assertNotIn("d2", a1)
        self.assertEqual(a1["d3"], a0["d3"])  # lane cao giữ nguyên
        self.assertEqual(a1["d5"][:2], (a0["d2"][0], 0))
        self.assertEqual(d["more"], {"n": 1, "counts": {"done": 1}})

    def _4c_victim(self, last1, last2, none2=False):
        base = [sub("ea", started=1), sub("q", dept="qa", started=2), sub("r", dept="review", started=3),
                sub("o", dept="ops", started=4), sub("ed1", "done", started=6, last=last1),
                sub("ed2", "done", started=5, last=last2)]  # ed1 khoá nhỏ hơn nhưng ở ô cao hơn
        o0, o1 = org_of([S("a", workers=base)]), org_of([S("a", workers=base + [sub("en", started=7)])])
        if none2:
            org_none(o0, wids=("ed2",), field="last_activity")
            org_none(o1, wids=("ed2",), field="last_activity")
        l1 = office.office_layout(o1, LCFG, office.office_layout(o0, LCFG))
        return ({"ed1", "ed2"} - set(wpos(by_sid(l1)["a"]))).pop()

    def test_4c_last_none_counts_as_zero_and_ties_by_key(self):
        self.assertEqual(self._4c_victim(50, 99, none2=True), "ed2")
        self.assertEqual(self._4c_victim(10, 10), "ed1")
        self.assertEqual(self._4c_victim(20, 10), "ed2")

    def test_4d_at_low_cap_with_free_lane_frees_finished_lane(self):
        # F1 của Review S1: chạm trần mà còn lane không chủ, worker đang chạy vẫn lấy lane toàn worker đã xong
        cfg = {"board_max_workers": 4}
        base = [sub("e%d" % i, "done", started=i, last=100 + i) for i in range(3)] + \
               [sub("q", "done", dept="qa", started=5, last=105)]
        l0 = lay([S("a", workers=base)], cfg)
        a0 = wpos(by_sid(l0)["a"])
        self.assertEqual(({a0["e%d" % i][0] for i in range(3)}, a0["q"][0]), ({0}, 1))
        l1 = lay([S("a", workers=base + [sub("o1", dept="ops", started=7), sub("o2", dept="ops", started=8)])],
                 cfg, l0)
        d = by_sid(l1)["a"]
        a1 = wpos(d)
        # 4d trừ 3 worker đã vẽ: o2 vào ô kế tiếp của lane, không giải phóng lane của qa; còn một chỗ dưới trần nên
        # e0 (đầu thứ tự xử lý) được xét lại ngay và lấy ô 0 của lane không chủ thấp nhất
        self.assertEqual((a1["o1"][:2], a1["o2"][:2], a1["q"], a1["e0"][:2]), ((0, 0), (0, 1), a0["q"], (2, 0)))
        self.assertEqual(d["more"], {"n": 2, "counts": {"done": 2}})
        self.assertEqual(lay([S("a", workers=base + [sub("o1", dept="ops", started=7),
                                                     sub("o2", dept="ops", started=8)])], cfg, l1), l1)

    def test_fixed_point_no_churn_with_same_input(self):
        # cùng đầu vào, `prev` là Layout vừa dựng: không worker/device/bàn nào đổi chỗ (không đổi chỗ vòng tròn)
        for seed in (1, 2, 3):
            o = org_of(rich_sessions(seed))
            for cfg in (LCFG, {"board_max_desks": 9, "board_max_workers": 5}, {"board_max_desks": 48, "board_max_workers": 2}):
                l0 = office.office_layout(o, cfg)
                l1 = office.office_layout(o, cfg, l0)
                l2 = office.office_layout(o, cfg, l1)
                self.assertEqual(l1, l0)
                self.assertEqual(l2, l0)

    def test_fixed_point_after_replacement_from_older_prev(self):
        # prev từ đầu vào cũ rồi thêm worker sống: 4d và 4c chạy thật; lần gọi kế với cùng đầu vào không đổi Layout
        ws = [sub("e%d" % i, "done", started=i, last=100 + i) for i in range(4)] + \
             [sub("r", dept="review", started=10), sub("o", dept="ops", started=11)]
        l1 = lay([S("a", workers=ws + [sub("x1", dept="qa", started=20)])], prev=lay([S("a", workers=ws)]))
        self.assertEqual(lay([S("a", workers=ws + [sub("x1", dept="qa", started=20)])], prev=l1), l1)
        rnd = random.Random(7)
        for _ in range(400):
            cfg = {"board_max_workers": rnd.randint(1, 12)}
            old = [sub("w%d" % i, rnd.choice(("running", "done", "done", "failed")), dept=rnd.choice(DEPTS + ("x",)),
                       started=rnd.randint(1, 50), last=rnd.randint(1, 50)) for i in range(rnd.randint(0, 14))]
            keep = [w for w in old if rnd.random() < 0.8]
            new = keep + [sub("n%d" % i, rnd.choice(("running", "stuck", "done")), dept=rnd.choice(DEPTS + ("x",)),
                              started=rnd.randint(1, 60)) for i in range(rnd.randint(0, 8))]
            l1 = lay([S("a", workers=new)], cfg, lay([S("a", workers=old)], cfg))
            d = by_sid(l1)["a"]
            self.assertLessEqual(len(d["workers"]), cfg["board_max_workers"])
            self.assertEqual(len(d["workers"]) + d["more"]["n"], len(new))
            self.assertEqual(lay([S("a", workers=new)], cfg, l1), l1)

    def test_finished_newcomer_does_not_evict_finished_worker(self):
        ws = [sub("d%d" % i, "done", started=i, last=100 + i) for i in range(1, 5)]
        l0 = lay([S("a", workers=ws)], {"board_max_workers": 3})
        self.assertEqual(sorted(wpos(by_sid(l0)["a"])), ["d1", "d2", "d3"])
        l1 = lay([S("a", workers=ws)], {"board_max_workers": 3}, l0)
        self.assertEqual(wpos(by_sid(l1)["a"]), wpos(by_sid(l0)["a"]))
        self.assertEqual(by_sid(l1)["a"]["more"], {"n": 1, "counts": {"done": 1}})

    def test_alive_workers_are_never_replaced(self):
        ws = [sub("w%d" % i, st="running" if i % 2 else "stuck", dept=DEPTS[i // 3], started=i) for i in range(12)]
        l0 = lay([S("a", workers=ws)])
        l1 = lay([S("a", workers=ws + [sub("n1", started=50), sub("n2", dept="qa", started=51),
                                       sub("n3", dept="zzz", started=52)])], prev=l0)
        d = by_sid(l1)["a"]
        self.assertEqual(wpos(d).keys() - {"n1", "n2", "n3"}, {w["id"] for w in ws})
        self.assertEqual(len(d["workers"]), 12)
        self.assertEqual(d["more"]["n"], 3)
        for k, v in wpos(by_sid(l0)["a"]).items():
            self.assertEqual(wpos(d)[k], v)


# ================================================================ T-L7
class DeviceTest(unittest.TestCase):
    def test_three_slots_overflow_to_more(self):
        ds = [bg("t%d" % i, started=5900.0 + i) for i in range(5)]
        d = by_sid(lay([S("a", workers=ds)]))["a"]
        self.assertEqual([(v["id"], v["slot"]) for v in d["devices"]], [("t0", 0), ("t1", 1), ("t2", 2)])
        self.assertEqual(d["more"], {"n": 2, "counts": {"running": 2}})

    def test_replace_oldest_non_running_never_running(self):
        ds = [bg("r1", started=5900.0), bg("d1", "done", started=5910.0), bg("d2", "done", started=5905.0)]
        l0 = lay([S("a", workers=ds)])
        d0 = {v["id"]: v["slot"] for v in by_sid(l0)["a"]["devices"]}
        self.assertEqual(len(d0), 3)
        l1 = lay([S("a", workers=ds + [bg("r2", started=5950.0)])], prev=l0)
        d = by_sid(l1)["a"]
        d1 = {v["id"]: v["slot"] for v in d["devices"]}
        self.assertEqual(d1, {"r1": d0["r1"], "d1": d0["d1"], "r2": d0["d2"]})  # d2 started nhỏ nhất bị thay
        self.assertEqual(d["more"], {"n": 1, "counts": {"done": 1}})
        # cả ba đang chạy: không bị thay
        rs = [bg("x%d" % i, started=5900.0 + i) for i in range(3)]
        l2 = lay([S("a", workers=rs)])
        l3 = lay([S("a", workers=rs + [bg("x9", started=5999.0)])], prev=l2)
        self.assertEqual({v["id"] for v in by_sid(l3)["a"]["devices"]}, {"x0", "x1", "x2"})
        self.assertEqual(by_sid(l3)["a"]["more"], {"n": 1, "counts": {"running": 1}})

    def test_running_first_when_competing(self):
        ds = [bg("d%d" % i, "done", started=5900.0 + i) for i in range(3)] + [bg("r", started=5999.0)]
        d = by_sid(lay([S("a", workers=ds)]))["a"]
        self.assertIn("r", {v["id"] for v in d["devices"]})
        self.assertEqual(len(d["devices"]), 3)
        self.assertEqual(d["more"]["n"], 1)

    def test_running_take_lowest_slots_before_finished(self):
        ds = [bg("d%d" % i, "done", started=5900.0 + i) for i in range(3)] + \
             [bg("r2", started=5990.0), bg("r1", started=5980.0)]
        d = by_sid(lay([S("a", workers=ds)]))["a"]
        self.assertEqual([(v["id"], v["slot"]) for v in d["devices"]], [("r1", 0), ("r2", 1), ("d0", 2)])
        self.assertEqual(d["more"], {"n": 2, "counts": {"done": 2}})

    def test_started_none_device_replaced_first(self):
        ds = [bg("d0", "done", started=5900.0), bg("d1", "done", started=5901.0), bg("dn", "done", started=5902.0)]
        o0 = org_none(org_of([S("a", workers=ds)]), wids=("dn",))
        o1 = org_none(org_of([S("a", workers=ds + [bg("r", started=5999.0)])]), wids=("dn",))
        l1 = office.office_layout(o1, LCFG, office.office_layout(o0, LCFG))
        self.assertEqual({v["id"] for v in by_sid(l1)["a"]["devices"]}, {"d0", "d1", "r"})


# ================================================================ T-L8
class CapsTest(unittest.TestCase):
    def test_cluster_full_at_six(self):
        ss = [S("s%d" % i, started=i) for i in range(1, 8)]
        ss[6]["workers"] = [sub("st", "stuck")]
        l = lay(ss)
        self.assertEqual(sorted(by_sid(l)), ["s%d" % i for i in range(1, 7)])
        self.assertEqual(l["more"], {"desks": 1, "stuck_desks": 1})
        self.assertEqual(lay([S("s%d" % i, started=i) for i in range(1, 8)])["more"], {"desks": 1, "stuck_desks": 0})

    def test_cfg_caps(self):
        ss = [S("s%d" % i, started=i, top="/w/t%d" % i) for i in range(1, 8)]
        l = lay(ss, {"board_max_desks": 3, "board_max_workers": 5})
        self.assertEqual(sorted(by_sid(l)), ["s1", "s2", "s3"])
        self.assertEqual(l["more"]["desks"], 4)
        self.assertEqual(l["limits"], {"desks": 3, "workers": 5, "devices": 3})
        d = by_sid(lay([S("a", workers=[sub("e%d" % i, started=i) for i in range(8)])],
                       {"board_max_workers": 5}))["a"]
        self.assertEqual(len(d["workers"]), 5)
        self.assertEqual(d["more"], {"n": 3, "counts": {"running": 3}})
        d0 = by_sid(lay([S("a", workers=[sub("e1"), bg("t1")])], {"board_max_workers": 0}))["a"]
        self.assertEqual((d0["workers"], len(d0["devices"]), d0["more"]["n"]), ([], 1, 1))

    def test_cfg_clamping(self):
        for cfg, want in (({"board_max_desks": 0, "board_max_workers": -3}, (1, 0)),
                          ({"board_max_desks": 999, "board_max_workers": 99}, (200, 12)),
                          ({"board_max_desks": "9", "board_max_workers": "x"}, (48, 12)),
                          ({"board_max_desks": None, "board_max_workers": True}, (48, 12)),
                          ({"board_max_desks": float("nan"), "board_max_workers": float("inf")}, (48, 12)),
                          ({"board_max_desks": 7.9, "board_max_workers": 3.2}, (7, 3)),
                          ({"board_max_desks": 200, "board_max_workers": 12}, (200, 12)),
                          ({"board_max_desks": 1, "board_max_workers": 0}, (1, 0)),
                          ({"board_max_desks": [], "board_max_workers": {}}, (48, 12)),
                          ({}, (48, 12))):
            l = office.office_layout({"projects": []}, cfg)
            self.assertEqual(l["limits"], {"desks": want[0], "workers": want[1], "devices": 3}, cfg)

    def test_prev_with_other_limits_is_dropped(self):
        ss = [S("s1", started=300), S("s2", started=100)]
        small = {"board_max_desks": 3, "board_max_workers": 12}
        prev_small = lay(ss, small, prev=lay([ss[0]], small))
        self.assertEqual((by_sid(prev_small)["s1"]["slot"], by_sid(prev_small)["s2"]["slot"]), (0, 1))
        self.assertEqual(lay(ss, LCFG, prev_small), lay(ss, LCFG))  # limits khác: coi như None (s2 lấy ô 0)
        self.assertEqual(by_sid(lay(ss, small, prev_small))["s1"]["slot"], 0)  # cùng limits: giữ

    def test_kept_desks_are_not_pushed_out(self):
        cfg = {"board_max_desks": 2, "board_max_workers": 12}
        l0 = lay([S("s1", started=300), S("s2", started=200, top="/w/b")], cfg)
        l1 = lay([S("s0", started=100, top="/w/c"), S("s1", started=300), S("s2", started=200, top="/w/b")],
                 cfg, l0)
        self.assertEqual(sorted(by_sid(l1)), ["s1", "s2"])
        self.assertEqual(l1["more"]["desks"], 1)
        self.assertEqual(dpos(l1), dpos(l0))

    def test_alert_and_more_stuck_count_undrawn_workers(self):
        ws = [sub("r1", started=1), sub("r2", started=2)] + [sub("k%d" % i, "stuck", started=10 + i) for i in range(3)]
        d = by_sid(lay([S("a", workers=ws)], {"board_max_workers": 2}))["a"]
        self.assertEqual(sorted(w["id"] for w in d["workers"]), ["r1", "r2"])
        self.assertEqual(d["alert"], {"stuck": 3})
        self.assertEqual(d["more"], {"n": 3, "counts": {"stuck": 3}})
        self.assertEqual(by_sid(lay([S("b", workers=[sub("r1")])]))["b"]["alert"], {"stuck": 0})

    def test_stuck_desks_counts_only_stuck_undrawn_desks(self):
        cfg = {"board_max_desks": 1, "board_max_workers": 12}
        ss = [S("s1", started=1), S("s2", started=2, workers=[sub("k", "stuck")]),
              S("s3", started=3, workers=[sub("k2", "stuck")]), S("s4", started=4, workers=[sub("ok")])]
        l = lay(ss, cfg)
        self.assertEqual(l["more"], {"desks": 3, "stuck_desks": 2})


# ================================================================ T-L9
class GeometryTest(unittest.TestCase):
    def fixture(self):
        full = [sub("%s%d" % (dp, i), dept=dp, started=10 * j + i)
                for j, dp in enumerate(DEPTS) for i in range(3)]
        ss = [S("a%d" % i, started=i, top="/w/a", workers=full + [bg("t%d" % k, started=5900.0 + k) for k in range(3)]
                if i == 0 else []) for i in range(6)]
        return ss + [S("b0", started=10, top="/w/b"), S("c0", started=11, top="/w/c")]

    def test_formulas(self):
        l = lay(self.fixture())
        self.assertEqual(len(l["floors"]), 1)
        f = l["floors"][0]
        self.assertEqual((f["level"], f["w"], f["h"]), (0, 30, 20))
        self.assertEqual([(c["slot"], c["x"], c["y"], c["w"], c["h"]) for c in f["clusters"]],
                         [(0, 0, 0, 15, 10), (1, 15, 0, 15, 10), (2, 0, 10, 15, 10)])
        ca = f["clusters"][0]
        self.assertEqual([d["session_id"] for d in ca["desks"]], ["a%d" % i for i in range(6)])
        for p, d in enumerate(ca["desks"]):
            px, py = ca["x"] + (p % 3) * 5, ca["y"] + (p // 3) * 5
            self.assertEqual((d["slot"], d["x"], d["y"], d["w"], d["h"]), (p, px + 1, py + 1, 2, 2))
        d0 = ca["desks"][0]
        self.assertEqual([(v["slot"], v["x"] - d0["x"], v["y"] - d0["y"]) for v in d0["devices"]],
                         [(k, DEVICE_CELLS[k][0], DEVICE_CELLS[k][1]) for k in range(3)])
        self.assertEqual(len(d0["workers"]), 12)
        for w in d0["workers"]:
            dx, dy = LANE_CELLS[w["lane"]][w["slot"]]
            self.assertEqual((w["x"], w["y"]), (ca["x"] + dx, ca["y"] + dy))
        self.assertEqual(sorted((w["lane"], w["slot"]) for w in d0["workers"]),
                         [(l_, s_) for l_ in range(4) for s_ in range(3)])
        check_geometry(self, l)

    def test_constants_match_spec_tables(self):
        self.assertEqual(tuple(tuple(tuple(c) for c in lane) for lane in office.LANES), LANE_CELLS)
        cells = {c for lane in LANE_CELLS for c in lane}
        self.assertEqual(len(cells), 12)
        self.assertEqual(cells, {(x, y) for x in range(4) for y in range(4) if x in (0, 3) or y in (0, 3)})
        self.assertEqual(tuple(office.CLUSTER_PODS), (3, 2))

    def test_geometry_on_rich_and_big(self):
        for l in (lay(rich_sessions()), office.office_layout(big_org(), LCFG)):
            check_geometry(self, l)
            check_promises(self, l)

    def test_floor_grows_only_south(self):
        ss = [S("a", top="/w/a", started=1), S("b", top="/w/b", started=2)]
        l0 = lay(ss)
        self.assertEqual(l0["floors"][0]["h"], 10)
        l1 = lay(ss + [S("c", top="/w/c", started=3)], prev=l0)
        self.assertEqual(l1["floors"][0]["h"], 20)
        for k, v in dpos(l0).items():
            self.assertEqual(dpos(l1)[k], v)
        self.assertEqual(l1["floors"][0]["clusters"][2]["y"], 10)


# ================================================================ T-L10
class KeysRefsTest(unittest.TestCase):
    def test_key_format_unique(self):
        l = lay([S("s1", workers=[sub("w1"), bg("b1")])])
        f = l["floors"][0]
        c, d = f["clusters"][0], f["clusters"][0]["desks"][0]
        self.assertEqual(f["key"], "p:/w/proj")
        self.assertEqual(c["key"], "p:/w/proj/t:/w/proj")
        self.assertEqual(d["key"], c["key"] + "/s:s1")
        self.assertEqual(d["workers"][0]["key"], d["key"] + "/w:sub:w1")
        self.assertEqual(d["devices"][0]["key"], d["key"] + "/w:bg:b1")

    def test_duplicate_suffix_in_input_order(self):
        l = lay([S("dup", started=1), S("dup", started=2), S("dup", started=3)])
        d = sorted(d["key"] for _, _, d in all_desks(l))
        self.assertEqual([k.split("/s:")[1] for k in d], ["dup", "dup#1", "dup#2"])
        self.assertEqual(len(set(all_keys(l))), len(all_keys(l)))

    def test_ref_resolves_to_source(self):
        o = org_of(rich_sessions(3))
        o2 = shuffle_org(o, random.Random(5))  # ref chỉ đúng với org_out của đúng lần gọi
        l = office.office_layout(o2, LCFG)
        n = 0
        for f in l["floors"]:
            self.assertEqual(o2["projects"][f["ref"][0]]["name"], f["name"])
            self.assertEqual(o2["projects"][f["ref"][0]]["root"], f["root"])
            for c in f["clusters"]:
                t = o2["projects"][c["ref"][0]]["teams"][c["ref"][1]]
                self.assertEqual((t["top"], t["branch"]), (c["top"], c["branch"]))
                for d in c["desks"]:
                    pi, ti, si = d["ref"]
                    s = o2["projects"][pi]["teams"][ti]["sessions"][si]
                    self.assertEqual((s["session_id"], s["name"]), (d["session_id"], d["name"]))
                    for w in d["workers"] + d["devices"]:
                        self.assertEqual(w["ref"][:3], d["ref"])
                        src = s["workers"][w["ref"][3]]
                        self.assertEqual(src["id"], w["id"])
                        self.assertEqual(src["kind"], "subagent" if "department" in w else "bgtask")
                        n += 1
        self.assertGreater(n, 50)

    def test_cluster_and_pod_slots_reused_lowest_first(self):
        mk = lambda tops: [S("s" + t, started=i, top="/w/" + t) for i, t in enumerate(tops)]
        l0 = lay(mk(["a", "b", "c"]))
        l1 = lay(mk(["b", "c", "d"]), prev=l0)  # cụm a đi (slot 0 trống): cụm d mới lấy slot 0
        self.assertEqual({c["top"]: c["slot"] for c in l1["floors"][0]["clusters"]},
                         {"/w/b": 1, "/w/c": 2, "/w/d": 0})
        l2 = lay(mk(["b", "c", "d", "e"]), prev=l1)
        self.assertEqual({c["top"]: c["slot"] for c in l2["floors"][0]["clusters"]}["/w/e"], 3)

    def test_floor_level_reused(self):
        pa, pb, pc = (S("a", top="/a", root="/a"), S("b", top="/b", root="/b"), S("c", top="/c", root="/c"))
        l0 = lay([pa, pb])
        lv = {f["root"]: f["level"] for f in l0["floors"]}
        self.assertEqual(lv, {"/a": 0, "/b": 1})
        l1 = lay([pb], prev=l0)
        self.assertEqual(l1["floors"][0]["level"], 1)
        l2 = lay([pb, pc], prev=l1)
        self.assertEqual({f["root"]: f["level"] for f in l2["floors"]}, {"/b": 1, "/c": 0})
        self.assertEqual([f["root"] for f in l2["floors"]], ["/c", "/b"])  # sắp theo level


# ================================================================ T-L11
class SeedTest(unittest.TestCase):
    def test_crc32_abc(self):
        self.assertEqual(zlib.crc32(b"abc"), 891568578)
        self.assertEqual(by_sid(lay([S("abc")]))["abc"]["seed"], 891568578)

    def test_mascot_index(self):
        self.assertEqual(office.mascot_index(891568578, 40), 891568578 % 40)
        self.assertEqual(office.mascot_index(7, 3), 1)
        self.assertEqual(office.mascot_index(0, 1), 0)
        self.assertIsNone(office.mascot_index(5, 0))
        self.assertIsNone(office.mascot_index(5, -1))

    def test_same_session_two_worktrees_same_seed(self):
        a = by_sid(lay([S("same", top="/w/a")]))["same"]["seed"]
        b = by_sid(lay([S("same", top="/w/b")]))["same"]["seed"]
        self.assertEqual(a, b)

    def test_empty_id_seed_from_key_and_worker_seed(self):
        d = by_sid(lay([S("", workers=[sub("w", dept="qa"), sub("v", dept="qa")])]))[""]
        self.assertEqual(d["seed"], zlib.crc32(d["key"].encode("utf-8")) & 0xFFFFFFFF)
        self.assertEqual({w["seed"] for w in d["workers"]}, {zlib.crc32(b"qa")})
        self.assertTrue(all(w["department"] == "qa" for w in d["workers"]))
        d2 = by_sid(lay([S("x", workers=[bg("t")])]))["x"]
        self.assertNotIn("seed", d2["devices"][0])


# ================================================================ T-L12
class SmokeTest(unittest.TestCase):
    def test_big_org_fixture_shape(self):
        o = big_org()
        n = sum(len(t["sessions"]) for p in o["projects"] for t in p["teams"])
        self.assertEqual(n, 48)
        self.assertTrue(all(len(t["sessions"]) <= 6 for p in o["projects"] for t in p["teams"]))
        s = o["projects"][0]["teams"][0]["sessions"][0]
        self.assertEqual(len(s["workers"]), 15)
        self.assertEqual({w["department"] for w in s["workers"] if w["kind"] == "subagent"}, set(DEPTS))
        with self.assertRaises(ValueError):
            big_org(projects=1, teams=1, desks=7)

    def test_60_sessions_x_500_workers(self):
        o = big_org(projects=2, teams=5, desks=60, subs=497, tasks=3)
        self.assertEqual(sum(len(s["workers"]) for p in o["projects"] for t in p["teams"] for s in t["sessions"]),
                         60 * 500)
        t0 = time.perf_counter()
        l = office.office_layout(o, LCFG)
        t1 = time.perf_counter()
        l2 = office.office_layout(o, LCFG, l)
        t2 = time.perf_counter()
        sys.stderr.write("T-L12 office_layout 60 session x 500 worker: %.1f ms (prev=None), %.1f ms (prev=layout); "
                         "Python %s, %s\n" % ((t1 - t0) * 1000, (t2 - t1) * 1000, platform.python_version(),
                                              platform.platform()))
        self.assertEqual(l2, l)
        ds = all_desks(l)
        self.assertLessEqual(len(ds), 48)
        self.assertEqual(len(ds) + l["more"]["desks"], 60)
        for _, _, d in ds:
            self.assertLessEqual(len(d["workers"]), 12)
            self.assertLessEqual(len(d["devices"]), 3)
            self.assertEqual(len(d["workers"]) + len(d["devices"]) + d["more"]["n"], 500)
            self.assertEqual(sum(d["more"]["counts"].values()), d["more"]["n"])
        check_geometry(self, l)
        check_promises(self, l)


# ================================================================ T-L13
class ConsumerPromisesTest(unittest.TestCase):
    def test_max_floor_h(self):
        self.assertEqual(office.max_floor_h(48), 240)
        self.assertEqual(office.max_floor_h(200), 1000)
        self.assertEqual(office.max_floor_h(4), 20)
        self.assertEqual(office.max_floor_h(1), 10)
        self.assertEqual(office.max_floor_h(3), 20)

    def test_random_projects_and_worktrees_over_rounds(self):
        rnd = random.Random(11)
        for lim in (4, 8, 48):
            cfg = {"board_max_desks": lim, "board_max_workers": 12}
            pool = [S("s%d_%d_%d" % (p, t, k), started=rnd.randint(1, 999), top="/p%d/t%d" % (p, t), root="/p%d" % p)
                    for p in range(5) for t in range(4) for k in range(2)]
            prev = None
            for rd in range(50):
                ss = rnd.sample(pool, rnd.randint(0, 14))
                prev = lay(ss, cfg, prev)
                check_promises(self, prev)
                check_geometry(self, prev)
                self.assertEqual(prev["limits"]["desks"], lim)

    def test_worst_case_slot_three_with_four_desks(self):
        cfg = {"board_max_desks": 4, "board_max_workers": 12}
        ss = [S("s%d" % i, started=i, top="/w/t%d" % i) for i in range(4)]
        l0 = lay(ss, cfg)
        self.assertEqual([c["slot"] for c in l0["floors"][0]["clusters"]], [0, 1, 2, 3])
        l1 = lay(ss[3:], cfg, l0)
        self.assertEqual(l1["floors"][0]["clusters"][0]["slot"], 3)
        self.assertEqual(l1["floors"][0]["h"], 20)
        self.assertEqual(l1["floors"][0]["h"], office.max_floor_h(4))
        check_promises(self, l1)


# ================================================================ T-L14
class ShapeTest(unittest.TestCase):
    def test_exact_key_sets(self):
        l = lay([S("a", workers=[sub("w"), bg("t")])])
        self.assertEqual(set(l), {"version", "limits", "styles", "floors", "more"})
        f = l["floors"][0]
        self.assertEqual(set(f), {"key", "level", "name", "root", "w", "h", "ref", "clusters"})
        c = f["clusters"][0]
        self.assertEqual(set(c), {"key", "slot", "top", "branch", "x", "y", "w", "h", "ref", "desks"})
        d = c["desks"][0]
        self.assertEqual(set(d), {"key", "session_id", "slot", "x", "y", "w", "h", "name", "state", "seed", "alert",
                                  "ref", "workers", "devices", "more"})
        self.assertEqual(set(d["workers"][0]), {"key", "id", "department", "slot", "lane", "x", "y", "state", "seed",
                                                "ref"})
        self.assertEqual(set(d["devices"][0]), {"key", "id", "slot", "x", "y", "state", "ref"})
        self.assertEqual(set(d["more"]), {"n", "counts"})
        self.assertEqual((d["w"], d["h"]), (2, 2))
        self.assertNotIn("w", d["workers"][0])
        self.assertNotIn("h", d["workers"][0])
        self.assertNotIn("w", d["devices"][0])
        self.assertNotIn("h", d["devices"][0])
        self.assertEqual(d["ref"], [0, 0, 0])
        self.assertEqual(d["workers"][0]["ref"], [0, 0, 0, 0])
        self.assertEqual(d["devices"][0]["ref"], [0, 0, 0, 1])
        self.assertEqual((f["name"], f["root"], c["top"], c["branch"], d["name"]), ("proj", "/w/proj", "/w/proj",
                                                                                      "main", "n-a"))
        self.assertEqual(l["floors"][0]["ref"], [0])
        self.assertEqual(c["ref"], [0, 0])

    def test_strings_untouched_and_empty_name_kept(self):
        l = lay([S("a", name="", top="/w/{weird} $x", branch="[b]")])
        d = by_sid(l)["a"]
        self.assertEqual(d["name"], "")
        self.assertEqual(l["floors"][0]["clusters"][0]["top"], "/w/{weird} $x")
        self.assertEqual(l["floors"][0]["clusters"][0]["branch"], "[b]")
        self.assertIsNone(lay([S("a", branch="")])["floors"][0]["clusters"][0]["branch"])


# ================================================================ T-L15
class CountsTest(unittest.TestCase):
    def test_counts_enum_positive_sum(self):
        ws = ([sub("r%d" % i, started=i) for i in range(4)] + [sub("k", "stuck", started=20), sub("f", "failed", started=30),
              sub("x", "killed", started=31)] + [bg("t%d" % i, st, started=5900.0 + i) for i, st in
                                                  enumerate(("running", "done", "failed", "killed", "ended"))])
        o = org_of([S("a", workers=ws), S("b", workers=ws[:2] + [bg("q", "ended")])])
        # ép state ngoài enum trên đầu ra thật của org.build
        s = o["projects"][0]["teams"][0]["sessions"][0]
        s["workers"][0]["state"], s["workers"][1]["state"], s["workers"][2]["state"] = "weird", None, 5
        for cfg in ({"board_max_workers": 1}, {"board_max_workers": 0}, {"board_max_workers": 3}, LCFG):
            l = office.office_layout(o, cfg)
            self.assertEqual(set(l["more"]), {"desks", "stuck_desks"})
            for _, _, d in all_desks(l):
                m = d["more"]
                self.assertTrue(set(m["counts"]) <= set(ENUM_W), m)
                self.assertTrue(all(isinstance(v, int) and v > 0 for v in m["counts"].values()))
                self.assertEqual(sum(m["counts"].values()), m["n"])
        l = office.office_layout(o, {"board_max_workers": 0})
        d = by_sid(l)["a"]
        # workers=0: cả 7 subagent vào more; device vẫn vẽ 3 cái (running trước, rồi started nhỏ: ended 500, done, failed),
        # 2 cái dư (failed, killed) vào more
        self.assertEqual(len(d["devices"]), 3)
        self.assertEqual(d["more"], {"n": 9, "counts": {"running": 1, "stuck": 1, "failed": 2, "killed": 2,
                                                         "unknown": 3}})

    def test_out_of_enum_goes_to_unknown(self):
        o = org_of([S("a", workers=[sub("r1"), sub("r2"), sub("r3"), bg("t1")])])
        ws = o["projects"][0]["teams"][0]["sessions"][0]["workers"]
        ws[0]["state"], ws[1]["state"], ws[2]["state"], ws[3]["state"] = "zzz", None, ["list"], {"d": 1}
        d = by_sid(office.office_layout(o, LCFG))["a"]
        self.assertEqual({w["state"] for w in d["workers"]}, {"unknown"})
        self.assertEqual(d["devices"][0]["state"], "unknown")
        d = by_sid(office.office_layout(o, {"board_max_workers": 0, "board_max_desks": 5}))["a"]
        self.assertEqual(d["more"]["counts"], {"unknown": 3})
        self.assertEqual(d["more"]["n"], 3)

    def test_subagents_and_devices_counted_together(self):
        ws = [sub("e%d" % i, started=i) for i in range(2)] + [bg("t%d" % i, started=5900.0 + i) for i in range(5)]
        d = by_sid(lay([S("a", workers=ws)], {"board_max_workers": 1}))["a"]
        self.assertEqual(len(d["workers"]), 1)
        self.assertEqual(len(d["devices"]), 3)
        self.assertEqual(d["more"], {"n": 3, "counts": {"running": 3}})  # 1 subagent + 2 device dư


# ================================================================ T-L16
class PurityPromisesTest(unittest.TestCase):
    ALLOWED = {"STATE_STYLE", "ALERT_STYLE", "LANES", "CLUSTER_PODS"}

    def tree(self):
        return ast.parse((ROOT / "pet_tracker" / "office.py").read_text(encoding="utf-8"))

    def test_no_global_no_cache_no_mutable_module_state(self):
        tree = self.tree()
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.Global)])
        bad_dec = {"cache", "lru_cache", "cached_property"}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in n.decorator_list:
                    x = dec.func if isinstance(dec, ast.Call) else dec
                    name = x.id if isinstance(x, ast.Name) else x.attr if isinstance(x, ast.Attribute) else ""
                    self.assertNotIn(name, bad_dec)
        mut = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
        for n in tree.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                names = {t.id for t in targets if isinstance(t, ast.Name)}
                v = n.value
                bad = isinstance(v, mut) or (isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
                                             and v.func.id in ("list", "dict", "set", "defaultdict", "OrderedDict",
                                                               "deque", "Counter"))
                if bad:
                    self.assertTrue(names <= self.ALLOWED, names)

    def test_constants_unchanged_and_styles_deep_copy(self):
        before = copy.deepcopy((office.STATE_STYLE, office.ALERT_STYLE, office.LANES, office.CLUSTER_PODS))
        o = org_of(rich_sessions())
        l = office.office_layout(o, LCFG)
        l["styles"]["desk"]["run"]["color"] = "HACKED"
        l["styles"]["worker"]["failed"].clear()
        l["styles"]["worker"] = None
        l2 = office.office_layout(o, LCFG)
        self.assertEqual(l2["styles"], office.STATE_STYLE)
        self.assertEqual(copy.deepcopy((office.STATE_STYLE, office.ALERT_STYLE, office.LANES, office.CLUSTER_PODS)),
                         before)

    def orgs(self):
        ss1 = [S("s1", started=300, top="/w/a", workers=[sub("w1")])]
        ss2 = ss1 + [S("s2", started=100, top="/w/a", workers=[sub("w2", "stuck"), bg("t")])]
        ss3 = [ss2[1], S("s3", started=50, top="/w/b")]
        return [org_of(x) for x in (ss1, ss2, ss3)]

    @staticmethod
    def chain(orgs, upto=None):
        prev, out = None, []
        for o in orgs[:upto]:
            prev = office.office_layout(copy.deepcopy(o), LCFG, prev)
            out.append(prev)
        return out

    def test_independent_chains_interleaved(self):
        os_ = self.orgs()
        a_alone, b_alone = self.chain(os_), self.chain(os_[1:])
        a, b, pa, pb = [], [], None, None
        for i in range(3):
            pa = office.office_layout(os_[i], LCFG, pa)
            a.append(pa)
            if i >= 1:
                pb = office.office_layout(os_[i], LCFG, pb)
                b.append(pb)
        self.assertEqual(a, a_alone)
        self.assertEqual(b, b_alone)

    def test_different_history_gives_different_positions_same_sessions(self):
        os_ = self.orgs()
        a, b = self.chain(os_[:2])[-1], self.chain(os_[1:2])[-1]
        self.assertEqual(set(by_sid(a)), set(by_sid(b)))
        self.assertNotEqual({k: (v["x"], v["y"]) for k, v in by_sid(a).items()},
                            {k: (v["x"], v["y"]) for k, v in by_sid(b).items()})

    def test_two_threads_same_results(self):
        os_ = self.orgs()
        want_a, want_b = self.chain(os_), self.chain(os_[1:])
        res, errs = {}, []

        def run(name, orgs):
            try:
                for _ in range(20):
                    res[name] = self.chain(orgs)
            except Exception as e:  # pragma: no cover
                errs.append(e)
        ts = [threading.Thread(target=run, args=("a", os_)), threading.Thread(target=run, args=("b", os_[1:]))]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual(res["a"], want_a)
        self.assertEqual(res["b"], want_b)


# ================================================================ T-L17
class ExportsTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(office.FLOOR_CLUSTER_COLS, 2)
        self.assertEqual(office.CLUSTER_W, 15)
        self.assertEqual(office.CLUSTER_H, 10)
        self.assertEqual(office.POD, 4)
        self.assertEqual(office.POD_STRIDE, 5)
        self.assertEqual(office.DEVICE_SLOTS, 3)
        for n in ("mascot_index", "STATE_STYLE", "CLUSTER_PODS", "LANES", "ALERT_STYLE", "max_floor_h", "valid_org",
                  "office_layout"):
            self.assertTrue(hasattr(office, n), n)
        self.assertEqual(len(office.LANES), 4)
        self.assertTrue(all(len(x) == 3 for x in office.LANES))


# ================================================================ T-S1
class StateStyleTest(unittest.TestCase):
    def test_shape(self):
        ss = office.STATE_STYLE
        self.assertEqual(set(ss), {"desk", "worker"})
        self.assertEqual(set(ss["desk"]), {"idle", "run", "wait", "done"})
        self.assertEqual(set(ss["worker"]), set(ENUM_W))
        for part in ss.values():
            for st in part.values():
                self.assertEqual(set(st), {"color", "mood", "marker"})
                self.assertIn(st["marker"], ("ring", "cross", None))
                self.assertIsInstance(st["color"], str)
                self.assertIn(st["mood"], mascots.MOODS)
                self.assertIn(st["color"], theme.DARK)
                self.assertIn(st["color"], theme.LIGHT)
        self.assertEqual(set(office.ALERT_STYLE), {"color", "marker"})
        self.assertIn(office.ALERT_STYLE["color"], theme.DARK)
        self.assertIn(office.ALERT_STYLE["color"], theme.LIGHT)

    def test_table_values(self):
        N = None
        want = {"desk": {"run": ("run", "run", N), "wait": ("wait", "wait", N), "done": ("done", "done", N),
                         "idle": ("idle", "idle", N)},
                "worker": {"running": ("ok", "run", N), "stuck": ("warn", "wait", "ring"),
                           "done": ("mut", "done", N), "failed": ("danger", "quota", "cross"),
                           "killed": ("idle", "idle", N), "ended": ("idle", "idle", N),
                           "unknown": ("idle", "idle", N)}}
        got = {p: {s: (v["color"], v["mood"], v["marker"]) for s, v in d.items()}
               for p, d in office.STATE_STYLE.items()}
        self.assertEqual(got, want)
        self.assertEqual(office.ALERT_STYLE, {"color": "warn", "marker": "ring"})

    def test_layout_styles_deep_copy(self):
        l = lay([S("a")])
        self.assertEqual(l["styles"], office.STATE_STYLE)
        self.assertIsNot(l["styles"], office.STATE_STYLE)
        for p in ("desk", "worker"):
            self.assertIsNot(l["styles"][p], office.STATE_STYLE[p])
            for s in office.STATE_STYLE[p]:
                self.assertIsNot(l["styles"][p][s], office.STATE_STYLE[p][s])
        self.assertEqual(office.office_layout(None, LCFG)["styles"], office.STATE_STYLE)

    def test_desk_states_normalised_and_in_styles(self):
        sts = ("idle", "run", "wait", "done", "error", "zzz", None, 7)
        ss = [S("s%d" % i, started=i, top="/w/t%d" % (i // 4)) for i in range(len(sts))]
        o = org_of(ss)
        for t in o["projects"][0]["teams"]:
            for s in t["sessions"]:
                s["state"] = sts[int(s["session_id"][1:])]
        l = office.office_layout(o, LCFG)
        got = {d["session_id"]: d["state"] for _, _, d in all_desks(l)}
        self.assertEqual([got["s%d" % i] for i in range(len(sts))],
                         ["idle", "run", "wait", "done", "wait", "idle", "idle", "idle"])
        for d in got.values():
            self.assertIn(d, l["styles"]["desk"])

    def test_worker_states_normalised_and_in_styles(self):
        sts = ["running", "stuck", "done", "failed", "killed", "ended", "weird", None, 5]
        ws = [sub("w%d" % i, started=i) for i in range(len(sts))] + [bg("b%d" % i, started=5900.0 + i) for i in range(3)]
        o = org_of([S("a", workers=ws)])
        sw = o["projects"][0]["teams"][0]["sessions"][0]["workers"]
        for w in sw:
            if w["kind"] == "subagent":
                w["state"] = sts[int(w["id"][1:])]
        sw[-3]["state"], sw[-2]["state"], sw[-1]["state"] = "ended", "weird", None
        l = office.office_layout(o, {"board_max_desks": 5, "board_max_workers": 12})
        d = by_sid(l)["a"]
        got = {w["id"]: w["state"] for w in d["workers"]}
        self.assertEqual(got, {"w0": "running", "w1": "stuck", "w2": "done", "w3": "failed", "w4": "killed",
                               "w5": "ended", "w6": "unknown", "w7": "unknown", "w8": "unknown"})
        self.assertEqual([v["state"] for v in d["devices"]], ["ended", "unknown", "unknown"])
        for x in list(got.values()) + [v["state"] for v in d["devices"]]:
            self.assertIn(x, l["styles"]["worker"])
        for st in l["styles"]["worker"]:
            self.assertIn(st, ENUM_W)

    def test_org_states_all_lookup(self):
        ws = [sub("r", started=1), sub("k", "stuck", started=2), sub("d", "done", started=3),
              sub("f", "failed", started=4), sub("x", "killed", started=5), bg("e", "ended")]
        d = by_sid(lay([S("a", workers=ws)]))["a"]
        for w in d["workers"] + d["devices"]:
            self.assertIn(w["state"], office.STATE_STYLE["worker"])
        self.assertEqual({w["state"] for w in d["workers"]}, {"running", "stuck", "done", "failed", "killed"})
        self.assertEqual(d["devices"][0]["state"], "ended")


# ================================================================ cấu hình
class ConfigKeysTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(config.DEFAULTS["board_max_desks"], 48)
        self.assertEqual(config.DEFAULTS["board_max_workers"], 12)
        self.assertEqual(type(config.DEFAULTS["board_max_desks"]), int)
        self.assertEqual(type(config.DEFAULTS["board_max_workers"]), int)

    def test_example_json(self):
        d = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(d["board_max_desks"], config.DEFAULTS["board_max_desks"])
        self.assertEqual(d["board_max_workers"], config.DEFAULTS["board_max_workers"])
        self.assertEqual((d["board_max_desks"], d["board_max_workers"]), (48, 12))

    def test_defaults_drive_layout_limits(self):
        l = office.office_layout({"projects": []}, config.DEFAULTS)
        self.assertEqual(l["limits"], {"desks": 48, "workers": 12, "devices": 3})
        self.assertFalse(math.isnan(l["limits"]["desks"]))


if __name__ == "__main__":
    unittest.main()
