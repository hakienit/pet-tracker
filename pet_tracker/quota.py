"""Quota / rate-limit của tài khoản.

Nguồn chính (không chính thức, nhưng chính là endpoint lệnh /usage của Claude Code gọi):
    GET https://api.anthropic.com/api/oauth/usage
    Authorization: Bearer <accessToken: Windows ~/.claude/.credentials.json, macOS Keychain>
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

from . import __version__
from . import platform as plat
from . import tls

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def _read_token(claude_dir: str):
    try:
        o = plat.read_credentials(claude_dir)
    except Exception as e:
        return None, str(e)
    tok = o.get("accessToken")
    if not tok:
        return None, "Không có OAuth token của Claude Code (chưa đăng nhập?)"
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib chép cả header Authorization sang URL redirect (kể cả host khác): không theo redirect."""

    def redirect_request(self, *args, **kwargs):
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=tls.context()))


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
            "User-Agent": f"Wisp/{__version__} (local desktop widget)",
        },
    )
    try:
        with _NO_REDIRECT.open(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            retry_after = float(e.headers.get("Retry-After") or 0)
        except (TypeError, ValueError):
            retry_after = 0.0
        return {"ok": False, "error": f"HTTP {e.code}", "status": e.code, "retry_after": retry_after,
                "source": "api"}
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
    wins.sort(key=lambda w: (0 if is_session_window(w) else 1, w["label"]))
    return wins


def is_session_window(w: dict) -> bool:
    """True nếu là cửa sổ 5 giờ (session), False nếu là cửa sổ 7 ngày."""
    return "session" in w["key"] or w["key"] == "five_hour"


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
