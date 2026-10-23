"""Máy trạng thái session: gộp sự kiện hook của Claude Code với dữ liệu poll từ sessions/<pid>.json.

Trạng thái hiển thị (thứ tự ưu tiên khi sắp xếp):
    wait   cần bạn: chờ duyệt quyền (wait_kind="permission") hoặc chờ trả lời (wait_kind="question")
    error  lượt vừa chạy lỗi (StopFailure)
    run    đang chạy (tool, detail: việc đang làm)
    done   vừa xong, chưa xem (last_msg: câu trả lời cuối)
    idle   rảnh

Không có hook nào cho session đó thì dùng poll: busy -> run, busy chuyển sang idle -> done, còn lại idle.
Module thuần: không đụng tkinter hay file, thời gian truyền vào để test được.
"""
from __future__ import annotations

import os

ORDER = {"wait": 0, "error": 1, "run": 2, "done": 3, "idle": 4}
DONE_TTL = 30 * 60          # "xong" không ai xem sau 30 phút thì về "rảnh"
RUN_STALE = 12.0            # hook nói đang chạy nhưng poll báo idle quá chừng này giây: coi như đã dừng (Esc)
IDLE_STALE = 6.0            # hook nói rảnh/xong nhưng poll báo busy quá chừng này: coi như đang chạy
WAIT_STALE = 30 * 60        # "cần bạn" mà poll báo idle suốt chừng này: người dùng đã bỏ prompt
DETAIL_MAX = 120


def _one_line(s, n: int = DETAIL_MAX) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _rel(path: str, cwd: str) -> str:
    if not path:
        return ""
    try:
        if cwd and os.path.commonpath([os.path.abspath(path), os.path.abspath(cwd)]) == os.path.abspath(cwd):
            return os.path.relpath(path, cwd).replace("\\", "/")
    except ValueError:  # khác ổ đĩa (Windows)
        pass
    return path.replace("\\", "/")


def summarize_tool(tool: str, inp, cwd: str = "") -> str:
    """Một dòng mô tả việc tool đang làm: lệnh Bash, file đang sửa, pattern đang tìm…"""
    inp = inp if isinstance(inp, dict) else {}
    if tool == "Bash":
        return _one_line(inp.get("command"))
    if tool in ("Edit", "MultiEdit", "Write", "Read", "NotebookEdit"):
        return _one_line(_rel(inp.get("file_path") or inp.get("notebook_path") or "", cwd))
    if tool in ("Grep", "Glob"):
        return _one_line(inp.get("pattern"))
    if tool == "WebFetch":
        return _one_line(inp.get("url"))
    if tool == "WebSearch":
        return _one_line(inp.get("query"))
    if tool in ("Task", "Agent"):
        return _one_line(inp.get("description") or inp.get("prompt"))
    if tool == "TodoWrite":
        todos = inp.get("todos") or []
        return _one_line(next((t.get("content") for t in todos if t.get("status") == "in_progress"), ""))
    for v in inp.values():  # tool khác (MCP…): giá trị chuỗi đầu tiên
        if isinstance(v, str) and v.strip():
            return _one_line(v)
    return ""


def _todo_progress(inp):
    todos = (inp or {}).get("todos") if isinstance(inp, dict) else None
    if not todos:
        return None
    return sum(1 for t in todos if t.get("status") == "completed"), len(todos)


def _question(inp) -> str:
    qs = (inp or {}).get("questions") if isinstance(inp, dict) else None
    if qs and isinstance(qs, list) and isinstance(qs[0], dict):
        return _one_line(qs[0].get("question"))
    return _one_line((inp or {}).get("question") if isinstance(inp, dict) else "")


class SessionStates:
    def __init__(self):
        self.rec: dict = {}       # session_id -> trạng thái theo hook
        self.polled: dict = {}    # session_id -> (status poll lần trước, lúc đổi)
        self.fallback: dict = {}  # session_id -> trạng thái suy ra từ poll (session chưa có hook)
        self.last_event = 0.0     # lúc nhận sự kiện hook gần nhất (Cài đặt → Hooks)

    # ---------------------------------------------------------------- hook
    def apply(self, ev: dict, now: float) -> bool:
        """Áp một sự kiện hook. True nếu trạng thái hiển thị có thể đã đổi."""
        sid = ev.get("session_id")
        name = ev.get("hook_event_name")
        if not sid or not name:
            return False
        self.last_event = now
        if name == "SessionEnd":
            return self.rec.pop(sid, None) is not None
        r = self.rec.setdefault(sid, {"state": "idle", "since": now, "tool": None, "detail": "", "last_msg": "",
                                       "wait_kind": None, "todo": None, "seen": True, "updated": now})
        cwd = ev.get("cwd") or ""
        tool, inp = ev.get("tool_name"), ev.get("tool_input")

        def set_state(st, **kw):
            if r["state"] != st:
                r["since"] = now
            r["state"] = st
            r.update(kw)

        if name == "UserPromptSubmit":
            set_state("run", tool=None, detail="", wait_kind=None, seen=True)
        elif name == "PreToolUse":
            if tool == "AskUserQuestion":
                set_state("wait", wait_kind="question", tool=tool, detail=_question(inp))
            else:
                set_state("run", wait_kind=None, tool=tool, detail=summarize_tool(tool, inp, cwd))
                if tool == "TodoWrite":
                    r["todo"] = _todo_progress(inp)
        elif name == "PermissionRequest":
            set_state("wait", wait_kind="permission", tool=tool or r["tool"],
                      detail=summarize_tool(tool, inp, cwd) if tool else r["detail"])
        elif name == "Notification":
            kind = ev.get("notification_type") or ""
            if kind == "permission_prompt":
                # tool/detail giữ từ PreToolUse ngay trước đó (PreToolUse chạy trước bước hỏi quyền)
                set_state("wait", wait_kind="permission")
            elif kind == "elicitation_dialog":
                set_state("wait", wait_kind="question", detail=_one_line(ev.get("message")) or r["detail"])
            elif kind == "idle_prompt" and r["state"] not in ("done", "error"):
                set_state("idle", wait_kind=None, tool=None)
            else:
                return False
        elif name in ("PostToolUse", "PostToolUseFailure"):
            set_state("run", wait_kind=None)
        elif name == "Stop":
            set_state("done", wait_kind=None, tool=None, detail="", seen=False,
                      last_msg=_one_line(ev.get("last_assistant_message"), 300))
        elif name == "StopFailure":
            set_state("error", wait_kind=None, tool=None, seen=False,
                      detail=_one_line(ev.get("error") or ev.get("message") or ev.get("reason")))
        elif name == "SessionStart":
            set_state("idle", wait_kind=None, tool=None, detail="")
        else:
            return False
        r["updated"] = now
        return True

    def mark_seen(self, sid: str, now: float) -> None:
        """Người dùng đã mở session (bấm vào card): "xong" / "lỗi" thành "rảnh"."""
        for table in (self.rec, self.fallback):
            r = table.get(sid)
            if r and r["state"] in ("done", "error"):
                r.update(state="idle", since=now, seen=True)

    # ---------------------------------------------------------------- gộp với poll
    def merge(self, sessions: list, now: float) -> list:
        """Gắn state, state_since, wait_kind, tool, detail, last_msg, todo vào từng session (dict từ
        ClaudeDataStore.active_sessions) rồi sắp theo thứ tự ưu tiên. Trả lại chính danh sách đó."""
        alive = set()
        for s in sessions:
            sid = s["session_id"]
            alive.add(sid)
            polled = s.get("status")
            prev = self.polled.get(sid)
            if prev is None or prev[0] != polled:
                self.polled[sid] = (polled, now)
            r = self.rec.get(sid)
            if r is not None:
                self._reconcile(r, polled, now)
            else:
                r = self._from_poll(sid, polled, prev[0] if prev else None, now)
            if r["state"] == "done" and now - r["since"] > DONE_TTL:
                r.update(state="idle", since=now, seen=True)
            s.update(state=r["state"], state_since=r["since"], wait_kind=r.get("wait_kind"), tool=r.get("tool"),
                     detail=r.get("detail") or "", last_msg=r.get("last_msg") or "", todo=r.get("todo"),
                     via_hooks=sid in self.rec)
        for table in (self.rec, self.polled, self.fallback):  # session đã tắt
            for sid in [k for k in table if k not in alive]:
                del table[sid]
        sessions.sort(key=lambda x: (ORDER.get(x["state"], 9), -(x.get("last_activity") or 0)))
        return sessions

    def _reconcile(self, r: dict, polled, now: float) -> None:
        """Hook có thể bị lỡ (Esc giữa chừng, Wisp mở sau khi session đã chạy): sửa theo poll khi lệch lâu."""
        quiet = now - r["updated"]
        if polled == "idle" and r["state"] == "run" and quiet > RUN_STALE:
            r.update(state="idle", since=now, tool=None, detail="")
        elif polled == "busy" and r["state"] in ("idle", "done") and quiet > IDLE_STALE:
            r.update(state="run", since=now)
        elif polled == "idle" and r["state"] == "wait" and quiet > WAIT_STALE:
            # Esc ngay tại prompt duyệt quyền không sinh sự kiện nào: đừng báo "cần bạn" mãi
            r.update(state="idle", since=now, wait_kind=None, tool=None, detail="")

    def _from_poll(self, sid: str, polled, before, now: float) -> dict:
        r = self.fallback.setdefault(sid, {"state": "idle", "since": now, "seen": True})
        if polled == "busy":
            if r["state"] != "run":
                r.update(state="run", since=now)
        elif before == "busy":  # vừa chạy xong
            r.update(state="done", since=now, seen=False)
        elif r["state"] == "run":
            r.update(state="idle", since=now)
        return r


def counts(sessions: list) -> dict:
    """Số session theo làn hiển thị: lỗi gộp vào "cần bạn"."""
    c = {"wait": 0, "run": 0, "done": 0, "idle": 0}
    for s in sessions:
        st = s.get("state", "idle")
        c["wait" if st == "error" else st] = c.get("wait" if st == "error" else st, 0) + 1
    return c


def headline(sessions: list, quota_pct, danger: float) -> str:
    """Trạng thái chung cho island, bóng nổi và mascot: wait > quota > run > done > idle."""
    c = counts(sessions)
    if c["wait"]:
        return "wait"
    if quota_pct is not None and quota_pct >= danger:
        return "quota"
    if c["run"]:
        return "run"
    if c["done"]:
        return "done"
    return "idle"
