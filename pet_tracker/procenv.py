"""Môi trường cho tiến trình con (deep link, script cập nhật)."""
from __future__ import annotations

import os

_SCRUB_PREFIXES = ("CLAUDE_", "CLAUDECODE", "MCP_SERVER_CONNECTION_BATCH_SIZE", "MCP_CONNECTION_NONBLOCKING")


# cấu hình của người dùng (không phải dấu vết của session cha): giữ lại cho claude chạy từ Wisp
_KEEP = {"CLAUDE_CONFIG_DIR", "CLAUDE_CODE_GIT_BASH_PATH", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
         "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_MAX_OUTPUT_TOKENS"}


def clean_env() -> dict:
    """Env cho tiến trình con, bỏ các biến Claude Code gắn vào process cha.
    Nếu widget được mở từ bên trong một session Claude Code, biến như CLAUDE_CODE_CHILD_SESSION=1
    sẽ lọt sang các tiến trình con mà widget mở."""
    return {k: v for k, v in os.environ.items() if k.upper() in _KEEP or not k.upper().startswith(_SCRUB_PREFIXES)}
