# Chạy Wisp (có console để xem log/lỗi). Dùng wisp.cmd nếu muốn chạy ẩn.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python main.py
