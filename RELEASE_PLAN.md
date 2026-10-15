# Release plan: Wisp (repo pet-tracker) cho macOS và Windows

Trạng thái: **chỉ là kế hoạch**. Chưa ký, chưa publish, chưa tạo tài khoản hay mua chứng chỉ nào.
Viết ngày 2026-10-15, dựa trên code hiện tại (v0.1.0, Python + tkinter, chỉ chạy trên Windows).

## 1. Tóm tắt

- Stack giữ nguyên: Python + tkinter (stdlib), đóng gói bằng **PyInstaller**. Không có dependency
  ngoài stdlib, nên build tương đối đơn giản.
- **Bản Windows gần như sẵn sàng.** Còn thiếu installer, ký số, versioning và CI.
- **Bản macOS chưa chạy được.** Khoảng một nửa tính năng gọi thẳng Win32 API (focus cửa sổ, gõ
  lệnh vào session, DPI, bo góc, phát hiện click ra ngoài, đọc token quota). Cần một đợt port
  trước khi nói tới release.
- Build trên GitHub Actions với runner `windows-latest` và `macos-14`. PyInstaller không
  cross-compile, nên không build được bản macOS từ máy Windows hiện tại.
- Việc phải làm trước tiên: `D:\vinova\pet-tracker` **chưa phải git repo**. Cần tạo repo (GitHub,
  private hoặc public) trước khi có CI và GitHub Releases.

## 2. Định dạng phân phối

### Windows

| Lựa chọn | Ưu | Nhược | Đề xuất |
|---|---|---|---|
| PyInstaller `--onedir` + installer **Inno Setup** (`.exe`, cài per-user vào `%LOCALAPPDATA%\Programs`) | không cần quyền admin; có shortcut Start Menu, tuỳ chọn "chạy cùng Windows", uninstaller | phải duy trì script `.iss` | **Chọn làm bản chính** |
| `.msi` (WiX) | hợp với triển khai qua Intune/GPO | WiX phức tạp hơn nhiều; per-user MSI khá rắc rối | chỉ làm nếu IT Vinova yêu cầu triển khai tập trung |
| Portable `.zip` (thư mục onedir) | không cần cài | không có auto-start, không có shortcut | phát hành kèm, cho người không muốn cài |
| PyInstaller `--onefile` | một file duy nhất | khởi động chậm (giải nén vào temp mỗi lần); hay bị antivirus báo nhầm | **không dùng** cho bản release |

Kiến trúc: chỉ x64. Bản x64 chạy được trên Windows ARM qua giả lập. Bản ARM64 native để sau, vì
GitHub runner ARM64 cho Windows và Python ARM64 vẫn cần thử.

### macOS

| Lựa chọn | Ghi chú | Đề xuất |
|---|---|---|
| `.app` đóng trong **`.dmg`** (kéo thả vào Applications) | cách quen thuộc nhất; dmg cũng ký và notarize được | **Chọn** |
| **universal2** (arm64 + x86_64 trong một app) | được, vì app chỉ dùng stdlib và Python từ python.org có bản universal2. PyInstaller hỗ trợ `--target-arch universal2` | **Chọn**. Một file cho mọi Mac |
| Tách arm64 / x64 | file nhỏ hơn, nhưng gấp đôi số build và dễ tải nhầm | chỉ dùng nếu universal2 gặp lỗi |
| `.pkg` | cần khi cài LaunchAgent hệ thống | không cần, auto-start làm trong app |

Info.plist cần `LSUIElement = true` để app không hiện icon trên Dock (widget nổi), cùng bundle id,
ví dụ `sg.vinova.wisp`.

## 3. Ký số và notarization

### macOS: Apple Developer ID + notarytool

- Cần tài khoản **Apple Developer Program**, khoảng 99 USD/năm. Nên đăng ký dưới tên tổ chức
  Vinova, việc này cần số D-U-N-S. Hoặc đăng ký cá nhân.
- Chứng chỉ **Developer ID Application** để ký `.app` và `.dmg`.
- Quy trình: ký từng binary trong bundle với hardened runtime
  (`codesign --options runtime --timestamp`), rồi ký `.app`, tạo `.dmg`, ký `.dmg`. Sau đó chạy
  `xcrun notarytool submit --wait`, rồi `xcrun stapler staple` vào `.dmg`.
- Python đóng gói có thể cần entitlement như `com.apple.security.cs.allow-unsigned-executable-memory`.
  Phải thử thực tế, chỉ thêm khi notarization hoặc runtime báo lỗi.
- CI cần các secret sau: chứng chỉ `.p12` dạng base64 cùng mật khẩu, và App Store Connect API key
  cho notarytool (key id, issuer id, file `.p8`).
- **Nếu không ký và notarize:** Gatekeeper chặn app tải từ internet ("cannot be opened" hoặc "is
  damaged"). Từ macOS 15 không còn mở được bằng chuột phải → Open. Người dùng phải vào System
  Settings → Privacy & Security → "Open Anyway", hoặc tự chạy `xattr -dr com.apple.quarantine`.
  Chỉ chấp nhận được nếu chỉ vài người nội bộ dùng.

### Windows: chứng chỉ ký code

| Lựa chọn | Chi phí (ước tính, cần báo giá) | Ghi chú |
|---|---|---|
| **Azure Artifact Signing** (tên cũ Trusted Signing) | khoảng 10 USD/tháng | rẻ nhất, ký từ CI dễ, không phải giữ token phần cứng. **Cần xác minh** Vinova (pháp nhân Singapore) có đủ điều kiện xác minh danh tính không, vì dịch vụ giới hạn theo quốc gia và loại tổ chức |
| Chứng chỉ **OV** (Sectigo, DigiCert…) | khoảng 200–500 USD/năm | từ 2023 khoá bắt buộc nằm trên HSM hoặc token. Muốn ký từ CI thì cần HSM trên cloud của nhà cung cấp hoặc chạy runner tự host |
| Chứng chỉ **EV** | khoảng 300–700 USD/năm | từ 2024 không còn được SmartScreen tin ngay, nên không đáng giá chênh cho app này |

- **Nếu không ký:** SmartScreen hiện "Windows protected your PC", người dùng phải bấm "More info"
  → "Run anyway". Antivirus dễ báo nhầm file PyInstaller hơn. Một số máy công ty chặn hẳn file
  chưa ký. Kể cả khi đã ký, SmartScreen vẫn cần thời gian tích luỹ reputation cho chứng chỉ mới.
- Ký cả `wisp.exe` lẫn installer, có timestamp (`signtool sign /tr … /td sha256 /fd sha256`).

## 4. Việc phải làm trước khi release (khác biệt nền tảng)

> **Cập nhật 2026-10-15 (giai đoạn 1 macOS đã code, chưa test trên Mac thật):** code đã tách lớp nền
> tảng `pet_tracker/platform/` (`win.py` + các `win_*.py`, `mac.py`); bóng macOS dùng PNG alpha thật;
> quota đọc Keychain; focus Terminal/iTerm2 theo tty; LaunchAgent; single instance bằng file lock.
> Cập nhật một chạm vẫn chỉ có trên Windows. (Popup thao tác session — gõ lệnh, handoff — đã bỏ khỏi app
> trên cả hai nền tảng.) Workflow có
> job `macos-14` build `.dmg` universal2 (ad-hoc sign, chưa notarize). Danh sách việc cần test trên Mac
> nằm trong README, mục macOS.

Bảng dưới liệt kê từng chỗ code đang phụ thuộc Windows, đếm theo số lần gọi Win32 API trong mỗi
module.

| Tính năng | Windows (hiện tại) | macOS (cần làm) | Mức độ |
|---|---|---|---|
| Bóng trong suốt | `-transparentcolor` với color key | Tk trên macOS không có `-transparentcolor`. Dùng `wm_attributes("-transparent", True)` và nền `systemTransparent`. Phải thử viền khử răng cưa vì macOS hỗ trợ alpha thật | trung bình |
| Always-on-top, không viền | `-topmost`, `overrideredirect` | `-topmost` có tác dụng, nhưng `overrideredirect` trên macOS có thể làm cửa sổ không nhận focus bàn phím, và không nổi trên app full-screen hay qua các Space. Có thể cần `NSWindow.collectionBehavior` qua PyObjC | trung bình–cao |
| DPI | `SetProcessDpiAwareness`, `GetDpiForSystem` | macOS tự scale theo point. Bỏ hệ số `S` hoặc lấy từ `tk scaling` | thấp |
| Bo góc panel | DWM attribute (chỉ Windows 11) | vẽ bo góc bằng canvas, hoặc chấp nhận góc vuông | thấp |
| Click ra ngoài để đóng panel | `GetAsyncKeyState` toàn cục | không bắt được click toàn cục nếu thiếu quyền. Đổi sang sự kiện `<FocusOut>` của panel | thấp |
| Vùng màn hình, vị trí chuột | `SystemParametersInfo`, `GetCursorPos` | `winfo_vrootwidth`/`height`, `winfo_pointerxy`; trừ menu bar và Dock qua NSScreen.visibleFrame (PyObjC) hoặc trừ một khoảng cố định | thấp |
| Kiểm tra process còn sống | `OpenProcess`, `GetProcessTimes` | đã có nhánh `os.kill(pid, 0)`. So `procStart` cần định dạng khác (cần xem Claude Code ghi gì trên macOS) | thấp |
| **Đọc token để lấy quota** | `~/.claude/.credentials.json` | trên macOS, Claude Code lưu OAuth token trong **Keychain**, nhiều khả năng không có file này. Cần đọc qua `security find-generic-password -s "<tên service>" -w`; tên service phải kiểm trên một máy Mac thật. Lần đầu macOS sẽ hỏi quyền truy cập Keychain | **cao**, quota là tính năng chính |
| Đường dẫn dữ liệu | `~/.claude`, `~/.claude.json`, `%APPDATA%\Wisp` | `~/.claude` giống hệt. State và log chuyển sang `~/Library/Application Support/Wisp` | thấp |
| **Focus cửa sổ session** | `AttachConsole` → cửa sổ Windows Terminal; đi ngược process cha; deep link `claude://` | pid → tty (`ps -o tty= -p <pid>`) → AppleScript chọn đúng tab theo tty trong Terminal.app hoặc iTerm2 (cần quyền **Automation** cho từng app). VS Code, Cursor: activate app qua `NSRunningApplication` (không cần quyền). Raise đúng cửa sổ cụ thể cần quyền **Accessibility**. Deep link `claude://code/continue?session=…` cho Claude desktop có lẽ dùng chung, cần thử | **cao** |
| **Gõ lệnh vào session** (`/model`, `/effort`, `/clear`, `/exit`) | `WriteConsoleInputW` vào console | macOS không có tương đương sạch. Hướng khả thi: AppleScript `write text` trong iTerm2, hoặc `do script … in tab` của Terminal.app (cần quyền Automation). `TIOCSTI` không dùng được ổn định. Có thể **bỏ tính năng này ở bản macOS đầu tiên** | **cao**, đề xuất hoãn |
| Handoff | `wt.exe -w new … claude --resume <id> --fork-session` | `osascript` mở cửa sổ Terminal hoặc iTerm2 mới chạy cùng lệnh | thấp |
| Mở thư mục, link | `os.startfile` | `subprocess.run(["open", …])` | thấp |
| Auto-start | shortcut trong `shell:startup`, hoặc installer ghi `HKCU\…\Run` | LaunchAgent `~/Library/LaunchAgents/sg.vinova.wisp.plist`, hoặc `SMAppService` (macOS 13+, cần app đã ký) | thấp |
| Font | Segoe UI Variable, Segoe Fluent Icons | SF Pro (`.AppleSystemUIFont`). Icon đổi sang ký tự Unicode hoặc ảnh nhỏ, vì không có Fluent Icons | thấp |

Cách tổ chức code đề xuất: tách module `platform/` gồm `win.py` và `mac.py`, cùng một interface
(`work_area`, `cursor_pos`, `focus_session`, `send_slash`, `read_oauth_token`, `autostart_enable`…).
`ui.py` chỉ gọi interface đó. Trên macOS, tính năng nào chưa làm thì menu hiện mờ, giống cách
"(chỉ CLI)" đang làm.

Lưu ý: hành vi của Claude Code trên macOS (vị trí credential, `procStart`, `entrypoint`) **phải
khảo sát trên một máy Mac thật trước khi code**, như đã làm với Windows. Hiện chưa có máy Mac
trong quy trình.

## 5. Build pipeline

- **Repo:** đã có, public: https://github.com/hakienit/pet-tracker (đã làm 2026-10-15).
- **Python cho build:** máy dev đang dùng Python 3.15. Để build ổn định nên ghim **Python 3.13**
  trong CI, vì PyInstaller thường cần thời gian để hỗ trợ bản Python mới nhất. Trên macOS dùng
  bản python.org universal2 (có sẵn Tk), không dùng Homebrew Python.
- **GitHub Actions:** phần Windows đã có ở `.github/workflows/release.yml` (đã làm 2026-10-15):
  push tag `v*` → `windows-latest`, Python 3.13 → kiểm tra tag khớp `__version__` và CHANGELOG →
  `build.ps1` → `SHA256SUMS.txt` → GitHub Release (publish ngay, từ 0.1.3; trước đó là draft). Chưa ký số, chưa có Inno Setup.
  Kế hoạch đầy đủ khi có chứng chỉ và bản macOS:
  1. `windows-latest`: cài Python 3.13 và PyInstaller (ghim version) → build `--onedir --noconsole`
     → ký exe → Inno Setup tạo installer → ký installer → zip bản portable.
  2. `macos-14` (Apple Silicon): cài Python universal2 → PyInstaller `--windowed --target-arch universal2`
     → codesign → tạo dmg → notarytool → staple.
  3. Job `release`: tạo và publish GitHub Release, đính kèm artifact và `SHA256SUMS.txt`.
     Người duyệt publish bằng tay.
- PR và push thường chỉ chạy build không ký, cộng một smoke test: import module, render bubble
  ra PNG, parse transcript mẫu.
- **Versioning:** SemVer. Nguồn duy nhất là `pet_tracker/__init__.py` (`__version__`). Tag `vX.Y.Z`
  phải khớp với giá trị này, CI kiểm tra. Version cũng ghi vào resource Windows (file version) và
  `CFBundleShortVersionString` của macOS.
- **Changelog:** đã có `CHANGELOG.md` (Keep a Changelog); `tools/changelog_section.py` trích mục của
  version làm release notes (đã làm 2026-10-15).
- **`build.ps1`:** đã chuyển sang `--onedir`, có icon và version info (đã làm 2026-10-15). Bản macOS
  sẽ cần thêm `.spec` cho Info.plist.
- **Icon app:** đã có `assets/wisp.ico` (tạo bằng `tools/make_icon.py`). macOS cần thêm `.icns` từ cùng hình.

## 6. Auto-update và kênh phân phối

### Kênh phân phối

| Kênh | Ưu | Nhược |
|---|---|---|
| **GitHub Releases của repo private** | gắn liền CI, có lịch sử version | người tải phải có quyền truy cập repo trên GitHub |
| GitHub Releases của repo public | ai cũng tải được, dùng được API cho update check không cần token | lộ mã nguồn, tức là lộ cách đọc token và gọi endpoint usage không chính thức |
| Thư mục nội bộ (Google Drive hoặc SharePoint của Vinova) | đơn giản cho người không có GitHub | không có API để kiểm tra bản mới, phải cập nhật bằng tay |

### Auto-update

- **Đã làm (2026-10-15, bản Windows):** cả thông báo lẫn cập nhật một chạm, dùng GitHub Releases
  của repo public `hakienit/pet-tracker`. Kiểm tra khi mở app và mỗi 24 giờ; tải zip, kiểm SHA256 với
  `SHA256SUMS.txt`, script PowerShell thay thư mục cài (có khôi phục khi lỗi), mở lại app. Đã test
  bằng release giả lập cục bộ, chưa test với exe build thật và release thật. Chi tiết trong README.
- **Giai đoạn 1 (kế hoạch ban đầu):** chỉ thông báo, không tự cài. Khi khởi động và mỗi 24 giờ, widget gọi
  GitHub Releases API (`/repos/<org>/pet-tracker/releases/latest`) và so với `__version__`. Có bản
  mới thì hiện chấm trên bóng và dòng "Có bản mới x.y.z" trong panel, bấm vào mở trang release.
  Repo private thì cần token, nên với repo private hãy bỏ qua tính năng này hoặc dùng một file
  `latest.json` đặt ở chỗ công khai.
- **Giai đoạn 2 (nếu cần):** tự tải và cài. Windows: tải installer đã ký rồi chạy `/SILENT`.
  macOS: dùng Sparkle (cần nhúng framework và ký EdDSA cho appcast), khá nặng với app Python.
  Chỉ đáng làm khi số người dùng lớn.

## 7. Checklist test trước khi release

### Chung (cả hai OS)

- [ ] Bóng hiện, kéo được, nhớ vị trí; vị trí vẫn đúng khi đổi màn hình hoặc độ phân giải (chạy hai màn hình).
- [ ] Panel mở và đóng (click bóng, click ra ngoài, nút ✕); resize và nhớ kích thước; cuộn khi nhiều session.
- [ ] Danh sách session khớp với các session thật: CLI, Claude desktop, IDE nếu có. Session đã thoát biến mất trong vài giây.
- [ ] Context, model, effort đúng với session (so với `/status` trong session).
- [ ] Quota 5 giờ và 7 ngày khớp `/usage`. Hiện đúng thông báo khi token hết hạn, khi mất mạng, khi đặt `quota_api_enabled=false`.
- [ ] Focus cửa sổ cho từng loại host.
- [ ] Không có dữ liệu nhạy cảm (token) trong log và state.
- [ ] CPU khi rảnh dưới 1% và RAM dưới 80 MB sau 8 giờ chạy (đã đo trên Windows: khoảng 48 MB lúc mới mở).

### Windows

- [ ] Cài, gỡ, cài đè bản mới bằng installer trên Windows 11 và Windows 10. Trên Windows 10 không có bo góc, phải hiện viền 1px.
- [ ] Không còn cảnh báo SmartScreen ở bản đã ký. Chữ ký hợp lệ (`signtool verify /pa`).
- [ ] Defender và antivirus của công ty không báo nhầm.
- [ ] DPI 100%, 125%, 150%, 200%.
- [ ] Tuỳ chọn chạy cùng Windows hoạt động. Chạy hai lần không mở hai widget (đã có khoá single-instance và nút bật/tắt auto-start; đã test từ source, cần test lại trên exe).
- [ ] Windows Terminal, conhost, VS Code terminal.

### macOS

- [ ] `.dmg` tải từ internet mở được không cảnh báo (`spctl -a -vvv`, `stapler validate`).
- [ ] Chạy được trên Apple Silicon và Intel từ cùng bản universal2. Thử macOS 13, 14, 15.
- [ ] Có hộp thoại hỏi quyền Keychain, Automation, Accessibility kèm hướng dẫn rõ. Từ chối quyền thì app không crash, tính năng tương ứng hiện mờ.
- [ ] Bóng nổi trên app full-screen và qua các Space; không hiện icon Dock.
- [ ] Màn hình Retina và màn hình ngoài không Retina.
- [ ] Terminal.app, iTerm2, VS Code.

## 8. Ước lượng công việc (thô)

| Hạng mục | Ước lượng |
|---|---|
| Tạo repo, CI build Windows không ký, Inno Setup, versioning, changelog | 1–2 ngày |
| Ký Windows (sau khi có chứng chỉ), đưa vào CI | 0,5–1 ngày |
| Khảo sát Claude Code trên Mac thật, tách lớp platform, port UI cơ bản (bóng, panel, quota, danh sách session) | 3–5 ngày |
| Focus cửa sổ trên macOS (Terminal, iTerm2, VS Code, Claude desktop) | 2–3 ngày |
| Ký và notarize macOS trong CI | 1 ngày |
| Update check giai đoạn 1 | 0,5 ngày |
| Test theo checklist trên cả hai OS | 1–2 ngày |

## 9. Quyết định cần người dùng chốt

1. **Phạm vi người dùng:** chỉ nội bộ Vinova hay phát hành rộng hơn? Câu trả lời quyết định có cần
   ký số ngay ở bản đầu hay không.
2. **Ngân sách ký số Windows:** Azure Artifact Signing (khoảng 10 USD/tháng, cần xác minh điều kiện
   cho pháp nhân Singapore), chứng chỉ OV (khoảng 200–500 USD/năm cộng HSM hoặc token), hay tạm
   chưa ký và chấp nhận cảnh báo SmartScreen.
3. **Apple Developer Program:** đăng ký tên tổ chức Vinova (cần D-U-N-S, mất vài ngày đến vài tuần)
   hay tài khoản cá nhân. Ai giữ chứng chỉ và API key notarization.
4. **Kênh phân phối:** đang dùng GitHub Releases của repo public `hakienit/pet-tracker`.
5. **Repo:** tạo dưới GitHub org nào, private hay public. Nếu public, có chấp nhận công khai phần
   gọi endpoint usage không chính thức không.
6. **Phạm vi bản macOS đầu tiên:** có chấp nhận bỏ tính năng gõ lệnh vào session (đổi model,
   effort, clear, exit) và chỉ giữ focus cùng handoff không.
7. **Auto-update:** đã làm cập nhật một chạm cho Windows (vẫn do người dùng bấm, không tự cài ngầm).
8. **Thời điểm:** release Windows trước (gần sẵn sàng) rồi macOS sau, hay chờ ra cả hai cùng lúc.
9. **Máy Mac để khảo sát và test:** có máy Mac nào (Apple Silicon và Intel) dùng được cho bước
   khảo sát Claude Code trên macOS không.
