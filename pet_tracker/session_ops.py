"""Dọn dẹp session: đóng process, xoá transcript, xoá git worktree đã xong; trạng thái git của thư mục session.

Worktree chỉ được xoá khi "xong": sạch (không thay đổi chưa commit, kể cả file mới) và branch đã merge vào
nhánh chính hoặc đã push hết lên upstream. Xoá bằng `git worktree remove` không --force (git tự từ chối nếu
còn thay đổi), rồi `git branch -d` (git tự từ chối nếu branch chưa merge). Worktree do Orca quản lý chỉ hiện
trạng thái, không xoá từ đây (xoá ngoài Orca để lại workspace "ma" trong Orca).
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .claude_data import process_alive
from .procenv import clean_env

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _git(cwd, *args, timeout: float = 8.0):
    """(returncode, stdout) của một lệnh git; (-1, lỗi) nếu không chạy được."""
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_NO_WINDOW, env=clean_env())
        return p.returncode, (p.stdout if p.returncode == 0 else (p.stderr or p.stdout)).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)


def is_orca(path: str) -> bool:
    # shortcut: nhận Orca theo đường dẫn <home>/orca/workspaces/..., đổi nếu Orca cho cấu hình thư mục khác
    parts = [x.lower() for x in Path(path).parts]
    return any(parts[i] == "orca" and parts[i + 1] == "workspaces" for i in range(len(parts) - 1))


def git_state(cwd: str):
    """Trạng thái git của thư mục session, None nếu không phải git repo.
    {top, common, linked, orca, branch, dirty, upstream, ahead, merged, base, done}"""
    if not cwd or not os.path.isdir(cwd):
        return None
    rc, out = _git(cwd, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    if rc != 0:
        return None
    top, gitdir, common = (os.path.abspath(x) for x in out.splitlines()[:3])
    linked = os.path.normcase(gitdir) != os.path.normcase(common)
    rc, out = _git(cwd, "status", "--porcelain=v2", "--branch")
    if rc != 0:
        return None
    branch, upstream, ahead, dirty = None, None, None, 0
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            branch = line[14:]
        elif line.startswith("# branch.upstream "):
            upstream = line[18:]
        elif line.startswith("# branch.ab "):
            ahead = int(line.split()[2].lstrip("+"))
        elif line and not line.startswith("#"):
            dirty += 1
    base = None
    rc, out = _git(cwd, "rev-parse", "--abbrev-ref", "origin/HEAD")
    candidates = ([out] if rc == 0 else []) + ["origin/main", "origin/master", "main", "master"]
    for c in candidates:
        if _git(cwd, "rev-parse", "--verify", "--quiet", c)[0] == 0:
            base = c
            break
    merged = bool(base) and _git(cwd, "merge-base", "--is-ancestor", "HEAD", base)[0] == 0
    pushed = upstream is not None and ahead == 0
    return {
        "top": str(Path(top)), "common": common, "linked": linked, "orca": is_orca(top),
        "branch": branch if branch and branch != "(detached)" else None,
        "dirty": dirty, "upstream": upstream, "ahead": ahead, "merged": merged, "base": base,
        "done": dirty == 0 and (merged or pushed),
    }


def state_text(st) -> tuple:
    """(chữ ngắn, loại) cho card: loại 'done' | 'warn' | None."""
    if not st:
        return "", None
    if st["dirty"]:
        return f"{st['dirty']} thay đổi chưa commit", "warn"
    if st["done"]:
        return "✓ xong", "done"
    if st["upstream"] and st["ahead"]:
        return f"{st['ahead']} commit chưa push", "warn"
    return "chưa push / merge", "warn"


def worktree_block_reason(sess: dict, sessions: list):
    """None nếu được xoá worktree của session này, ngược lại là lý do (hiện trong menu)."""
    st = sess.get("git")
    if not st or not st["linked"]:
        return "không phải worktree"
    if st["orca"]:
        return "worktree Orca: xoá trong Orca"
    if not st["done"]:
        return state_text(st)[0]
    top = os.path.normcase(st["top"])
    for o in sessions:
        cwd = os.path.normcase(o.get("cwd") or "")
        if o["session_id"] != sess["session_id"] and (cwd == top or cwd.startswith(top + os.sep)):
            return "session khác đang dùng"
    return None


# ---------------------------------------------------------------- thao tác (chạy trên thread nền)
def close_session(sess: dict, wait: float = 6.0) -> tuple:
    """Kết thúc process Claude Code của session. Kiểm tra lại pid + procStart để không giết nhầm process khác
    đã nhận lại pid đó."""
    pid = sess.get("pid")
    if not pid or not process_alive(pid, sess.get("proc_start")):
        return True, "session đã đóng"
    try:
        os.kill(pid, signal.SIGTERM)  # Windows: TerminateProcess
    except OSError as e:
        return False, f"không đóng được: {e}"
    end = time.time() + wait
    while time.time() < end:
        if not process_alive(pid, sess.get("proc_start")):
            return True, "đã đóng session"
        time.sleep(0.2)
    return False, "process chưa thoát"


def delete_transcript(sess: dict, claude_dir: str) -> tuple:
    """Xoá transcript .jsonl và thư mục đi kèm (subagents, tool results). Chỉ xoá trong <claude_dir>/projects."""
    p = sess.get("transcript")
    if not p:
        return True, "không có transcript"
    root = os.path.normcase(os.path.abspath(os.path.join(claude_dir, "projects"))) + os.sep
    p = os.path.abspath(p)
    if not os.path.normcase(p).startswith(root) or not p.endswith(".jsonl"):
        return False, f"bỏ qua đường dẫn lạ: {p}"
    try:
        if os.path.exists(p):
            os.remove(p)
        side = p[:-len(".jsonl")]
        if os.path.isdir(side):
            shutil.rmtree(side)
    except OSError as e:
        return False, f"không xoá được transcript: {e}"
    return True, "đã xoá session"


def remove_worktree(sess: dict) -> tuple:
    """Xoá worktree (sau khi đã đóng session) và branch local nếu đã merge."""
    st = git_state(sess.get("cwd"))  # kiểm tra lại ngay trước khi xoá, không tin số liệu cũ
    if not st or not st["linked"] or st["orca"] or not st["done"]:
        return False, "worktree không còn ở trạng thái xong, không xoá"
    # chạy git từ thư mục .git chung: process con không được đứng trong thư mục sắp xoá (Windows khoá thư mục)
    rc, out = _git(st["common"], "worktree", "remove", st["top"], timeout=60)
    if rc != 0:
        return False, f"git worktree remove: {out.splitlines()[-1] if out else rc}"
    msg = f"đã xoá worktree {os.path.basename(st['top'])}"
    if st["branch"]:
        rc, out = _git(st["common"], "branch", "-d", st["branch"])
        msg += f", xoá branch {st['branch']}" if rc == 0 else f", giữ branch {st['branch']} (chưa merge)"
    return True, msg
