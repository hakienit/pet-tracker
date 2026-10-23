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
- agent-*.meta.json cạnh mỗi subagent: agentType, description, toolUseId, spawnDepth, finished (chỉ ghi lúc xong).
- Worker: tool_use `Agent`/`Task` (assistant), `toolUseResult.backgroundTaskId` (user) mở một task nền; record
  queue-operation chứa <task-notification> (kèm <status>) là tín hiệu xong của subagent/task nền.

Context window đang dùng = input + cache_creation + cache_read của assistant message mới nhất
trên nhánh chính (đó chính là toàn bộ prompt gửi lên API ở lượt đó).
"""
from __future__ import annotations

import glob
import json
import os
import re
import stat
import time
from datetime import datetime
from pathlib import Path

from . import platform as plat


_TITLE_MARKERS = (b'"customTitle"', b'"aiTitle"', b'"agentName"')

# Giới hạn ingest worker (subagent / task nền). Dữ liệu transcript và meta là dữ liệu không tin cậy.
MAX_POLL_BYTES = 8 << 20   # poll đọc từng chunk cỡ này (RAM có trần), lặp tới EOF trong cùng lần gọi
MAX_LINE = 1 << 20         # mọi dòng dài hơn ngần này (chờ hay đã đủ) bị bỏ, bất kể ranh giới chunk; dòng chờ không giữ trong RAM
MIN_LINE = 20              # dòng ngắn hơn ngần này không phải record: bỏ qua (file toàn \n không làm chạy tốn công)
MAX_SMALL_LINE = 16 << 10  # chỉ dòng ngắn hơn ngần này mới quét marker tiêu đề / task nền (hai loại record này nhỏ)
MAX_STR = 200              # chuỗi từ transcript/meta lưu lại bị cắt ở đây
CAP_ITEMS = 500            # agent_calls, bg_tasks, open_tools mỗi Transcript; workers mỗi session
CAP_NOTIFS = 2000          # notifs, task_notifs mỗi Transcript (chuỗi ngắn, cần nhiều hơn vì giữ tín hiệu "xong")
MAX_META = 64 * 1024       # meta lớn hơn thì bỏ qua
MAX_DEPTH = 8              # kẹp spawnDepth

# Marker thông báo: chỉ record queue-operation, chỉ phần đầu (trước <summary>/<result>, nơi agent có thể ghi chữ
# tuỳ ý). Khớp trên byte thô: chuỗi lồng trong JSON luôn bị escape nên marker thật chỉ xuất hiện ở khoá thật.
_RE_NOTIF = re.compile(rb'"content":"<task-notification>(.{0,2000})')
_RE_CUT = re.compile(rb'<summary>|<result>')
_RE_TASK = re.compile(rb'<task-id>([^<\\"\s]{1,200})</task-id>')
_RE_TUID = re.compile(rb'<tool-use-id>([^<\\"\s]{1,200})</tool-use-id>')
_RE_STATUS = re.compile(rb'<status>([A-Za-z_-]{1,32})</status>')
_RE_NLS = re.compile(rb"\n+")
_RE_RESULT_ID = re.compile(rb'"tool_use_id":"([^"\\]{1,200})"')
_NO_META = {"agent_type": "?", "description": "", "tool_use_id": None, "depth": 0, "finished": False}

# Ước tính local chỉ cần 7 ngày gần nhất. Transcript không đổi lâu hơn thế không được đọc (trừ khi là của
# một session đang chạy), để thời gian khởi động và RAM không tăng theo toàn bộ lịch sử trên máy.
USAGE_HORIZON_SEC = 7 * 86400 + 3600


def _put(d: dict, k, v, cap: int) -> None:
    """Gán d[k] = v; đầy thì bỏ phần tử cũ nhất (dict giữ thứ tự chèn)."""
    if k not in d and len(d) >= cap:
        del d[next(iter(d))]
    d[k] = v


def _open_regular(p: str):
    """Mở file thường để đọc: (file nhị phân, fstat) hoặc (None, None). O_NONBLOCK + fstat trên fd để FIFO/thiết bị
    không làm treo thread thu thập (os.stat theo symlink, FIFO báo size 0, open() chặn tới khi có writer)."""
    try:
        fd = os.open(p, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    except OSError:
        return None, None
    try:
        st = os.fstat(fd)
        if stat.S_ISREG(st.st_mode):
            return os.fdopen(fd, "rb"), st
    except OSError:
        pass
    os.close(fd)
    return None, None


def _s(v) -> str:
    return v[:MAX_STR] if isinstance(v, str) else ""


def _depth(v) -> int:
    """spawnDepth từ meta: ép int có bảo vệ, kẹp 0..MAX_DEPTH."""
    if isinstance(v, bool):
        return 0
    try:
        n = int(v)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(MAX_DEPTH, n))


def _meta_path(jsonl: str):
    """Đường dẫn meta chỉ dựng từ đường dẫn jsonl; không bao giờ ghép id lấy từ dữ liệu vào đường dẫn."""
    return jsonl[:-len(".jsonl")] + ".meta.json" if jsonl.endswith(".jsonl") else None


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
        self._reset_workers()

    def _reset_workers(self) -> None:
        self.agent_calls: list = []   # id tool_use Agent/Task file này phát ra (dedupe, giữ thứ tự)
        self.notifs: dict = {}        # tool_use_id -> status của task-notification
        self.task_notifs: dict = {}   # task_id -> status
        self.bg_tasks: dict = {}      # task_id -> {tool_use_id, started, status}
        self.open_tools: dict = {}    # chỉ file subagent: id tool_use chưa có tool_result (dict giữ thứ tự để bỏ cái cũ nhất)
        self._skip = False            # đang bỏ phần còn lại của một dòng quá lớn

    def poll(self) -> bool:
        try:
            st = os.stat(self.path)
        except OSError:
            return False
        if not stat.S_ISREG(st.st_mode) or (st.st_size == self.offset and st.st_mtime == self.mtime):
            return False
        self.mtime = st.st_mtime
        if st.st_size < self.offset:  # file bị ghi lại từ đầu
            self.offset, self.buf, self.msgs, self.last_main = 0, b"", {}, None
            self._reset_workers()
        f, st = _open_regular(self.path)  # st: fstat của đúng fd đang đọc
        if f is None:
            return False
        try:
            with f:
                f.seek(self.offset)
                left = st.st_size - self.offset
                while left > 0:  # đọc từng chunk MAX_POLL_BYTES tới EOF: RAM có trần, không trễ lúc khởi động
                    data = f.read(min(MAX_POLL_BYTES, left))  # đúng cỡ: read(n) lớn cấp phát n byte
                    if not data:
                        break
                    left -= len(data)
                    self.offset += len(data)
                    self._feed(data)
        except OSError:
            return False
        return True

    def _feed(self, data: bytes) -> None:
        """Ghép data với dòng chờ trong buf, ingest các dòng đủ, giữ dòng cuối (có thể chưa ghi xong) trong buf."""
        if self._skip:  # bỏ nốt phần còn lại của dòng quá lớn trước đó
            i = data.find(b"\n")
            if i < 0:
                return
            data, self._skip = data[i + 1:], False
        else:
            data = self.buf + data
        # Duyệt bằng find, không split: file toàn \n hay toàn dòng ngắn không sinh list hàng triệu phần tử. Dòng rỗng
        # thì nhảy qua cả dãy \n bằng một lần match. Dòng ngắn hơn MIN_LINE hay dài hơn MAX_LINE bị bỏ, không cắt lát.
        pos, find = 0, data.find
        while True:
            j = find(b"\n", pos)
            if j < 0:
                break
            if j == pos:
                pos = _RE_NLS.match(data, pos).end()
                continue
            if MIN_LINE <= j - pos <= MAX_LINE:
                self._ingest(data[pos:j])
            pos = j + 1
        self.buf = data[pos:]  # phần cuối có thể chưa ghi xong
        if len(self.buf) > MAX_LINE:
            self.buf, self._skip = b"", True

    def _ingest(self, line: bytes) -> None:
        if b'"type":"assistant"' in line:
            self._ingest_assistant(line)  # cũng ghi agent_calls / open_tools, trước guard usage (xem đó)
            return
        # Dòng user/tool_result khổng lồ chiếm gần hết dung lượng file, nên không quét marker trên chúng: record
        # queue-operation có "type" ngay đầu; record khởi chạy task nền và record tên/tiêu đề đều ngắn (đo trên
        # dữ liệu thật: mọi record tên/tiêu đề < 1 KB).
        small = len(line) <= MAX_SMALL_LINE
        if b'"type":"queue-operation"' in line[:256]:
            self._ingest_notif(line)
        elif small and b'"backgroundTaskId":' in line:
            self._ingest_bg(line)
        # độc lập với nhánh trên: record khởi chạy task nền cũng là tool_result của Bash. Byte regex vì dòng user rất lớn.
        if self.sidechain_file and b'"tool_result"' in line:
            for i in _RE_RESULT_ID.findall(line):
                self.open_tools.pop(i.decode("utf-8", "replace"), None)
        if small and any(m in line for m in _TITLE_MARKERS):  # cố ý bỏ qua dòng > MAX_SMALL_LINE (có test)
            try:
                d = json.loads(line)
            except Exception:
                return
            t = d.get("customTitle") or d.get("aiTitle") or d.get("agentName")
            if t and (d.get("type") == "custom-title" or not self.title or d.get("type") == "ai-title"):
                self.title = t

    def _ingest_notif(self, line: bytes) -> None:
        """record queue-operation có <task-notification>; không có <status> (Monitor...) thì bỏ."""
        m = _RE_NOTIF.search(line)
        if not m:
            return
        head = m.group(1)
        cut = _RE_CUT.search(head)
        if cut:
            head = head[:cut.start()]
        task, status = _RE_TASK.search(head), _RE_STATUS.search(head)
        if not task or not status:
            return
        task, status = task.group(1).decode("utf-8", "replace"), status.group(1).decode("ascii")
        _put(self.task_notifs, task, status, CAP_NOTIFS)
        if task in self.bg_tasks:
            self.bg_tasks[task]["status"] = status
        tuid = _RE_TUID.search(head)
        if tuid:
            _put(self.notifs, tuid.group(1).decode("utf-8", "replace"), status, CAP_NOTIFS)

    def _ingest_bg(self, line: bytes) -> None:
        """record user có toolUseResult.backgroundTaskId: một task nền (Bash) vừa bắt đầu."""
        try:
            d = json.loads(line)
        except Exception:
            return
        if not isinstance(d, dict) or d.get("type") != "user":
            return
        r = d.get("toolUseResult")
        tid = r.get("backgroundTaskId") if isinstance(r, dict) else None
        if not isinstance(tid, str) or not tid or tid[:MAX_STR] in self.bg_tasks:
            return
        tid, tuid = tid[:MAX_STR], None
        msg = d.get("message")
        for b in (msg.get("content") if isinstance(msg, dict) else None) or ():
            if isinstance(b, dict) and isinstance(b.get("tool_use_id"), str):
                tuid = b["tool_use_id"][:MAX_STR]
                break
        _put(self.bg_tasks, tid, {"tool_use_id": tuid, "started": _parse_ts(d.get("timestamp")),
                                  "status": self.task_notifs.get(tid)}, CAP_ITEMS)

    def _ingest_assistant(self, line: bytes) -> None:
        try:
            d = json.loads(line)
        except Exception:
            return
        if d.get("type") != "assistant":
            return
        msg = d.get("message") or {}
        if not isinstance(msg, dict):
            return
        # Agent/Task tool_use và (file subagent) tool_use đang mở: ghi trước guard usage, kể cả record <synthetic>
        content = msg.get("content")
        for b in content if isinstance(content, list) else ():
            if isinstance(b, dict) and b.get("type") == "tool_use" and isinstance(b.get("id"), str):
                i = b["id"][:MAX_STR]
                if b.get("name") in ("Agent", "Task") and i not in self.agent_calls:
                    self.agent_calls.append(i)
                    del self.agent_calls[:-CAP_ITEMS]
                if self.sidechain_file:
                    _put(self.open_tools, i, None, CAP_ITEMS)
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
        self._metas: dict = {}           # path meta -> {key (mtime_ns, size), d (đã làm sạch), done (ngừng đọc)}
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

        ep = glob.escape(str(proj))  # claude_dir có thể chứa [ * ?
        mains = glob.glob(os.path.join(ep, "*", "*.jsonl"))
        subs = glob.glob(os.path.join(ep, "*", "*", "subagents", "*.jsonl"))
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
        self._metas = {k: v for k, v in self._metas.items() if k[:-len(".meta.json")] + ".jsonl" in self.transcripts}

    def poll_all(self) -> None:
        self._scan_files()
        for t in list(self.transcripts.values()):
            t.poll()

    # ---- sessions
    def read_session_files(self) -> list:
        out = []
        for p in glob.glob(os.path.join(glob.escape(str(self.claude_dir / "sessions")), "*.json")):
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
        for p in glob.glob(os.path.join(glob.escape(main[:-len(".jsonl")]), "subagents", "*.jsonl")):
            self._pinned.add(p)
            out.append(self._load(p, sidechain=True))
        return out

    def _meta(self, mp: str) -> dict:
        """Meta subagent đã làm sạch. Đọc lại khi mtime/size đổi, ngừng đọc khi `done`. Hỏng/quá lớn/thiếu: _NO_META."""
        c = self._metas.get(mp)
        if c and c["done"]:
            return c["d"]
        try:
            st = os.stat(mp)
        except OSError:
            return c["d"] if c else _NO_META
        key = (st.st_mtime_ns, st.st_size)
        if c and c["key"] == key:
            return c["d"]
        d = _NO_META
        if stat.S_ISREG(st.st_mode) and st.st_size <= MAX_META:
            try:
                f, _ = _open_regular(mp)
                if f is None:
                    raise OSError
                with f:
                    raw = json.loads(f.read(MAX_META + 1))
                if isinstance(raw, dict):
                    d = {"agent_type": _s(raw.get("agentType")) or "?", "description": _s(raw.get("description")),
                         "tool_use_id": _s(raw.get("toolUseId")) or None, "depth": _depth(raw.get("spawnDepth")),
                         "finished": raw.get("finished") is True}
            except Exception:
                pass
        self._metas[mp] = {"key": key, "d": d, "done": False}
        return d

    def _workers(self, main, subs: list) -> list:
        """Subagent (từ meta + transcript riêng) và task nền của một session. Notification tìm trong mọi transcript
        của chính session này (kể cả transcript subagent cha)."""
        trs = ([main] if main else []) + subs
        notifs, tasks = {}, {}
        for t in trs:
            notifs.update(t.notifs)
            tasks.update(t.task_notifs)
        out = []
        for t in subs:
            mp = _meta_path(t.path)
            m = self._meta(mp)
            ns = notifs.get(m["tool_use_id"]) if m["tool_use_id"] else None
            if mp in self._metas and (m["finished"] or ns):
                self._metas[mp]["done"] = True
            tot = t.totals()
            out.append({
                "kind": "subagent", "id": _s(Path(t.path).stem), "tool_use_id": m["tool_use_id"],
                "agent_type": m["agent_type"], "description": m["description"], "depth": m["depth"],
                "finished": m["finished"], "notif_status": ns, "mtime": t.mtime,
                "started": t.first_ts, "last_activity": t.last_ts,
                "tokens": tot["input"] + tot["cache_create"] + tot["cache_read"] + tot["output"],
                "open_tools": len(t.open_tools), "agent_calls": list(t.agent_calls),
            })
        seen = set()
        for t in trs:
            for tid, b in t.bg_tasks.items():
                if tid not in seen:
                    seen.add(tid)
                    out.append({"kind": "bgtask", "id": tid, "tool_use_id": b["tool_use_id"],
                                "started": b["started"], "status": b["status"] or tasks.get(tid)})
        if len(out) > CAP_ITEMS:  # giữ CAP_ITEMS worker mới nhất
            out.sort(key=lambda w: w.get("mtime") or w.get("started") or 0)
            out = out[-CAP_ITEMS:]
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
                "agent_calls": list(tr.agent_calls) if tr else [],
                "workers": self._workers(tr, subs) if tr else [],
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
