"""S4: DEFAULTS cho org + Collector đưa `org` vào snapshot. Không cần Tk display."""
import json
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Import config/org trước stub tkinter: patch.dict gỡ mọi module import trong lúc stub khỏi sys.modules.
from pet_tracker import config, org

try:
    import tkinter  # noqa: F401
    from pet_tracker import ui
except ImportError:
    # Python không có _tkinter: ui.py chỉ dùng tk trong thân hàm nên stub đủ để import.
    # Chỉ stub trong lúc import rồi gỡ ra, để test khác (cần Tk thật) không thấy MagicMock.
    with mock.patch.dict(sys.modules, tkinter=mock.MagicMock(), **{"tkinter.font": mock.MagicMock()}):
        from pet_tracker import ui


class FakeStore:
    def __init__(self, sessions):
        self.sessions = sessions
        self.polls = 0

    def poll_all(self):
        self.polls += 1

    def active_sessions(self, context_windows):
        return [dict(s) for s in self.sessions]

    def usage_window(self, seconds, now):
        return {"input": 1, "output": 2}


def session(sid="s1"):
    return {"session_id": sid, "cwd": "/repo", "started_at": 1.0, "status": "busy", "name": "x",
            "agent_calls": [], "workers": []}


class DefaultsTest(unittest.TestCase):
    def test_org_keys(self):
        self.assertEqual(config.DEFAULTS["agent_prefixes"], ["les-"])
        self.assertEqual(config.DEFAULTS["stuck_after_sec"], 120)

    def _load(self, text=None):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "config.json"
            if text is not None:
                f.write_text(text, encoding="utf-8")
            with mock.patch.object(config, "CONFIG_FILE", f):
                return config.load_config()

    def test_list_default_not_shared(self):
        a = self._load()
        a["agent_prefixes"].append("x-")
        self.assertEqual(self._load()["agent_prefixes"], ["les-"])
        self.assertEqual(config.DEFAULTS["agent_prefixes"], ["les-"])

    def test_user_values_win_and_wrong_type_does_not_crash(self):
        cfg = self._load(json.dumps({"agent_prefixes": ["a-"], "stuck_after_sec": 5}))
        self.assertEqual((cfg["agent_prefixes"], cfg["stuck_after_sec"]), (["a-"], 5))
        cfg = self._load(json.dumps({"agent_prefixes": "les-", "stuck_after_sec": "abc"}))
        self.assertIsNone(cfg["config_error"])


class CollectorTest(unittest.TestCase):
    def make(self, sessions):
        cfg = dict(config.DEFAULTS, refresh_sessions_sec=0.01, quota_api_enabled=False)
        with mock.patch.object(ui, "ClaudeDataStore", return_value=FakeStore(sessions)), \
                mock.patch.object(ui, "account_info", return_value={"email": "a@b"}):
            return ui.Collector(cfg, queue.Queue())

    def run_items(self, c, n=2, git=None):
        """Chạy thread collector thật tới khi có n snapshot, rồi dừng."""
        logs = []
        with mock.patch.object(ui.session_ops, "git_state", return_value=git or {"branch": "main"}), \
                mock.patch.object(ui, "log", side_effect=logs.append):
            c.start()
            try:
                items = [c.out.get(timeout=5) for _ in range(n)]
            finally:
                c.stop.set()
                c.kick.set()
                c.join(5)
        self.assertFalse(c.is_alive())
        return items, logs

    def test_snapshot_has_org(self):
        c = self.make([session()])
        (snap, _), logs = self.run_items(c)
        self.assertEqual(logs, [])
        self.assertNotIn("error", snap)
        self.assertIn("counts", snap["org"])
        self.assertEqual(snap["org"]["counts"]["subagent"]["total"], 0)
        self.assertEqual([s["session_id"] for s in snap["sessions"]], ["s1"])
        self.assertEqual(snap["sessions"][0]["git"], {"branch": "main"})
        self.assertEqual(snap["sessions"][0]["agent_calls"], [])  # sessions không bị org đổi
        self.assertEqual(snap["local"]["5h"], {"input": 1, "output": 2})
        self.assertEqual(snap["account"], {"email": "a@b"})
        json.dumps(snap["org"])

    def test_org_failure_keeps_snapshot_and_collector_alive(self):
        secret = "SECRET\n" + "X" * 1000
        c = self.make([session()])
        with mock.patch.object(ui.org, "build", side_effect=ValueError(secret)):
            snaps, logs = self.run_items(c, 2)  # lần 2 chứng minh thread không chết
        for snap in snaps:
            self.assertIsNone(snap["org"])
            self.assertNotIn("error", snap)
            self.assertEqual([s["session_id"] for s in snap["sessions"]], ["s1"])
            self.assertIn("local", snap)
        self.assertTrue(logs)
        for line in logs:
            self.assertNotIn(secret, line)
            self.assertNotIn("\n", line)  # repr: xuống dòng bị escape, không chèn được dòng log giả
            self.assertLess(len(line), 400)

    def test_org_recovers_after_failure(self):
        c = self.make([session()])
        real = ui.org.build
        calls = []

        def flaky(*a):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return real(*a)

        with mock.patch.object(ui.org, "build", side_effect=flaky):
            (first, second), _ = self.run_items(c, 2)
        self.assertIsNone(first["org"])
        self.assertIn("counts", second["org"])

    def test_org_built_with_loop_now(self):
        # build nhận đúng `now` của vòng lặp, cùng giá trị với snap["ts"] (kill M3: time.time() + offset)
        c = self.make([session()])
        with mock.patch.object(ui.org, "build", wraps=org.build) as build:
            snaps, _ = self.run_items(c, 2)
        self.assertGreaterEqual(len(build.call_args_list), 2)
        for i, snap in enumerate(snaps):
            self.assertEqual(build.call_args_list[i].args[2], snap["ts"])

    def test_org_built_after_git_attached(self):
        # org đọc project/team từ git của session, nên build phải chạy sau vòng gắn git (kill M5)
        git = {"top": "/work/team-a", "common": "/work/proj/.git", "branch": "feat"}
        c = self.make([session()])
        snaps, _ = self.run_items(c, 2, git=git)
        proj = snaps[0]["org"]["projects"][0]
        self.assertEqual(proj["root"], "/work/proj")
        self.assertEqual(proj["name"], "proj")
        self.assertEqual([t["top"] for t in proj["teams"]], ["/work/team-a"])
        self.assertEqual(proj["teams"][0]["branch"], "feat")


if __name__ == "__main__":
    unittest.main()
