"""Cấu hình + lưu trạng thái (vị trí bóng) giữa các lần mở."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Wisp"
LEGACY_APP_NAME = "pet-tracker"  # tên cũ (Claude PET): thư mục state cũ, chuyển sang một lần

# Khi chạy từ exe (PyInstaller), config.json đặt cạnh wisp.exe; khi chạy source thì ở gốc dự án.
PROJECT_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
               else Path(__file__).resolve().parent.parent)
if sys.platform == "win32":
    _STATE_BASE = Path(os.environ.get("APPDATA", str(Path.home())))
elif sys.platform == "darwin":
    _STATE_BASE = Path.home() / "Library" / "Application Support"
else:
    _STATE_BASE = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
STATE_DIR = _STATE_BASE / APP_NAME
LEGACY_STATE_DIR = _STATE_BASE / LEGACY_APP_NAME
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
    # 1 giờ: bản vừa publish hiện banner trong ngày; API GitHub không xác thực cho 60 request/giờ
    "update_interval_hours": 1,
    # Ghi đè URL API (chỉ dùng để test); None = https://api.github.com/repos/hakienit/pet-tracker/releases/latest
    "update_api_url": None,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg["context_windows"] = dict(DEFAULTS["context_windows"])
    cfg["config_error"] = None  # lỗi đọc config.json (hiện trên panel); None = ổn hoặc không có file
    if CONFIG_FILE.exists():
        try:
            user = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            if not isinstance(user, dict):
                raise ValueError("nội dung phải là một object JSON {...}")
            for k, v in user.items():
                if k == "context_windows" and isinstance(v, dict):
                    cfg["context_windows"].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            cfg["config_error"] = f"{CONFIG_FILE.name} lỗi, đang dùng mặc định: {e}"[:200]
    return cfg


def _migrate_legacy_state() -> None:
    """Bản cũ (pet-tracker / Claude PET) lưu vị trí bóng, kích thước panel ở thư mục khác: chép sang một lần."""
    old = LEGACY_STATE_DIR / "state.json"
    if STATE_FILE.exists() or not old.exists():
        return
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, STATE_FILE)
    except OSError:
        pass


def load_state() -> dict:
    _migrate_legacy_state()
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")  # ghi rồi đổi tên: tắt máy giữa chừng không làm hỏng state
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except Exception:
        pass
