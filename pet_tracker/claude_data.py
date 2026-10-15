"""Đọc dữ liệu local của Claude Code.

Nguồn (khảo sát trên Claude Code 2.1.295/2.1.300, Windows):
- <claude_dir>/sessions/<pid>.json : một file cho mỗi process Claude Code đang/đã chạy
    {pid, sessionId, cwd, name, status(idle|busy), startedAt, procStart(FILETIME), entrypoint, version, ...}
  File không bị xoá ngay khi process thoát -> phải kiểm tra pid còn sống + procStart khớp.
- <claude_dir>/projects/<cwd-encoded>/<sessionId>.jsonl : transcript. Mỗi dòng 1 JSON record.
    type=assistant  -> message.usage {input_tokens, cache_creation_input_tokens,
                        cache_read_input_tokens, output_tokens}, message.model, message.id,
                        isSidechain, timestamp, cwd, gitBranch.
                        Một API response được ghi nhiều record (apiBlockIndex 0..n) với cùng
                        message.id và cùng usage -> phải dedupe theo message.id.
    type=custom-title / ai-title -> tên session.
- <claude_dir>/projects/<proj>/<sessionId>/subagents/agent-*.jsonl : transcript subagent (isSidechain=true),
  tính vào usage nhưng không tính vào context của session chính.

Context window đang dùng = input + cache_creation + cache_read của assistant message mới nhất
trên nhánh chính (đó chính là toàn bộ prompt gửi lên API ở lượt đó).
"""
from __future__ import annotations

import glob
import json
import os
import time
from datetime import datetime
from pathlib import Path

from . import platform as plat


_TITLE_MARKERS = (b'"customTitle"', b'"aiTitle"', b'"agentName"')

# Ước tính local chỉ cần 7 ngày gần nhất. Transcript không đổi lâu hơn thế không được đọc (trừ khi là của
# một session đang chạy), để thời gian khởi động và RAM không tăng theo toàn bộ lịch sử trên máy.
USAGE_HORIZON_SEC = 7 * 86400 + 3600


def _parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


# ---------------------------------------------------------------- process check
def process_alive(pid: int, proc_start=None) -> bool:
    """True nếu pid còn chạy (Windows: so cả thời điểm tạo process với procStart, xem platform/win.py)."""
    return plat.process_alive(pid, proc_start)


# ---------------------------------------------------------------- transcript
class Transcript:
    """Đọc tăng dần (incremental) một file .jsonl, chỉ parse phần mới ghi thêm."""

    def __init__(self, path: str, sidechain: bool = False):
        self.path = path
        self.sidechain_file = sidechain
        self.offset = 0
        self.buf = b""
        self.msgs: dict = {}          # message.id -> usage record (dedupe)
        self.last_main = None         # assistant record mới nhất nhánh chính
        self.model = None
        self.effort = None
        self.title = None
        self.cwd = None
        self.git_branch = None
        self.last_ts = None
        self.first_ts = None
        self.mtime = 0.0

    def poll(self) -> bool:
        try:
            st = os.stat(self.path)
        except OSError:
            return False
        if st.st_size == self.offset and st.st_mtime == self.mtime:
            return False
        self.mtime = st.st_mtime
        if st.st_size < self.offset:  # file bị ghi lại từ đầu
            self.offset, self.buf, self.msgs, self.last_main = 0, b"", {}, None
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read()
                self.offset = f.tell()
        except OSError:
            return False
        data = self.buf + data
        lines = data.split(b"\n")
        self.buf = lines.pop()  # dòng cuối có thể chưa ghi xong
        for line in lines:
            self._ingest(line)
        return True

    def _ingest(self, line: bytes) -> None:
        if b'"type":"assistant"' in line:
            self._ingest_assistant(line)
        elif any(m in line for m in _TITLE_MARKERS):
            try:
                d = json.loads(line)
            except Exception:
                return
            t = d.get("customTitle") or d.get("aiTitle") or d.get("agentName")
            if t and (d.get("type") == "custom-title" or not self.title or d.get("type") == "ai-title"):
                self.title = t

    def _ingest_assistant(self, line: bytes) -> None:
        try:
            d = json.loads(line)
        except Exception:
            return
        if d.get("type") != "assistant":
            return
        msg = d.get("message") or {}
        usage = msg.get("usage")
        if not usage or msg.get("model") == "<synthetic>":  # record giả khi lỗi API / ngắt: không có model thật
            return
        mid = msg.get("id") or d.get("requestId") or d.get("uuid")
        ts = _parse_ts(d.get("timestamp")) or time.time()
        rec = {
            "id": mid,
            "ts": ts,
            "model": msg.get("model") or d.get("requestedModel"),
            "input": int(usage.get("input_tokens") or 0),
            "cache_create": int(usage.get("cache_creation_input_tokens") or 0),
            "cache_read": int(usage.get("cache_read_input_tokens") or 0),
            "output": int(usage.get("output_tokens") or 0),
            "sidechain": bool(d.get("isSidechain")) or self.sidechain_file,
            "effort": d.get("effort") or d.get("perTurnEffort"),
        }
        rec["context"] = rec["input"] + rec["cache_create"] + rec["cache_read"]
        self.msgs[mid] = rec  # record sau (apiBlockIndex lớn hơn) ghi đè, usage giống nhau
        if self.first_ts is None or ts < self.first_ts:
            self.first_ts = ts
        if self.last_ts is None or ts >= self.last_ts:
            self.last_ts = ts
        if not rec["sidechain"]:
            if self.last_main is None or ts >= self.last_main["ts"]:
                self.last_main = rec
                self.model = rec["model"]
                self.effort = rec["effort"] or self.effort
                self.cwd = d.get("cwd") or self.cwd
                self.git_branch = d.get("gitBranch") or self.git_branch

    def totals(self) -> dict:
        t = {"input": 0, "cache_create": 0, "cache_read": 0, "output": 0, "messages": 0}
        for r in self.msgs.values():
            t["input"] += r["input"]
            t["cache_create"] += r["cache_create"]
            t["cache_read"] += r["cache_read"]
            t["output"] += r["output"]
            t["messages"] += 1
        return t


# ---------------------------------------------------------------- store
class ClaudeDataStore:
    def __init__(self, claude_dir: str):
        self.claude_dir = Path(claude_dir)
        self.transcripts: dict = {}      # path -> Transcript (chỉ file mới đổi gần đây hoặc của session đang chạy)
        self._session_path: dict = {}    # sessionId -> main transcript path (mọi file, kể cả cũ)
        self._pinned: set = set()        # path transcript của session đang chạy: không bỏ dù cũ
        self._last_scan = 0.0

    def _load(self, p: str, sidechain: bool = False):
        t = self.transcripts.get(p)
        if t is None:
            t = self.transcripts[p] = Transcript(p, sidechain=sidechain)
            t.poll()
        return t

    # ---- discovery
    def _scan_files(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_scan < 15:
            return
        self._last_scan = now
        cutoff = now - USAGE_HORIZON_SEC
        proj = self.claude_dir / "projects"

        def recent(p):
            try:
                return os.path.getmtime(p) >= cutoff
            except OSError:
                return False

        mains = glob.glob(str(proj / "*" / "*.jsonl"))
        subs = glob.glob(str(proj / "*" / "*" / "subagents" / "*.jsonl"))
        self._session_path = {Path(p).stem: p for p in mains}
        for p in mains:
            if p not in self.transcripts and recent(p):
                self.transcripts[p] = Transcript(p)
        for p in subs:
            if p not in self.transcripts and recent(p):
                self.transcripts[p] = Transcript(p, sidechain=True)
        for p, t in list(self.transcripts.items()):
            if not os.path.exists(p) or (p not in self._pinned and t.mtime and t.mtime < cutoff):
                del self.transcripts[p]

    def poll_all(self) -> None:
        self._scan_files()
        for t in list(self.transcripts.values()):
            t.poll()

    # ---- sessions
    def read_session_files(self) -> list:
        out = []
        for p in glob.glob(str(self.claude_dir / "sessions" / "*.json")):
            try:
                d = json.loads(Path(p).read_text(encoding="utf-8"))
            except Exception:
                continue
            if not d.get("sessionId") or not d.get("pid"):
                continue
            d["_file"] = p
            out.append(d)
        return out

    def transcript_for(self, session_id: str):
        p = self._session_path.get(session_id)
        if p is None:
            self._scan_files(force=True)
            p = self._session_path.get(session_id)
        if not p or not os.path.exists(p):
            return None
        self._pinned.add(p)
        return self._load(p)

    def subagents_for(self, session_id: str) -> list:
        main = self._session_path.get(session_id)
        if not main:
            return []
        out = []
        for p in glob.glob(os.path.join(main[:-len(".jsonl")], "subagents", "*.jsonl")):
            self._pinned.add(p)
            out.append(self._load(p, sidechain=True))
        return out

    def active_sessions(self, context_windows: dict) -> list:
        """Danh sách session Claude Code đang chạy (pid còn sống) kèm context usage."""
        self._pinned = set()
        seen: dict = {}
        for s in self.read_session_files():
            if not process_alive(s["pid"], s.get("procStart")):
                continue
            sid = s["sessionId"]
            if sid in seen and (seen[sid].get("updatedAt") or 0) >= (s.get("updatedAt") or 0):
                continue
            seen[sid] = s
        sessions = []
        empty = {"input": 0, "cache_create": 0, "cache_read": 0, "output": 0, "messages": 0}
        for sid, s in seen.items():
            tr = self.transcript_for(sid)
            model = (tr.model if tr else None) or "?"
            limit = context_window_for(model, context_windows)
            ctx = tr.last_main["context"] if (tr and tr.last_main) else 0
            subs = self.subagents_for(sid) if tr else []
            tot = tr.totals() if tr else dict(empty)
            for st in subs:
                for k, v in st.totals().items():
                    tot[k] += v
            sessions.append({
                "session_id": sid,
                "pid": s["pid"],
                "proc_start": s.get("procStart"),
                "transcript": tr.path if tr else None,
                "name": s.get("name") or (tr.title if tr else None) or sid[:8],
                "title": tr.title if tr else None,
                "cwd": (tr.cwd if tr and tr.cwd else None) or s.get("cwd") or "?",
                "home_cwd": s.get("cwd"),
                "git_branch": tr.git_branch if tr else None,
                "status": s.get("status") or "?",
                "entrypoint": s.get("entrypoint"),
                "host_session_id": s.get("hostSessionId"),
                "version": s.get("version"),
                "started_at": (s.get("startedAt") or 0) / 1000.0,
                "model": model,
                "effort": tr.effort if tr else None,
                "context_tokens": ctx,
                "context_limit": limit,
                "context_pct": (100.0 * ctx / limit) if limit else 0.0,
                "last_activity": tr.last_ts if tr else None,
                "subagents": len(subs),
                "totals": tot,
                "has_transcript": tr is not None,
            })
        sessions.sort(key=lambda x: (x["status"] != "busy", -(x["last_activity"] or 0)))
        return sessions

    # ---- rolling usage (ước tính local)
    def usage_window(self, seconds: float, now=None) -> dict:
        now = now or time.time()
        lo = now - seconds
        t = {"input": 0, "cache_create": 0, "cache_read": 0, "output": 0, "messages": 0, "by_model": {}}
        for tr in self.transcripts.values():
            for r in tr.msgs.values():
                if r["ts"] < lo:
                    continue
                t["input"] += r["input"]
                t["cache_create"] += r["cache_create"]
                t["cache_read"] += r["cache_read"]
                t["output"] += r["output"]
                t["messages"] += 1
                bm = t["by_model"].setdefault(r["model"] or "?", {"output": 0, "messages": 0})
                bm["output"] += r["output"]
                bm["messages"] += 1
        return t


def context_window_for(model, table: dict) -> int:
    if model:
        best = None
        for k in table:
            if k != "default" and model.startswith(k) and (best is None or len(k) > len(best)):
                best = k
        if best:
            return int(table[best])
    return int(table.get("default", 200_000))


def short_model(model) -> str:
    if not model or model == "?":
        return "?"
    m = model.replace("claude-", "")
    parts = m.split("-")
    if len(parts) >= 3 and parts[1].isdigit():
        return f"{parts[0].capitalize()} {parts[1]}.{parts[2]}"
    return m


def account_info(claude_dir: str) -> dict:
    """Thông tin tài khoản từ .claude.json (không chứa token). Mặc định ~/.claude.json; khi đặt
    CLAUDE_CONFIG_DIR (claude_dir khác ~/.claude), Claude Code ghi file này trong thư mục đó."""
    home_file = Path.home() / ".claude.json"
    dir_file = Path(claude_dir) / ".claude.json"
    custom = Path(claude_dir).resolve() != (Path.home() / ".claude").resolve()
    for p in ((dir_file, home_file) if custom else (home_file, dir_file)):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        o = d.get("oauthAccount") or {}
        if not o:
            continue
        return {
            "email": o.get("emailAddress"),
            "org": o.get("organizationName"),
            "org_type": o.get("organizationType"),
            "tier": o.get("userRateLimitTier") or o.get("organizationRateLimitTier"),
        }
    return {}
