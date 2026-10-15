# Chạy pet-tracker (có console để xem log/lỗi). Dùng pet-tracker.cmd nếu muốn chạy ẩn.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python main.py
