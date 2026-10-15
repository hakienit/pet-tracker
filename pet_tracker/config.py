"""Cấu hình + lưu trạng thái (vị trí bóng) giữa các lần mở."""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "pet-tracker"
import sys

# Khi chạy từ exe (PyInstaller), config.json đặt cạnh pet-tracker.exe; khi chạy source thì ở gốc dự án.
PROJECT_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
               else Path(__file__).resolve().parent.parent)
if sys.platform == "win32":
    STATE_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
elif sys.platform == "darwin":
    STATE_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    STATE_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / APP_NAME
STATE_FILE = STATE_DIR / "state.json"
CONFIG_FILE = PROJECT_DIR / "config.json"

DEFAULTS = {
    # Thư mục dữ liệu Claude Code (mặc định ~/.claude, tôn trọng CLAUDE_CONFIG_DIR)
    "claude_dir": os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude"),
    # Chu kỳ refresh (giây)
    "refresh_sessions_sec": 3,
    "refresh_quota_sec": 60,
    # Gọi endpoint usage của Claude (dùng OAuth token local của Claude Code). Tắt -> chỉ ước tính local.
    "quota_api_enabled": True,
    # Context window theo model. Khớp theo prefix; "default" dùng khi không khớp.
    # Đo thực tế trên máy này: Opus 5.5 đã chạy tới 464k tokens, Haiku 5.5 tới 351k -> window 1M.
    "context_windows": {
        "default": 1_000_000,
    },
    # Ngưỡng cảnh báo màu (%)
    "warn_percent": 60,
    "danger_percent": 85,
    # Kích thước bóng (px logic, sẽ nhân theo DPI)
    "bubble_size": 64,
    # Kiểm tra bản mới trên GitHub Releases khi mở app và mỗi update_interval_hours giờ
    "update_check": True,
    "update_interval_hours": 24,
    # Ghi đè URL API (chỉ dùng để test); None = https://api.github.com/repos/hakienit/pet-tracker/releases/latest
    "update_api_url": None,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg["context_windows"] = dict(DEFAULTS["context_windows"])
    if CONFIG_FILE.exists():
        try:
            user = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, v in user.items():
                if k == "context_windows" and isinstance(v, dict):
                    cfg["context_windows"].update(v)
                else:
                    cfg[k] = v
        except Exception:
            pass
    return cfg


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    except Exception:
        pass
