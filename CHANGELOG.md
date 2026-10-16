# Changelog

Mọi thay đổi đáng chú ý của Wisp (trước đây là Claude PET / pet-tracker) được ghi ở đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), version theo
[Semantic Versioning](https://semver.org/).

## [Unreleased]

Bản làm lại giao diện 0.2, theo spec ở `docs/site/design.html` và kế hoạch ở `docs/REDESIGN_PLAN.md`.

### Added
- **Biết khi nào session cần bạn**: Wisp nhận sự kiện từ hooks kiểu `http` của Claude Code. Server chỉ nghe trên
  127.0.0.1, có token riêng, và không trả quyết định nào. Session có 4 trạng thái: cần bạn (chờ duyệt / đang hỏi),
  đang chạy (kèm tool và file / lệnh), xong (kèm câu trả lời cuối), rảnh. Không bật hooks thì Wisp suy ra trạng thái
  từ poll như trước.
- Hooks là tuỳ chọn opt-in: lần đầu Wisp hỏi trong panel, sau đó bật / gỡ trong Cài đặt. Wisp chỉ thêm và gỡ đúng
  entry của mình trong `settings.json`, ghi nguyên tử, giữ bản backup `settings.json.wisp-bak`.
- Thông báo thả xuống từ island, kèm âm thanh khi có session cần bạn. Có tuỳ chọn âm thanh khi xong, giờ yên lặng,
  và tắt thông báo cho từng session.
- Quota có dự báo giờ hết theo tốc độ hiện tại, cảnh báo ở 80% / 95% và khi quota đã hồi.
- Khối "Token · máy này": hôm nay / tuần / tháng (input + output + cache), chỉ tính trên máy này.
- Bóng nổi có hai kiểu: tín hiệu (6 kiểu viền) và mascot (40 mẫu, 8 màu hoặc ảnh riêng). Mascot có biểu cảm và
  chuyển động theo trạng thái, chip dưới chân có 3 kiểu. Cả island lẫn bóng đều có viền động theo trạng thái.
- Trang Cài đặt trong panel: ngôn ngữ, giao diện, kiểu hiển thị, bóng nổi, mascot, chuyển động, mở cùng máy, thông
  báo, hooks, ngưỡng quota, cập nhật, nâng cao.
- Hai ngôn ngữ, tiếng Việt và tiếng Anh, mặc định theo hệ điều hành. Theme sáng / tối theo hệ thống.
- Menu ⋯ của session có thêm: mở thư mục dự án, sao chép ID, chi tiết, tắt thông báo. Thao tác không hoàn tác được
  có khối xác nhận liệt kê rõ hậu quả.
- Font Archivo (OFL) đóng gói kèm app, nạp riêng cho process, nên chữ giống nhau trên Windows và macOS.
- 42 unit test (`python -m unittest discover -s tests -t .`), chạy trong CI.

### Changed
- Panel chia làn theo trạng thái (cần bạn, đang chạy, xong, rảnh, đã đóng). Bấm tên làn để thu / mở. Card có nền và
  viền theo trạng thái, effort hiện cạnh model.
- Island rộng cố định theo nội dung, đổi rộng có animation, đèn có nhãn số thay cho chấm không nhãn.
- Cỡ chữ tính bằng pixel, bỏ cách cộng thêm 3pt trên macOS. Icon vẽ bằng vector, giống nhau trên hai hệ điều hành.
- Kết quả thao tác hiện bằng thông báo, không ghi ở footer nữa.
- Kiểm tra bản mới mỗi 24 giờ (`update_interval_hours` mặc định 24). Bóng nổi mặc định 80 px.

### Removed
- Khối "Token đã dùng" 5 giờ / 7 ngày (thay bằng dự báo quota và token theo ngày / tuần / tháng).

## [0.1.7] - 2026-10-16

### Added
- Cài bằng một lệnh: `install.ps1` (Windows, `irm … | iex`) và `install.sh` (macOS, `curl … | bash`).
  Script tải bản mới nhất, kiểm SHA256, cài rồi mở app; chạy lại để cập nhật.

### Changed
- README thành trang giới thiệu ngắn; tài liệu chi tiết chuyển sang `docs/GUIDE.md`.

## [0.1.6] - 2026-10-16

### Fixed
- Cập nhật một chạm không còn thất bại với lỗi "Cannot rename the item ... because it is in use" khi Wisp
  được mở từ Explorer: script cập nhật chạy từ `%TEMP%` thay vì kế thừa thư mục cài làm thư mục làm việc.
  Bản 0.1.1–0.1.5 vẫn mang lỗi này nên cần tải tay bản 0.1.6 một lần.

## [0.1.5] - 2026-10-16

### Added
- Dạng Dynamic Island (mặc định): viên thuốc đen ghim giữa mép trên màn hình, hiện % quota, số agent,
  số session đang chạy và chấm cảnh báo; click để panel nở xuống. Bật/tắt trong menu chuột phải,
  bóng tròn kéo thả kiểu cũ vẫn dùng được.

## [0.1.4] - 2026-10-16

### Added
- Chuột phải vào header của panel mở cùng menu với bóng: Làm mới, Mở thư mục ~/.claude, Kiểm tra
  cập nhật, Chạy cùng Windows, Thoát.
- Link tải cố định bản mới nhất trong README: mỗi release kèm thêm `wisp-win-x64.zip` và
  `wisp-macos-universal2.dmg` (không có version trong tên).

## [0.1.3] - 2026-10-16

### Changed
- Kiểm tra bản mới mỗi giờ thay vì mỗi 24 giờ (`update_interval_hours` mặc định 1): bản vừa publish
  hiện banner trong vòng một giờ, không phải chờ tới hôm sau hoặc mở lại app.
- Workflow release publish release ngay khi push tag, không còn tạo draft.

### Fixed
- Bấm vào session chạy trong Orca đưa được cửa sổ Orca lên (trước đây báo "không tìm thấy cửa sổ host
  session" vì pty host của Orca không còn nối với process có cửa sổ). Chỉ đưa cửa sổ lên, không chọn tab.

## [0.1.1] - 2026-10-15

### Changed
- Đổi tên app thành **Wisp**, logo mới (đốm lửa có mắt trong vòng quota), cũng hiện trên header panel.
  File chạy là `wisp.exe`, gói phát hành `wisp-<version>-win-x64.zip` / `wisp-<version>-macos-universal2.dmg`,
  launcher `wisp.cmd`. State và log chuyển sang `%APPDATA%\Wisp` (macOS: `~/Library/Application Support/Wisp`);
  vị trí bóng, kích thước panel và mục auto-start của bản cũ được chuyển sang tự động.
- Phần token cuối panel chỉ còn tổng token 5 giờ / 7 ngày (không tách input/output/cache).

### Added
- Nút ⋯ và chuột phải trên card session để dọn dẹp:
  - **Handoff rồi đóng**: session tự viết handoff và lưu theo quy định của repo; repo không quy định thì
    vào `%APPDATA%\Wisp\handoffs`. Tốn token một lượt (bản fork chạy ngầm, session gốc không bị đụng).
  - **Đóng session** (giữ transcript), **Xoá session** (đóng + xoá transcript), **Xoá worktree** (chỉ khi
    worktree sạch và branch đã merge/push; worktree của Orca chỉ hiện trạng thái).
  - Handoff lỗi thì không đóng. Mọi thao tác phải bấm hai lần để xác nhận.
- Mục **Đã đóng gần đây** (10 session cuối Wisp đóng): nút **Resume** mở terminal chạy
  `claude --resume <id>` ở đúng thư mục, nút mở file handoff, nút bỏ khỏi danh sách.
- Card session hiện trạng thái git của thư mục: số thay đổi chưa commit, commit chưa push, hoặc "✓ xong".

### Removed
- Popup đổi model, đổi effort, compact, clear, handoff. Click vào session để đưa cửa sổ của nó lên vẫn
  giữ nguyên. Khoá `keep_default_model` không còn dùng.

### Fixed
- Đóng/xoá session không còn lỗi `[WinError 6] The handle is invalid` sau khi bấm vào session để
  focus cửa sổ: tìm cửa sổ console xong, Wisp trả lại std handle của mình.
- Panel không còn chớp và giật khi làm mới: chỉ phần có số liệu đổi được vẽ lại; số liệu của card session
  được sửa tại chỗ. Đồng hồ "reset sau…" của quota chạy đúng.
- Cập nhật một chạm từ chối chạy nếu thư mục cài có file khác ngoài bản build (trước đây nếu `wisp.exe` nằm
  thẳng trong Downloads/Desktop, cập nhật sẽ xoá cả thư mục đó).
- Xoá worktree an toàn hơn: đếm cả file chưa track khi git config ẩn chúng, báo trước file bị .gitignore
  (vd `.env`) sẽ mất, kiểm tra lại session khác đang dùng worktree, branch chưa merge chỉ coi là "đã push"
  khi remote còn đúng commit đó, và chỉ xoá branch local khi đã merge.
- Đóng session tắt cả cây process (Windows) và mọi process đang chạy cùng session; macOS kiểm tra tên process
  trước khi gửi tín hiệu.
- Handoff: fork chỉ có công cụ đọc/ghi file (không Bash, không MCP), prompt đi qua stdin, chỉ nhận file `.md`
  vừa ghi trong repo hoặc thư mục handoff của Wisp.
- Xác nhận bấm hai lần không còn bị một cú double-click vượt qua; click trong panel khi popup đang mở chỉ đóng
  popup.
- Không còn gửi token OAuth theo redirect; deep link Claude desktop kiểm tra id chặt hơn; tên session có `;`
  không làm hỏng Resume (Windows Terminal); `state.json` ghi nguyên tử; giữ `CLAUDE_CONFIG_DIR` và các biến
  cấu hình Claude Code khi chạy `claude` từ Wisp.
- Workflow release: quyền ghi chỉ ở job tạo release, tên tag không còn dán thẳng vào script, action pin
  theo commit SHA, PyInstaller pin `6.22.3`.
- Cập nhật một chạm kiểm chữ ký Ed25519 của `SHA256SUMS.txt` (file `SHA256SUMS.txt.sig`, ký trong CI bằng
  secret `WISP_SIGNING_KEY`); release bị sửa hoặc không có chữ ký thì không cài.
- Không tắt process khi không xác minh được đó là Claude Code (thiếu thời điểm tạo process thì kiểm tên);
  handoff từ chối chạy qua `claude.cmd` (npm) khi tham số có ký tự đặc biệt của cmd.
- Cảnh báo khi bản Claude PET (pet-tracker) cũ vẫn đang chạy song song.
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

[Unreleased]: https://github.com/hakienit/pet-tracker/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/hakienit/pet-tracker/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/hakienit/pet-tracker/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/hakienit/pet-tracker/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/hakienit/pet-tracker/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/hakienit/pet-tracker/compare/v0.1.1...v0.1.3
[0.1.1]: https://github.com/hakienit/pet-tracker/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/hakienit/pet-tracker/releases/tag/v0.1.0
