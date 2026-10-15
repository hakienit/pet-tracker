"""Dọn dẹp session: đóng process, xoá transcript, xoá git worktree đã xong; trạng thái git của thư mục session.

Worktree chỉ được xoá khi "xong": sạch (không thay đổi chưa commit, kể cả file mới) và branch đã merge vào
nhánh chính hoặc đã push đúng commit hiện tại lên remote. Xoá bằng `git worktree remove` không --force (git tự
từ chối nếu còn thay đổi), rồi `git branch -d` chỉ khi đã merge. Worktree do Orca quản lý chỉ hiện trạng thái,
không xoá từ đây (xoá ngoài Orca để lại workspace "ma" trong Orca).
"""
from __future__ import annotations

import glob
import json
import os
import re
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
        # rstrip: giữ khoảng trắng đầu dòng của `status --short`
        return p.returncode, (p.stdout if p.returncode == 0 else (p.stderr or p.stdout)).rstrip()
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)


def is_orca(path: str) -> bool:
    # shortcut: nhận Orca theo đường dẫn <home>/orca/workspaces/..., đổi nếu Orca cho cấu hình thư mục khác
    parts = [x.lower() for x in Path(path).parts]
    return any(parts[i] == "orca" and parts[i + 1] == "workspaces" for i in range(len(parts) - 1))


def git_state(cwd: str):
    """Trạng thái git của thư mục session, None nếu không phải git repo.
    {top, common, linked, orca, branch, dirty, ignored, upstream, ahead, merged, base, done}
    dirty: số file đổi/chưa track; ignored: đường dẫn bị .gitignore (git worktree remove xoá luôn mà không hỏi)."""
    if not cwd or not os.path.isdir(cwd):
        return None
    rc, out = _git(cwd, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    if rc != 0:
        return None
    top, gitdir, common = (os.path.abspath(x) for x in out.splitlines()[:3])
    linked = os.path.normcase(gitdir) != os.path.normcase(common)
    # ghi rõ cờ untracked/ignored: không để config git của người dùng (status.showUntrackedFiles=no) giấu file
    rc, out = _git(cwd, "status", "--porcelain=v2", "--branch", "--untracked-files=all", "--ignored=matching")
    if rc != 0:
        return None
    branch, upstream, ahead, dirty, ignored = None, None, None, 0, []
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            branch = line[14:]
        elif line.startswith("# branch.upstream "):
            upstream = line[18:]
        elif line.startswith("# branch.ab "):
            ahead = int(line.split()[2].lstrip("+"))
        elif line.startswith("! "):
            ignored.append(line[2:])
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
        "dirty": dirty, "ignored": ignored, "upstream": upstream, "ahead": ahead, "merged": merged, "base": base,
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
    for o in sessions:
        if o["session_id"] != sess["session_id"] and (_under(o.get("cwd"), st["top"])
                                                       or _under(o.get("home_cwd"), st["top"])):
            return "session khác đang dùng"
    return None


def live_session_files(claude_dir: str) -> list:
    """sessions/<pid>.json của các process Claude Code còn sống (pid + procStart khớp)."""
    out = []
    for p in glob.glob(os.path.join(claude_dir, "sessions", "*.json")):
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("pid") and d.get("sessionId") and process_alive(d["pid"], d.get("procStart")):
            out.append(d)
    return out


def _under(path, top: str) -> bool:
    if not path:
        return False
    path, top = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(top))
    return path == top or path.startswith(top.rstrip(os.sep) + os.sep)


# ---------------------------------------------------------------- thao tác (chạy trên thread nền)
HANDOFF_PROMPT = """Viết bản handoff cho phiên làm việc này để một phiên sau tiếp tục được ngay: mục tiêu, \
những gì đã làm (commit, file chính), trạng thái hiện tại, việc còn dở, bước tiếp theo, lưu ý và rủi ro.
Lưu file markdown (.md) theo quy định của repo này (CLAUDE.md, AGENTS.md, rules, docs) về nơi và cách lưu \
handoff hay ghi chú. Nếu repo không quy định thì lưu vào {fallback}.
Không commit, không sửa file nào khác. Câu trả lời cuối chỉ gồm đường dẫn tuyệt đối của file đã ghi."""

_SID_RE = re.compile(r"^[0-9A-Za-z-]{8,64}$")
_MODEL_RE = re.compile(r"^[0-9A-Za-z._:\[\]-]{1,80}$")


def claude_command() -> str:
    exe = "claude.exe" if sys.platform == "win32" else "claude"
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / exe)


def write_handoff(sess: dict, fallback_dir: Path, timeout: float = 300.0) -> tuple:
    """Fork session ở chế độ không tương tác (session gốc không bị đụng tới, bản fork không lưu lại) để nó tự
    viết handoff theo quy định của repo. (ok, đường dẫn file | lỗi)."""
    sid = sess.get("session_id") or ""
    cwd = sess.get("home_cwd") or sess.get("cwd")
    if not _SID_RE.match(sid) or not cwd or not os.path.isdir(cwd):
        return False, "thiếu sessionId hoặc thư mục không tồn tại"
    name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (sess.get("name") or sid[:8]))[:60]
    fallback = Path(fallback_dir) / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.md"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    # --tools giới hạn hẳn công cụ (không Bash, không MCP); --allowedTools chỉ duyệt sẵn chúng. Prompt đi qua
    # stdin, không qua dòng lệnh (claude.cmd của npm chạy qua cmd.exe: xuống dòng, %, & bị diễn giải).
    tools = ["Read", "Glob", "Grep", "Write", "Edit"]
    args = [claude_command(), "-p", "--resume", sid, "--fork-session", "--no-session-persistence",
            "--output-format", "json", "--permission-mode", "acceptEdits", "--add-dir", str(fallback.parent),
            "--strict-mcp-config", "--tools", *tools, "--allowedTools", *tools]
    if _MODEL_RE.match(sess.get("model") or "") and sess["model"] != "?":
        args += ["--model", sess["model"]]
    # claude.cmd (bản npm) chạy qua cmd.exe: ký tự đặc biệt của cmd trong tham số (vd đường dẫn APPDATA có &)
    # có thể bị diễn giải thành lệnh; không chạy trong trường hợp đó
    if args[0].lower().endswith((".cmd", ".bat")) and any(re.search(r'[%&|<>^"!\r\n]', a) for a in args[1:]):
        return False, "claude là bản npm (claude.cmd) và đường dẫn có ký tự đặc biệt; cài bản native để dùng handoff"
    started = time.time()
    try:
        p = subprocess.run(args, cwd=cwd, input=HANDOFF_PROMPT.format(fallback=fallback), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           creationflags=_NO_WINDOW, env=clean_env())
    except subprocess.TimeoutExpired:
        return False, "viết handoff quá lâu, chưa đóng session"
    except OSError as e:
        return False, f"không chạy được claude: {e}"
    try:
        res = json.loads(p.stdout)
        text = (res.get("result") or "").strip()
        failed = res.get("is_error")
    except ValueError:
        text, failed = (p.stderr or p.stdout).strip(), True
    line = text.strip("`\"' \n").splitlines()[-1].strip("`\"' ") if text else ""
    if failed or p.returncode != 0 or not line:
        return False, f"handoff lỗi, chưa đóng session: {(text or p.stderr or p.returncode)!s:.200}"
    path = Path(line) if os.path.isabs(line) else Path(cwd) / line
    # chỉ nhận file .md vừa ghi, nằm trong repo hoặc thư mục handoff của Wisp (nút Handoff sẽ mở file này)
    try:
        fresh = path.is_file() and path.stat().st_mtime >= started - 2
    except OSError:
        fresh = False
    if path.suffix.lower() != ".md" or not fresh or not (_under(str(path), cwd) or _under(str(path), str(fallback.parent))):
        return False, f"handoff không ra file .md mới trong repo, chưa đóng session: {line[:160]}"
    return True, str(path.resolve())


def _process_name(pid: int) -> str:
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf, n = ctypes.create_unicode_buffer(1024), ctypes.c_ulong(1024)
            ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
            return os.path.basename(buf.value) if ok else ""
        finally:
            k32.CloseHandle(h)
    try:
        out = subprocess.run(["ps", "-o", "comm=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    return os.path.basename(out.strip())


def _is_claude_process(pid: int, proc_start) -> bool:
    """Windows có procStart thì process_alive đã loại pid bị dùng lại. Thiếu nó (hoặc macOS, không so được
    thời điểm tạo) thì kiểm tra tên process trước khi tắt."""
    if sys.platform == "win32" and proc_start:
        return True
    name = _process_name(pid).lower()
    return "claude" in name or name in ("node", "node.exe")


def _kill(pid: int) -> None:
    if sys.platform == "win32":
        # /T: cả cây process (bash nền, MCP, dev server); nếu không, chúng giữ khoá thư mục worktree
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15,
                       creationflags=_NO_WINDOW)
    else:
        os.kill(pid, signal.SIGTERM)


def close_session(sess: dict, claude_dir: str, wait: float = 8.0) -> tuple:
    """Kết thúc mọi process Claude Code đang chạy session này (một session có thể được resume ở hai terminal).
    Kiểm tra lại pid + procStart để không giết nhầm process khác đã nhận lại pid đó."""
    procs = {(d["pid"], d.get("procStart")) for d in live_session_files(claude_dir)
             if d.get("sessionId") == sess.get("session_id")}
    if sess.get("pid") and process_alive(sess["pid"], sess.get("proc_start")):
        procs.add((sess["pid"], sess.get("proc_start")))
    if not procs:
        return True, "session đã đóng"
    for pid, start in procs:
        if not _is_claude_process(pid, start):
            return False, f"pid {pid} không còn là Claude Code, không đóng"
        try:
            _kill(pid)
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"không đóng được: {e}"
    end = time.time() + wait
    while time.time() < end:
        if not any(process_alive(pid, start) for pid, start in procs):
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


def _remote_has_head(st: dict) -> bool:
    """Branch chưa merge nhưng "đã push": hỏi thẳng remote (ref tracking local có thể cũ, branch đã bị xoá)."""
    b = st["branch"]
    if not b:
        return False
    rc_r, remote = _git(st["top"], "config", f"branch.{b}.remote")
    rc_m, merge = _git(st["top"], "config", f"branch.{b}.merge")
    rc_h, head = _git(st["top"], "rev-parse", "HEAD")
    if rc_r or rc_m or rc_h:
        return False
    rc, out = _git(st["top"], "ls-remote", remote.strip(), merge.strip(), timeout=20)
    return rc == 0 and bool(out) and out.split()[0] == head.strip()


def remove_worktree(sess: dict, claude_dir: str) -> tuple:
    """Xoá worktree (sau khi đã đóng session) và branch local nếu đã merge."""
    st = git_state(sess.get("cwd"))  # kiểm tra lại ngay trước khi xoá, không tin số liệu cũ
    if not st or not st["linked"] or st["orca"] or not st["done"]:
        return False, "worktree không còn ở trạng thái xong, không xoá"
    for d in live_session_files(claude_dir):  # session khác mở trong worktree sau khi menu đã hiện
        if d.get("sessionId") != sess.get("session_id") and _under(d.get("cwd"), st["top"]):
            return False, "có session khác đang chạy trong worktree, không xoá"
    if not st["merged"] and not _remote_has_head(st):
        return False, "branch chưa merge và remote không còn đúng commit này, không xoá"
    # chạy git từ thư mục .git chung: process con không được đứng trong thư mục sắp xoá (Windows khoá thư mục)
    rc, out = _git(st["common"], "-c", "status.showUntrackedFiles=all", "worktree", "remove", st["top"], timeout=60)
    if rc != 0:
        return False, f"git worktree remove: {out.splitlines()[-1] if out else rc}"
    msg = f"đã xoá worktree {os.path.basename(st['top'])}"
    if st["branch"] and st["merged"]:
        rc, out = _git(st["common"], "branch", "-d", st["branch"])
        msg += f", xoá branch {st['branch']}" if rc == 0 else f", giữ branch {st['branch']}"
    elif st["branch"]:
        msg += f", giữ branch {st['branch']} (đã push, chưa merge)"
    return True, msg
