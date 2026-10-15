"""Lớp nền tảng: mọi chỗ gọi API riêng của Windows / macOS đi qua đây.

Interface chung (win.py và mac.py đều cài đủ):

  Hằng       NAME, IS_WINDOWS, IS_MAC, GLOBAL_MOUSE, CAN_TYPE_INTO_SESSION, TYPE_UNSUPPORTED_REASON,
             CAN_SELF_UPDATE
  Cửa sổ     init_process(), dpi_scale(root), work_area(root), cursor_pos(root), mouse_down(),
             transparent_key(), make_transparent(toplevel), round_corners(win, border_hex)
  Hệ thống   state_dir(), open_path(target), process_alive(pid, proc_start), read_credentials(claude_dir)
  Session    focus_session(sess), type_into_session(pid, text), open_terminal(cwd, args, title, env)
  Khởi động  autostart_command(), autostart_is_enabled(), autostart_enable(), autostart_disable(),
             autostart_refresh(), SingleInstance
  Cập nhật   update_asset_name(version), install_dir(), launch_swap(stage, target, wait_pid, env, log_file)

Chỉ win.py (và các module win_*.py) được import ctypes.windll / winreg.
"""
from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WINDOWS:
    from .win import *  # noqa: F401,F403
    from .win import __all__ as _names
else:  # macOS (Linux dùng tạm cùng nhánh posix, chưa hỗ trợ chính thức)
    from .mac import *  # noqa: F401,F403
    from .mac import __all__ as _names

__all__ = ["IS_WINDOWS", "IS_MAC"] + list(_names)
