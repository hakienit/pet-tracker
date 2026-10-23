"""Token đã dùng trên máy này: hôm nay, tuần này (từ thứ Hai), tháng này. Tổng = input + output + cache.

Chỉ tính transcript trong ~/.claude của máy này, nên số liệu khác quota của tài khoản (tài khoản có thể dùng ở
nhiều máy). Ngày đã qua được cache trong <state>/usage_daily.json để không phải đọc lại transcript cũ tới 31 ngày
mỗi lần mở; hôm nay luôn tính trực tiếp từ dữ liệu ClaudeDataStore đang theo dõi.
"""
from __future__ import annotations

import glob
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from .claude_data import Transcript

KEEP_DAYS = 40


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _start(d: date) -> float:
    return datetime(d.year, d.month, d.day).timestamp()


def ranges(now: float) -> dict:
    """Ngày bắt đầu (date) của hôm nay / tuần / tháng theo giờ máy."""
    today = datetime.fromtimestamp(now).date()
    return {"today": today, "week": today - timedelta(days=today.weekday()), "month": today.replace(day=1)}


def msg_total(r: dict) -> int:
    return int(r["input"] + r["cache_create"] + r["cache_read"] + r["output"])


def per_day(transcripts, lo: float, hi: float) -> dict:
    """{ngày: tổng token} của mọi message có thời điểm trong [lo, hi). Message trùng id trong một file chỉ tính một lần
    (Transcript đã dedupe)."""
    out: dict = {}
    for tr in transcripts:
        for r in tr.msgs.values():
            if lo <= r["ts"] < hi:
                k = _day(r["ts"])
                out[k] = out.get(k, 0) + msg_total(r)
    return out


class LocalUsage:
    def __init__(self, claude_dir: str, cache_path: Path):
        self.claude_dir = Path(claude_dir)
        self.cache_path = Path(cache_path)
        self.days: dict = {}       # ngày đã qua -> tổng
        self.built_for = None      # ngày (str) mà cache đã đủ tới hôm qua
        try:
            d = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self.days = {str(k): int(v) for k, v in (d.get("days") or {}).items()}
            self.built_for = d.get("built_for")
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def needs_build(self, now: float) -> bool:
        return self.built_for != _day(now)

    def build(self, now: float) -> None:
        """Tính các ngày còn thiếu từ đầu tuần / đầu tháng (cái nào sớm hơn) tới hôm qua. Chạy ở thread nền:
        lần đầu có thể đọc tới 31 ngày transcript."""
        rg = ranges(now)
        first = min(rg["week"], rg["month"])
        today = rg["today"]
        need = [first + timedelta(days=i) for i in range((today - first).days)]
        missing = [d for d in need if d.isoformat() not in self.days]
        if missing:
            lo, hi = _start(missing[0]), _start(today)
            files = [p for p in glob.glob(str(self.claude_dir / "projects" / "*" / "*.jsonl"))
                     + glob.glob(str(self.claude_dir / "projects" / "*" / "*" / "subagents" / "*.jsonl"))
                     if self._mtime(p) >= lo]
            trs = []
            for p in files:
                tr = Transcript(p)
                tr.poll()
                trs.append(tr)
            got = per_day(trs, lo, hi)
            for d in missing:
                self.days[d.isoformat()] = got.get(d.isoformat(), 0)
        cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
        self.days = {k: v for k, v in self.days.items() if k >= cutoff}
        self.built_for = today.isoformat()
        self._save()

    @staticmethod
    def _mtime(p: str) -> float:
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0

    def _save(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"built_for": self.built_for, "days": self.days}), encoding="utf-8")
            os.replace(tmp, self.cache_path)
        except OSError:
            pass

    def totals(self, live_transcripts, now: float) -> dict:
        """{"today", "week", "month"}: hôm nay tính từ live_transcripts, ngày cũ lấy từ cache.
        Cache chưa dựng xong thì tuần / tháng là None (UI hiện "…")."""
        rg = ranges(now)
        today = rg["today"]
        t0 = _start(today)
        today_total = per_day(live_transcripts, t0, now + 1).get(today.isoformat(), 0)
        ready = self.built_for == today.isoformat()

        def since(d: date):
            if not ready:
                return None
            return today_total + sum(v for k, v in self.days.items() if d.isoformat() <= k < today.isoformat())

        return {"today": today_total, "week": since(rg["week"]), "month": since(rg["month"])}
