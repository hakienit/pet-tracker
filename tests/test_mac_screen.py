"""Vùng dùng được của màn hình trên macOS (NSScreen.visibleFrame qua ctypes). Chỉ chạy trên macOS; workflow
mac-probe chạy cả runner Apple Silicon và Intel (Intel cần objc_msgSend_stret)."""
import sys
import unittest


@unittest.skipUnless(sys.platform == "darwin", "chỉ macOS")
class MacScreen(unittest.TestCase):
    def test_visible_frame_inside_screen(self):
        from pet_tracker.platform import mac
        screens = mac._screens()
        self.assertTrue(screens)
        (fl, ft, fr, fb), (l, t, r, b) = screens[0]
        self.assertEqual((fl, ft), (0, 0))  # màn hình chính là gốc toạ độ của Tk
        self.assertTrue(fl <= l < r <= fr and ft <= t < b <= fb, screens[0])
        print("screens:", screens)

    def test_work_area_picks_screen(self):
        from pet_tracker.platform import mac
        main = mac._screens()[0][1]
        self.assertEqual(mac.work_area(None, None), main)
        self.assertEqual(mac.work_area(None, (main[0] + 5, main[1] + 5)), main)
        far = mac.work_area(None, (-100000, -100000))  # ngoài mọi màn hình: màn hình gần nhất
        self.assertEqual(len(far), 4)


if __name__ == "__main__":
    unittest.main()
