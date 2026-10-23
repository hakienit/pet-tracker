"""Test pet_tracker.org: hàm thuần dựng cây Project > Team > Session > Worker từ dữ liệu session thô."""
import ast
import copy
import json
import unittest
from pathlib import Path

from pet_tracker import org

NOW = 10_000.0
CFG = {"agent_prefixes": ["les-"], "stuck_after_sec": 120}


def sess(**kw):
    s = {"session_id": "s1", "started_at": 1000.0, "cwd": "/r", "name": "n", "status": "busy",
         "git": {"top": "/r", "common": "/r/.git", "branch": "main"}, "agent_calls": [], "workers": []}
    s.update(kw)
    return s


def sub(id, **kw):
    w = {"kind": "subagent", "id": id, "tool_use_id": "tu-" + id, "agent_type": "les-engineering",
         "description": "d", "depth": 1, "finished": False, "notif_status": None, "mtime": NOW - 10,
         "started": NOW - 100, "last_activity": NOW - 10, "tokens": 5, "open_tools": 0, "agent_calls": []}
    w.update(kw)
    return w


def bg(id, **kw):
    w = {"kind": "bgtask", "id": id, "tool_use_id": "tb-" + id, "started": NOW - 50, "status": None}
    w.update(kw)
    return w


def workers(sessions, cfg=CFG, now=NOW, sid="s1"):
    """Worker của một session, theo id."""
    for p in org.build(sessions, cfg, now)["projects"]:
        for t in p["teams"]:
            for s in t["sessions"]:
                if s["session_id"] == sid:
                    return {w["id"]: w for w in s["workers"]}
    raise AssertionError("không thấy session " + sid)


def state_of(w, cfg=CFG, extra=(), **skw):
    return workers([sess(workers=[w, *extra], **skw)], cfg)[w["id"]]["state"]


class DepartmentTest(unittest.TestCase):
    def test_prefix_and_namespace(self):
        P = ["les-"]
        self.assertEqual(org.department("les-engineering", P), "engineering")
        self.assertEqual(org.department("hba:qa-engineer", P), "qa-engineer")
        self.assertEqual(org.department("code-quality-reviewer", P), "code-quality-reviewer")

    def test_many_colons_take_last_segment(self):
        self.assertEqual(org.department("a:b:les-qa", ["les-"]), "qa")

    def test_only_first_matching_prefix_removed_once(self):
        self.assertEqual(org.department("les-x-y", ["x-", "les-", "les-x-"]), "x-y")
        self.assertEqual(org.department("les-les-qa", ["les-"]), "les-qa")

    def test_empty_result_returns_original(self):
        self.assertEqual(org.department("les-", ["les-"]), "les-")
        self.assertEqual(org.department("ns:les-", ["les-"]), "ns:les-")

    def test_non_string_type(self):
        self.assertEqual(org.department(None, ["les-"]), "")

    def test_build_uses_cfg_prefixes(self):
        w = sub("a", agent_type="hba:acme-qa")
        out = workers([sess(workers=[w])], {"agent_prefixes": ["acme-"], "stuck_after_sec": 120})["a"]
        self.assertEqual((out["type"], out["department"]), ("hba:acme-qa", "qa"))

    def test_bad_prefixes_fall_back_to_default(self):
        for bad in ("les-", None, 5, {"les-": 1}):
            out = workers([sess(workers=[sub("a")])], {"agent_prefixes": bad})["a"]
            self.assertEqual(out["department"], "engineering", bad)


class SubagentStateTest(unittest.TestCase):
    def test_finished_is_done_even_if_busy(self):
        self.assertEqual(state_of(sub("a", finished=True, open_tools=2)), "done")

    def test_notification_statuses(self):
        self.assertEqual(state_of(sub("a", notif_status="completed")), "done")
        self.assertEqual(state_of(sub("a", notif_status="failed")), "failed")
        self.assertEqual(state_of(sub("a", notif_status="killed")), "killed")

    def test_unknown_notification_status_is_done(self):
        self.assertEqual(state_of(sub("a", notif_status="weird")), "done")

    def test_empty_or_non_string_notification_is_not_notified(self):
        for bad in ("", ["x"], 0):
            self.assertEqual(state_of(sub("a", notif_status=bad, mtime=NOW - 500)), "stuck", bad)
            self.assertEqual(state_of(sub("a", notif_status=bad, mtime=NOW - 5)), "running", bad)

    def test_notification_beats_recent_activity(self):
        self.assertEqual(state_of(sub("a", notif_status="failed", mtime=NOW)), "failed")

    def test_recent_write_is_running_boundary_inclusive(self):
        self.assertEqual(state_of(sub("a", mtime=NOW - 120)), "running")
        self.assertEqual(state_of(sub("a", mtime=NOW - 120.5)), "stuck")

    def test_silent_without_work_is_stuck(self):
        self.assertEqual(state_of(sub("a", mtime=NOW - 500)), "stuck")

    def test_threshold_from_cfg(self):
        cfg = {"agent_prefixes": ["les-"], "stuck_after_sec": 600}
        self.assertEqual(state_of(sub("a", mtime=NOW - 500), cfg), "running")

    def test_bad_threshold_uses_default_120(self):
        for bad in ("5", None, True, float("nan"), -1):
            cfg = {"stuck_after_sec": bad}
            self.assertEqual(state_of(sub("a", mtime=NOW - 100), cfg), "running", bad)
            self.assertEqual(state_of(sub("a", mtime=NOW - 500), cfg), "stuck", bad)

    def test_cfg_not_a_dict(self):
        self.assertEqual(state_of(sub("a", mtime=NOW - 500), None), "stuck")

    def test_open_tool_keeps_running(self):
        self.assertEqual(state_of(sub("a", mtime=NOW - 5000, open_tools=1)), "running")

    def test_hung_tool_never_shows_stuck(self):
        # giới hạn đã biết của spec: công cụ treo luôn có tool đang chờ nên không bao giờ stuck
        self.assertEqual(state_of(sub("a", mtime=NOW - 10**6, open_tools=1)), "running")

    def test_running_child_keeps_parent_running(self):
        parent = sub("p", mtime=NOW - 500, agent_calls=["tu-c"])
        child = sub("c", mtime=NOW - 1)
        w = workers([sess(workers=[parent, child])])
        self.assertEqual((w["p"]["state"], w["c"]["state"]), ("running", "running"))

    def test_stuck_or_ended_child_does_not_keep_parent_running(self):
        for child in (sub("c", mtime=NOW - 500), sub("c", finished=True), sub("c", notif_status="failed")):
            parent = sub("p", mtime=NOW - 500, agent_calls=["tu-c"])
            self.assertEqual(workers([sess(workers=[parent, child])])["p"]["state"], "stuck")

    def test_running_grandchild_propagates_up(self):
        a = sub("a", mtime=NOW - 500, agent_calls=["tu-b"])
        b = sub("b", mtime=NOW - 500, agent_calls=["tu-c"])
        c = sub("c", mtime=NOW - 1)
        w = workers([sess(workers=[a, b, c])])
        self.assertEqual([w[k]["state"] for k in "abc"], ["running"] * 3)

    def test_ended_parent_stays_ended_with_running_child(self):
        parent = sub("p", finished=True, agent_calls=["tu-c"])
        w = workers([sess(workers=[parent, sub("c")])])
        self.assertEqual(w["p"]["state"], "done")

    def test_missing_mtime_falls_back_to_last_activity(self):
        w = sub("a", last_activity=NOW - 5)
        del w["mtime"]
        self.assertEqual(state_of(w), "running")
        w["last_activity"] = NOW - 5000
        self.assertEqual(state_of(w), "stuck")

    def test_session_fields_in_output(self):
        w = workers([sess(workers=[sub("a", depth=3, tokens=42, description="hello")])])["a"]
        self.assertEqual((w["kind"], w["depth"], w["tokens"], w["description"]), ("subagent", 3, 42, "hello"))
        self.assertEqual((w["started"], w["last_activity"]), (NOW - 100, NOW - 10))


class BgTaskStateTest(unittest.TestCase):
    def test_no_notification_is_running(self):
        self.assertEqual(state_of(bg("t")), "running")

    def test_statuses(self):
        self.assertEqual(state_of(bg("t", status="completed")), "done")
        self.assertEqual(state_of(bg("t", status="failed")), "failed")
        self.assertEqual(state_of(bg("t", status="killed")), "killed")

    def test_unknown_status_is_done(self):
        self.assertEqual(state_of(bg("t", status="weird")), "done")

    def test_empty_or_non_string_status_is_no_status(self):
        for bad in ("", ["x"], 0):
            self.assertEqual(state_of(bg("t", status=bad)), "running", bad)
            self.assertEqual(state_of(bg("t", status=bad, started=999.0)), "ended", bad)

    def test_task_started_before_session_is_ended(self):
        # session được resume: notification của lần chạy trước không còn nên task không thể "running"
        self.assertEqual(state_of(bg("t", started=999.0)), "ended")

    def test_task_started_after_session_is_running(self):
        self.assertEqual(state_of(bg("t", started=1000.0)), "running")
        self.assertEqual(state_of(bg("t", started=1500.0)), "running")

    def test_unknown_start_is_running(self):
        self.assertEqual(state_of(bg("t", started=None)), "running")

    def test_real_status_wins_over_old_start(self):
        self.assertEqual(state_of(bg("t", started=1.0, status="failed")), "failed")

    def test_output_fields(self):
        w = workers([sess(workers=[bg("t")])])["t"]
        self.assertEqual((w["kind"], w["tool_use_id"], w["started"]), ("bgtask", "tb-t", NOW - 50))


class TreeTest(unittest.TestCase):
    def test_parent_is_session_by_default(self):
        w = workers([sess(workers=[sub("a")])])
        self.assertIsNone(w["a"]["parent"])

    def test_session_agent_calls_means_session_parent(self):
        w = workers([sess(agent_calls=["tu-a"], workers=[sub("a")])])
        self.assertIsNone(w["a"]["parent"])

    def test_nested_parent(self):
        a = sub("a", agent_calls=["tu-b"])
        b = sub("b", agent_calls=["tu-c"])
        w = workers([sess(agent_calls=["tu-a"], workers=[a, b, sub("c")])])
        self.assertEqual((w["a"]["parent"], w["b"]["parent"], w["c"]["parent"]), (None, "a", "b"))

    def test_child_listed_before_parent(self):
        w = workers([sess(workers=[sub("c"), sub("p", agent_calls=["tu-c"])])])
        self.assertEqual(w["c"]["parent"], "p")

    def test_unknown_tool_use_id_falls_back_to_session(self):
        w = workers([sess(workers=[sub("a", tool_use_id="zzz"), sub("b", tool_use_id=None)])])
        self.assertEqual((w["a"]["parent"], w["b"]["parent"]), (None, None))

    def test_parent_lookup_stays_inside_session(self):
        other = sess(session_id="s2", workers=[sub("p", agent_calls=["tu-c"])])
        mine = sess(workers=[sub("c")])
        self.assertIsNone(workers([other, mine])["c"]["parent"])

    def test_cycle_falls_back_to_session(self):
        a = sub("a", agent_calls=["tu-b"])
        b = sub("b", agent_calls=["tu-a"])
        w = workers([sess(workers=[a, b])])
        self.assertEqual((w["a"]["parent"], w["b"]["parent"]), (None, None))

    def test_self_reference(self):
        w = workers([sess(workers=[sub("a", agent_calls=["tu-a"])])])
        self.assertIsNone(w["a"]["parent"])

    def test_session_wins_when_both_list_same_tool_use_id(self):
        w = workers([sess(agent_calls=["tu-c"], workers=[sub("p", agent_calls=["tu-c"]), sub("c")])])
        self.assertIsNone(w["c"]["parent"])

    def test_parent_with_bad_id_is_not_linked(self):
        for bad in (5, None, "", ["p"]):
            p = sub("p", agent_calls=["tu-c"])
            p["id"] = bad
            c = sub("c")
            out = org.build([sess(workers=[p, c])], CFG, NOW)["projects"][0]["teams"][0]["sessions"][0]["workers"]
            self.assertIsNone(out[1]["parent"], bad)

    def test_parent_with_duplicate_id_is_not_linked(self):
        w = workers([sess(workers=[sub("p", agent_calls=["tu-c"]), sub("p"), sub("c")])])
        self.assertIsNone(w["c"]["parent"])

    def test_bgtask_id_equal_to_subagent_id_keeps_link(self):
        out = org.build([sess(workers=[sub("p", agent_calls=["tu-c"]), bg("p"), sub("c")])], CFG, NOW)
        ws = out["projects"][0]["teams"][0]["sessions"][0]["workers"]
        self.assertEqual([w["parent"] for w in ws if w["id"] == "c"], ["p"])

    def test_unlinked_child_does_not_keep_parent_running(self):
        p = sub("p", mtime=NOW - 500, agent_calls=["tu-c"])
        p["id"] = 5
        out = org.build([sess(workers=[p, sub("c")])], CFG, NOW)["projects"][0]["teams"][0]["sessions"][0]["workers"]
        self.assertEqual(out[0]["state"], "stuck")

    def test_child_of_cycle_keeps_its_parent(self):
        a = sub("a", agent_calls=["tu-b", "tu-c"])
        b = sub("b", agent_calls=["tu-a"])
        w = workers([sess(workers=[a, b, sub("c")])])
        self.assertEqual((w["a"]["parent"], w["b"]["parent"], w["c"]["parent"]), (None, None, "a"))

    def test_depth_cap_8(self):
        n = 12
        ws = [sub(f"w{i}", agent_calls=[f"tu-w{i + 1}"]) for i in range(n)]
        got = workers([sess(workers=ws)])
        level = {}

        def lv(i):
            if i not in level:
                p = got[f"w{i}"]["parent"]
                level[i] = 1 if p is None else lv(int(p[1:])) + 1
            return level[i]

        self.assertLessEqual(max(lv(i) for i in range(n)), 8)
        self.assertEqual(got["w7"]["parent"], "w6")      # tầng 8 vẫn lồng
        self.assertIsNone(got["w8"]["parent"])           # tầng 9 trở đi về session

    def test_workers_keep_input_order(self):
        s = org.build([sess(workers=[sub("b"), bg("a"), sub("c")])], CFG, NOW)["projects"][0]["teams"][0]["sessions"][0]
        self.assertEqual([w["id"] for w in s["workers"]], ["b", "a", "c"])


class GroupingTest(unittest.TestCase):
    def build(self, *sessions):
        return org.build(list(sessions), CFG, NOW)["projects"]

    def test_one_repo_two_worktrees(self):
        a = sess(session_id="a", git={"top": "/r", "common": "/r/.git", "branch": "main"})
        b = sess(session_id="b", cwd="/wt/a/sub",
                 git={"top": "/wt/a", "common": "/r/.git", "branch": "feat"})
        ps = self.build(a, b)
        self.assertEqual(len(ps), 1)
        self.assertEqual((ps[0]["name"], ps[0]["root"]), ("r", "/r"))
        self.assertEqual([(t["top"], t["branch"]) for t in ps[0]["teams"]], [("/r", "main"), ("/wt/a", "feat")])

    def test_team_is_top_not_cwd(self):
        a = sess(session_id="a", cwd="/r/pkg/x")
        b = sess(session_id="b", cwd="/r/pkg/y")
        ps = self.build(a, b)
        self.assertEqual(len(ps[0]["teams"]), 1)
        self.assertEqual(len(ps[0]["teams"][0]["sessions"]), 2)

    def test_common_not_named_dot_git_is_root(self):
        ps = self.build(sess(git={"top": "/x/wt", "common": "/x/bare", "branch": None}))
        self.assertEqual((ps[0]["root"], ps[0]["name"]), ("/x/bare", "bare"))

    def test_two_repos_two_projects(self):
        a = sess(session_id="a")
        b = sess(session_id="b", cwd="/q", git={"top": "/q", "common": "/q/.git", "branch": "m"})
        self.assertEqual([p["name"] for p in self.build(a, b)], ["r", "q"])

    def test_no_git_uses_cwd(self):
        ps = self.build(sess(git=None, cwd="/home/u/notes"))
        self.assertEqual((ps[0]["root"], ps[0]["name"]), ("/home/u/notes", "notes"))
        self.assertEqual(ps[0]["teams"][0]["top"], "/home/u/notes")
        self.assertIsNone(ps[0]["teams"][0]["branch"])

    def test_no_git_key_at_all(self):
        s = sess()
        del s["git"]
        self.assertEqual(self.build(s)[0]["root"], "/r")

    def test_partial_git_dict(self):
        ps = self.build(sess(git={"top": "/t"}, cwd="/t/sub"))
        self.assertEqual((ps[0]["root"], ps[0]["teams"][0]["top"]), ("/t", "/t"))
        ps = self.build(sess(git={}, cwd="/c"))
        self.assertEqual((ps[0]["root"], ps[0]["teams"][0]["top"]), ("/c", "/c"))

    def test_no_cwd_no_git(self):
        ps = self.build(sess(git=None, cwd=None))
        self.assertEqual(len(ps), 1)
        self.assertTrue(ps[0]["name"])

    def test_windows_paths(self):
        a = sess(session_id="a", cwd="C:\\repo\\src",
                 git={"top": "C:\\repo", "common": "C:\\repo\\.git", "branch": "main"})
        b = sess(session_id="b", cwd="C:\\wt\\a",
                 git={"top": "C:\\wt\\a", "common": "C:\\repo\\.git", "branch": "x"})
        ps = self.build(a, b)
        self.assertEqual(len(ps), 1)
        self.assertEqual((ps[0]["root"], ps[0]["name"]), ("C:\\repo", "repo"))
        self.assertEqual([t["top"] for t in ps[0]["teams"]], ["C:\\repo", "C:\\wt\\a"])

    def test_windows_no_git_and_trailing_sep(self):
        ps = self.build(sess(git=None, cwd="D:\\proj\\notes\\"))
        self.assertEqual(ps[0]["name"], "notes")
        ps = self.build(sess(git={"top": "C:\\repo\\", "common": "C:\\repo\\.git\\", "branch": None}))
        self.assertEqual((ps[0]["root"], ps[0]["name"]), ("C:\\repo", "repo"))

    def test_mixed_separators(self):
        ps = self.build(sess(git={"top": "C:/repo", "common": "C:/repo/.git", "branch": None}))
        self.assertEqual((ps[0]["root"], ps[0]["name"]), ("C:/repo", "repo"))

    def test_trailing_separator_same_team_and_root(self):
        a = sess(session_id="a", git={"top": "/r", "common": "/r/.git", "branch": "main"})
        b = sess(session_id="b", git={"top": "/r/", "common": "/r/.git/", "branch": "main"})
        c = sess(session_id="c", git=None, cwd="/r/")
        ps = self.build(a, b, c)
        self.assertEqual(len(ps), 1)
        self.assertEqual(len(ps[0]["teams"]), 1)
        self.assertEqual((ps[0]["teams"][0]["top"], ps[0]["root"]), ("/r", "/r"))
        self.assertEqual(len(ps[0]["teams"][0]["sessions"]), 3)

    def test_team_branch_filled_by_later_session(self):
        a = sess(session_id="a", git={"top": "/r", "common": "/r/.git", "branch": None})
        b = sess(session_id="b", git={"top": "/r", "common": "/r/.git", "branch": "feat"})
        c = sess(session_id="c", git={"top": "/r", "common": "/r/.git", "branch": "other"})
        self.assertEqual(self.build(a, b, c)[0]["teams"][0]["branch"], "feat")

    def test_git_is_cleaned_copy(self):
        g = {"top": "/r", "common": "/r/.git", "branch": "ma\x85in\u202e", "dirty": 3}
        s = sess(git=g)
        out = org.build([s], CFG, NOW)["projects"][0]["teams"][0]["sessions"][0]["git"]
        self.assertIsNot(out, g)
        self.assertEqual((out["branch"], out["dirty"]), ("main", 3))
        self.assertEqual(g["branch"], "ma\x85in\u202e")

    def test_session_keeps_existing_keys(self):
        s = org.build([sess(extra="x")], CFG, NOW)["projects"][0]["teams"][0]["sessions"][0]
        for k in ("session_id", "started_at", "cwd", "git", "name", "status", "extra", "workers", "counts"):
            self.assertIn(k, s)
        self.assertNotIn("agent_calls", s)


class CountsTest(unittest.TestCase):
    def setUp(self):
        self.s1 = sess(session_id="s1", workers=[
            sub("a"), sub("b", mtime=NOW - 999), sub("c", finished=True), sub("d", notif_status="failed"),
            sub("e", notif_status="killed"), bg("t"), bg("u", status="completed"), bg("v", started=1.0)])
        self.s2 = sess(session_id="s2", cwd="/wt", git={"top": "/wt", "common": "/r/.git", "branch": "x"},
                       workers=[sub("a"), bg("t")])

    def test_session_counts(self):
        c = org.build([self.s1], CFG, NOW)["projects"][0]["teams"][0]["sessions"][0]["counts"]
        self.assertEqual(c["subagent"], {"total": 5, "running": 1, "stuck": 1, "done": 1, "failed": 1,
                                         "killed": 1, "ended": 3})
        self.assertEqual(c["bgtask"], {"total": 3, "running": 1, "stuck": 0, "done": 1, "failed": 0,
                                       "killed": 0, "ended": 2})

    def test_rollup_team_project_root(self):
        tree = org.build([self.s1, self.s2], CFG, NOW)
        proj = tree["projects"][0]
        t1, t2 = proj["teams"]
        self.assertEqual(t1["counts"]["subagent"]["total"], 5)
        self.assertEqual(t2["counts"]["subagent"]["running"], 1)
        self.assertEqual(proj["counts"]["subagent"]["total"], 6)
        self.assertEqual(proj["counts"]["bgtask"]["running"], 2)
        self.assertEqual(tree["counts"], proj["counts"])

    def test_empty_counts_are_zero(self):
        c = org.build([sess()], CFG, NOW)["projects"][0]["counts"]
        self.assertEqual(c["subagent"]["total"], 0)
        self.assertEqual(c["bgtask"]["stuck"], 0)

    def test_empty_input(self):
        tree = org.build([], CFG, NOW)
        self.assertEqual(tree["projects"], [])
        self.assertEqual(tree["counts"]["subagent"]["total"], 0)


class RobustnessTest(unittest.TestCase):
    def test_worker_with_missing_fields(self):
        bad = [{}, {"kind": "subagent"}, {"kind": "bgtask"}, {"kind": "other", "id": "x"}, None, 5, "x", [],
               {"kind": "subagent", "id": "s", "depth": "x", "tokens": None, "mtime": "no", "open_tools": "q",
                "agent_calls": 7, "started": "y", "finished": "yes"}]
        ok = sub("ok")
        w = workers([sess(workers=[*bad, ok])])
        self.assertEqual(w["ok"]["state"], "running")
        self.assertEqual(w["s"]["depth"], 0)
        self.assertEqual(w["s"]["tokens"], 0)
        self.assertIsNone(w["s"]["started"])

    def test_session_without_workers_keys(self):
        for s in (sess(workers=None), sess(workers="x")):
            self.assertEqual(workers([s]), {})
        s = sess()
        del s["workers"], s["agent_calls"]
        self.assertEqual(workers([s]), {})

    def test_bad_agent_calls_ignored(self):
        w = workers([sess(agent_calls=5, workers=[sub("a", agent_calls=[None, ["x"], {}, "tu-b"]), sub("b")])])
        self.assertEqual(w["b"]["parent"], "a")

    def test_depth_clamped(self):
        w = workers([sess(workers=[sub("a", depth=99), sub("b", depth=-4), sub("c", depth="2"), sub("d", depth=2.9)])])
        self.assertEqual([w[k]["depth"] for k in "abcd"], [8, 0, 2, 2])

    def test_non_dict_session_skipped(self):
        tree = org.build([None, "x", sess()], CFG, NOW)
        self.assertEqual(len(tree["projects"]), 1)

    def test_strings_cut_and_stripped(self):
        w = sub("a", description="x\x00\n\r\t\x1b[31m" + "y" * 500, agent_type="les-\x07eng")
        out = workers([sess(workers=[w])])["a"]
        self.assertEqual(out["description"], "x[31m" + "y" * 195)
        self.assertEqual(out["type"], "les-eng")
        self.assertEqual(out["department"], "eng")

    def test_c1_bidi_and_separator_chars_stripped(self):
        w = sub("a", description="a\x85b\x9bc\u202ed\u2028e\u2029f\u200bg\u200fh\u202ai\x7fj")
        self.assertEqual(workers([sess(workers=[w])])["a"]["description"], "abcdefghij")

    def test_isolates_alm_and_bom_stripped(self):
        w = sub("a", description="a\u2066b\u2067c\u2068d\u2069e\u061cf\ufeffg")
        self.assertEqual(workers([sess(workers=[w])])["a"]["description"], "abcdefg")

    def test_subagent_with_missing_meta_defaults(self):
        # meta thiếu hoặc không đọc được: claude_data cấp giá trị mặc định
        d = sub("m", agent_type="?", description="", tool_use_id=None, depth=0, finished=False, notif_status=None)
        w = workers([sess(workers=[d])])["m"]
        self.assertEqual((w["type"], w["department"], w["description"], w["depth"], w["parent"]),
                         ("?", "?", "", 0, None))
        self.assertEqual(w["state"], "running")
        self.assertEqual(state_of({**d, "mtime": NOW - 500}), "stuck")
        self.assertEqual(state_of({**d, "mtime": NOW - 500, "notif_status": "failed"}), "failed")
        self.assertEqual(state_of({**d, "mtime": NOW - 500, "open_tools": 1}), "running")

    def test_other_string_fields_cut(self):
        long = "z" * 500
        tree = org.build([sess(name=long + "\n", cwd="/" + long, git={"top": "/" + long, "common": "/q/.git",
                                                                      "branch": long})], CFG, NOW)
        p = tree["projects"][0]
        self.assertLessEqual(len(p["teams"][0]["top"]), 200)
        self.assertLessEqual(len(p["teams"][0]["branch"]), 200)
        self.assertLessEqual(len(p["teams"][0]["sessions"][0]["name"]), 200)

    def test_non_string_fields_become_empty(self):
        out = workers([sess(workers=[sub("a", description=None, agent_type=5)])])["a"]
        self.assertEqual((out["description"], out["type"]), ("", ""))

    def test_json_dumps_ok(self):
        s = sess(workers=[sub("a", agent_calls=["tu-b"]), sub("b"), bg("t"), {"kind": "subagent"}],
                 agent_calls=["tu-a"])
        tree = org.build([s, sess(session_id="s2", git=None)], CFG, NOW)
        json.dumps(tree)

    def test_input_not_mutated(self):
        sessions = [sess(workers=[sub("a", description="x\n"), bg("t")], agent_calls=["tu-a"])]
        before = copy.deepcopy(sessions)
        org.build(sessions, CFG, NOW)
        self.assertEqual(sessions, before)


class PurityTest(unittest.TestCase):
    BAD_IMPORTS = {"tkinter", "os", "subprocess", "time", "datetime", "pathlib", "io", "socket", "importlib",
                   "shutil"}
    BAD_CALLS = {"open", "__import__", "eval", "exec"}

    def test_no_forbidden_imports_or_calls(self):
        src = Path(org.__file__).read_text(encoding="utf-8")
        imports, calls = set(), set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)
        self.assertFalse(imports & self.BAD_IMPORTS, imports)
        self.assertFalse(calls & self.BAD_CALLS, calls)


if __name__ == "__main__":
    unittest.main()
