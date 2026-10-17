"""Cập nhật một chạm trên macOS: mở dmg, chép .app (stage_update), thay .app đang cài (launch_swap).
Chỉ chạy trên macOS (cần hdiutil, ditto); workflow mac-probe chạy file này trên runner macos-14."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from pet_tracker import updater

MAC = sys.platform == "darwin"


def fake_app(root: Path, marker: str) -> Path:
    app = root / "Wisp.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir()
    exe = app / "Contents" / "MacOS" / "Wisp"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    (app / "Contents" / "Info.plist").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict>'
        "<key>CFBundleExecutable</key><string>Wisp</string>"
        "<key>CFBundleIdentifier</key><string>sg.vinova.wisp.test</string>"
        "<key>CFBundlePackageType</key><string>APPL</string></dict></plist>")
    (app / "Contents" / "Resources" / "marker.txt").write_text(marker)
    return app


class InstallDirProblem(unittest.TestCase):
    def test_app_bundle_only_needs_writable_parent(self):
        with tempfile.TemporaryDirectory() as d:
            app = fake_app(Path(d), "x")
            self.assertIsNone(updater.install_dir_problem(app))


@unittest.skipUnless(MAC, "chỉ macOS")
class MacUpdate(unittest.TestCase):
    def test_stage_and_swap(self):
        from pet_tracker.platform import mac
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "src"
            src.mkdir()
            fake_app(src, "new")
            (src / "Applications").symlink_to("/Applications")
            dmg = d / "new.dmg"
            subprocess.run(["hdiutil", "create", "-volname", "Wisp", "-srcfolder", str(src), "-ov", "-format", "UDZO",
                            str(dmg)], check=True, capture_output=True)

            work = d / "pet-update-test"
            stage = mac.stage_update(dmg, work / "new")
            self.assertEqual(stage.name, "Wisp.app")
            self.assertEqual((stage / "Contents/Resources/marker.txt").read_text(), "new")

            apps = d / "Apps"
            apps.mkdir()
            target = fake_app(apps, "old")
            running = subprocess.Popen(["sleep", "2"])
            log = d / "update.log"
            swap = mac.launch_swap(stage, target, running.pid, log_file=log)
            running.wait()
            swap.wait(timeout=60)
            text = log.read_text()
            self.assertIn("update: done", text, text)
            self.assertEqual((target / "Contents/Resources/marker.txt").read_text(), "new")
            self.assertFalse((apps / "Wisp.old.app").exists())
            self.assertFalse(work.exists(), "thư mục tạm pet-update-* phải bị xoá")

    def test_swap_restores_old_app_when_copy_fails(self):
        from pet_tracker.platform import mac
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            apps = d / "Apps"
            apps.mkdir()
            target = fake_app(apps, "old")
            log = d / "update.log"
            swap = mac.launch_swap(d / "missing" / "Wisp.app", target, 999999, log_file=log)
            swap.wait(timeout=60)
            time.sleep(0.5)
            self.assertEqual((target / "Contents/Resources/marker.txt").read_text(), "old")
            self.assertIn("restoring backup", log.read_text())


if __name__ == "__main__":
    unittest.main()
