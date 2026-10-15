"""Action điều khiển một Claude Code session từ widget.

Khảo sát 2026-10-15 (Claude Code 2.1.300):
- Không có API/IPC công khai để đổi model, effort, clear… của một session đang chạy.
  Named pipe `messagingSocketPath` (cc-msg-…) chỉ dùng để gửi tin nhắn giữa các session
  (hiện ra như tin nhắn cho agent), không chạy slash command.
- Windows: session CLI đọc bàn phím từ console. Widget AttachConsole(pid) rồi ghi KEY_EVENT vào
  CONIN$ (WriteConsoleInputW) = gõ hộ slash command: /model <id>, /effort <level>,
  /compact, /clear, /exit (platform/win_console.py). macOS: chưa hỗ trợ (giai đoạn 1).
- Session trong Claude desktop app: tiến trình claude.exe chạy với --output-format stream-json,
  không có console input; app không có deep link đổi model/effort. Chỉ hỗ trợ "mở trong app"
  và handoff.
- Handoff: mở cửa sổ terminal mới chạy `claude --resume <sessionId> --fork-session` trong thư mục
  của session -> session mới mang toàn bộ hội thoại, session cũ giữ nguyên.
- Danh sách model / effort lấy từ cache catalog của Claude Code:
  ~/.claude/cache/model-catalog/<org>-…-cc.json (models[].id, name, section, thinking.effort_options).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import threading
import time
from pathlib import Path

from . import platform as plat


DEFAULT_EFFORTS = ["low", "medium", "high", "xhigh", "max"]


# ---------------------------------------------------------------- catalog
def load_catalog(claude_dir: str) -> list:
    """[(model_id, name, [efforts])] các model chính (section main) theo cache của Claude Code."""
    files = [p for p in glob.glob(str(Path(claude_dir) / "cache" / "model-catalog" / "*-cc.json"))
             if not os.path.basename(p).startswith("tok-")]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for f in files:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            out = []
            for m in d["catalog"]["config"]["models"]:
                if m.get("section") != "main":
                    continue
                effs = [o["id"] for o in ((m.get("thinking") or {}).get("effort_options") or [])]
                out.append((m["id"], m.get("name") or m["id"], effs or DEFAULT_EFFORTS))
            if out:
                return out
        except Exception:
            continue
    return [("opus", "Opus", DEFAULT_EFFORTS), ("sonnet", "Sonnet", DEFAULT_EFFORTS), ("haiku", "Haiku", DEFAULT_EFFORTS)]


# ---------------------------------------------------------------- capability
def is_cli(sess: dict) -> bool:
    return (sess.get("entrypoint") or "") == "cli"


def command_block_reason(sess: dict) -> str | None:
    """None nếu gửi được slash command vào session; ngược lại là lý do (hiện trong menu)."""
    if not plat.CAN_TYPE_INTO_SESSION:
        return plat.TYPE_UNSUPPORTED_REASON
    if not is_cli(sess):
        return "chỉ CLI"
    if sess.get("status") == "busy":
        return "đang bận"
    return None


# /model và /effort gõ trong terminal được Claude Code lưu luôn thành mặc định cho session mới
# (ghi "model" / "modelSettings.<model>.effortLevel" vào ~/.claude/settings.json, kèm thông báo
# "saved as your default for new sessions"). Widget chỉ muốn đổi cho đúng session được chọn, nên
# chụp lại các khoá này trước khi gửi lệnh và trả về giá trị cũ sau khi Claude Code ghi xong.
_GUARDED_KEYS = ("model", "modelSettings")


def _settings_path(claude_dir) -> Path:
    return Path(claude_dir or (Path.home() / ".claude")) / "settings.json"


def _restore_defaults_later(path: Path, before: dict, before_mtime: float, timeout: float = 5.0) -> None:
    def work():
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.25)
            try:
                if path.stat().st_mtime != before_mtime:
                    break
            except OSError:
                return
        time.sleep(0.3)  # để Claude Code ghi xong
        try:
            cur = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        changed = False
        for k in _GUARDED_KEYS:
            if cur.get(k) != before.get(k):
                changed = True
                if k in before:
                    cur[k] = before[k]
                else:
                    cur.pop(k, None)
        if changed:
            tmp = path.with_name(path.name + ".pet-tmp")
            tmp.write_text(json.dumps(cur, indent=2, ensure_ascii=False) + os.linesep.replace("\r", ""),
                           encoding="utf-8")
            os.replace(tmp, path)

    threading.Thread(target=work, daemon=True, name="restore-defaults").start()


def send_slash(sess: dict, command: str, claude_dir=None, keep_defaults: bool = True) -> tuple:
    why = command_block_reason(sess)
    if why:
        return False, f"không gửi được ({why})"
    guard = keep_defaults and command.split()[0] in ("/model", "/effort")
    path = _settings_path(claude_dir)
    before, before_mtime = {}, 0.0
    if guard:
        try:
            before_mtime = path.stat().st_mtime
            before = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            guard = False
    ok, msg = plat.type_into_session(int(sess["pid"]), command + "\r")
    if ok and guard:
        _restore_defaults_later(path, before, before_mtime)
    return ok, (f"đã gửi {command}" if ok else msg)


# ---------------------------------------------------------------- env
_SCRUB_PREFIXES = ("CLAUDE_", "CLAUDECODE", "MCP_SERVER_CONNECTION_BATCH_SIZE", "MCP_CONNECTION_NONBLOCKING")


def clean_env() -> dict:
    """Env cho tiến trình con, bỏ các biến Claude Code gắn vào process cha.
    Nếu widget được mở từ bên trong một session Claude Code, biến như CLAUDE_CODE_CHILD_SESSION=1
    làm session mới tắt ghi transcript và không đăng ký vào ~/.claude/sessions."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(_SCRUB_PREFIXES)}


# ---------------------------------------------------------------- handoff
def claude_command() -> str:
    exe = "claude.exe" if plat.IS_WINDOWS else "claude"
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / exe)


def handoff(sess: dict) -> tuple:
    """Mở terminal mới: claude --resume <id> --fork-session trong cwd của session."""
    sid = sess.get("session_id")
    cwd = sess.get("home_cwd") or sess.get("cwd")
    if not sid or not cwd or not os.path.isdir(cwd):
        return False, "thiếu sessionId hoặc thư mục không tồn tại"
    args = [claude_command(), "--resume", sid, "--fork-session"]
    title = f"handoff: {(sess.get('name') or sid)[:40]}"
    try:
        return plat.open_terminal(cwd, args, title, clean_env())
    except Exception as e:
        return False, f"không mở được terminal: {type(e).__name__}: {e}"
