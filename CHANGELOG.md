# Changelog

Mọi thay đổi đáng chú ý của Claude PET (pet-tracker) được ghi ở đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), version theo
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Removed
- Popup thao tác session (nút ⋯ và chuột phải trên card): đổi model, đổi effort, compact, clear, thoát,
  handoff. Click vào session để đưa cửa sổ của nó lên vẫn giữ nguyên. Khoá `keep_default_model` không
  còn dùng.

### Fixed
- Thông báo ở footer (kết quả focus, cập nhật, auto-start…) không còn biến mất khi panel tự vẽ lại.
- Bóng đặt được trên màn hình thứ hai: vị trí được giữ trong vùng dùng được của màn hình chứa bóng
  (trước đây luôn bị kéo về màn hình chính); panel và popup mở trên đúng màn hình đó.
- macOS: chuột phải vào bóng nhận cả `Button-2` (Tk 8.6) và Control-click.
- Gọi API quota chạy ở thread riêng, nên mất mạng không còn làm danh sách session đứng tới 15 giây. Lỗi
  HTTP (429, 401, 5xx) được giãn thời gian thử lại (tối đa 15 phút, tôn trọng `Retry-After`); khi lỗi
  tạm thời, panel giữ số liệu quota gần nhất (tối đa 30 phút) kèm ghi chú lỗi.
- Bóng hiện cửa sổ quota gần giới hạn nhất thay vì luôn là 5 giờ.
- Không còn đọc toàn bộ lịch sử transcript lúc khởi động: chỉ đọc file đổi trong 7 ngày gần nhất và file
  của session đang chạy.
- Card session cập nhật khi đổi effort, git branch, giới hạn context.
- `config.json` sai cú pháp được báo trên panel và trong log thay vì bị bỏ qua.
- Thông tin tài khoản đọc `.claude.json` trong `CLAUDE_CONFIG_DIR` khi biến này được đặt.

### Added
- macOS giai đoạn 1 (thử nghiệm, chưa test trên Mac thật): bóng trong suốt alpha thật, panel, quota
  (token từ Keychain), danh sách session, focus Terminal/iTerm2 theo tty,
  mở khi đăng nhập (LaunchAgent), chỉ chạy một bản. Workflow build thêm `.dmg` universal2.

### Changed
- Tách lớp nền tảng `pet_tracker/platform/` (Windows / macOS); code dùng chung không còn gọi Win32 trực tiếp.

## [0.1.0] - 2026-10-15

### Added
- Bóng nổi always-on-top, kéo thả, nhớ vị trí; vòng quota 5 giờ, số agent, badge session đang chạy,
  chấm cảnh báo context.
- Panel stats: quota tài khoản (5 giờ, 7 ngày) từ endpoint usage của Claude Code, danh sách session
  đang chạy với model, effort, thư mục, git branch, context đã dùng, ước tính usage từ transcript.
- Click session để đưa cửa sổ host lên trước (Windows Terminal, conhost, Claude desktop qua deep link,
  IDE qua process cha).
- Popup thao tác session CLI: đổi model, đổi effort, compact, clear, thoát; handoff sang terminal mới
  (`--resume --fork-session`). Đổi model/effort không làm đổi mặc định của người dùng.
- Panel resize được, cuộn bằng chuột, touchpad hoặc kéo thanh cuộn.
- Chỉ chạy một bản; bật/tắt chạy cùng Windows.
- Kiểm tra bản mới trên GitHub Releases và cập nhật một chạm (tải, kiểm SHA256, thay thư mục, mở lại).
- Script build PyInstaller (onedir, icon, version info, zip portable) và workflow release trên
  GitHub Actions.

[Unreleased]: https://github.com/hakienit/pet-tracker/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hakienit/pet-tracker/releases/tag/v0.1.0
