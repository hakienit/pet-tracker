"""Lịch sử quota trên máy: mỗi lần lấy quota lưu một điểm, để dự báo giờ hết và tính nhịp đốt.

File: <state>/quota_history.jsonl, mỗi dòng {"t": ts, "k": key, "p": percent, "r": resets_at}.
Giữ 8 ngày, file > 1 MB thì ghi lại cho gọn.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

KEEP_SEC = 8 * 86400
MAX_BYTES = 1_000_000
FIT_SEC = 30 * 60        # dự báo theo độ dốc của 30 phút gần nhất
MIN_POINTS = 3
MIN_SPAN = 5 * 60
SESSION_LEN = 5 * 3600
WEEK_LEN = 7 * 86400


def window_len(key: str) -> int:
    return SESSION_LEN if ("session" in key or key == "five_hour") else WEEK_LEN


def forecast(points: list, now: float, resets_at, length: int):
    """points: [(t, percent)] của cùng một cửa sổ (cùng resets_at), tăng dần theo t.
    Trả {"eta": ts lúc chạm 100%, "before_reset": bool} hoặc None nếu không dự báo được."""
    pts = [(t, p) for t, p in points if now - FIT_SEC <= t <= now]
    if len(pts) < MIN_POINTS or pts[-1][0] - pts[0][0] < MIN_SPAN:
        return None
    n = len(pts)
    mt = sum(t for t, _ in pts) / n
    mp = sum(p for _, p in pts) / n
    den = sum((t - mt) ** 2 for t, _ in pts)
    if den <= 0:
        return None
    slope = sum((t - mt) * (p - mp) for t, p in pts) / den  # %/giây
    cur = pts[-1][1]
    if slope <= 1e-6 or cur >= 100:
        return None
    eta = now + (100.0 - cur) / slope
    return {"eta": eta, "before_reset": bool(resets_at) and eta < resets_at}


def pace(percent: float, now: float, resets_at, length: int):
    """Nhịp = % đã dùng / % thời gian đã trôi của cửa sổ. 1.3 = nhanh hơn mức chia đều 30%.
    None khi cửa sổ vừa mở (< 5% thời gian) hoặc thiếu giờ reset."""
    if not resets_at or length <= 0:
        return None
    elapsed = 1.0 - (resets_at - now) / length
    if elapsed < 0.05 or elapsed > 1.0:
        return None
    return percent / (100.0 * elapsed)


class QuotaHistory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.points: list = []  # (t, key, percent, resets_at)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        self.points.append((float(d["t"]), str(d["k"]), float(d["p"]), d.get("r")))
                    except (ValueError, KeyError, TypeError):
                        continue
        except OSError:
            pass

    def add(self, windows: list, now: float) -> None:
        new = [(now, w["key"], float(w["percent"]), w.get("resets_at")) for w in windows or []]
        if not new:
            return
        self.points.extend(new)
        cutoff = now - KEEP_SEC
        old = len(self.points)
        self.points = [p for p in self.points if p[0] >= cutoff]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            big = self.path.exists() and self.path.stat().st_size > MAX_BYTES
            if big or len(self.points) < old:
                tmp = self.path.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.writelines(self._line(p) for p in self.points)
                os.replace(tmp, self.path)
            else:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.writelines(self._line(p) for p in new)
        except OSError:
            pass  # không ghi được lịch sử: dự báo vẫn chạy với dữ liệu trong RAM

    @staticmethod
    def _line(p) -> str:
        return json.dumps({"t": round(p[0], 1), "k": p[1], "p": p[2], "r": p[3]}) + "\n"

    def series(self, key: str, resets_at) -> list:
        """[(t, percent)] của cửa sổ key hiện tại (cùng resets_at, lệch tối đa 2 phút vì API làm tròn)."""
        out = []
        for t, k, p, r in self.points:
            if k == key and (not resets_at or not r or abs(float(r) - float(resets_at)) < 120):
                out.append((t, p))
        return out

    def annotate(self, windows: list, now: float) -> None:
        """Gắn "forecast" và "pace" vào từng cửa sổ quota."""
        for w in windows or []:
            length = window_len(w["key"])
            w["forecast"] = forecast(self.series(w["key"], w.get("resets_at")), now, w.get("resets_at"), length)
            w["pace"] = pace(float(w["percent"]), now, w.get("resets_at"), length)
