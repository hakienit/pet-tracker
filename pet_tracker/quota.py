"""Quota / rate-limit của tài khoản.

Nguồn chính (không chính thức, nhưng chính là endpoint lệnh /usage của Claude Code gọi):
    GET https://api.anthropic.com/api/oauth/usage
    Authorization: Bearer <accessToken trong ~/.claude/.credentials.json>
    anthropic-beta: oauth-2025-04-20
Trả về (quan sát 2026-10-15):
    five_hour: {utilization: 8.0, resets_at: ISO}
    seven_day: null | {utilization, resets_at}
    limits: [{kind: "session"|"weekly_scoped"|..., group: "session"|"weekly",
              percent, severity: "normal"|..., resets_at, scope: {model: {display_name}}, is_active}]
Token chỉ đọc từ file local và chỉ gửi tới api.anthropic.com; không log, không lưu nơi khác.
Nếu token hết hạn (expiresAt), widget KHÔNG tự refresh - mở Claude Code là nó tự refresh.

Nguồn phụ: ước tính local từ transcript (tokens trong 5h / 7 ngày gần nhất). Không quy ra %
được vì giới hạn thật của Anthropic tính theo "usage" nội bộ, không phải tokens thô.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def _read_token(claude_dir: str) -> tuple[str | None, str | None]:
    p = Path(claude_dir) / ".credentials.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None, "Không đọc được .credentials.json (chưa đăng nhập Claude Code?)"
    o = d.get("claudeAiOauth") or {}
    tok = o.get("accessToken")
    if not tok:
        return None, "Không có OAuth token trong .credentials.json"
    exp = o.get("expiresAt")
    if exp and exp / 1000.0 < time.time():
        return None, "Token hết hạn - mở Claude Code để nó tự refresh"
    return tok, None


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fetch_api_usage(claude_dir: str, timeout: float = 15.0) -> dict:
    tok, err = _read_token(claude_dir)
    if not tok:
        return {"ok": False, "error": err, "source": "api"}
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": "Bearer " + tok,
            "anthropic-beta": "oauth-2025-04-20",
            "Accept": "application/json",
            "User-Agent": "pet-tracker/0.1 (local desktop widget)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "source": "api"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:120], "source": "api"}
    return {"ok": True, "source": "api", "fetched_at": time.time(), "windows": _normalize(data)}


def _normalize(data: dict) -> list[dict]:
    wins: list[dict] = []
    limits = data.get("limits") or []
    for l in limits:
        kind = l.get("kind") or ""
        group = l.get("group") or kind
        scope = (l.get("scope") or {}) or {}
        model = ((scope.get("model") or {}) or {}).get("display_name")
        if group == "session":
            label = "5 giờ (session)"
        elif group == "weekly":
            label = "7 ngày" + (f" ({model})" if model else "")
        else:
            label = kind
        wins.append({
            "key": kind + (":" + model if model else ""),
            "label": label,
            "percent": float(l.get("percent") or 0),
            "severity": l.get("severity") or "normal",
            "resets_at": _parse_iso(l.get("resets_at")),
            "active": bool(l.get("is_active", True)),
        })
    if not wins:  # fallback: các field cũ
        fh = data.get("five_hour")
        if fh:
            wins.append({"key": "five_hour", "label": "5 giờ (session)", "percent": float(fh.get("utilization") or 0),
                         "severity": "normal", "resets_at": _parse_iso(fh.get("resets_at")), "active": True})
        for k, lbl in (("seven_day", "7 ngày"), ("seven_day_opus", "7 ngày (Opus)"), ("seven_day_sonnet", "7 ngày (Sonnet)")):
            sd = data.get(k)
            if sd:
                wins.append({"key": k, "label": lbl, "percent": float(sd.get("utilization") or 0),
                             "severity": "normal", "resets_at": _parse_iso(sd.get("resets_at")), "active": True})
    # 5h lên đầu
    wins.sort(key=lambda w: (0 if "session" in w["key"] or w["key"] == "five_hour" else 1, w["label"]))
    return wins


def fmt_reset(ts: float | None) -> str:
    if not ts:
        return ""
    d = ts - time.time()
    if d <= 0:
        return "đang reset"
    h, m = divmod(int(d // 60), 60)
    if h >= 24:
        days, h = divmod(h, 24)
        return f"reset sau {days}d {h}h"
    return f"reset sau {h}h {m:02d}m" if h else f"reset sau {m}m"
