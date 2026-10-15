# pet-tracker — bóng nổi theo dõi Claude Code agents (Windows 11)

Widget "PET" nổi trên màn hình, luôn ở trên cùng, không khung cửa sổ. Bóng hiện % quota 5 giờ
và số agent đang chạy; bấm vào mở panel stats, bấm lại hoặc click ra ngoài thì thu về. Kéo để
đổi vị trí, vị trí được nhớ giữa các lần mở.

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
D:\vinova\pet-tracker\pet-tracker.cmd
```

`pet-tracker.cmd` chạy ẩn bằng `pythonw`. Thêm thư mục `D:\vinova\pet-tracker` vào PATH để gõ
`pet-tracker` ở bất kỳ đâu. Muốn xem log trực tiếp trong console thì chạy `.\run.ps1`.

Thao tác:

| Thao tác | Kết quả |
|---|---|
| Click trái vào bóng | mở / đóng panel |
| Click ra ngoài panel | đóng panel |
| Kéo bóng | di chuyển, vị trí lưu ở `%APPDATA%\pet-tracker\state.json` |
| Click phải vào bóng | popup: Làm mới, Mở thư mục ~/.claude, Thoát |
| Click vào một session trong panel | đưa cửa sổ đang host session đó lên foreground (xem mục "Focus cửa sổ session") |
| Kéo tay nắm ở góc trên-trái panel | đổi rộng và cao panel; kích thước lưu trong `state.json`, nhấp đúp tay nắm để về mặc định. Khi nội dung dài hơn, cuộn bằng con lăn chuột hoặc kéo thanh cuộn mảnh bên phải |
| Chuột phải vào session, hoặc nút ⋯ | popup thao tác: đổi model, đổi effort, compact, clear, handoff, thoát (xem mục "Thao tác với session") |

Chỉ chạy một bản: mở `pet-tracker` lần nữa khi nó đang chạy sẽ không tạo bóng thứ hai, mà bản đang
chạy mở panel lên (dùng named mutex và event của Windows, theo từng user).

Tự khởi động cùng Windows: click phải vào bóng → "Chạy cùng Windows" để bật hoặc tắt. Widget ghi giá trị
`ClaudePET` vào `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (không cần quyền admin). Khi
chạy từ source, lệnh là `pythonw main.py`. Khi chạy từ exe, lệnh là đường dẫn exe. Nếu bạn dời thư mục
hoặc chuyển từ source sang exe, lần khởi động kế tiếp sẽ tự cập nhật đường dẫn.

## Build thành .exe (dùng nội bộ)

```bash
pwsh -File D:\vinova\pet-tracker\build.ps1
```

Script cài PyInstaller, build dạng thư mục, không console, có icon và version info, rồi tạo:

| File | Dùng để |
|---|---|
| `dist\pet-tracker\pet-tracker.exe` | chạy trực tiếp |
| `dist\pet-tracker-<version>-win-x64.zip` | gửi cho đồng nghiệp: giải nén ra một thư mục cố định rồi chạy `pet-tracker.exe` |

- Nếu PyInstaller chưa hỗ trợ bản Python trên máy (máy này đang dùng 3.15), cài Python 3.13 rồi chạy
  `pwsh -File build.ps1 -Python "C:\...\Python313\python.exe"`.
- Bản không ký số: lần đầu chạy, Windows SmartScreen sẽ cảnh báo, bấm "More info" → "Run anyway".
- `config.json` (nếu cần) đặt cạnh `pet-tracker.exe`.
- Mỗi máy cần đã cài và đăng nhập Claude Code; widget đọc dữ liệu từ `~/.claude` của máy đó.
- Icon nằm ở `assets/`, tạo lại bằng `python tools/make_icon.py`.

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
| `keep_default_model` | true | khi đổi model/effort từ widget, trả `model`/`modelSettings` trong `~/.claude/settings.json` về giá trị cũ |

Log nhẹ (lỗi, lần kéo, mở panel) ở `%APPDATA%\pet-tracker\pet-tracker.log`.

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
  chính nó rồi gắn lại; chạy bằng `pet-tracker.cmd` (pythonw) thì không có vấn đề này.
- Cần cùng phiên desktop (session 1); process chạy dưới user khác / elevated có thể từ chối
  `AttachConsole`.

## Thao tác với session (popup chuột phải)

Card session hiện model và effort của lượt gần nhất (field `effort` trên record assistant trong
transcript). Chuột phải vào card, hoặc bấm nút ⋯, mở popup thao tác: chọn model và effort bằng
chip (chip tô màu là giá trị hiện tại), bên dưới là danh sách lệnh. Esc hoặc click ra ngoài để đóng.
Các thao tác:

| Thao tác | Cách làm | Áp dụng cho |
|---|---|---|
| Mở cửa sổ session | như click trái | mọi session |
| Đổi model | gõ `/model <id>` vào session (chỉ đổi cho session đó, xem ghi chú bên dưới); danh sách model lấy từ cache catalog của Claude Code (`~/.claude/cache/model-catalog/*-cc.json`, các model `section: main`) | CLI, đang rảnh |
| Đổi effort | gõ `/effort <level>`; các mức lấy từ `effort_options` của model hiện tại | CLI, đang rảnh |
| Compact context | gõ `/compact` | CLI, đang rảnh |
| Clear context | gõ `/clear`, cần bấm hai lần để xác nhận; hội thoại cũ vẫn lưu, mở lại bằng `/resume` | CLI, đang rảnh |
| Handoff sang terminal mới | mở cửa sổ Windows Terminal mới chạy `claude --resume <sessionId> --fork-session` trong thư mục của session: session mới mang toàn bộ hội thoại, session cũ giữ nguyên | mọi session đã có hội thoại |
| Thoát session | gõ `/exit`, cần bấm hai lần để xác nhận | CLI, đang rảnh |

Cách "gõ" lệnh: widget `AttachConsole(pid)` vào console của process `claude`, mở `CONIN$` và ghi
các phím bằng `WriteConsoleInputW`, giống như bạn tự gõ rồi Enter. Claude Code không có API hay IPC
công khai nào khác cho việc này. Named pipe `messagingSocketPath` trong `sessions/<pid>.json` chỉ
dùng để gửi tin nhắn giữa các session, không chạy được slash command.

Giữ nguyên mặc định của bạn: khi gõ trong terminal, `/model` và `/effort` của Claude Code luôn lưu
luôn thành mặc định cho mọi session mới (ghi `model` và `modelSettings` vào `~/.claude/settings.json`,
kèm dòng "saved as your default for new sessions"). Widget chụp hai khoá đó trước khi gửi lệnh và trả
lại giá trị cũ ngay sau khi Claude Code ghi xong, nên chỉ session được chọn đổi model/effort. Dòng
"saved as your default" vẫn hiện trong terminal vì Claude Code in nó trước khi widget khôi phục. Muốn
để Claude Code lưu mặc định như bình thường thì đặt `"keep_default_model": false` trong `config.json`.

Đã test trên Claude Code 2.1.300 (session CLI thử trong Windows Terminal): đổi model, đổi effort,
compact (transcript có bản ghi `compact_boundary`), clear (session sang `sessionId` mới, giữ tên),
handoff (mở session CLI mới với `sessionId` mới, mang theo hội thoại), exit (process đóng trong khoảng
1 giây). Settings mặc định không đổi sau các lần đổi model/effort.

Giới hạn:

- `/compact` và handoff cần session đã có ít nhất một lượt hội thoại.
- **Session trong Claude desktop app không đổi được model, effort, clear, exit từ widget.** Process
  `claude.exe` của app chạy với `--output-format stream-json`, nhận lệnh qua pipe riêng của app chứ
  không qua console, và app không có deep link cho các thao tác này. Popup hiện các mục đó ở trạng
  thái mờ "chỉ CLI". Dùng "Mở cửa sổ session" rồi đổi trong app.
- Session CLI đang bận (`status: busy`) bị khoá các lệnh gõ phím, vì phím gõ lúc đó sẽ thành tin
  nhắn xếp hàng chứ không phải lệnh.
- Nếu bạn đang gõ dở trong ô nhập của session, lệnh sẽ bị nối vào sau chữ đang gõ. Hãy để ô nhập
  trống trước khi dùng popup.
- Hành vi chính xác của `/compact`, `/clear`, `/model`, `/effort` phụ thuộc phiên bản Claude Code
  (đã khảo sát trên 2.1.300).
- Widget xoá các biến môi trường `CLAUDE_*` khi khởi động. Nếu widget được mở từ bên trong một
  session Claude Code, các biến như `CLAUDE_CODE_CHILD_SESSION=1` sẽ khiến session handoff tắt ghi
  transcript và không xuất hiện trong danh sách.

## Cấu trúc code

```
pet-tracker/
  main.py                  entry point
  pet-tracker.cmd          launcher ẩn console (pythonw)
  run.ps1 / build.ps1      chạy có console / build exe + zip portable
  tools/make_icon.py       vẽ icon (assets/pet-tracker.ico, .png) bằng stdlib
  config.example.json
  pet_tracker/
    config.py              defaults, config.json, state.json (vị trí bóng)
    claude_data.py         sessions/*.json, parser transcript .jsonl, context, ước tính local
    quota.py               gọi endpoint usage OAuth, chuẩn hoá cửa sổ limit
    ui.py                  bubble + panel (tkinter), thread collector
    winfocus.py            map session → cửa sổ (AttachConsole, parent chain, deep link) + SetForegroundWindow
    actions.py             gõ slash command vào console session CLI, handoff (--resume --fork-session), catalog model
    render.py              vẽ khử răng cưa (bóng, thanh progress, pill) thành PhotoImage
    single.py              chỉ cho chạy một bản (named mutex + event)
    autostart.py           bật/tắt chạy cùng Windows (HKCU Run)
```
