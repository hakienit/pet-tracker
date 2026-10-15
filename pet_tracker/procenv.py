"""Môi trường cho tiến trình con (deep link, script cập nhật)."""
from __future__ import annotations

import os

_SCRUB_PREFIXES = ("CLAUDE_", "CLAUDECODE", "MCP_SERVER_CONNECTION_BATCH_SIZE", "MCP_CONNECTION_NONBLOCKING")


def clean_env() -> dict:
    """Env cho tiến trình con, bỏ các biến Claude Code gắn vào process cha.
    Nếu widget được mở từ bên trong một session Claude Code, biến như CLAUDE_CODE_CHILD_SESSION=1
    sẽ lọt sang các tiến trình con mà widget mở."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(_SCRUB_PREFIXES)}
