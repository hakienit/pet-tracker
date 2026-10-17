# Wisp: hướng dẫn đầy đủ

Trang giới thiệu và lệnh cài nhanh ở [README](../README.md). Trang này dành cho người muốn hiểu sâu: thao
tác, cấu hình, macOS, nguồn dữ liệu, cách focus cửa sổ, build và release.

## Chạy

Yêu cầu: Python 3.10+ (máy này có 3.15) kèm tkinter (bản cài chuẩn python.org có sẵn). Không
cần cài thêm package nào.

```bash
D:\vinova\pet-tracker\wisp.cmd
```

`wisp.cmd` chạy ẩn bằng `pythonw`. Thêm thư mục `D:\vinova\pet-tracker` vào PATH để gõ
`wisp` ở bất kỳ đâu. Muốn xem log trực tiếp trong console thì chạy `.\run.ps1`.

Thao tác:

| Thao tác | Kết quả |
|---|---|
| Click trái vào island / bóng | mở / đóng panel |
| Click ra ngoài panel | đóng panel |
| Kéo bóng (kiểu bóng nổi) | di chuyển, vị trí lưu ở `state.json`. Bóng được giữ trong vùng dùng được của màn hình đang chứa nó; nếu màn hình đó đã rút ra, lần mở sau bóng về màn hình gần nhất. Island ghim giữa mép trên, không kéo được |
| Click phải vào island, bóng hoặc header của panel (macOS: cả Control-click) | menu: Làm mới ngay, Cài đặt, Chuyển sang bóng nổi / island, Tắt âm thanh 1 giờ, Kiểm tra cập nhật, Thoát Wisp |
| Click vào một session trong panel | đưa cửa sổ đang host session đó lên foreground (xem mục "Focus cửa sổ session") |
| Nút ⋯ hoặc click phải vào một session | menu của session: mở, mở thư mục dự án, sao chép ID, chi tiết, tắt thông báo, bàn giao / đóng / xoá (thao tác không hoàn tác được có khối xác nhận) |
| Bấm tên làn (cần bạn, đang chạy, xong, rảnh, đã đóng) | thu / mở làn |
| Kéo tay nắm ở góc panel | đổi rộng và cao panel; kích thước lưu trong `state.json`, nhấp đúp tay nắm để về mặc định. Khi nội dung dài hơn, cuộn bằng con lăn chuột hoặc kéo thanh cuộn mảnh bên phải |

Chỉ chạy một bản: mở Wisp lần nữa khi nó đang chạy sẽ không tạo bóng thứ hai, mà bản đang
chạy mở panel lên (dùng named mutex và event của Windows, theo từng user).

Tự khởi động cùng Windows: Cài đặt → "Mở cùng máy" để bật hoặc tắt. Widget ghi giá trị
`Wisp` vào `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (không cần quyền admin; mục tên cũ
`ClaudePET` của bản trước tự được đổi sang `Wisp`). Khi
chạy từ source, lệnh là `pythonw main.py`. Khi chạy từ exe, lệnh là đường dẫn exe. Nếu bạn dời thư mục
hoặc chuyển từ source sang exe, lần khởi động kế tiếp sẽ tự cập nhật đường dẫn.

## Build thành .exe (dùng nội bộ)

```bash
pwsh -File D:\vinova\pet-tracker\build.ps1
```

Script cài PyInstaller, build dạng thư mục, không console, có icon và version info, rồi tạo:

| File | Dùng để |
|---|---|
| `dist\wisp\wisp.exe` | chạy trực tiếp |
| `dist\wisp-<version>-win-x64.zip` | gửi cho đồng nghiệp: giải nén ra một thư mục cố định rồi chạy `wisp.exe` |

- Nếu PyInstaller chưa hỗ trợ bản Python trên máy (máy này đang dùng 3.15), cài Python 3.13 rồi chạy
  `pwsh -File build.ps1 -Python "C:\...\Python313\python.exe"`.
- Bản không ký số: lần đầu chạy, Windows SmartScreen sẽ cảnh báo, bấm "More info" → "Run anyway".
- `config.json` (nếu cần) đặt cạnh `wisp.exe`.
- Mỗi máy cần đã cài và đăng nhập Claude Code; widget đọc dữ liệu từ `~/.claude` của máy đó.
- Icon nằm ở `assets/`, tạo lại bằng `python tools/make_icon.py`.

## Cài cho đồng nghiệp (bản exe)

Cách nhanh nhất là chạy lệnh cài trong PowerShell:

```powershell
irm https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.ps1 | iex
```

`install.ps1` tải `wisp-win-x64.zip` của bản mới nhất bằng `Invoke-WebRequest` (không gắn Mark of the Web
nên SmartScreen không chặn), so SHA256 với `SHA256SUMS.txt`, tắt Wisp đang chạy từ thư mục cài, giải nén
vào `%LOCALAPPDATA%\Programs\Wisp` (đổi bằng biến môi trường `WISP_INSTALL_DIR`), giữ `config.json`, tạo
shortcut "Wisp" trong Start Menu rồi mở app. Chạy lại lệnh để cài lại hoặc cập nhật. Lệnh này tin tuyệt đối
vào repo: ai push được vào `main` là sửa được script cài.

Cài tay:

1. Tải [wisp-win-x64.zip](https://github.com/hakienit/pet-tracker/releases/latest/download/wisp-win-x64.zip) (luôn là bản mới nhất).
2. Giải nén vào một thư mục cố định mà bạn có quyền ghi, ví dụ
   `%LOCALAPPDATA%\Programs\Wisp`. Không đặt trong `Program Files` (cập nhật một chạm cần quyền
   ghi vào thư mục cài) và không chạy thẳng từ trong file zip.
3. Chạy `wisp.exe`. Bản chưa ký số nên lần đầu Windows SmartScreen cảnh báo: bấm "More info" →
   "Run anyway".
4. Cài đặt → "Mở cùng máy" nếu muốn tự mở khi đăng nhập.

Yêu cầu: máy đã cài và đăng nhập Claude Code (widget đọc `~/.claude` của máy đó).

## Cập nhật

- Khi mở app và mỗi `update_interval_hours` giờ (mặc định 24), widget hỏi GitHub Releases
  (`https://api.github.com/repos/hakienit/pet-tracker/releases/latest`; API này đã bỏ qua draft và
  pre-release). Có bản mới hơn `__version__` thì island / bóng hiện mũi tên xanh và đầu panel có banner
  "Có bản mới x.y.z" kèm nút "Cập nhật". Menu chuột phải → "Kiểm tra cập nhật" để hỏi ngay.
- Nút "Cập nhật" (bản build): tải asset của release (`wisp-<ver>-win-x64.zip` hoặc
  `wisp-<ver>-macos-universal2.dmg`), `SHA256SUMS.txt` và `SHA256SUMS.txt.sig`, kiểm chữ ký Ed25519 của
  `SHA256SUMS.txt` bằng khoá công khai trong `pet_tracker/updater.py`, so SHA256 (sai hoặc thiếu chữ ký thì huỷ).
  - Windows: giải nén vào thư mục tạm, rồi một script PowerShell ẩn chờ app thoát, đổi tên thư mục cài thành
    `<thư mục>.old`, chép bản mới vào, giữ lại `config.json` cũ, mở lại app và xoá bản cũ. Log:
    `%APPDATA%\Wisp\update.log`.
  - macOS (từ 0.2.0): mở dmg chỉ đọc (`hdiutil`, không hiện trong Finder), chép `Wisp.app` ra thư mục tạm, rồi
    một script bash chạy nền chờ app thoát, đổi `Wisp.app` thành `Wisp.old.app`, chép bản mới vào (`ditto`), mở
    lại app. Cần quyền ghi vào thư mục chứa `Wisp.app` (thường `/Applications`). Log:
    `~/Library/Application Support/Wisp/update.log`.
  - Nếu chép lỗi, script khôi phục bản cũ và mở lại nó. Vị trí bóng, kích thước panel, Cài đặt, auto-start nằm
    ngoài thư mục cài nên không mất.
- Chạy từ source: nút đổi thành "Tải về" và chỉ mở trang release (không tự thay code; dùng `git pull`).
- Tắt kiểm tra tự động: `"update_check": false` trong `config.json` (vẫn kiểm tra được bằng tay).
- File app tự tải về không bị Windows gắn "Mark of the Web", nên bản cập nhật không gặp lại cảnh báo
  SmartScreen.

## Release (người bảo trì)

1. Ghi thay đổi vào mục `[Unreleased]` của `CHANGELOG.md`; khi phát hành, đổi thành
   `## [x.y.z] - YYYY-MM-DD` và thêm link so sánh ở cuối file.
2. Tăng `__version__` trong `pet_tracker/__init__.py` cho khớp, commit.
3. Tạo tag và push:

   ```bash
   git tag -a v0.2.0 -m "Wisp 0.2.0"
   ```

   ```bash
   git push origin main v0.2.0
   ```

4. Workflow `.github/workflows/release.yml` (GitHub Actions: `windows-latest` Python 3.13 và `macos-14` Python
   3.13 universal2 của python.org) kiểm tra tag khớp `__version__` và CHANGELOG có mục tương ứng, chạy unit test,
   `build.ps1` và `build_macos.sh`, tạo `SHA256SUMS.txt`, ký nó
   thành `SHA256SUMS.txt.sig` bằng secret `WISP_SIGNING_KEY`, rồi tạo và **publish** GitHub Release kèm
   zip, checksum và chữ ký, release notes lấy từ CHANGELOG. Thiếu secret thì job release lỗi.
   - Khoá ký: tạo một lần bằng `python tools/release_sign.py keygen <file ngoài repo>`. Đặt khoá công
     khai vào `SIGNING_PUBLIC_KEY` (`pet_tracker/updater.py`), nội dung file khoá bí mật vào secret
     `WISP_SIGNING_KEY` của repo (Settings → Secrets and variables → Actions). Mất khoá bí mật thì bản đã
     cài không nhận bản cập nhật ký bằng khoá mới, người dùng phải tải tay một lần.
   - Action trong workflow được pin theo commit SHA; khi nâng version, lấy SHA mới bằng
     `git ls-remote https://github.com/actions/<tên> refs/tags/<tag>`.
5. Release được publish ngay (không qua draft): app của mọi người thấy bản mới ở lần kiểm tra kế tiếp
   (mặc định tối đa 24 giờ). Bản lỗi thì sửa và ra version mới; đừng xoá release đang có người cài.

Chạy tay workflow (Actions → release → Run workflow) chỉ build và upload artifact, không tạo release.

## macOS (thử nghiệm)

Bản macOS dùng chung code với Windows; mọi chỗ khác nhau nằm trong `pet_tracker/platform/mac.py`. So sánh từng
thành phần và công nghệ build: [docs/site/platform-compare.html](site/platform-compare.html). Bản 0.2.0 đã chạy
trên runner GitHub `macos-14` (Tk 8.6.15, xem "Kiểm tra trên macOS không cần máy Mac" bên dưới), **chưa chạy trên
máy Mac thật**.

| Tính năng | macOS |
|---|---|
| Island, bóng nổi, panel, menu, thông báo | có. Tk 8.6 không vẽ ảnh trên nền trong suốt, nên island và bóng tín hiệu là cửa sổ nền đặc cắt theo hình bằng CALayer; bóng mascot, chip và huy hiệu vẽ bằng hình vector của Canvas |
| Quota | có, token đọc từ Keychain (`security find-generic-password -s "Claude Code-credentials"`); lần đầu macOS hỏi quyền |
| Danh sách session, context, model, effort, hooks | có (đọc `~/.claude` giống Windows) |
| Click session để mở | Claude desktop: deep link; CLI trong Terminal.app / iTerm2: chọn đúng tab theo tty qua AppleScript (cần quyền Automation); app khác: `open -a` |
| Đóng panel khi click ra ngoài, chuột phải lần đầu khi Wisp không active | có, đọc nút chuột toàn cục bằng `CGEventSourceButtonState` (không cần quyền) |
| Mở khi đăng nhập | có, LaunchAgent `~/Library/LaunchAgents/sg.vinova.wisp.plist` |
| Chỉ chạy một bản | có (file lock + Unix socket) |
| Cập nhật | một chạm (từ 0.2.0), xem mục "Cập nhật" |

Cài nhanh (cũng là cách cập nhật):

```bash
curl -fsSL https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.sh | bash
```

`install.sh` tải `.dmg` bằng `curl` (không gắn `com.apple.quarantine` nên Gatekeeper không chặn), so
SHA256, chép `Wisp.app` vào `/Applications` (không có quyền ghi thì `~/Applications`; đổi bằng
`WISP_INSTALL_DIR`) rồi mở app.

Cài tay (bản chưa ký số): mở `wisp-<version>-macos-universal2.dmg`, kéo "Wisp" vào
Applications. Lần đầu macOS chặn app không rõ nguồn: vào System Settings → Privacy & Security → "Open
Anyway" (hoặc chạy `xattr -dr com.apple.quarantine "/Applications/Wisp.app"`). State và log ở
`~/Library/Application Support/Wisp/`.

Build tay trên Mac (cần Python 3.13 universal2 từ python.org):

```bash
PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 ./build_macos.sh
```

Chạy từ source trên Mac:

```bash
python3 main.py
```

Kiểm tra trên macOS không cần máy Mac: nhánh `probe/mac-render` có workflow `mac-probe` chạy trên runner
`macos-14`. Merge code cần kiểm vào nhánh đó rồi push; workflow chạy unit test (gồm `tests/test_mac_update.py`,
cập nhật một chạm với app giả), `tools/mac_probe.py` (cách vẽ nào Tk hiện được) và `tools/ui_shot.py` (island và
các kiểu bóng thật với dữ liệu mẫu), rồi đẩy ảnh chụp về `probe-out/` của nhánh đó. `tools/ui_shot.py` chạy được
cả trên Windows để so.

Đã kiểm trên runner (Apple Silicon và Intel): vùng dùng được theo `NSScreen.visibleFrame`, nạp font Archivo, đọc
Keychain đúng cách Claude Code lưu (account `claude-code-user`, secret chia mảnh), so `procStart` với
`ps -o lstart=`, cập nhật một chạm với app giả.

Còn cần test trên Mac thật:

1. Màn hình Retina: ảnh có mờ không (runner chỉ có màn hình 1x); island nổi trên app full-screen và khi đổi Space.
2. Quota với tài khoản thật: lần đầu macOS hỏi quyền Keychain, sau đó quota hiện đúng.
3. Click session: Terminal.app, iTerm2 chọn đúng tab; VS Code / Cursor được đưa lên; Claude desktop
   nhận deep link `claude://code/continue?session=local_…` (thử bằng `open "claude://code/continue?session=local_…"`).
4. Cập nhật một chạm với `Wisp.app` cài thật trong `/Applications`.
5. LaunchAgent: bật, đăng xuất/đăng nhập lại, app tự mở; tắt thì không mở.

## Cấu hình

Copy `config.example.json` thành `config.json` (cùng thư mục) và sửa:

| Khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `claude_dir` | `~/.claude` (tôn trọng `CLAUDE_CONFIG_DIR`) | thư mục dữ liệu Claude Code |
| `refresh_sessions_sec` | 3 | chu kỳ đọc session / transcript |
| `refresh_quota_sec` | 60 | chu kỳ gọi API quota |
| `quota_api_enabled` | true | `false` để không gọi API, chỉ dùng ước tính local |
| `context_windows` | `{"default": 1000000}` | giới hạn context theo prefix model id |
| `warn_percent` / `danger_percent` | 60 / 85 | ngưỡng đổi màu vàng / đỏ |
| `bubble_size` | 80 | cỡ bóng nổi (px logic, tự nhân theo DPI) |
| `update_check` | true | tự kiểm tra bản mới khi mở app và mỗi `update_interval_hours` giờ |
| `update_interval_hours` | 24 | chu kỳ kiểm tra bản mới |
| `hook_port` | 47615 | cổng server nhận sự kiện hooks (chỉ 127.0.0.1) |
| `update_api_url` | null | chỉ dùng để test (trỏ tới API giả lập); null = GitHub Releases của repo |

Các tuỳ chọn đổi trong **Cài đặt** (ngôn ngữ, giao diện, kiểu hiển thị, bóng nổi, mascot, thông báo, ngưỡng quota…)
được lưu ở `%APPDATA%\Wisp\state.json`, khoá `prefs`. `warn_percent`, `danger_percent`, `quota_api_enabled`,
`update_check` trong `config.json` là giá trị mặc định cho tới khi đổi trong Cài đặt.

Log nhẹ (lỗi, lần kéo, mở panel) ở `%APPDATA%\Wisp\wisp.log` (macOS: `~/Library/Application Support/Wisp/`).

## Hooks: biết khi nào session cần bạn

Từ 0.2, Wisp hỏi một lần có thêm hooks vào `~/.claude/settings.json` (theo `CLAUDE_CONFIG_DIR` nếu đặt) không.
Bật thì mỗi entry có dạng:

```json
{"hooks": [{"type": "http", "url": "http://127.0.0.1:47615/wisp/<token>", "timeout": 3}]}
```

cho các event `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Notification`, `Stop`,
`StopFailure`.

- Wisp chỉ thêm / gỡ entry có URL chứa `/wisp/`, giữ nguyên mọi hook khác. Lần ghi đầu tiên có backup
  `settings.json.wisp-bak`. JSON sai thì không ghi gì.
- Server chỉ nghe trên 127.0.0.1, sai token thì trả 404. Server chỉ đổi hiển thị, không trả quyết định nên không ảnh
  hưởng việc duyệt quyền.
- Wisp tắt thì Claude Code bỏ qua lỗi kết nối và chạy tiếp, nhưng có thể in một dòng `hook ... failed: ECONNREFUSED`.
  Gỡ hooks trong Cài đặt nếu không dùng Wisp nữa.
- Không bật hooks: trạng thái suy ra từ `sessions/<pid>.json` như bản 0.1 (đang chạy / xong / rảnh, không biết
  "cần bạn").

## Lựa chọn tech stack

Python + tkinter (thư viện chuẩn). Lý do: máy đã có Python và tkinter, không cần tải Electron
(~100 MB) hay toolchain Rust cho Tauri; tkinter trên Windows làm được đủ ba thứ cần thiết:
`overrideredirect` (bỏ khung cửa sổ), `-topmost` (always on top) và `-transparentcolor` (bóng
tròn thật sự, phần ngoài hình tròn trong suốt và click xuyên qua). Trên macOS phần tương ứng là cửa sổ
`-transparent` của Tk aqua cộng vài lời gọi AppKit qua ctypes (mức nổi, bo góc). Toàn bộ app ~8500 dòng Python,
chiếm ~50 MB RAM, khởi động dưới 1 giây. Việc đọc dữ liệu chạy ở thread riêng, UI không bị
khựng. Hạn chế của tkinter: không có blur/acrylic, không có animation mượt; nếu sau này cần
giao diện đẹp hơn thì chuyển phần UI sang Tauri/WebView2, phần collector (`pet_tracker/`) giữ
nguyên.

## Nguồn dữ liệu và cách tính

Đã khảo sát thực tế trên Claude Code 2.1.295 / 2.1.300, Windows, ngày 2026-10-15.

### Session đang chạy

`~/.claude/sessions/<pid>.json`: Claude Code ghi một file cho mỗi process, gồm `pid`,
`sessionId`, `cwd`, `name`, `status` (`busy`/`idle`), `startedAt`, `procStart` (FILETIME),
`entrypoint` (`cli` / `claude-desktop`), `version`. File này **không bị xoá** khi process thoát,
nên widget kiểm tra pid còn sống (`OpenProcess` + `GetExitCodeProcess`) và so `procStart` với
thời điểm tạo process thật để loại trường hợp pid bị tái sử dụng.

### Context window của từng session

`~/.claude/projects/<cwd-mã-hoá>/<sessionId>.jsonl`: transcript, mỗi dòng một JSON record.
Record `type: "assistant"` có `message.usage` với `input_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`, `output_tokens`, cùng `message.model`, `message.id`, `isSidechain`,
`timestamp`, `cwd`, `gitBranch`.

Context đang dùng = `input + cache_creation + cache_read` của assistant message **mới nhất** trên
nhánh chính (`isSidechain: false`). Đó chính là toàn bộ prompt Claude Code gửi lên API ở lượt
đó, nên đúng bằng số Claude Code dùng để quyết định auto-compact.

Lưu ý format:

- Một API response được ghi thành nhiều record (`apiBlockIndex` 0..n) với **cùng** `message.id`
  và cùng usage. Widget dedupe theo `message.id`, nếu không tổng tokens sẽ bị nhân lên nhiều lần.
- Subagent (Agent tool) có transcript riêng ở
  `projects/<proj>/<sessionId>/subagents/agent-*.jsonl` (`isSidechain: true`). Chúng được tính
  vào tổng usage của session nhưng **không** tính vào context của session chính.
- Tên session lấy từ `sessions/<pid>.json` (`name`), fallback sang record `custom-title` /
  `ai-title` trong transcript.
- `cwd` lấy từ record mới nhất (session chạy trong worktree sẽ hiện đường dẫn worktree), fallback
  về `cwd` trong file session.
- Transcript được đọc tăng dần (chỉ phần mới ghi thêm), nên file 6 MB+ cũng không tốn CPU.

### Giới hạn context

Claude Code không ghi giới hạn context ra file local nào. Widget dùng bảng `context_windows`
trong config, mặc định **1.000.000 tokens** cho mọi model, vì trên máy này đã quan sát session
Opus 5.5 chạy tới 464k và Haiku 5.5 tới 351k tokens mà chưa compact, nghĩa là window ≥ 1M.
Nếu tài khoản/model của bạn chỉ có 200k thì sửa `context_windows` trong `config.json`, ví dụ
`{"default": 200000, "claude-opus-5-5[1m]": 1000000}` (khớp theo prefix model id, prefix dài hơn
thắng).

### Quota / rate limit của tài khoản

Không có API công khai chính thức cho quota của gói Claude. Widget dùng đúng endpoint mà lệnh
`/usage` của Claude Code gọi:

```
GET https://api.anthropic.com/api/oauth/usage
Authorization: Bearer <accessToken>     (đọc từ ~/.claude/.credentials.json)
anthropic-beta: oauth-2025-04-20
```

Response có `limits[]` với `kind` (`session` = 5 giờ, `weekly_scoped` = 7 ngày theo model),
`percent`, `resets_at`, `is_active`, và các field cũ `five_hour`, `seven_day`. Giới hạn:

- Endpoint **không chính thức**, có thể đổi format bất kỳ lúc nào. Khi hỏng, panel báo
  "Không lấy được quota từ API" và vẫn hiển thị ước tính local.
- Token chỉ được đọc từ file local và chỉ gửi tới `api.anthropic.com`; widget không log, không
  lưu token ở đâu khác. Widget **không** tự refresh token; khi `expiresAt` qua hạn, panel báo
  "Token hết hạn" — mở Claude Code là nó tự refresh.
- Tắt hẳn bằng `"quota_api_enabled": false`.

### Ước tính local (fallback)

Tổng tokens từ mọi transcript trên máy trong 5h / 7 ngày gần nhất (dedupe theo `message.id`,
gồm cả subagent). Chỉ là **ước tính tương đối**: giới hạn thật của Anthropic tính theo "usage"
nội bộ (có trọng số theo model, cache read rẻ hơn, effort cao tốn hơn), không phải tokens thô,
nên không thể quy ra % — widget chỉ hiển thị số tokens và số message để so sánh giữa các ngày.
Chỉ thấy usage của Claude Code trên máy này; usage từ claude.ai web / app khác không có trong
transcript.

## Focus cửa sổ session (click vào session trong panel)

Cách map session → cửa sổ, đã khảo sát và test trên máy này (Claude Code 2.1.300, Claude desktop
2.37337, Windows Terminal 1.24):

| Nơi chạy session | Cách tìm | Kết quả |
|---|---|---|
| Claude desktop app (tab Code) | `sessions/<pid>.json` có `hostSessionId` = `local_…`; app xử lý deep link `claude://code/continue?session=<local_id>` (regex trong app: `^local_[A-Za-z0-9-]{1,64}$`). Đồng thời focus cửa sổ `Claude.exe` là process cha của `claude.exe` | mở **đúng session** trong app, cửa sổ lên foreground |
| CLI trong Windows Terminal | `AttachConsole(pid)` + `GetConsoleWindow()` trả cửa sổ ẩn `PseudoConsoleWindow`; WT đặt owner của nó = cửa sổ WT thật → `GetAncestor(GA_ROOTOWNER)` | cửa sổ WT **đúng** (kể cả khi mở nhiều cửa sổ WT) lên foreground |
| CLI trong console cổ điển (conhost) | `GetConsoleWindow()` trả thẳng cửa sổ console | lên foreground |
| VS Code / Cursor / JetBrains terminal tích hợp | đi ngược parent chain (`claude.exe` ← shell ← `Code.exe`…) qua `CreateToolhelp32Snapshot`, lấy top-level window hiển thị của ancestor đầu tiên | cửa sổ IDE lên foreground (chưa test thực tế trên máy này, chưa có session nào chạy trong IDE) |
| Fallback | cửa sổ có tiêu đề chứa tên session (Claude Code đặt tiêu đề tab = `✳ <tên>`) | |

Kỹ thuật đưa lên foreground: `ShowWindow(SW_RESTORE)` nếu đang minimize, `AttachThreadInput` với
thread của cửa sổ foreground hiện tại + nhấn/thả ALT để vượt khoá `SetForegroundWindow`, rồi
`SetForegroundWindow` + `BringWindowToTop`. Sau khi focus thành công panel tự thu lại; lỗi hiện bằng thông
báo và ghi vào log.

Các trường hợp **không focus được / giới hạn**:

- **Không chuyển được tab** trong Windows Terminal: WT không có API chọn tab; widget chỉ đưa
  cửa sổ WT chứa session lên, nếu session ở tab khác bạn tự bấm tab (tab có tiêu đề `✳ <tên>`).
  Tương tự với tab/split trong VS Code, Cursor.
- Session **chạy ẩn** (ví dụ `claude -p` do app khác gọi, không có cửa sổ) → "không tìm thấy cửa sổ
  host session".
- Session qua **SSH / WSL / remote** hoặc hostSessionId không phải `local_…` (cloud) → chỉ focus
  được cửa sổ Claude desktop, không chắc mở đúng session.
- Ứng dụng khác đang **always-on-top và tự chiếm focus** (trên máy này: cửa sổ Tauri "Codex +
  Claude Usage") có thể lấy lại foreground sau ~1 giây; widget không thể ngăn.
- Khi chạy widget bằng `python main.py` (có console), bước `AttachConsole` phải tách console của
  chính nó rồi gắn lại; chạy bằng `wisp.cmd` (pythonw) thì không có vấn đề này.
- Cần cùng phiên desktop (session 1); process chạy dưới user khác / elevated có thể từ chối
  `AttachConsole`.

## Cấu trúc code

```
pet-tracker/
  main.py                  entry point
  wisp.cmd                 launcher ẩn console (pythonw, Windows)
  run.ps1 / build.ps1      Windows: chạy có console / build exe + zip portable
  build_macos.sh           macOS: build .app universal2 + .dmg
  install.ps1 / install.sh  cài bản mới nhất bằng một lệnh (Windows / macOS)
  docs/GUIDE.md            tài liệu đầy đủ (README là trang giới thiệu)
  docs/site/               landing (index.html), spec UI (design.html), so sánh Windows / macOS, nguồn README
  assets/                  icon, font Archivo, âm thanh, mascots.json
  tools/                   make_icon, make_sounds, changelog_section, release_sign, shoot_landing (README từ
                           landing), ui_shot (chụp island / bóng thật), dev.py (tự khởi động lại khi sửa code)
  tests/                   unit test (python -m unittest discover -s tests -t .)
  CHANGELOG.md             lịch sử thay đổi (Keep a Changelog)
  .github/workflows/release.yml  build Windows + macOS, tạo và publish GitHub Release khi push tag v*
  config.example.json
  pet_tracker/
    config.py              defaults, config.json, state.json, prefs, thư mục state theo OS
    claude_data.py         sessions/*.json, parser transcript .jsonl, context, ước tính local
    states.py              trạng thái session (cần bạn / đang chạy / xong / rảnh), làn, headline
    hooks.py               server hooks http (127.0.0.1 + token), thêm / gỡ entry trong settings.json
    quota.py               gọi endpoint usage OAuth, chuẩn hoá cửa sổ limit
    quota_history.py       lịch sử quota, dự báo giờ hết
    usage_local.py         token theo ngày / tuần / tháng trên máy này
    session_ops.py         mở, đóng, xoá, bàn giao session
    i18n.py, theme.py      chuỗi Việt / Anh; màu, cỡ chữ (lấy từ spec)
    vector.py, render.py   vẽ SVG khử răng cưa bằng Python thuần; ảnh cho Tk
    mascots.py, sounds.py  40 mascot (biểu cảm, dáng); âm thanh thông báo
    tls.py                 chứng chỉ certifi khi có (Python python.org trên macOS)
    procenv.py             env sạch (bỏ biến CLAUDE_*) cho tiến trình con
    updater.py             kiểm tra GitHub Releases, tải + kiểm chữ ký và SHA256, gọi platform để thay bản cài
    ui/                    giao diện tkinter: app (vòng lặp, collector), island, bubble, panel, settings, menus,
                           toast, kit (font, ảnh, widget), gfx (icon, viền động, bóng tín hiệu, vẽ vector lên Canvas)
    platform/
      __init__.py          chọn win.py hoặc mac.py, mô tả interface chung
      win.py               Windows: DPI, vùng dùng được theo từng màn hình, chuột, DWM, credentials file, autostart
      win_focus.py         map session → cửa sổ (AttachConsole, parent chain, deep link) + SetForegroundWindow
      win_single.py        chỉ chạy một bản (named mutex + event)
      win_autostart.py     chạy cùng Windows (HKCU Run)
      win_update.py        script PowerShell thay thư mục cài
      mac.py               macOS: Keychain, AppleScript, LaunchAgent, file lock, AppKit qua ctypes, cập nhật dmg
```
