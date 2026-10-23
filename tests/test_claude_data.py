"""Test ingest worker (subagent / task nền) của claude_data: dữ liệu mẫu trong tests/fixtures và thư mục tạm,
không đọc ~/.claude thật, không cần Tk."""
import json
import os
import shutil
import tempfile
import threading
import tracemalloc
import unittest
from pathlib import Path

from pet_tracker import claude_data
from pet_tracker.claude_data import ClaudeDataStore, Transcript

FX = Path(__file__).parent / "fixtures"
SID = "sess1"
CW = {"default": 1_000_000}
OLD_KEYS = {
    "session_id", "pid", "proc_start", "transcript", "name", "title", "cwd", "home_cwd", "git_branch", "status",
    "entrypoint", "host_session_id", "version", "started_at", "model", "effort", "context_tokens", "context_limit",
    "context_pct", "last_activity", "subagents", "totals", "has_transcript",
}


def jl(*recs):
    return "".join((r if isinstance(r, str) else json.dumps(r, separators=(",", ":"))) + "\n" for r in recs)


def asst(mid, blocks, model="claude-test-1", usage=True):
    m = {"id": mid, "role": "assistant", "model": model, "content": blocks}
    if usage:
        m["usage"] = {"input_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 1}
    return {"type": "assistant", "message": m, "timestamp": "2026-10-22T08:00:00.000Z"}


def tu(i, name="Agent"):
    return {"type": "tool_use", "id": i, "name": name, "input": {}}


def bg(task, tuid="toolu_B"):
    return {"type": "user", "timestamp": "2026-10-22T08:00:00.000Z",
            "message": {"role": "user", "content": [{"tool_use_id": tuid, "type": "tool_result", "content": "bg"}]},
            "toolUseResult": {"stdout": "", "backgroundTaskId": task}}


def notif(task, tuid=None, status=None):
    c = f"<task-notification>\n<task-id>{task}</task-id>\n"
    if tuid:
        c += f"<tool-use-id>{tuid}</tool-use-id>\n"
    if status:
        c += f"<status>{status}</status>\n"
    c += "<summary>s</summary>\n</task-notification>"
    return {"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-10-22T08:00:00.000Z",
            "sessionId": SID, "content": c}


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def fixture(self, name, dest):
        p = self.root / dest
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FX / name, p)
        return p

    def transcript(self, name, sidechain=False):
        t = Transcript(str(self.fixture(name, "t/" + name)), sidechain=sidechain)
        t.poll()
        return t

    # ---- cây thư mục ~/.claude giả
    def claude(self, sid=SID, main=None, subs=None, name="claude"):
        """main: nội dung transcript chính; subs: {"agent-x": (nội dung jsonl, dict meta | str | None)}."""
        c = self.root / name
        (c / "sessions").mkdir(parents=True, exist_ok=True)
        (c / "sessions" / f"{os.getpid()}-{sid}.json").write_text(json.dumps(
            {"pid": os.getpid(), "sessionId": sid, "cwd": "/tmp/fx", "status": "idle", "startedAt": 1_700_000_000_000}))
        proj = c / "projects" / "p"
        proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{sid}.jsonl").write_text(main if main is not None else "", encoding="utf-8")
        for stem, (body, meta) in (subs or {}).items():
            d = proj / sid / "subagents"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{stem}.jsonl").write_text(body, encoding="utf-8")
            if meta is not None:
                (d / f"{stem}.meta.json").write_text(meta if isinstance(meta, str) else json.dumps(meta))
        return c

    def meta_path(self, stem, sid=SID):
        return self.root / "claude" / "projects" / "p" / sid / "subagents" / f"{stem}.meta.json"

    def session(self, store, sid=SID):
        store.poll_all()  # như Collector: poll_all trước active_sessions
        return next(s for s in store.active_sessions(CW) if s["session_id"] == sid)

    def workers(self, store, sid=SID):
        return {w["id"]: w for w in self.session(store, sid)["workers"]}


class TranscriptIngest(Base):
    def test_main_fixture_fields(self):
        t = self.transcript("main.jsonl")
        self.assertEqual(t.agent_calls, ["toolu_A1", "toolu_T1"])
        self.assertEqual(t.notifs, {"toolu_A1": "completed", "toolu_B1": "failed", "toolu_B2": "killed"})
        self.assertEqual(set(t.bg_tasks), {"bgs1", "bgs2", "bgs3"})
        self.assertEqual(t.bg_tasks["bgs1"]["tool_use_id"], "toolu_B1")
        self.assertEqual(t.bg_tasks["bgs1"]["status"], "failed")
        self.assertEqual(t.bg_tasks["bgs2"]["status"], "killed")
        self.assertIsNone(t.bg_tasks["bgs3"]["status"])
        self.assertIsInstance(t.bg_tasks["bgs1"]["started"], float)
        self.assertEqual(set(t.open_tools), set())  # file chính không theo dõi open_tools

    def test_monitor_notification_ignored(self):
        t = self.transcript("main.jsonl")
        self.assertNotIn("mon1", t.bg_tasks)
        self.assertNotIn("mon1", t.task_notifs)
        self.assertEqual(len(t.notifs), 3)

    def test_decoys_ignored(self):
        # chuỗi marker trong text của assistant, notification giả nằm trong tool_result, <status> giả trong <result>
        t = self.transcript("main.jsonl")
        self.assertNotIn("fake", t.task_notifs)
        self.assertNotIn("toolu_D1", t.agent_calls)
        self.assertIsNone(t.bg_tasks["bgs3"]["status"])
        self.assertEqual(t.notifs["toolu_A1"], "completed")

    def test_status_only_after_summary_or_result_ignored(self):
        c = ("<task-notification>\n<task-id>k1</task-id>\n<tool-use-id>toolu_1</tool-use-id>\n"
             "<summary>x</summary>\n<result><status>completed</status></result>\n</task-notification>")
        p = self.write("m.jsonl", jl({"type": "queue-operation", "operation": "enqueue", "content": c}))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual((t.notifs, t.task_notifs), ({}, {}))

    def test_title_still_read(self):
        # đường quét marker tiêu đề đã được cổng theo độ dài dòng: hành vi cũ giữ nguyên với record thật
        t = self.transcript("main.jsonl")
        self.assertEqual(t.title, "fixture")
        p = self.write("m.jsonl", jl({"type": "ai-title", "aiTitle": "ai one"}, {"type": "agent-name", "agentName": "nm"}))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.title, "ai one")

    def test_bg_record_size_ceiling(self):
        small = dict(bg("k_small"), pad="x" * 10_000)
        huge = dict(bg("k_huge"), pad="x" * (claude_data.MAX_SMALL_LINE + 10))
        p = self.write("m.jsonl", jl(small, huge))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(list(t.bg_tasks), ["k_small"])

    def test_usage_and_agent_call_same_line(self):
        t = self.transcript("main.jsonl")
        self.assertIn("msg_1", t.msgs)
        self.assertIn("toolu_A1", t.agent_calls)

    def test_synthetic_line_still_records_agent_call(self):
        t = self.transcript("main.jsonl")
        self.assertNotIn("msg_2", t.msgs)
        self.assertIn("toolu_T1", t.agent_calls)

    def test_task_name_accepted(self):
        p = self.write("m.jsonl", jl(asst("m1", [tu("toolu_K", "Task")])))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.agent_calls, ["toolu_K"])

    def test_agent_call_not_duplicated_across_records(self):
        p = self.write("m.jsonl", jl(asst("m1", [tu("toolu_K")]), asst("m1", [tu("toolu_K")])))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.agent_calls, ["toolu_K"])

    def test_subagent_open_tools(self):
        t = self.transcript("agent-x.jsonl", sidechain=True)
        self.assertEqual(set(t.open_tools), {"toolu_S2"})

    def test_open_tools_tool_use_in_text_not_counted(self):
        # fixture có tool_result chứa chuỗi giả "type":"tool_use","id":"toolu_FAKE" (đã escape)
        t = self.transcript("agent-x.jsonl", sidechain=True)
        self.assertNotIn("toolu_FAKE", t.open_tools)

    def test_open_tools_incremental(self):
        p = self.write("a.jsonl", jl(asst("m1", [tu("toolu_1", "Bash")])))
        t = Transcript(str(p), sidechain=True)
        t.poll()
        self.assertEqual(set(t.open_tools), {"toolu_1"})
        with open(p, "a") as f:
            f.write(jl({"type": "user", "message": {"role": "user", "content": [
                {"tool_use_id": "toolu_1", "type": "tool_result", "content": "x"}]}}))
        t.poll()
        self.assertEqual(set(t.open_tools), set())

    def test_rewrite_shorter_clears_new_fields(self):
        p = self.fixture("main.jsonl", "m.jsonl")
        t = Transcript(str(p))
        t.poll()
        self.assertTrue(t.notifs and t.bg_tasks and t.agent_calls)
        p.write_text(jl(asst("n1", [tu("toolu_NEW")])), encoding="utf-8")
        self.assertTrue(t.poll())
        self.assertEqual(t.agent_calls, ["toolu_NEW"])
        self.assertEqual((t.notifs, t.task_notifs, t.bg_tasks, t.open_tools), ({}, {}, {}, {}))
        self.assertEqual(list(t.msgs), ["n1"])

    def test_rewrite_clears_open_tools_and_skip_state(self):
        p = self.write("a.jsonl", jl(asst("m1", [tu("toolu_1", "Bash")])) + "x" * (claude_data.MAX_LINE + 10))
        t = Transcript(str(p), sidechain=True)
        t.poll()
        p.write_text(jl(asst("m2", [tu("toolu_2")])), encoding="utf-8")
        t.poll()
        self.assertEqual(set(t.open_tools), {"toolu_2"})
        self.assertEqual(list(t.msgs), ["m2"])

    def test_pending_line_over_limit_dropped_and_next_line_ok(self):
        big = '{"type":"assistant","pad":"' + "a" * (claude_data.MAX_LINE + 5000)
        p = self.write("m.jsonl", jl(asst("m1", [tu("toolu_1")])) + big)
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.buf, b"")  # dòng chờ quá lớn không giữ trong RAM
        with open(p, "a") as f:  # phần còn lại của dòng bị bỏ, rồi một dòng hợp lệ
            f.write(jl(asst("ghost", [tu("toolu_GHOST")])) + jl(asst("m2", [tu("toolu_2")])))  # phần đuôi dòng bị bỏ có hình dạng hợp lệ
        t.poll()
        self.assertEqual(list(t.msgs), ["m1", "m2"])
        self.assertEqual(t.agent_calls, ["toolu_1", "toolu_2"])

    def test_pending_under_limit_kept(self):
        line = jl(asst("m1", [tu("toolu_1")]))
        p = self.write("m.jsonl", line[:50])
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(len(t.buf), 50)
        with open(p, "a") as f:
            f.write(line[50:])
        t.poll()
        self.assertEqual(t.agent_calls, ["toolu_1"])

    def test_strings_cut_at_200(self):
        long_id = "t" * 300
        p = self.write("m.jsonl", jl(asst("m1", [tu(long_id)]), bg("b" * 300, "u" * 300)))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.agent_calls, ["t" * 200])
        (tid, info), = t.bg_tasks.items()
        self.assertEqual(len(tid), 200)
        self.assertEqual(len(info["tool_use_id"]), 200)

    def test_bg_tasks_cap_keeps_newest(self):
        n = claude_data.CAP_ITEMS + 50
        p = self.write("m.jsonl", jl(*[bg(f"bg{i}") for i in range(n)]))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(len(t.bg_tasks), 500)
        self.assertIn(f"bg{n - 1}", t.bg_tasks)
        self.assertNotIn("bg0", t.bg_tasks)

    def test_agent_calls_cap(self):
        n = claude_data.CAP_ITEMS + 5
        p = self.write("m.jsonl", jl(*[asst(f"m{i}", [tu(f"toolu_{i}")]) for i in range(n)]))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(len(t.agent_calls), 500)
        self.assertEqual(t.agent_calls[-1], f"toolu_{n - 1}")

    def test_notifs_cap(self):
        n = claude_data.CAP_NOTIFS + 10
        p = self.write("m.jsonl", jl(*[notif(f"k{i}", f"toolu_{i}", "completed") for i in range(n)]))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(len(t.notifs), claude_data.CAP_NOTIFS)
        self.assertEqual(len(t.task_notifs), claude_data.CAP_NOTIFS)
        self.assertIn(f"toolu_{n - 1}", t.notifs)

    def test_notification_id_over_200_ignored(self):
        p = self.write("m.jsonl", jl(notif("k" * 300, "toolu_1", "completed")))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual((t.notifs, t.task_notifs), ({}, {}))

    def test_last_notification_status_wins(self):
        p = self.write("m.jsonl", jl(notif("k", "toolu_1", "completed"), notif("k", "toolu_1", "failed")))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.notifs["toolu_1"], "failed")

    def test_notification_without_tool_use_id_keeps_task_status(self):
        p = self.write("m.jsonl", jl(bg("k"), notif("k", None, "completed")))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.notifs, {})
        self.assertEqual(t.bg_tasks["k"]["status"], "completed")

    def test_notification_before_bg_record_applies_status(self):
        p = self.write("m.jsonl", jl(notif("k", None, "completed"), bg("k")))
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.bg_tasks["k"]["status"], "completed")

    def patch(self, **kw):
        for k, v in kw.items():
            self.addCleanup(setattr, claude_data, k, getattr(claude_data, k))
            setattr(claude_data, k, v)

    def test_chunked_read_completes_in_one_poll(self):
        self.patch(MAX_POLL_BYTES=4096)
        body = jl(*[asst(f"m{i}", [tu(f"toolu_{i}")]) for i in range(100)])
        self.assertGreater(len(body), 3 * 4096)
        p = self.write("m.jsonl", body)
        t = Transcript(str(p))
        self.assertTrue(t.poll())
        self.assertEqual(t.offset, len(body))  # đọc tới EOF ngay trong một lần poll
        self.assertEqual((len(t.agent_calls), len(t.msgs), t.buf), (100, 100, b""))  # dòng vắt ranh giới chunk ghép đúng
        self.assertFalse(t.poll())

    def test_chunked_read_incremental_append(self):
        self.patch(MAX_POLL_BYTES=4096)
        p = self.write("m.jsonl", jl(asst("m0", [tu("toolu_0")])))
        t = Transcript(str(p))
        t.poll()
        with open(p, "a") as f:
            f.write(jl(*[asst(f"m{i}", [tu(f"toolu_{i}")]) for i in range(1, 60)]))
        t.poll()
        self.assertEqual(len(t.agent_calls), 60)

    def test_big_line_spanning_chunks_dropped_next_lines_ok(self):
        self.patch(MAX_POLL_BYTES=4096, MAX_LINE=10_000)
        big = asst("big", [tu("toolu_BIG"), {"type": "text", "text": "x" * 11_000}])  # dài hơn MAX_LINE và hơn một chunk
        mid = asst("mid", [tu("toolu_MID"), {"type": "text", "text": "y" * 6_000}])  # vắt ranh giới nhưng < MAX_LINE
        for pad in (0, 1000, 3000, 4000):
            with self.subTest(pad=pad):
                p = self.write(f"m{pad}.jsonl", jl(asst("m1", [tu("toolu_1"), {"type": "text", "text": "p" * pad}]), big, mid, asst("m2", [tu("toolu_2")])))
                t = Transcript(str(p))
                t.poll()
                self.assertEqual(t.agent_calls, ["toolu_1", "toolu_MID", "toolu_2"])
                self.assertEqual(list(t.msgs), ["m1", "mid", "m2"])
                self.assertEqual(t.buf, b"")

    def test_every_line_over_max_line_dropped_whatever_the_boundaries(self):
        self.patch(MAX_LINE=10_000)
        big = asst("big", [tu("toolu_BIG"), {"type": "text", "text": "x" * 11_000}])
        lines = [asst("m1", [tu("toolu_1")]), big, asst("m2", [tu("toolu_2")]), big, asst("m3", [tu("toolu_3")])]
        ref = None
        for pad in (0, 7, 1000, 4090):
            body = jl(asst("m0", [{"type": "text", "text": "p" * pad}]), *lines)
            for chunk in (512, 4096, 10_000, 10_001, 1 << 20):
                self.patch(MAX_POLL_BYTES=chunk)
                p = self.write(f"c{pad}_{chunk}.jsonl", body)
                t = Transcript(str(p))
                t.poll()
                with self.subTest(pad=pad, chunk=chunk):
                    self.assertEqual(t.agent_calls, ["toolu_1", "toolu_2", "toolu_3"])
                    self.assertEqual(list(t.msgs), ["m0", "m1", "m2", "m3"])
                # đọc tăng dần (ghi từng mảnh 777 byte, poll sau mỗi mảnh) cho cùng kết quả với đọc nguội
                q = self.root / f"i{pad}_{chunk}.jsonl"
                q.write_bytes(b"")
                inc = Transcript(str(q))
                raw = body.encode()
                for k in range(0, len(raw), 777):
                    with open(q, "ab") as f:
                        f.write(raw[k:k + 777])
                    inc.poll()
                with self.subTest(pad=pad, chunk=chunk, mode="incremental"):
                    self.assertEqual((inc.totals(), inc.last_main, inc.agent_calls), (t.totals(), t.last_main, t.agent_calls))

    def test_max_line_boundary_exact_kept_one_over_dropped(self):
        self.patch(MAX_LINE=5000)

        def line(n):  # record dài đúng n byte (không tính \n)
            base = len(json.dumps(asst("m", [tu("toolu_X"), {"type": "text", "text": ""}]), separators=(",", ":")))
            return json.dumps(asst("m", [tu("toolu_X"), {"type": "text", "text": "x" * (n - base)}]), separators=(",", ":"))
        for n, kept in ((5000, True), (5001, False)):
            with self.subTest(n=n):
                self.assertEqual(len(line(n)), n)
                p = self.write(f"b{n}.jsonl", line(n) + "\n")
                t = Transcript(str(p))
                t.poll()
                self.assertEqual(t.agent_calls, ["toolu_X"] if kept else [])

    def test_lines_shorter_than_min_line_never_reach_ingest(self):
        seen = []
        p = self.write("m.jsonl", "\n" + "a" * (claude_data.MIN_LINE - 1) + "\n\n" + "b" * claude_data.MIN_LINE + "\n" + "c" * 3 + "\n" + jl(asst("m1", [tu("toolu_1")])))
        t = Transcript(str(p))
        t._ingest = seen.append  # thay _ingest của instance để đếm lời gọi
        t.poll()
        self.assertEqual(len(seen), 2)  # dòng đúng MIN_LINE byte và record thật; mọi dòng ngắn hơn không tới _ingest
        self.assertTrue(all(len(x) >= claude_data.MIN_LINE for x in seen))
        self.assertEqual(seen[0], b"b" * claude_data.MIN_LINE)

    def test_open_tools_cap_evicts_oldest(self):
        n = claude_data.CAP_ITEMS + 5
        p = self.write("a.jsonl", jl(*[asst(f"m{i}", [tu(f"toolu_{i}", "Bash")]) for i in range(n)]))
        t = Transcript(str(p), sidechain=True)
        t.poll()
        self.assertEqual(len(t.open_tools), claude_data.CAP_ITEMS)
        self.assertIn(f"toolu_{n - 1}", t.open_tools)
        self.assertNotIn("toolu_0", t.open_tools)

    def test_unterminated_big_line_across_chunks_then_recovers(self):
        self.patch(MAX_POLL_BYTES=4096, MAX_LINE=10_000)
        p = self.write("m.jsonl", jl(asst("m1", [tu("toolu_1")])) + '{"type":"assistant","pad":"' + "a" * 30_000)
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.buf, b"")
        with open(p, "a") as f:
            f.write(jl(asst("ghost", [tu("toolu_GHOST")])) + jl(asst("m2", [tu("toolu_2")])))
        t.poll()
        self.assertEqual(t.agent_calls, ["toolu_1", "toolu_2"])

    def test_short_lines_skipped_valid_record_still_ingested(self):
        junk = "\n" * 50_000 + "x\n" * 1000 + "{}\n"
        p = self.write("m.jsonl", junk + jl(asst("m1", [tu("toolu_1")])) + "\n\n")
        t = Transcript(str(p))
        t.poll()
        self.assertEqual(t.agent_calls, ["toolu_1"])
        self.assertEqual(list(t.msgs), ["m1"])

    def test_newline_runs_straddling_chunks_ingest_each_record_once(self):
        recs = [asst(f"m{i}", [tu(f"toolu_{i}")]) for i in range(6)]
        for run in (1, 2, 37, 500):
            body = ("\n" * run).join(json.dumps(r, separators=(",", ":")) for r in recs) + "\n" * run
            for chunk in (7, 64, 100, 333, 1 << 20):
                self.patch(MAX_POLL_BYTES=chunk)
                p = self.write(f"nl{run}_{chunk}.jsonl", body)
                t = Transcript(str(p))
                t.poll()
                with self.subTest(run=run, chunk=chunk):
                    self.assertEqual(t.agent_calls, [f"toolu_{i}" for i in range(6)])
                    self.assertEqual(list(t.msgs), [f"m{i}" for i in range(6)])
                    self.assertEqual(t.buf, b"")
                q = self.root / f"nli{run}_{chunk}.jsonl"  # ghi tăng dần, mảnh 50 byte cắt cả giữa chuỗi \n
                q.write_bytes(b"")
                inc = Transcript(str(q))
                for k in range(0, len(body), 50):
                    with open(q, "a") as f:
                        f.write(body[k:k + 50])
                    inc.poll()
                with self.subTest(run=run, chunk=chunk, mode="incremental"):
                    self.assertEqual(inc.agent_calls, t.agent_calls)

    def test_bare_newlines_do_not_materialise_huge_list(self):
        self.patch(MAX_POLL_BYTES=4 << 20)
        p = self.write("nl.jsonl", "")
        with open(p, "wb") as f:
            f.write(b"\n" * (12 << 20))
            f.write(jl(asst("m1", [tu("toolu_1")])).encode())
        t = Transcript(str(p))
        tracemalloc.start()
        try:
            t.poll()
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(t.agent_calls, ["toolu_1"])
        self.assertLess(peak, 20 << 20)  # split() ra ~4M phần tử mỗi chunk: >= 32 MB nếu không gộp dãy \n

    def test_title_key_on_line_over_small_limit_ignored_on_purpose(self):
        # cổng MAX_SMALL_LINE: record tiêu đề thật < 1 KB; dòng dài hơn mang khoá tiêu đề không phải tiêu đề
        long_title = {"type": "ai-title", "aiTitle": "t" * (claude_data.MAX_SMALL_LINE + 10)}
        p = self.write("m.jsonl", jl(long_title))
        t = Transcript(str(p))
        t.poll()
        self.assertIsNone(t.title)


class MetaReading(Base):
    def one(self, meta, body=None, notif_line=None):
        main = jl(asst("m1", [tu("toolu_A1")])) + (jl(notif_line) if notif_line else "")
        c = self.claude(main=main, subs={"agent-x": (body or jl(asst("s1", [{"type": "text", "text": "hi"}])), meta)})
        s = ClaudeDataStore(str(c))
        return s, self.workers(s)["agent-x"]

    def test_fields_from_meta(self):
        _, w = self.one({"agentType": "les-scout", "description": "d", "toolUseId": "toolu_A1", "spawnDepth": 1})
        self.assertEqual((w["kind"], w["agent_type"], w["description"], w["tool_use_id"], w["depth"], w["finished"]),
                         ("subagent", "les-scout", "d", "toolu_A1", 1, False))
        self.assertIsNone(w["notif_status"])

    def test_no_meta_defaults(self):
        c = self.claude(main="", subs={"agent-x": (jl(asst("s1", [tu("toolu_1", "Bash")])), None)})
        w = self.workers(ClaudeDataStore(str(c)))["agent-x"]
        self.assertIsNone(w["tool_use_id"])
        self.assertEqual((w["agent_type"], w["description"], w["depth"], w["finished"]), ("?", "", 0, False))

    def test_meta_strings_cut_and_types_guarded(self):
        _, w = self.one({"agentType": "a" * 500, "description": {"x": 1}, "toolUseId": ["l"], "finished": "false"})
        self.assertEqual(len(w["agent_type"]), 200)
        self.assertEqual(w["description"], "")
        self.assertIsNone(w["tool_use_id"])
        self.assertFalse(w["finished"])

    def test_spawn_depth_guard(self):
        for raw, want in (("3", 3), (99, 8), (-5, 0), ("x", 0), (None, 0), (float("inf"), 0), (2.0, 2), ([1], 0), (True, 0)):
            with self.subTest(raw=raw):
                self.assertEqual(claude_data._depth(raw), want)

    def test_meta_over_64kb_skipped(self):
        meta = json.dumps({"agentType": "les-x", "description": "p" * (64 * 1024 + 1), "toolUseId": "toolu_A1", "finished": True})
        _, w = self.one(meta)
        self.assertEqual((w["agent_type"], w["description"], w["finished"]), ("?", "", False))
        self.assertIsNone(w["tool_use_id"])

    def test_meta_corrupt_or_wrong_type_skipped(self):
        for raw in ("{not json", "[1,2]", '"str"', "", "\x00\xff"):
            with self.subTest(raw=raw):
                _, w = self.one(raw)
                self.assertEqual(w["agent_type"], "?")

    def test_meta_reread_when_mtime_changes(self):
        s, w = self.one({"agentType": "a", "description": "one", "toolUseId": "toolu_A1"})
        self.assertEqual(w["description"], "one")
        mp = self.meta_path("agent-x")
        mp.write_text(json.dumps({"agentType": "a", "description": "two", "toolUseId": "toolu_A1"}))
        st = mp.stat()
        os.utime(mp, (st.st_atime, st.st_mtime + 5))
        self.assertEqual(self.workers(s)["agent-x"]["description"], "two")

    def test_meta_not_reread_without_mtime_change(self):
        s, _ = self.one({"agentType": "a", "description": "one", "toolUseId": "toolu_A1"})
        mp = self.meta_path("agent-x")
        st = mp.stat()
        mp.write_text(json.dumps({"agentType": "a", "description": "two", "toolUseId": "toolu_A1"}))
        os.utime(mp, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(self.workers(s)["agent-x"]["description"], "one")

    def test_meta_not_reread_after_finished(self):
        s, w = self.one({"agentType": "a", "description": "one", "toolUseId": "toolu_A1", "finished": True})
        self.assertTrue(w["finished"])
        mp = self.meta_path("agent-x")
        mp.write_text(json.dumps({"agentType": "a", "description": "two", "toolUseId": "toolu_A1"}))
        st = mp.stat()
        os.utime(mp, (st.st_atime, st.st_mtime + 5))
        w = self.workers(s)["agent-x"]
        self.assertEqual((w["description"], w["finished"]), ("one", True))

    def test_meta_not_reread_after_notification(self):
        s, w = self.one({"agentType": "a", "description": "one", "toolUseId": "toolu_A1"},
                        notif_line=notif("agt1", "toolu_A1", "completed"))
        self.assertEqual(w["notif_status"], "completed")
        mp = self.meta_path("agent-x")
        mp.write_text(json.dumps({"agentType": "a", "description": "two", "toolUseId": "toolu_A1"}))
        st = mp.stat()
        os.utime(mp, (st.st_atime, st.st_mtime + 5))
        self.assertEqual(self.workers(s)["agent-x"]["description"], "one")

    def test_meta_path_built_only_from_jsonl_path(self):
        # agentId/toolUseId độc hại không được ghép vào đường dẫn: file mồi ở nơi ghép id sẽ tới không được đọc
        evil = "../../evil"
        sub = self.root / "claude" / "projects" / "p" / SID / "subagents"
        body = jl(dict(asst("s1", [{"type": "text", "text": "x"}]), agentId=evil))
        c = self.claude(main=jl(asst("m1", [tu("toolu_A1")])),
                        subs={"agent-x": (body, {"agentType": "own", "description": "own", "toolUseId": evil, "agentId": evil})})
        for d in (sub, sub.parent, sub.parent.parent):
            (d / "evil.meta.json").write_text(json.dumps({"agentType": "EVIL", "description": "EVIL", "finished": True}))
        w = self.workers(ClaudeDataStore(str(c)))["agent-x"]
        self.assertEqual((w["agent_type"], w["description"], w["finished"]), ("own", "own", False))
        self.assertEqual(w["tool_use_id"], evil)  # chỉ là dữ liệu, không phải đường dẫn

    def test_meta_path_helper(self):
        self.assertEqual(claude_data._meta_path("/a/b/agent-x.jsonl"), "/a/b/agent-x.meta.json")


class OpenRegular(Base):
    def test_directory_rejected_and_fd_closed(self):
        d = self.root / "d"
        d.mkdir()
        fds = lambda: len(os.listdir("/dev/fd")) if os.path.isdir("/dev/fd") else 0  # noqa: E731
        before = fds()
        self.assertEqual(claude_data._open_regular(str(d)), (None, None))
        self.assertEqual(fds(), before)

    def test_missing_rejected(self):
        self.assertEqual(claude_data._open_regular(str(self.root / "nope")), (None, None))

    def test_regular_file_returns_binary_file_and_fstat(self):
        p = self.write("r.bin", "abc")
        f, st = claude_data._open_regular(str(p))
        self.addCleanup(lambda: f.close())
        self.assertEqual((f.read(), st.st_size), (b"abc", 3))


@unittest.skipUnless(hasattr(os, "mkfifo"), "cần os.mkfifo")
class NonRegularFiles(Base):
    def call(self, fn):
        """Chạy fn trong thread: FIFO không có writer làm open() treo mãi. Fail nếu còn treo sau 3 giây."""
        out = {}

        def run():
            try:
                out["r"] = fn()
            except BaseException as e:  # noqa: BLE001
                out["e"] = e
        th = threading.Thread(target=run, daemon=True)
        th.start()
        th.join(3)
        if th.is_alive():
            self.addCleanup(self.unblock)
            self.fail("treo trên FIFO")
        self.assertNotIn("e", out)
        return out.get("r")

    def fifo(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(path)
        self.fifos = getattr(self, "fifos", []) + [path]
        return path

    def unblock(self):  # nhả thread đang treo (nếu có) để process thoát sạch
        for p in getattr(self, "fifos", []):
            try:
                os.close(os.open(p, os.O_RDWR | os.O_NONBLOCK))
            except OSError:
                pass

    def test_transcript_poll_skips_fifo(self):
        p = self.fifo(self.root / "agent-f.jsonl")
        t = Transcript(str(p), sidechain=True)
        self.assertFalse(self.call(t.poll))
        self.assertEqual((t.offset, t.msgs), (0, {}))

    def test_meta_fifo_skipped(self):
        c = self.claude(main=jl(asst("m1", [tu("toolu_A1")])), subs={"agent-x": (jl(asst("s1", [tu("toolu_S", "Bash")])), None)})
        self.fifo(self.meta_path("agent-x"))
        w = self.call(lambda: self.workers(ClaudeDataStore(str(c))))["agent-x"]
        self.assertEqual((w["agent_type"], w["description"], w["tool_use_id"], w["finished"]), ("?", "", None, False))

    def test_jsonl_fifo_in_subagents_dir_skipped(self):
        c = self.claude(main=jl(asst("m1", [tu("toolu_A1")])), subs={"agent-x": (jl(asst("s1", [tu("toolu_S", "Bash")])), None)})
        self.fifo(self.root / "claude" / "projects" / "p" / SID / "subagents" / "agent-f.jsonl")
        workers = self.call(lambda: self.workers(ClaudeDataStore(str(c))))
        self.assertEqual(workers["agent-x"]["open_tools"], 1)

    def test_open_regular_fifo(self):
        p = self.fifo(self.root / "f")
        self.assertEqual(self.call(lambda: claude_data._open_regular(str(p))), (None, None))

    def test_regular_files_still_read(self):  # đường mở mới (O_NONBLOCK + fdopen) đọc file thường như cũ
        t = self.transcript("agent-x.jsonl", sidechain=True)
        self.assertEqual(len(t.msgs), 2)


class ActiveSessions(Base):
    def test_old_keys_kept_new_keys_added(self):
        c = self.claude(main=(FX / "main.jsonl").read_text(), subs={"agent-x": ((FX / "agent-x.jsonl").read_text(), None)})
        s = self.session(ClaudeDataStore(str(c)))
        self.assertEqual(set(s), OLD_KEYS | {"agent_calls", "workers"})
        self.assertEqual(s["subagents"], 1)
        self.assertEqual(s["agent_calls"], ["toolu_A1", "toolu_T1"])

    def test_claude_dir_with_glob_characters(self):
        c = self.claude(main=jl(asst("m1", [tu("toolu_A1")])), name="cl[ax]*?d",
                        subs={"agent-x": (jl(asst("s1", [{"type": "text", "text": "x"}])), {"toolUseId": "toolu_A1", "agentType": "t"})})
        s = self.session(ClaudeDataStore(str(c)))
        self.assertTrue(s["has_transcript"])
        self.assertEqual((s["agent_calls"], s["subagents"], [w["id"] for w in s["workers"]]), (["toolu_A1"], 1, ["agent-x"]))

    def test_no_transcript_session_has_empty_new_keys(self):
        c = self.root / "claude"
        (c / "sessions").mkdir(parents=True)
        (c / "projects").mkdir()
        (c / "sessions" / "1.json").write_text(json.dumps({"pid": os.getpid(), "sessionId": "nope", "cwd": "/x"}))
        s = self.session(ClaudeDataStore(str(c)), "nope")
        self.assertEqual((s["agent_calls"], s["workers"]), ([], []))

    def test_workers_content_and_json(self):
        c = self.claude(main=(FX / "main.jsonl").read_text(), subs={
            "agent-x": ((FX / "agent-x.jsonl").read_text(), json.loads((FX / "agent-x.meta.json").read_text())),
            "agent-y": ((FX / "agent-y.jsonl").read_text(), json.loads((FX / "agent-y.meta.json").read_text())),
        })
        sess = self.session(ClaudeDataStore(str(c)))
        json.dumps(sess)  # JSON thuần
        w = {x["id"]: x for x in sess["workers"]}
        self.assertEqual(set(w), {"agent-x", "agent-y", "bgs1", "bgs2", "bgs3"})  # Monitor (mon1) không có
        x = w["agent-x"]
        self.assertEqual((x["kind"], x["tool_use_id"], x["agent_type"], x["depth"], x["finished"], x["notif_status"]),
                         ("subagent", "toolu_A1", "les-scout", 1, False, "completed"))
        self.assertEqual((x["tokens"], x["open_tools"], x["agent_calls"]), (16, 1, []))
        self.assertIsInstance(x["mtime"], float)
        self.assertIsInstance(x["started"], float)
        self.assertIsInstance(x["last_activity"], float)
        y = w["agent-y"]
        self.assertTrue(y["finished"])
        self.assertIsNone(y["notif_status"])
        self.assertEqual(w["bgs1"], {"kind": "bgtask", "id": "bgs1", "tool_use_id": "toolu_B1", "started": w["bgs1"]["started"], "status": "failed"})
        self.assertIsInstance(w["bgs1"]["started"], float)
        self.assertEqual((w["bgs2"]["status"], w["bgs3"]["status"]), ("killed", None))

    def test_nested_subagent_notification_in_parent_subagent_transcript(self):
        main = jl(asst("m1", [tu("toolu_A1")]), notif("agt1", "toolu_A1", "completed"))
        x_body = jl(asst("s1", [tu("toolu_A2")]), notif("agt2", "toolu_A2", "failed"))  # thông báo của con nằm trong cha
        y_body = jl(asst("s2", [{"type": "text", "text": "y"}]))
        c = self.claude(main=main, subs={
            "agent-x": (x_body, {"agentType": "les-lead", "description": "x", "toolUseId": "toolu_A1", "spawnDepth": 1}),
            "agent-y": (y_body, {"agentType": "les-dev", "description": "y", "toolUseId": "toolu_A2", "spawnDepth": 2}),
        })
        sess = self.session(ClaudeDataStore(str(c)))
        w = {x["id"]: x for x in sess["workers"]}
        self.assertEqual(sess["agent_calls"], ["toolu_A1"])
        self.assertEqual(w["agent-x"]["agent_calls"], ["toolu_A2"])
        self.assertEqual((w["agent-y"]["depth"], w["agent-y"]["notif_status"]), (2, "failed"))
        self.assertEqual(w["agent-x"]["notif_status"], "completed")

    def test_notification_from_other_session_not_used(self):
        c = self.claude(sid="s-one", main=jl(asst("m1", [tu("toolu_A1")])),
                        subs={"agent-x": (jl(asst("s1", [tu("toolu_Z", "Bash")])), {"toolUseId": "toolu_A1", "agentType": "t"})})
        proj = c / "projects" / "p"
        (proj / "s-two.jsonl").write_text(jl(notif("zzz", "toolu_A1", "completed")))  # cùng id nhưng session khác
        self.assertIsNone(self.workers(ClaudeDataStore(str(c)), "s-one")["agent-x"]["notif_status"])

    def test_bgtask_in_subagent_transcript_and_status_from_main(self):
        main = jl(notif("bgs9", None, "completed"))
        body = jl(asst("s1", [tu("toolu_Q", "Bash")]), bg("bgs9", "toolu_Q"))  # record bg cũng là tool_result của Bash
        c = self.claude(main=main, subs={"agent-x": (body, {"toolUseId": "toolu_A1", "agentType": "t"})})
        w = self.workers(ClaudeDataStore(str(c)))
        self.assertEqual((w["bgs9"]["status"], w["bgs9"]["tool_use_id"]), ("completed", "toolu_Q"))
        self.assertEqual(w["agent-x"]["open_tools"], 0)

    def test_subagent_id_cut(self):
        c = self.claude(main="", subs={"agent-" + "z" * 230: (jl(asst("s1", [{"type": "text", "text": "x"}])), None)})
        (w,) = self.session(ClaudeDataStore(str(c)))["workers"]
        self.assertEqual(len(w["id"]), 200)

    def test_subagents_for_does_not_glob_session_id(self):
        c = self.claude(sid="ab", main=jl(asst("m1", [tu("toolu_1")])),
                        subs={"agent-x": (jl(asst("s1", [{"type": "text", "text": "x"}])), None)})
        for sid in ("a[bc]", "*", "a?"):
            self.claude(sid=sid, main=jl(asst("m2", [tu("toolu_2")])))
        s = ClaudeDataStore(str(c))
        s.poll_all()
        self.assertEqual([Path(t.path).stem for t in s.subagents_for("ab")], ["agent-x"])
        for sid in ("a[bc]", "*", "a?"):
            with self.subTest(sid=sid):
                self.assertEqual(s.subagents_for(sid), [])

    def test_workers_capped_per_session(self):
        subs = {f"agent-{i:04d}": (jl(asst(f"s{i}", [{"type": "text", "text": "x"}])), None) for i in range(claude_data.CAP_ITEMS + 5)}
        c = self.claude(main=jl(*[bg(f"bg{i}") for i in range(20)]), subs=subs)
        for i in range(claude_data.CAP_ITEMS + 5):  # mtime tăng dần theo i, đều mới hơn thời điểm bắt đầu của bg
            f = self.meta_path(f"agent-{i:04d}").with_suffix("").with_suffix(".jsonl")
            os.utime(f, (2_000_000_000 + i, 2_000_000_000 + i))
        sess = self.session(ClaudeDataStore(str(c)))
        self.assertEqual(len(sess["workers"]), claude_data.CAP_ITEMS)
        # 525 worker, giữ 500 mới nhất: bỏ 20 bgtask (cũ nhất) và 5 subagent cũ nhất
        self.assertEqual({w["id"] for w in sess["workers"]}, {f"agent-{i:04d}" for i in range(5, claude_data.CAP_ITEMS + 5)})
        self.assertEqual(sess["subagents"], claude_data.CAP_ITEMS + 5)  # số đếm cũ không bị cắt

    def test_second_call_picks_up_new_notification(self):
        c = self.claude(main=jl(bg("bgs1")))
        s = ClaudeDataStore(str(c))
        self.assertIsNone(self.workers(s)["bgs1"]["status"])
        with open(c / "projects" / "p" / f"{SID}.jsonl", "a") as f:
            f.write(jl(notif("bgs1", "toolu_B", "completed")))
        s.poll_all()
        self.assertEqual(self.workers(s)["bgs1"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
