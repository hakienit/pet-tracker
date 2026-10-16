import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from pet_tracker import quota_history as Q
from pet_tracker import usage_local as U


class Forecast(unittest.TestCase):
    def test_linear_growth(self):
        now = 10_000.0
        pts = [(now - 1800 + i * 300, 40 + i * 2) for i in range(7)]  # 2% / 5 phút, giờ là 52%
        f = Q.forecast(pts, now, now + 3 * 3600, Q.SESSION_LEN)
        self.assertAlmostEqual(f["eta"], now + 48 / (2 / 300), delta=1)
        self.assertTrue(f["before_reset"])

    def test_flat_or_too_few(self):
        now = 10_000.0
        self.assertIsNone(Q.forecast([(now - 600, 10), (now, 10), (now - 300, 10)], now, now + 100, 1))
        self.assertIsNone(Q.forecast([(now - 60, 10), (now, 12)], now, None, 1))

    def test_after_reset(self):
        now = 10_000.0
        pts = [(now - 1800 + i * 300, 10 + i) for i in range(7)]
        self.assertFalse(Q.forecast(pts, now, now + 600, Q.SESSION_LEN)["before_reset"])

    def test_pace(self):
        now = 0.0
        self.assertAlmostEqual(Q.pace(65, now, now + 2.5 * 3600, Q.SESSION_LEN), 1.3)
        self.assertIsNone(Q.pace(1, now, now + Q.SESSION_LEN, Q.SESSION_LEN))  # cửa sổ vừa mở

    def test_history_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "q.jsonl"
            h = Q.QuotaHistory(p)
            for i in range(5):
                h.add([{"key": "session", "percent": 10 + i, "resets_at": 50_000}], 1000 + i * 120)
            self.assertEqual(len(Q.QuotaHistory(p).series("session", 50_000)), 5)
            h.add([{"key": "session", "percent": 1, "resets_at": 1}], 1000 + Q.KEEP_SEC + 10_000)
            self.assertEqual(len(Q.QuotaHistory(p).points), 1)


class LocalUsage(unittest.TestCase):
    def test_week_month(self):
        now = datetime(2026, 10, 16, 15, 0).timestamp()  # thứ Sáu
        rg = U.ranges(now)
        self.assertEqual(str(rg["week"]), "2026-10-12")
        self.assertEqual(str(rg["month"]), "2026-10-01")

    def test_totals_with_files(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "projects" / "p"
            proj.mkdir(parents=True)
            today = datetime(2026, 10, 16, 15, 0)
            now = today.timestamp()

            def line(mid, when, n):
                return json.dumps({"type": "assistant", "timestamp": when.astimezone().isoformat(),
                                   "message": {"id": mid, "model": "claude-x", "usage": {
                                       "input_tokens": n, "output_tokens": n, "cache_read_input_tokens": n,
                                       "cache_creation_input_tokens": n}}}, separators=(",", ":")) + "\n"

            f = proj / "s.jsonl"
            f.write_text(line("a", today - timedelta(days=1), 10)        # hôm qua: tuần + tháng
                         + line("b", today - timedelta(days=6), 100)     # thứ Bảy tuần trước: chỉ tháng
                         + line("b", today - timedelta(days=6), 100)     # trùng id: không tính lại
                         + line("c", today - timedelta(hours=1), 1), encoding="utf-8")
            u = U.LocalUsage(d, Path(d) / "cache.json")
            self.assertTrue(u.needs_build(now))
            u.build(now)
            from pet_tracker.claude_data import Transcript
            tr = Transcript(str(f))
            tr.poll()
            t = u.totals([tr], now)
            self.assertEqual(t, {"today": 4, "week": 44, "month": 444})
            self.assertFalse(U.LocalUsage(d, Path(d) / "cache.json").needs_build(now))


if __name__ == "__main__":
    unittest.main()
