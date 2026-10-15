<p align="center"><img src="assets/wisp.png" width="128" alt="Wisp"></p>

# Wisp — đốm lửa nhỏ canh các agent Claude Code (Windows 11)

Wisp (trước đây là Claude PET / pet-tracker) là một bóng nổi trên màn hình, luôn ở trên cùng, không khung
cửa sổ. Bóng hiện % của cửa sổ quota
đang gần giới hạn nhất (thường là 5 giờ; khi cửa sổ 7 ngày cao hơn thì bóng hiện nó, kèm chữ "7 ngày"
thay cho số agent); bấm vào mở panel stats, bấm lại hoặc click ra ngoài thì thu về. Kéo để đổi vị trí
(kể cả sang màn hình thứ hai), vị trí được nhớ giữa các lần mở.

Panel hiển thị:

- **Quota tài khoản**: cửa sổ 5 giờ (session) và các cửa sổ 7 ngày (theo model, ví dụ Fable),
  % đã dùng, thời gian reset. Đổi màu xanh / vàng / đỏ theo ngưỡng.
- **Sessions đang chạy**: mọi process Claude Code còn sống trên máy (CLI lẫn Claude Desktop):
  tên session, model, thư mục dự án (+ git branch), trạng thái busy/idle, context window đã dùng
  (tokens / giới hạn, %), số message, output tokens, số subagent.
- **Ước tính local**: tokens output / input mới / số message trong 5h và 7 ngày gần nhất, tính
  từ transcript trên máy.

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
| Click trái vào bóng | mở / đóng panel |
| Click ra ngoài panel | đóng panel |
| Kéo bóng | di chuyển, vị trí lưu ở `%APPDATA%\Wisp\state.json`. Bóng được giữ trong vùng dùng được của màn hình đang chứa nó; nếu màn hình đó đã rút ra, lần mở sau bóng về màn hình gần nhất |
| Click phải vào bóng (macOS: cả Control-click) | popup: Làm mới, Mở thư mục ~/.claude, Kiểm tra cập nhật, Chạy cùng Windows, Thoát |
| Click vào một session trong panel | đưa cửa sổ đang host session đó lên foreground (xem mục "Focus cửa sổ session") |
| Kéo tay nắm ở góc trên-trái panel | đổi rộng và cao panel; kích thước lưu trong `state.json`, nhấp đúp tay nắm để về mặc định. Khi nội dung dài hơn, cuộn bằng con lăn chuột hoặc kéo thanh cuộn mảnh bên phải |

Chỉ chạy một bản: mở Wisp lần nữa khi nó đang chạy sẽ không tạo bóng thứ hai, mà bản đang
chạy mở panel lên (dùng named mutex và event của Windows, theo từng user).

Tự khởi động cùng Windows: click phải vào bóng → "Chạy cùng Windows" để bật hoặc tắt. Widget ghi giá trị
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

1. Mở https://github.com/hakienit/pet-tracker/releases, tải `wisp-<version>-win-x64.zip` ở bản
   mới nhất.
2. Giải nén vào một thư mục cố định mà bạn có quyền ghi, ví dụ
   `%LOCALAPPDATA%\Programs\Wisp`. Không đặt trong `Program Files` (cập nhật một chạm cần quyền
   ghi vào thư mục cài) và không chạy thẳng từ trong file zip.
3. Chạy `wisp.exe`. Bản chưa ký số nên lần đầu Windows SmartScreen cảnh báo: bấm "More info" →
   "Run anyway".
4. Click phải vào bóng → "Chạy cùng Windows" nếu muốn tự mở khi đăng nhập.

Yêu cầu: máy đã cài và đăng nhập Claude Code (widget đọc `~/.claude` của máy đó).

## Cập nhật

- Khi mở app và mỗi giờ, widget hỏi GitHub Releases
  (`https://api.github.com/repos/hakienit/pet-tracker/releases/latest`; API này đã bỏ qua draft và
  pre-release). Có bản mới hơn `__version__` thì bóng hiện chấm xanh ở góc trên-trái và đầu panel có
  dòng "Có bản mới x.y.z", kèm nút "Cập nhật" và link "Xem thay đổi". Click phải vào bóng →
  "Kiểm tra cập nhật" để hỏi ngay.
- Nút "Cập nhật" (bản exe): tải `wisp-<ver>-win-x64.zip`, `SHA256SUMS.txt` và `SHA256SUMS.txt.sig` của
  release, kiểm chữ ký Ed25519 của `SHA256SUMS.txt` bằng khoá công khai trong `pet_tracker/updater.py`, so
  SHA256 (sai hoặc thiếu chữ ký thì huỷ), giải nén vào thư mục tạm, rồi một script PowerShell ẩn chờ app thoát, đổi tên
  thư mục cài thành `<thư mục>.old`, chép bản mới vào, giữ lại `config.json` cũ, mở lại app và xoá bản
  cũ. Nếu chép lỗi, script khôi phục bản cũ và mở lại nó. Log: `%APPDATA%\Wisp\update.log`.
  Vị trí bóng, kích thước panel, auto-start nằm ngoài thư mục cài nên không mất.
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
   git tag v0.1.0
   ```

   ```bash
   git push origin main v0.1.0
   ```

4. Workflow `.github/workflows/release.yml` (GitHub Actions, `windows-latest`, Python 3.13) kiểm tra
   tag khớp `__version__` và CHANGELOG có mục tương ứng, chạy `build.ps1`, tạo `SHA256SUMS.txt`, ký nó
   thành `SHA256SUMS.txt.sig` bằng secret `WISP_SIGNING_KEY`, rồi tạo GitHub Release dạng **draft** kèm
   zip, checksum và chữ ký, release notes lấy từ CHANGELOG. Thiếu secret thì job release lỗi.
   - Khoá ký: tạo một lần bằng `python tools/release_sign.py keygen <file ngoài repo>`. Đặt khoá công
     khai vào `SIGNING_PUBLIC_KEY` (`pet_tracker/updater.py`), nội dung file khoá bí mật vào secret
     `WISP_SIGNING_KEY` của repo (Settings → Secrets and variables → Actions). Mất khoá bí mật thì bản đã
     cài không nhận bản cập nhật ký bằng khoá mới, người dùng phải tải tay một lần.
   - Action trong workflow được pin theo commit SHA; khi nâng version, lấy SHA mới bằng
     `git ls-remote https://github.com/actions/<tên> refs/tags/<tag>`.
5. Mở draft trên GitHub, tải zip về thử, rồi bấm **Publish**. Chỉ sau khi publish thì app của mọi
   người mới thấy bản mới.

Chạy tay workflow (Actions → release → Run workflow) chỉ build và upload artifact, không tạo release.

## macOS (giai đoạn 1, thử nghiệm)

Bản macOS là "bản xem": theo dõi được, nhưng chưa điều khiển session. Code đã tách lớp nền tảng
(`pet_tracker/platform/`) và workflow build sẵn `.dmg` universal2 (Apple Silicon + Intel), nhưng **chưa
chạy trên máy Mac thật**: mọi thứ dưới đây mới kiểm tra bằng giả lập import trên Windows.

| Tính năng | macOS giai đoạn 1 |
|---|---|
| Bóng nổi, kéo thả, panel, resize, cuộn | có (bóng dùng PNG alpha thật thay cho color key) |
| Quota | có, token đọc từ Keychain (`security find-generic-password -s "Claude Code-credentials"`); lần đầu macOS hỏi quyền |
| Danh sách session, context, model, effort | có (đọc `~/.claude` giống Windows) |
| Click session để mở | Claude desktop: deep link; CLI trong Terminal.app / iTerm2: chọn đúng tab theo tty qua AppleScript (cần quyền Automation); app khác: `open -a` |
| Đóng panel khi click ra ngoài | đóng khi app mất focus (macOS không cho đọc chuột toàn cục nếu không có quyền) |
| Mở khi đăng nhập | có, LaunchAgent `~/Library/LaunchAgents/sg.vinova.wisp.plist` |
| Chỉ chạy một bản | có (file lock + Unix socket) |
| Cập nhật | báo có bản mới, nút "Tải về" mở trang release (chưa cập nhật một chạm) |

Cài (bản chưa ký số): mở `wisp-<version>-macos-universal2.dmg`, kéo "Wisp" vào
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

Cần test trên Mac thật (đánh dấu `TODO(mac)` trong `pet_tracker/platform/mac.py`):

1. Bóng trong suốt thật (`-transparent` + `systemTransparent`), không viền lạ; nổi trên app full-screen
   và khi đổi Space.
2. Tên service Keychain của Claude Code (`security dump-keychain | grep -i claude`) và định dạng JSON
   lưu trong đó; quota hiện đúng.
3. Định dạng `sessions/<pid>.json` trên macOS (`pid`, `procStart`, `entrypoint`, `hostSessionId`).
4. Panel đóng khi click ra ngoài (FocusOut) mà không tự đóng khi đang thao tác trong panel.
5. Click session: Terminal.app, iTerm2 chọn đúng tab; VS Code / Cursor được đưa lên; Claude desktop
   nhận deep link `claude://code/continue?session=local_…`.
6. Chuột phải (và Control-click) vào bóng mở được popup.
7. Font, cỡ chữ và icon dự phòng (Unicode) dễ đọc; ảnh có bị mờ trên Retina không.
8. LaunchAgent: bật, đăng xuất/đăng nhập lại, app tự mở; tắt thì không mở.
9. Mở app lần hai chỉ hiện panel của bản đang chạy.
10. `.dmg` từ GitHub Actions mở được trên cả Apple Silicon và Intel.

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
| `bubble_size` | 64 | đường kính bóng (px logic, tự nhân theo DPI) |
| `update_check` | true | tự kiểm tra bản mới khi mở app và mỗi `update_interval_hours` giờ |
| `update_interval_hours` | 1 | chu kỳ kiểm tra bản mới |
| `update_api_url` | null | chỉ dùng để test (trỏ tới API giả lập); null = GitHub Releases của repo |

Log nhẹ (lỗi, lần kéo, mở panel) ở `%APPDATA%\Wisp\wisp.log`.

## Lựa chọn tech stack

Python + tkinter (thư viện chuẩn). Lý do: máy đã có Python và tkinter, không cần tải Electron
(~100 MB) hay toolchain Rust cho Tauri; tkinter trên Windows làm được đủ ba thứ cần thiết:
`overrideredirect` (bỏ khung cửa sổ), `-topmost` (always on top) và `-transparentcolor` (bóng
tròn thật sự, phần ngoài hình tròn trong suốt và click xuyên qua). Toàn bộ app ~2000 dòng Python,
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
`SetForegroundWindow` + `BringWindowToTop`. Sau khi focus thành công panel tự thu lại; kết quả
(hoặc lý do lỗi) hiện ở footer panel 6 giây và ghi vào log.

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
  wisp.cmd          launcher ẩn console (pythonw, Windows)
  run.ps1 / build.ps1      Windows: chạy có console / build exe + zip portable
  build_macos.sh           macOS: build .app universal2 + .dmg
  tools/make_icon.py       vẽ icon (assets/wisp.ico, .png; --png-size cho .icns) bằng stdlib
  tools/changelog_section.py  trích release notes từ CHANGELOG.md
  CHANGELOG.md             lịch sử thay đổi (Keep a Changelog)
  .github/workflows/release.yml  build Windows + macOS, tạo GitHub Release draft khi push tag v*
  config.example.json
  pet_tracker/
    config.py              defaults, config.json, state.json (vị trí bóng), thư mục state theo OS
    claude_data.py         sessions/*.json, parser transcript .jsonl, context, ước tính local
    quota.py               gọi endpoint usage OAuth, chuẩn hoá cửa sổ limit
    ui.py                  bubble + panel (tkinter), thread collector, popup, updater UI
    procenv.py             env sạch (bỏ biến CLAUDE_*) cho tiến trình con
    render.py              vẽ khử răng cưa (bóng, thanh progress, pill); PNG alpha cho macOS
    updater.py             kiểm tra GitHub Releases, tải + kiểm SHA256, gọi platform để thay bản cài
    platform/
      __init__.py          chọn win.py hoặc mac.py, mô tả interface chung
      win.py               Windows: DPI, vùng dùng được theo từng màn hình, chuột, DWM, credentials file, autostart, cập nhật
      win_focus.py         map session → cửa sổ (AttachConsole, parent chain, deep link) + SetForegroundWindow
      win_single.py        chỉ chạy một bản (named mutex + event)
      win_autostart.py     chạy cùng Windows (HKCU Run)
      win_update.py        script PowerShell thay thư mục cài
      mac.py               macOS giai đoạn 1: Keychain, AppleScript, LaunchAgent, file lock
```
