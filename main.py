"""pet-tracker entry point. Chạy: pythonw main.py  (hoặc pet-tracker.cmd)"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pet_tracker.actions import clean_env  # noqa: E402
from pet_tracker.ui import run  # noqa: E402

# Bỏ biến môi trường Claude Code (nếu widget được mở từ trong một session) để mọi tiến trình con
# (terminal handoff, deep link) chạy như được mở bình thường.
for _k in set(os.environ) - set(clean_env()):
    del os.environ[_k]

if __name__ == "__main__":
    from pet_tracker.single import SingleInstance

    instance = SingleInstance()
    if instance.already:  # đã có bản đang chạy: nhờ nó mở panel rồi thoát
        instance.notify_running()
        sys.exit(0)
    run(instance)
