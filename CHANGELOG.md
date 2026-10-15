# Changelog

Mọi thay đổi đáng chú ý của Claude PET (pet-tracker) được ghi ở đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), version theo
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- macOS giai đoạn 1 (thử nghiệm, chưa test trên Mac thật): bóng trong suốt alpha thật, panel, quota
  (token từ Keychain), danh sách session, focus Terminal/iTerm2 theo tty, handoff qua Terminal.app,
  mở khi đăng nhập (LaunchAgent), chỉ chạy một bản. Workflow build thêm `.dmg` universal2.

### Changed
- Tách lớp nền tảng `pet_tracker/platform/` (Windows / macOS); code dùng chung không còn gọi Win32 trực tiếp.
- Popup session trong Claude desktop không còn hiện chip model/effort mờ không bấm được: hiện model/effort
  hiện tại, giải thích vì sao không đổi được từ ngoài, và nút "Mở trong Claude app".

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
