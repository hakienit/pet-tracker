"""macOS: đọc token Claude Code trong Keychain (cả dạng chia mảnh) và loại pid bị dùng lại bằng procStart.
Chỉ chạy trên macOS; workflow mac-probe chạy file này trên runner."""
import base64
import json
import os
import subprocess
import sys
import unittest
import uuid

MAC = sys.platform == "darwin"


def security(*args):
    return subprocess.run(["security", *args], capture_output=True, text=True)


@unittest.skipUnless(MAC, "chỉ macOS")
class Keychain(unittest.TestCase):
    def setUp(self):
        self.svc = f"Wisp Test {uuid.uuid4().hex[:8]}-credentials"
        self.accounts = []

    def tearDown(self):
        for acc in self.accounts:
            security("delete-generic-password", "-s", self.svc, "-a", acc)

    def add(self, account, secret):
        self.accounts.append(account)
        r = security("add-generic-password", "-U", "-s", self.svc, "-a", account, "-w", secret)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_plain(self):
        from pet_tracker.platform import mac
        self.add(mac.KEYCHAIN_ACCOUNT, json.dumps({"claudeAiOauth": {"accessToken": "t1"}}))
        self.assertEqual(mac.keychain_json(self.svc)["claudeAiOauth"]["accessToken"], "t1")

    def test_chunked(self):
        from pet_tracker.platform import mac
        blob = base64.b64encode(json.dumps({"claudeAiOauth": {"accessToken": "t" * 3000}}).encode()).decode()
        half = len(blob) // 2
        self.add(mac.KEYCHAIN_ACCOUNT + "#m", json.dumps({"n": 2, "l": len(blob)}))
        self.add(mac.KEYCHAIN_ACCOUNT + "#0", blob[:half])
        self.add(mac.KEYCHAIN_ACCOUNT + "#1", blob[half:])
        self.assertEqual(mac.keychain_json(self.svc)["claudeAiOauth"]["accessToken"], "t" * 3000)

    def test_missing(self):
        from pet_tracker.platform import mac
        self.assertIsNone(mac.keychain_json(self.svc))


@unittest.skipUnless(MAC, "chỉ macOS")
class ProcStart(unittest.TestCase):
    def test_matches_ps_lstart(self):
        from pet_tracker.platform import mac
        p = subprocess.Popen(["sleep", "30"])
        try:
            env = dict(os.environ, LC_ALL="C", TZ="UTC")
            start = subprocess.run(["ps", "-o", "lstart=", "-p", str(p.pid)], capture_output=True, text=True,
                                   env=env).stdout.strip()
            self.assertTrue(start)
            self.assertTrue(mac.process_alive(p.pid, start))
            self.assertTrue(mac.process_alive(p.pid, None))
            mac._lstart_cache.clear()
            self.assertFalse(mac.process_alive(p.pid, "Mon Jan  1 00:00:00 2001"))  # pid bị dùng lại
        finally:
            p.kill()
            p.wait()
        self.assertFalse(mac.process_alive(p.pid, start))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(MAC, "chỉ macOS")
class Fonts(unittest.TestCase):
    def test_archivo_registered_for_tk(self):
        import tkinter as tk
        from tkinter import font as tkfont
        from pet_tracker.ui.kit import register_fonts
        self.assertTrue(register_fonts())
        root = tk.Tk()
        try:
            fams = set(tkfont.families(root))
        finally:
            root.destroy()
        print("archivo families:", sorted(f for f in fams if "Archivo" in f))
        self.assertIn("Archivo", fams)
