"""Bật/tắt chạy cùng Windows qua HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run (không cần admin)."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ClaudePET"


def launch_command() -> str:
    """Lệnh khởi động: exe khi đã build (PyInstaller), hoặc pythonw main.py khi chạy từ source."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    interp = pyw if pyw.exists() else exe
    main = Path(__file__).resolve().parents[2] / "main.py"
    return f'"{interp}" "{main}"'


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, value_name)
            return True
    except OSError:
        return False


def current_command(value_name: str = VALUE_NAME):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            return winreg.QueryValueEx(k, value_name)[0]
    except OSError:
        return None


def enable(value_name: str = VALUE_NAME) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, value_name, 0, winreg.REG_SZ, launch_command())


def disable(value_name: str = VALUE_NAME) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, value_name)
    except FileNotFoundError:
        pass


def refresh_if_enabled(value_name: str = VALUE_NAME) -> None:
    """Nếu đã bật nhưng đường dẫn cũ (vd. chuyển từ source sang exe, hoặc dời thư mục) thì cập nhật."""
    cur = current_command(value_name)
    if cur is not None and cur != launch_command():
        enable(value_name)


if __name__ == "__main__":
    print(launch_command(), is_enabled())
