import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from pet_tracker import hooks as H

URL = H.hook_url(47615, "tok")


class SettingsMerge(unittest.TestCase):
    def test_add_to_empty(self):
        d = H.add_hooks({}, URL)
        self.assertEqual(set(d["hooks"]), set(H.EVENTS))
        self.assertEqual(H.hook_status(d, URL), "on")

    def test_keeps_other_keys_and_hooks(self):
        mine = {"matcher": "Bash", "hooks": [{"type": "command", "command": "lint.sh"}]}
        src = {"model": "opus", "hooks": {"PreToolUse": [mine], "SessionStart": [{"hooks": [{"type": "command",
                                                                                              "command": "x"}]}]}}
        d = H.add_hooks(src, URL)
        self.assertEqual(d["model"], "opus")
        self.assertIn(mine, d["hooks"]["PreToolUse"])
        self.assertIn("SessionStart", d["hooks"])
        self.assertEqual(src["hooks"]["PreToolUse"], [mine], "không được sửa dict gốc")

    def test_idempotent(self):
        once = H.add_hooks({}, URL)
        self.assertEqual(H.add_hooks(once, URL), once)

    def test_new_url_replaces_old(self):
        d = H.add_hooks(H.add_hooks({}, H.hook_url(1, "old")), URL)
        urls = {h["url"] for gs in d["hooks"].values() for g in gs for h in g["hooks"]}
        self.assertEqual(urls, {URL})

    def test_remove_only_ours(self):
        other = {"hooks": [{"type": "command", "command": "keep"}]}
        mixed = {"hooks": [{"type": "command", "command": "also-keep"}, {"type": "http", "url": URL}]}
        d = H.add_hooks({"hooks": {"Stop": [other], "Notification": [mixed]}}, URL)
        r = H.remove_hooks(d)
        self.assertEqual(r["hooks"]["Stop"], [other])
        self.assertEqual(r["hooks"]["Notification"], [{"hooks": [{"type": "command", "command": "also-keep"}]}])
        self.assertNotIn("PreToolUse", r["hooks"])
        self.assertEqual(H.hook_status(r, URL), "off")
        self.assertEqual(H.remove_hooks(H.add_hooks({}, URL)), {})

    def test_status_stale(self):
        self.assertEqual(H.hook_status(H.add_hooks({}, H.hook_url(1, "old")), URL), "stale")

    def test_bad_shapes(self):
        with self.assertRaises(H.HookConfigError):
            H.add_hooks({"hooks": []}, URL)
        with self.assertRaises(H.HookConfigError):
            H.add_hooks({"hooks": {"Stop": "x"}}, URL)


class SettingsFile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.p = Path(self.dir.name) / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_install_backup_uninstall(self):
        self.p.write_text('{"theme": "dark"}', encoding="utf-8")
        H.install(self.dir.name, URL)
        self.assertEqual(H.status(self.dir.name, URL), "on")
        self.assertEqual(json.loads((self.p.parent / "settings.json.wisp-bak").read_text()), {"theme": "dark"})
        H.uninstall(self.dir.name)
        self.assertEqual(json.loads(self.p.read_text()), {"theme": "dark"})

    def test_invalid_json_is_not_touched(self):
        self.p.write_text("{oops", encoding="utf-8")
        with self.assertRaises(H.HookConfigError):
            H.install(self.dir.name, URL)
        self.assertEqual(self.p.read_text(), "{oops")
        self.assertEqual(H.status(self.dir.name, URL), "error")

    def test_missing_file(self):
        H.install(self.dir.name, URL)
        self.assertEqual(H.status(self.dir.name, URL), "on")


class Server(unittest.TestCase):
    def test_accepts_only_token_path(self):
        srv = H.HookServer(0, "tok")  # cổng 0: hệ điều hành chọn cổng trống
        self.assertTrue(srv.start())
        port = srv._srv.server_address[1]
        try:
            body = json.dumps({"hook_event_name": "Stop", "session_id": "a"}).encode()
            ok = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/wisp/tok", data=body), timeout=5)
            self.assertEqual(ok.status, 200)
            self.assertEqual(srv.events.get(timeout=2)["session_id"], "a")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/wisp/bad", data=body), timeout=5)
            self.assertTrue(srv.events.empty())
            self.assertEqual(urllib.request.urlopen(f"http://127.0.0.1:{port}/wisp/tok/ping", timeout=5).status, 200)
        finally:
            srv.stop()


if __name__ == "__main__":
    unittest.main()
