"""Hooks của Claude Code: server nhận sự kiện trên 127.0.0.1 và cài / gỡ hook trong settings.json.

Claude Code gửi JSON sự kiện qua hook kiểu "http" (POST) tới http://127.0.0.1:<port>/wisp/<token>. Wisp tắt thì
Claude Code bỏ qua lỗi kết nối và chạy tiếp. Server chỉ ghi nhận sự kiện để đổi hiển thị: không chạy lệnh, không
trả quyết định (body rỗng), nên không ảnh hưởng tới việc duyệt quyền.

Cài đặt chỉ thêm / gỡ đúng các entry có URL chứa MARKER; mọi key và hook khác trong settings.json giữ nguyên.
"""
from __future__ import annotations

import http.server
import json
import os
import queue
import secrets
import threading
from pathlib import Path

MARKER = "/wisp/"
DEFAULT_PORT = 47615
MAX_BODY = 256 * 1024
TIMEOUT_SEC = 3
# SessionStart / SessionEnd không đăng ký: khi Wisp tắt, lỗi kết nối của chúng hiện ra lúc mở / thoát session.
EVENTS = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Notification", "Stop",
          "StopFailure")


class HookConfigError(Exception):
    """settings.json không đọc / ghi được: không động vào file."""


def new_token() -> str:
    return secrets.token_urlsafe(18)


def hook_url(port: int, token: str) -> str:
    return f"http://127.0.0.1:{int(port)}{MARKER}{token}"


# ---------------------------------------------------------------- settings.json (hàm thuần trên dict)
def _is_ours(h) -> bool:
    return isinstance(h, dict) and h.get("type") == "http" and MARKER in str(h.get("url") or "")


def remove_hooks(data: dict) -> dict:
    """Bản sao của data đã bỏ mọi hook của Wisp. Nhóm matcher hoặc event rỗng do việc bỏ này thì xoá luôn."""
    data = json.loads(json.dumps(data))
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data
    for ev in list(hooks):
        groups = hooks[ev]
        if not isinstance(groups, list):
            continue
        kept = []
        for g in groups:
            if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                inner = [h for h in g["hooks"] if not _is_ours(h)]
                if not inner and len(inner) != len(g["hooks"]):
                    continue  # nhóm chỉ có hook của Wisp
                g = dict(g, hooks=inner)
            kept.append(g)
        if kept:
            hooks[ev] = kept
        else:
            del hooks[ev]
    if not hooks:
        del data["hooks"]
    return data


def add_hooks(data: dict, url: str) -> dict:
    """Bản sao của data có đúng một hook Wisp (url) cho mỗi event trong EVENTS. Gọi nhiều lần vẫn vậy."""
    data = remove_hooks(data)
    if "hooks" in data and not isinstance(data["hooks"], dict):
        raise HookConfigError('"hooks" trong settings.json không phải object')
    hooks = data.setdefault("hooks", {})
    for ev in EVENTS:
        groups = hooks.setdefault(ev, [])
        if not isinstance(groups, list):
            raise HookConfigError(f'"hooks.{ev}" trong settings.json không phải danh sách')
        groups.append({"hooks": [{"type": "http", "url": url, "timeout": TIMEOUT_SEC}]})
    return data


def hook_status(data: dict, url: str) -> str:
    """"on": đủ hook trỏ đúng url. "stale": có hook Wisp nhưng sai url / thiếu event. "off": không có."""
    found = {}
    for ev, groups in (data.get("hooks") or {}).items() if isinstance(data.get("hooks"), dict) else []:
        for g in groups if isinstance(groups, list) else []:
            for h in (g.get("hooks") if isinstance(g, dict) else None) or []:
                if _is_ours(h):
                    found.setdefault(ev, set()).add(h.get("url"))
    if not found:
        return "off"
    ok = all(found.get(ev) == {url} for ev in EVENTS) and set(found) <= set(EVENTS)
    return "on" if ok else "stale"


# ---------------------------------------------------------------- settings.json (file)
def settings_path(claude_dir: str) -> Path:
    return Path(claude_dir) / "settings.json"


def read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig") or "{}")
    except (OSError, ValueError) as e:
        raise HookConfigError(f"không đọc được {path.name}: {e}") from e
    if not isinstance(data, dict):
        raise HookConfigError(f"{path.name} không phải object JSON")
    return data


def write_settings(path: Path, data: dict) -> None:
    """Ghi nguyên tử. Lần đầu Wisp ghi thì chép bản gốc sang settings.json.wisp-bak (không ghi đè bản backup)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        bak = path.with_name(path.name + ".wisp-bak")
        if path.exists() and not bak.exists():
            bak.write_bytes(path.read_bytes())
        tmp = path.with_name(path.name + ".wisp-tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        raise HookConfigError(f"không ghi được {path.name}: {e}") from e


def install(claude_dir: str, url: str) -> None:
    p = settings_path(claude_dir)
    write_settings(p, add_hooks(read_settings(p), url))


def uninstall(claude_dir: str) -> None:
    p = settings_path(claude_dir)
    data = read_settings(p)
    if hook_status(data, "") != "off":
        write_settings(p, remove_hooks(data))


def status(claude_dir: str, url: str) -> str:
    try:
        return hook_status(read_settings(settings_path(claude_dir)), url)
    except HookConfigError:
        return "error"


# ---------------------------------------------------------------- server
class HookServer:
    """HTTP server trên 127.0.0.1 ở thread riêng. Sự kiện hợp lệ vào self.events (queue)."""

    def __init__(self, port: int, token: str):
        self.port, self.token = int(port), token
        self.events: queue.Queue = queue.Queue(maxsize=2000)
        self.error = None
        self._srv = None

    def start(self) -> bool:
        path = MARKER + self.token
        events = self.events

        class Handler(http.server.BaseHTTPRequestHandler):
            def _reply(self, code: int):
                self.send_response(code)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):  # noqa: N802
                if self.path != path:
                    return self._reply(404)
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    return self._reply(400)
                if n <= 0 or n > MAX_BODY:
                    return self._reply(413 if n > MAX_BODY else 400)
                try:
                    ev = json.loads(self.rfile.read(n).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    return self._reply(400)
                if isinstance(ev, dict):
                    try:
                        events.put_nowait(ev)
                    except queue.Full:  # UI đứng lâu: bỏ sự kiện cũ còn hơn làm chậm Claude Code
                        pass
                self._reply(200)

            def do_GET(self):  # noqa: N802  (Cài đặt → Hooks → Kiểm tra)
                self._reply(200 if self.path == path + "/ping" else 404)

            def log_message(self, *a):
                pass

        try:
            self._srv = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError as e:
            self.error = f"cổng {self.port} đang bận ({e.strerror or e})"
            return False
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, daemon=True, name="hooks").start()
        return True

    def stop(self) -> None:
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None
