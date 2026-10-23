"""Định dạng thời gian, số token, nhãn quota theo ngôn ngữ hiện tại (i18n)."""
from __future__ import annotations

import time
from datetime import datetime

from ..i18n import t


def k(n) -> str:
    n = float(n or 0)
    if n < 1000:
        return f"{int(n)}"
    if n < 1_000_000:
        v = n / 1000
        return f"{v:.0f}k" if v >= 100 else f"{v:.1f}k".replace(".0k", "k")
    if n < 1_000_000_000:
        v = n / 1_000_000
        return f"{v:.0f}M" if v >= 100 else f"{v:.1f}M".replace(".0M", "M")
    return f"{n / 1_000_000_000:.2f}B".replace(".00B", "B")


def ago(ts) -> str:
    if not ts:
        return ""
    d = max(0, time.time() - ts)
    if d < 10:
        return t("ago.now")
    if d < 60:
        return t("ago.s", n=int(d))
    if d < 3600:
        return t("ago.m", n=int(d // 60))
    if d < 86400:
        return t("ago.h", n=int(d // 3600))
    return t("ago.d", n=int(d // 86400))


def ago_long(ts) -> str:
    """"2 phút trước" / "2m ago"; "vừa xong" giữ nguyên."""
    a = ago(ts)
    return a if not a or a == t("ago.now") else t("ago.ago", x=a)


def left(seconds: float) -> str:
    s = max(0, int(seconds))
    h, m = divmod(s // 60, 60)
    if h >= 24:
        return t("left.dh", d=h // 24, h=h % 24)
    return t("left.hm", h=h, m=m) if h else t("left.m", m=m)


def clock(ts) -> str:
    """15:40 nếu trong 20 giờ tới, ngược lại "T4 22/10" / "Wed 22/10"."""
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts)
    if abs(ts - time.time()) < 20 * 3600:
        return f"{dt:%H:%M}"
    return f"{t('weekday').split(',')[dt.weekday()]} {dt:%d/%m}"


def window_label(w: dict) -> str:
    key = w.get("key", "")
    if "session" in key or key == "five_hour":
        return t("q.5h")
    model = key.split(":", 1)[1] if ":" in key else None
    if not model:
        for suffix, name in (("_opus", "Opus"), ("_sonnet", "Sonnet")):
            if key.endswith(suffix):
                model = name
    return t("q.7d_model", m=model) if model else t("q.7d")
