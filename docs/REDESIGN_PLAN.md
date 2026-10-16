# Kế hoạch cải tiến Wisp (0.2 → 0.5)

Bản nháp ngày 2026-10-16. Preview giao diện: [`docs/redesign/wisp-drafts.html`](redesign/wisp-drafts.html), mở bằng
trình duyệt. File có bản hiện tại (00) và 10 bản nháp (01–10). Bấm "Chọn bản này" để đánh dấu, chọn được nhiều bản để ghép.
Thêm `?only=d06` vào cuối đường dẫn để xem riêng một bản.

## 1. Tóm tắt

Wisp 0.1.7 làm tốt ba việc: hiện quota, liệt kê session, dọn dẹp session. Vấn đề lớn nhất là Wisp không biết lúc nào
**session cần bạn** (chờ duyệt quyền, chờ trả lời câu hỏi, vừa làm xong). Session đang chờ duyệt vẫn hiện "Đang chạy".
Đây lại là tính năng chính của mọi đối thủ.

Kế hoạch gồm ba hướng làm song song:

1. **Trạng thái thật**: nhận sự kiện từ Claude Code hooks (kiểu `http`, chạy tới server localhost của Wisp). Bốn trạng thái:
   cần bạn, đang chạy, xong, rảnh. Không bật hooks thì quay về cách đọc file như hiện nay.
2. **Làm lại giao diện**, kể cả phần đã có: island, card session, quota, thông báo, cài đặt, bàn phím. Mọi màu, cỡ chữ,
   khoảng cách và thời lượng animation nằm trong một bộ token dùng chung.
3. **Đồng bộ macOS và Windows**: cùng font và bộ icon đóng gói kèm app, cỡ chữ tính bằng pixel thay cho cách cộng thêm
   3pt trên Mac, cùng kiểu thông báo do Wisp tự vẽ.

Nguyên tắc:

- Đối thủ chỉ để tham khảo (READ_and_VIEW_ONLY): đọc README và trang giới thiệu. Không cài, không chạy, không
  copy code hay asset của họ.
- Vẫn chỉ dùng Python stdlib + tkinter, không thêm dependency.
- Thao tác nào ghi vào `~/.claude` của người dùng (cài hooks) đều phải opt-in, có backup và có nút gỡ.
- Giao diện trên hai hệ điều hành giống nhau về bố cục, chữ, icon, màu. Chỉ khác ở chỗ hệ điều hành bắt buộc (vị trí
  menu bar, phím Cmd/Ctrl).

## 2. Đánh giá bản hiện tại: giữ, sửa, bỏ

| # | Hiện tại | Vấn đề | Quyết định |
|---|---|---|---|
| 1 | Trạng thái chỉ có `busy`/`idle`, đọc từ `sessions/<pid>.json` mỗi 3 giây (`claude_data.py`) | Không biết session đang chờ bạn. Chậm tới 3 giây. | **Sửa**: hooks + máy trạng thái (mục 3.1), polling làm dự phòng |
| 2 | Rảnh màu xanh lá, đang chạy màu cam Claude (`ui.py:1173`) | Xanh lá đọc thành "tốt / đang chạy". Cam là màu thương hiệu nhưng lại dùng làm màu trạng thái. | **Sửa**: rảnh = xám, chạy = lam, cần bạn = hổ phách, xong = xanh ngọc. Cam chỉ dùng cho logo. |
| 3 | Trạng thái chỉ báo bằng màu (viền trái 3px, chấm ●) | Người mù màu không phân biệt được. Viền trái màu là kiểu thẻ đã quá nhàm. | **Sửa**: mỗi trạng thái có icon + chữ + màu khác cả độ sáng |
| 4 | Island: `62% · 4 agent · ● 2 · ● ●` (`ui.py:537`) | Chấm không có nhãn. Ô thứ hai lúc là "N agent" lúc là "7 ngày". Island co giãn theo nội dung nên nhảy và căn lại giữa. | **Sửa**: island có bố cục cố định theo từng trạng thái, đổi kích thước có animation |
| 5 | Island luôn ở màn hình chính (`_work_area()` không truyền điểm) | Dùng hai màn hình thì không chọn được | **Sửa**: menu "Hiện trên màn hình này", nhớ lựa chọn |
| 6 | Sắp xếp: busy trước, rồi theo thời gian (`claude_data.py:290`) | Việc cần bạn có thể nằm dưới | **Sửa**: cần bạn → đang chạy → xong chưa xem → rảnh |
| 7 | Card 5 dòng, có `msg` / `out` / entrypoint | Số msg và token output ít giá trị nhưng chiếm chỗ. Thiếu thứ quan trọng: đang làm gì. | **Sửa**: tên, trạng thái, đang làm gì (tool + file/lệnh, hoặc câu trả lời cuối), project · branch, context dạng thanh nhỏ. Số msg/out chuyển vào menu chi tiết. |
| 8 | Khối "TOKEN ĐÃ DÙNG" 5h/7d (`ui.py:1324`) | Đặt cạnh % quota gây rối. Người dùng không làm gì được với con số này. | **Bỏ**: thay bằng dự báo và nhịp quota (mục 3.5) |
| 9 | Thông báo chỉ ở footer, tự mất sau vài giây (`_flash`) | Dễ bỏ lỡ, nhất là lỗi thao tác | **Sửa**: thông báo thả xuống từ island + trạng thái ngay trên card. Footer chỉ giữ version. |
| 10 | "Đã đóng gần đây" luôn mở trong panel | Chiếm chỗ của session đang chạy | **Sửa**: thu gọn thành một dòng, bấm mới mở |
| 11 | Cài đặt chỉ sửa được trong `config.json` | Người dùng thường không biết các khoá | **Thêm**: trang Cài đặt trong panel |
| 12 | Không dùng được bàn phím, không có phím tắt toàn cục. Esc chỉ đóng popup. | Chậm với người dùng bàn phím, không có focus ring | **Thêm**: phím tắt mở Wisp, ↑↓/Enter/Esc trong panel, focus ring rõ |
| 13 | Nút ⋯ cỡ 8pt, mũi tên "mở" chỉ hiện khi hover | Vùng bấm khoảng 14px, dưới mức 24px của WCAG 2.2. Hover không có trên màn cảm ứng. | **Sửa**: vùng bấm tối thiểu 28px. Hành động chính hiện sẵn, không chỉ lúc hover. |
| 14 | Chữ nhỏ nhất 8pt (khoảng 10.7px). macOS cộng thêm 3pt (`ui.py:343`). | Khó đọc. Cỡ chữ hai OS lệch nhau. | **Sửa**: cỡ chữ tính bằng pixel (Tk nhận size âm = pixel), nhỏ nhất 12px |
| 15 | Font Segoe UI Variable / SF + icon Segoe Fluent, macOS rơi về ký tự Unicode (`FALLBACK_ICONS`) | Hai OS trông khác hẳn nhau | **Sửa**: đóng gói một font có tiếng Việt + một font icon (Lucide, giấy phép ISC), nạp riêng cho process |
| 16 | Tiêu đề mục viết hoa: "GIỚI HẠN SỬ DỤNG", "SESSIONS" | Chữ hoa có dấu khó đọc. Trộn Anh–Việt. | **Sửa**: viết thường đầu câu, theo bảng thuật ngữ ở mục 3.9 |
| 17 | Xác nhận nguy hiểm: bấm lần hai trên cùng dòng (`_sheet_row`) | Dùng được nhưng dễ hiểu nhầm | **Sửa**: dòng xác nhận riêng có nút "Xoá" và "Huỷ" rõ ràng |
| 18 | `ui.py` dài 2028 dòng, hằng màu rải rác | Khó làm lại giao diện | **Sửa**: tách module (mục 5) |
| 19 | Bóng tròn kéo thả (chế độ cũ) | Phải bảo trì hai kiểu hiển thị | **Cần chốt** (mục 9): giữ nhưng vẽ lại theo token mới, hoặc bỏ |
| 20 | Model hiện bằng viên thuốc nhiều màu | Nhiều màu cạnh tranh với màu trạng thái | **Sửa**: model là chữ xám, chỉ trạng thái mới có màu |

Giữ nguyên: focus cửa sổ session (Windows Terminal, VS Code, Orca, Claude desktop), dọn dẹp session (handoff, đóng,
xoá, xoá worktree cùng mọi kiểm tra an toàn), tự cập nhật có chữ ký, vẽ khử răng cưa bằng `render.py`, chỉ vẽ lại
phần dữ liệu đổi (`_signature`, `_patch_sessions`).

## 3. Thiết kế mới

### 3.1 Máy trạng thái session

| Trạng thái | Tín hiệu (hooks) | Dự phòng khi không có hooks |
|---|---|---|
| **Cần bạn**: chờ duyệt | `PermissionRequest`, hoặc `Notification` với `notification_type = permission_prompt` | Transcript có `tool_use` chưa có kết quả quá 5 giây và status vẫn `busy`. Hiện "có thể đang chờ duyệt". |
| **Cần bạn**: chờ trả lời | `PreToolUse` với `tool_name = AskUserQuestion`, `Notification` loại `elicitation_dialog` | `tool_use` AskUserQuestion chưa có kết quả |
| **Đang chạy** | `UserPromptSubmit`, `PreToolUse` (kèm `tool_name`, tóm tắt `tool_input`), `PostToolUse` | `status = busy` |
| **Xong** (chưa xem) | `Stop`, lấy `last_assistant_message` | `busy` chuyển sang `idle` |
| **Lỗi** | `StopFailure`, `PostToolUseFailure` | không có |
| **Rảnh** | `Notification` loại `idle_prompt`, hoặc trạng thái Xong đã được xem | `status = idle` |
| Kết thúc | `SessionEnd` | process chết (như hiện nay) |
| Subagent | `SubagentStart`/`SubagentStop` | đếm file subagent (như hiện nay) |

- "Xong" chuyển thành "Rảnh" khi người dùng bấm vào session trong Wisp, khi gõ prompt mới, hoặc sau 30 phút.
- Máy trạng thái là module thuần (`states.py`), không đụng tkinter, có unit test.
- Tóm tắt `tool_input` chỉ giữ lệnh hoặc đường dẫn file, cắt 120 ký tự, không lưu xuống đĩa.

### 3.2 Hooks: cách nhận sự kiện

Theo tài liệu Claude Code (https://code.claude.com/docs/en/hooks), hook có kiểu `"type": "http"`: Claude Code POST JSON
sự kiện tới URL. Không kết nối được hoặc lỗi HTTP thì Claude Code bỏ qua và chạy tiếp, nên Wisp tắt cũng không làm
hỏng session. Không cần chạy `wisp.exe` cho mỗi sự kiện.

```json
{
  "hooks": {
    "Notification": [{"hooks": [{"type": "http", "url": "http://127.0.0.1:47615/hook/<token>", "timeout": 3}]}],
    "Stop":         [{"hooks": [{"type": "http", "url": "http://127.0.0.1:47615/hook/<token>", "timeout": 3}]}]
  }
}
```

- Server: `http.server` + thread riêng, chỉ bind `127.0.0.1`. Cổng mặc định 47615 (đổi được trong cài đặt).
  `<token>` ngẫu nhiên, lưu trong state của Wisp. Request sai token thì trả 404 và bỏ qua.
- Body tối đa 256 KB. JSON sai thì bỏ qua. Không bao giờ chạy lệnh theo nội dung nhận được.
- Các event đăng ký: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`,
  `PermissionRequest`, `Notification`, `SubagentStart`, `SubagentStop`, `Stop`, `StopFailure`, `SessionEnd`.
- Ở 0.2 và 0.3, Wisp trả `200` với body rỗng, tức là chỉ quan sát, không quyết định gì.
- Hooks trong `~/.claude/settings.json` chạy cho cả CLI, IDE extension và Claude desktop (theo tài liệu).

Cài và gỡ hooks (`hooks_install.py`), phần dễ gây mất dữ liệu nhất:

1. Hỏi một lần lúc mở bản 0.2 lần đầu ("Cho Wisp biết khi session cần bạn?"), sau đó bật/tắt trong Cài đặt.
2. Đọc `settings.json` (theo `CLAUDE_CONFIG_DIR` nếu có). JSON sai thì dừng, báo lỗi, không ghi gì.
3. Backup `settings.json.wisp-bak-<thời gian>` trước khi ghi lần đầu.
4. Chỉ thêm entry của Wisp (nhận diện bằng URL `127.0.0.1:<port>/hook/`). Giữ nguyên mọi key và hook khác. Cài lại
   không tạo bản trùng.
5. Ghi nguyên tử (file tạm rồi `os.replace`), như `state.json` hiện nay.
6. Gỡ chỉ xoá đúng entry của Wisp, xoá cả mảng event nếu mảng rỗng do Wisp tạo ra.
7. Unit test bắt buộc: settings rỗng, đã có hooks khác, JSON sai, cài hai lần, gỡ khi đã bị sửa tay.

### 3.3 Island

- Bố cục cố định theo từng trạng thái, không co giãn theo số chữ. Đổi trạng thái thì đổi rộng có animation 200ms.
- Bên trái: vòng quota nhỏ + %. Bên phải theo mức ưu tiên: cần bạn (icon chuông + số, có thể kèm tên session) > sắp
  hết quota (giờ dự kiến hết) > đang chạy (số) > rảnh.
- Có session cần bạn: island nở thành dạng "live activity" ghi tên session (cách của bản 02/06), hoặc chỉ hiện số
  (bản 01). Do bản nháp được chọn quyết định.
- Bấm: mở panel. Chuột phải: menu. Kéo thả: chỉ ở chế độ bóng.
- Chọn màn hình hiển thị. macOS: căn giữa dưới menu bar, nếu có notch thì ôm notch (cần thử, mục 4).

### 3.4 Panel và card session

- Header: logo, tên tài khoản, nút làm mới, nút Cài đặt (bánh răng), không còn nút đóng (Esc hoặc bấm ra ngoài để đóng).
- Quota (mục 3.5), rồi danh sách session đã sắp xếp. Bản 06 chia làn, bản 04 chia ô, các bản còn lại dùng danh sách.
- Card: trạng thái (icon + chữ + thời gian), tên, đang làm gì, project · branch, thanh context nhỏ + %.
  Card "cần bạn" có nút **Mở cửa sổ** hiện sẵn. Card đang chạy có tiến độ todo (đọc từ `TodoWrite` trong transcript)
  nếu có.
- Menu ⋯ (vùng bấm 28px): mở cửa sổ, chi tiết (msg, token, model, effort, entrypoint, đường dẫn đầy đủ), handoff,
  đóng, xoá, xoá worktree. Thao tác nguy hiểm có dòng xác nhận riêng.
- "Đã đóng gần đây (N)" thu gọn ở cuối.

### 3.5 Quota: dự báo và nhịp

- Lưu mỗi lần lấy quota vào `%APPDATA%\Wisp\quota_history.jsonl` (macOS: `~/Library/Application Support/Wisp/`), giữ
  8 ngày, tối đa 1 MB.
- Dự báo 5 giờ: hồi quy tuyến tính trên 30 phút gần nhất trong cửa sổ hiện tại. Dốc ≤ 0 hoặc chưa đủ 3 điểm thì
  không dự báo. Hiện "Theo tốc độ này hết lúc 15:10, trước reset 30 phút" khi giờ hết sớm hơn giờ reset.
- Nhịp = % đã dùng chia % thời gian đã trôi của cửa sổ. Ví dụ 1.3× nghĩa là đốt nhanh hơn mức chia đều. Thanh 7 ngày có
  vạch "nhịp đều".
- Mức đốt của từng session: chia tỉ lệ theo token trong 30 phút gần nhất (ước tính, ghi rõ là ước tính).
- Báo một lần cho mỗi cửa sổ: chạm 80%, chạm 95%, dự báo hết trước reset, quota đã hồi.
- Biểu đồ (bản 07): vẽ bằng Canvas `create_line` (Windows làm mịn bằng ảnh từ `render.py`).

### 3.6 Thông báo

- Do Wisp tự vẽ: một Toplevel thả xuống từ island, giống nhau trên hai OS, không cần quyền thông báo của hệ điều hành.
- Cần bạn: giữ tới khi xử lý xong hoặc bấm "Để sau". Xong / quota: tự ẩn sau 6 giây. Tối đa 3 thông báo chồng nhau.
- Không báo khi cửa sổ của session đó đang ở trên cùng (Windows: so `GetForegroundWindow` với cửa sổ tìm được trong
  `win_focus.py`; macOS làm sau).
- Âm thanh: `winsound.PlaySound(..., SND_ASYNC)` trên Windows, `afplay` trên macOS. Ba file wav ngắn tự làm. Mặc định
  chỉ kêu khi "cần bạn". Có giờ yên lặng.
- Thông báo hệ điều hành (toast Windows, Notification Center) để sau 0.5, vì cần AppUserModelID / ký app.

### 3.7 Cài đặt và bàn phím

- Trang Cài đặt mở ngay trong panel (không mở cửa sổ mới). Các mục:
  - Thông báo: âm thanh, giờ yên lặng.
  - Quota: ngưỡng cảnh báo và ngưỡng nguy hiểm.
  - Giao diện: island hay bóng, sáng / tối / theo hệ thống, màn hình hiển thị.
  - Hooks: trạng thái, cài, gỡ, cổng.
  - Khởi động cùng máy.
  - Nâng cao: mở `config.json`, mở thư mục log.
- Lưu vào `config.json` bằng ghi nguyên tử. Khoá không biết thì giữ nguyên.
- Phím tắt mở/đóng Wisp: Ctrl+Alt+W (Windows, `RegisterHotKey` trên thread có message loop), ⌃⌥W (macOS, Carbon
  `RegisterEventHotKey` qua ctypes, cần thử).
- Trong panel: Tab và ↑↓ chuyển card, Enter mở cửa sổ, Menu hoặc Shift+F10 mở menu ⋯, Esc ẩn. Focus ring 2px màu nhấn.

### 3.8 Token thiết kế (theo UI UX Pro Max)

Đã chạy công cụ tra cứu của skill UI UX Pro Max (bản tải về để đọc, không cài). Kết quả cho "developer tool desktop
widget dark monitoring": phong cách Dark Mode (OLED) + Minimalism, chữ JetBrains Mono / IBM Plex Sans, mật độ cao, chuyển
động nhẹ. Các luật áp vào Wisp:

- Tương phản chữ tối thiểu 4.5:1, icon và viền điều khiển 3:1. Có script `tools/check_contrast.py` để kiểm bộ màu.
- Không báo thông tin chỉ bằng màu. Màu cần phân biệt phải khác cả độ sáng, không chỉ khác sắc.
- Không dùng emoji làm icon. Một bộ icon nét, độ dày nét thống nhất.
- Số liệu dùng chữ số đều (font mono, hoặc font có tabular figures) để không nhảy khi cập nhật.
- Chuyển động: vào 180ms ease-out, ra 120ms (khoảng 65% thời gian vào), island đổi kích thước 200ms. Tối đa 1–2 thứ
  chuyển động cùng lúc. Tắt khi hệ điều hành bật giảm chuyển động (Windows `SPI_GETCLIENTAREAANIMATION`, macOS
  `reduceMotion`).
- Thông báo không quan trọng tự ẩn. Thông báo cần hành động thì không.
- Vùng bấm tối thiểu 28px. Hover chỉ là phụ, mọi hành động đều bấm được.

Token nằm trong `theme.py`: `color` (nền, bề mặt, viền, chữ ba cấp, nhấn, bốn màu trạng thái, ok/warn/danger), `type`
(12/13/14/16/20/28/38 px), `space` (4/6/8/12/16/20), `radius`, `motion`. Có bộ tối và bộ sáng. Bộ sáng làm khi bản nháp
được chọn cần (05, 08) hoặc ở 0.4.

### 3.9 Thuật ngữ

| Dùng | Bỏ |
|---|---|
| session | agent |
| Cần bạn, Đang chạy, Xong, Rảnh | busy, idle, "Đang chạy" cho session đang chờ |
| quota 5 giờ, quota 7 ngày | GIỚI HẠN SỬ DỤNG |
| Mở lại (thay Resume) | Resume |
| Handoff (giữ, là thuật ngữ) | |
| context | Context viết hoa giữa câu |
| Mở cùng máy (hai OS) | "Chạy cùng Windows" / "Mở khi đăng nhập" |

## 4. Đồng bộ macOS và Windows

| Phần | Windows hiện tại | macOS hiện tại | Đích (cả hai) |
|---|---|---|---|
| Font chữ | Segoe UI Variable | SF Pro, +3pt | Font đóng gói có tiếng Việt, nạp riêng cho process (Windows `AddFontResourceExW(FR_PRIVATE)`, macOS `CTFontManagerRegisterFontsForURL` scope process). Cỡ chữ tính bằng pixel. |
| Icon | Segoe Fluent Icons | ký tự Unicode | Font icon Lucide (ISC) đóng gói, nạp như trên |
| Màu, khoảng cách | hằng số trong `ui.py` | như Windows | `theme.py` dùng chung |
| Nền trong suốt island/bóng | color key `-transparentcolor` | alpha thật | Giữ nguyên: là khác biệt kỹ thuật, nhìn giống nhau |
| Góc bo panel | DWM (Windows 11), vuông (Windows 10) | vuông | macOS: cửa sổ trong suốt + nền bo góc vẽ sẵn bằng ảnh alpha. Windows 10 chấp nhận góc vuông. |
| Ảnh trên Retina | không áp dụng | PhotoImage 1x có thể mờ (`TODO(mac)` trong `dpi_scale`) | Cần thử. Nếu mờ: trên macOS vẽ thanh và vòng bằng item Canvas (Tk aqua tự khử răng cưa), Windows vẫn dùng ảnh từ `render.py`. |
| Vị trí island | giữa mép trên vùng làm việc, màn hình chính | dưới menu bar, màn hình chính | Chọn được màn hình. macOS có notch: thử đặt cửa sổ ôm notch. Nếu Tk không cho đè lên menu bar thì đặt ngay dưới. |
| Đóng panel khi bấm ra ngoài | đọc chuột toàn cục | mất focus | Giữ cả hai cách, thêm Esc và bấm lại island |
| Phím tắt toàn cục | không có | không có | Ctrl+Alt+W / ⌃⌥W |
| Thông báo | không có | không có | Wisp tự vẽ (mục 3.6) |
| Âm thanh | không có | không có | `winsound` / `afplay` |
| Theo chế độ sáng/tối | không | không | Windows: registry `AppsUseLightTheme`. macOS: `defaults read -g AppleInterfaceStyle`. |
| Dọn dẹp session | đủ | chưa thử trên Mac thật | Thử theo checklist ở `docs/GUIDE.md` (macOS) |
| Cập nhật | một chạm | mở trang release | 0.5: một chạm sau khi có ký số và notarization |
| Chữ trong menu | "Chạy cùng Windows" | "Mở khi đăng nhập" | "Mở cùng máy" |

Kiểm tra đồng bộ: mỗi release chụp màn hình island (4 trạng thái) và panel trên cả hai OS, đặt cạnh nhau trong PR.

## 5. Kiến trúc code

```
pet_tracker/
  ui/                    # tách từ ui.py, không đổi hành vi trước khi đổi giao diện
    app.py               # PetApp, _pump, vòng đời
    theme.py             # token màu / chữ / khoảng cách / chuyển động, bộ sáng + tối
    widgets.py           # bar, pill, button, icon (từ _bar, _pill, _button, _icon_btn)
    island.py            # island + bóng
    panel.py             # khung panel, cuộn, resize
    cards.py             # card session, quota, đã đóng
    sheets.py            # menu, xác nhận, trang Cài đặt
    toast.py             # thông báo
  states.py              # máy trạng thái (thuần, có test)
  hooks_server.py        # server http localhost
  hooks_install.py       # cài / gỡ hooks trong settings.json (có test)
  quota_history.py       # lưu snapshot, dự báo, nhịp (thuần, có test)
  fonts.py               # nạp font đóng gói theo OS
assets/fonts/            # font chữ + font icon (OFL / ISC, kèm file giấy phép)
tests/                   # unittest stdlib: states, hooks_install, quota_history, contrast
```

Thứ tự: tách `ui.py` trước, giữ nguyên hành vi (so ảnh chụp trước/sau), rồi mới đổi giao diện. Mỗi bước một PR.

## 6. Lộ trình

### Giai đoạn 0: thử nghiệm kỹ thuật (2–3 ngày, chưa release)

Làm các thử nghiệm này trước vì chúng quyết định thiết kế:

1. Hook `http` chạy với bản Claude Code đang dùng trên Windows. Đo độ trễ từ lúc hiện prompt duyệt tới lúc Wisp nhận
   sự kiện (mục tiêu < 1 giây).
2. Wisp tắt: session không chậm, không báo lỗi.
3. `PermissionRequest` trả 200 body rỗng: terminal vẫn hiện prompt như thường. Hết `timeout`: chuyện gì xảy ra (tài
   liệu chưa nói rõ).
4. Nạp font riêng cho process trên Windows và macOS. Tk thấy tên font.
5. macOS thật: PhotoImage trên Retina có mờ không. Cửa sổ có đặt được trong vùng notch / menu bar không.

### 0.2.0: Biết khi nào cần bạn (khoảng 2 tuần)

- Tách `ui.py`, `theme.py`, nạp font + icon đóng gói, cỡ chữ theo pixel, bỏ `bump = 3`.
- Hooks: server, cài/gỡ opt-in, máy trạng thái, dự phòng polling.
- Island mới, card mới, sắp xếp mới, thông báo tự vẽ, âm thanh "cần bạn".
- Giao diện theo bản nháp được chọn (bộ tối).
- Bỏ khối token. Footer chỉ còn version. "Đã đóng gần đây" thu gọn.

Xong khi:

- Prompt duyệt quyền hiện thì island đổi sang "cần bạn" trong 1 giây.
- Tắt hooks thì Wisp vẫn chạy như 0.1.7.
- Test `hooks_install` qua hết các trường hợp ở mục 3.2.
- Ảnh chụp Windows và macOS khớp nhau.

### 0.3.0: Quota thông minh (khoảng 1 tuần)

Lịch sử quota, dự báo, nhịp, vạch nhịp 7 ngày, mức đốt từng session, bốn loại cảnh báo quota.

Xong khi: test dự báo đúng với dữ liệu mẫu (tăng đều, đứng yên, vừa reset). Cảnh báo chỉ hiện một lần cho mỗi cửa sổ.

### 0.4.0: Điều khiển từ Wisp (khoảng 2 tuần)

- Trang Cài đặt, phím tắt toàn cục, điều hướng bàn phím, giờ yên lặng, không báo khi đang nhìn đúng cửa sổ.
- Bộ sáng, theo chế độ của hệ điều hành.
- Cho phép / Từ chối ngay trong Wisp qua `PermissionRequest`:
  - Opt-in riêng, mặc định tắt.
  - Chỉ áp dụng cho session có prompt trong terminal.
  - Không bấm thì sau `timeout` (đặt khoảng 120 giây) quay về prompt của terminal, nếu thử nghiệm ở giai đoạn 0 xác
    nhận được cách này.
  - Không bao giờ tự cho phép.

### 0.5.0: macOS ngang Windows

Chạy hết checklist macOS trong `docs/GUIDE.md` trên máy thật. Notch, Retina, dọn dẹp session. Cập nhật một chạm khi có
Apple Developer ID và notarization (xem `RELEASE_PLAN.md`).

### Sau 0.5 (chưa cam kết)

Đẩy thông báo lên điện thoại (ntfy, tự host được), hỗ trợ Codex / Gemini CLI, nhiều `CLAUDE_CONFIG_DIR`, thông báo của
hệ điều hành, SSH remote.

## 7. Kiểm thử

- `python -m unittest discover tests`: chạy trong CI ở job build hiện có.
- Thử tay mỗi release:
  - Bốn trạng thái island.
  - Prompt duyệt quyền, câu hỏi AskUserQuestion, turn xong.
  - Tắt Wisp khi Claude Code đang chạy.
  - Cài rồi gỡ hooks, so `settings.json` với bản backup.
  - Hai màn hình, DPI 100% / 150%, Windows 10 và 11, macOS (Intel + Apple Silicon khi có máy).
- Kiểm tra tương phản bằng `tools/check_contrast.py` cho cả bộ tối và bộ sáng.

## 8. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Ghi hỏng `settings.json` của người dùng | Opt-in, backup, ghi nguyên tử, chỉ đụng entry của Wisp, test |
| Tài liệu hooks đổi hoặc `PermissionRequest` timeout không như mong đợi | Giai đoạn 0 thử trước. Duyệt từ Wisp là opt-in, mặc định tắt. Polling luôn là dự phòng. |
| Process khác trên máy giả sự kiện tới cổng localhost | Token ngẫu nhiên trong URL, chỉ bind 127.0.0.1. Sự kiện chỉ đổi hiển thị, không chạy lệnh. Cho phép/Từ chối luôn cần người bấm. |
| Tk trên macOS không làm được notch / Retina đẹp | Có phương án dự phòng ở mục 4. Bản 10 (OLED Notch) phụ thuộc nhiều nhất vào việc này. |
| Font đóng gói làm app nặng hơn | Một font chữ (2–4 file, khoảng 300–600 KB) + font icon chỉ giữ glyph dùng (khoảng 20 KB) |
| Animation nặng trên Python | Chỉ animate island và thông báo. Cache ảnh như hiện nay. Tắt khi giảm chuyển động. |

## 9. Đã chốt (2026-10-16)

1. **Giao diện**:
   - Theo bản 06: bố cục chia làn, island, thông báo, font Archivo.
   - Khối quota theo bản 01, có dòng dự báo.
   - Context ghi như bản 00: `142k / 200k 71%` kèm thanh.
   - Theme theo hệ thống (sáng / tối).
   - Có animation cho island và bóng nổi.
   - Preview thiết kế đã chốt: [`docs/redesign/wisp-prefinal.html`](redesign/wisp-prefinal.html).
2. **Bóng nổi**: giữ, chọn bản B2 (đèn tín hiệu).
3. **Hooks**: hỏi bật lúc mở 0.2 lần đầu.
4. **Âm thanh**: có. Có viền lửa động khi session cần bạn, trên cả island lẫn bóng nổi.
5. **Bổ sung (vòng 2)**, chi tiết xem trong `wisp-prefinal.html`:
   - Island và bóng nổi B2: cả 4 trạng thái đều có viền động. Rảnh là ánh xám chạy chậm, đang chạy là dải lam, cần
     bạn là lửa, sắp hết quota là viền đỏ nhấp nháy. Không hiện chữ "hết hh:mm". Có bản mới thì thêm đèn mũi tên xanh.
   - Mascot to ở đầu panel, đổi biểu cảm theo trạng thái chung. Người dùng chọn 1 trong 20 mẫu (Cài đặt → Mascot).
     Bản tkinter cần thêm bộ vẽ hình vector (đa giác + đường cong, khử răng cưa bằng supersample) vào `render.py`.
   - Hai ngôn ngữ, Tiếng Việt và English: mọi chữ đi qua một bảng `i18n.py`. Mặc định theo ngôn ngữ hệ điều hành,
     đổi được trong Cài đặt.
   - Card session có nền và viền theo trạng thái. Viền động cho "cần bạn" (lửa) và "đang chạy" (lam). Effort hiện
     cạnh model.
   - Khối "Token trên máy này": hôm nay / tuần này / tháng này. Tổng = input + output + cache, chỉ tính transcript
     trên máy này. Tháng cần tới 31 ngày dữ liệu, nhiều hơn mức 7 ngày đang đọc. Vì vậy lưu tổng theo ngày vào
     `usage_daily.json` để không phải đọc lại transcript cũ mỗi lần mở.
   - Cập nhật: banner nằm ngay dưới header, có các trạng thái: có bản mới, đang tải (thanh %), đang kiểm chữ ký,
     đang cài, lỗi (Thử lại / Tải tay), macOS (Tải về). "Đang dùng bản mới nhất" hiện trong Cài đặt.
   - Trang Cài đặt có 6 nhóm:
     - Chung: ngôn ngữ, giao diện, kiểu hiển thị, màn hình, mascot, hiệu ứng chuyển động, mở cùng máy.
     - Thông báo: âm thanh khi cần bạn / khi xong, báo khi xong, giờ yên lặng, cảnh báo quota.
     - Hooks: trạng thái, kiểm tra, gỡ.
     - Quota: hai ngưỡng màu, bật/tắt API.
     - Cập nhật: phiên bản, tự kiểm tra, kiểm tra ngay.
     - Nâng cao: làm mới, mở ~/.claude, config.json, log, thoát.
   - Menu ⋯ của session:
     - Mở cửa sổ, mở thư mục dự án, sao chép ID, chi tiết.
     - Tắt thông báo cho session này.
     - Handoff rồi đóng, đóng, xoá session, xoá worktree.
     - Thao tác nguy hiểm có dòng xác nhận riêng với nút Xoá / Huỷ.
   - Chuột phải vào island / bóng: làm mới, cài đặt, đổi island ↔ bóng, tắt âm thanh 1 giờ, kiểm tra cập nhật, thoát.
   - **Vòng 3**:
     - Island: chốt.
     - Bóng nổi có hai loại.
       - Đèn tín hiệu: 12 kiểu viền / thanh quota, phần giữa giữ nguyên.
       - Mascot: mascot chính là bóng. Trạng thái thể hiện bằng biểu cảm + chuyển động: ngủ, đi, nhảy gọi,
         nhảy múa khi xong, run khi gần hết quota. Chip % quota dưới chân.
       - Mọi mascot đều dùng được làm bóng.
     - Thư viện mascot: 40 mẫu chia 4 nhóm. Có 8 màu (xoay hue màu thân) và "Ảnh của bạn". Ảnh riêng là PNG/SVG:
       có chuyển động, không có biểu cảm.
     - Biểu cảm thứ năm "gần hết quota": lo lắng + giọt mồ hôi.
     - Chữ: gọn, nói đúng việc, không kể chuyện. Header panel là "Wisp" + dòng đếm "1 cần bạn · 1 đang chạy ·
       1 xong · 1 rảnh". Thang chữ cố định 12 / 13 / 14 / 15 / 18 px.
     - Làn trạng thái trong panel bấm để thu / mở, trạng thái thu gọn được nhớ. Mặc định thu "Rảnh" và "Đã đóng".
     - Tự kiểm tra cập nhật mỗi 24 giờ: đổi mặc định `update_interval_hours` từ 1 về 24.
   - **Vòng 4 (pre-final)**:
     - Bóng nổi có hai lựa chọn: tín hiệu và mascot.
     - Tín hiệu: 6 kiểu cho người dùng chọn: 01 Vòng liền, 02 Vòng mảnh + chấm, 05 Vạch chia, 08 Mực nước,
       10 Chấm tròn, 11 Bo vuông.
       - Vùng giữa (% + ba đèn) nằm trong khung an toàn 56×46 px quanh tâm.
       - Chữ có viền cùng màu đĩa để không bị vạch hay mực nước che.
     - Mascot: cả 40 mẫu.
       - Mỗi trạng thái có hiệu ứng riêng: zZ bay lên, bụi dưới chân + mắt đảo, sóng lan, pháo giấy, mồ hôi rơi
         + quầng đỏ.
       - Chip dưới chân có 3 kiểu: "% + đèn", "% + việc cần bạn", "hai thanh 5h / 7d + đèn".
     - Xác nhận xoá có 6 kiểu: khối trong menu, hộp thoại, giữ để xoá, bấm lần nữa + đếm ngược, xoá ngay + hoàn
       tác 8 giây, trượt để xoá.
       - "Hoàn tác" cần xoá mềm: chuyển transcript vào thư mục rác của Wisp, 8 giây sau mới xoá hẳn.
       - "Trượt để xoá" khó dùng bằng bàn phím: nếu chọn kiểu này thì thêm phím tắt thay thế.

## 9c. Bản final (2026-10-17): spec, landing, README

Quyết định cuối:
- Mọi kiểu bóng nổi đều là tuỳ chọn trong **Cài đặt → Bóng nổi**:
  - Kiểu: tín hiệu hoặc mascot.
  - Tín hiệu: 6 kiểu viền.
  - Mascot: 40 mẫu, 8 màu, ảnh riêng, 3 kiểu chip.
  - Mascot của bóng cũng là mascot ở đầu panel.
- Xác nhận xoá: kiểu 01, khối xác nhận trong menu. Khối này liệt kê hậu quả và có hai nút Huỷ / Xoá.
- Mặc định khi cài mới:
  - Hiển thị: island.
  - Bóng nổi: tín hiệu "Vòng liền".
  - Mascot: "Wisp cổ điển", màu gốc.
  - Chip: "% + đèn".
  - Giao diện: theo hệ thống. Ngôn ngữ: theo hệ điều hành.

File (chưa commit):

| File | Vai trò |
|---|---|
| `docs/site/assets/wisp-ui.js`, `wisp-ui.css` | Thư viện component dùng chung: màu, chữ, icon, 40 mascot, island, bóng nổi, panel, cài đặt, menu, thông báo. Bản app port màu / chữ / chuyển động từ đây sang `theme.py`, và path mascot sang `render.py`. |
| `docs/site/design.html` | Spec final (EN/VI), là nguồn đối chiếu khi code. |
| `docs/site/index.html` | Landing chính (mẫu B · Terminal, chọn 2026-10-17), song ngữ, host tĩnh được (GitHub Pages với thư mục `docs/`, hoặc web host bất kỳ). Có demo 4 trạng thái và playground chọn bóng nổi. `?shot=<khối>` dùng để chụp ảnh. |
| `docs/site/landing/` | Các mẫu landing khác (A Aurora, C Bento, E Parade) lưu lại để dùng sau, kèm trang `index.html` liệt kê mẫu. |
| `docs/site/README.md`, `README.vi.md` | Bản nháp README tiếng Anh / tiếng Việt cho 0.2, sinh từ landing chính. |
| `docs/site/img/*.png` | Ảnh README (hero, demo APNG, tính năng, bóng nổi, mascot) × 2 ngôn ngữ, rộng 2000 px. Tạo cùng README bằng `python tools/shoot_landing.py` (Chrome/Edge headless). |
| `docs/redesign/` | Lịch sử bản nháp, không link từ README. |

Việc khi release 0.2.0 (không làm sớm hơn, vì README không được mô tả tính năng chưa có):
1. Chạy lại `python tools/shoot_landing.py --preview` nếu landing đổi, xem `docs/site/landing/readme/main/preview-*.html`.
2. Chuyển `docs/site/README.md` → `README.md` và `README.vi.md` ra gốc repo, sửa đường dẫn tương đối
   (`img/` → `docs/site/img/`, `../../CHANGELOG.md` → `CHANGELOG.md`, `../GUIDE.md` → `docs/GUIDE.md`).
3. Bật GitHub Pages (Settings → Pages → branch `main`, thư mục `/docs`). Landing có ở
   `https://hakienit.github.io/pet-tracker/site/`. Link này đã ghi sẵn trong README nháp.

## 9b. Kết quả thử nghiệm giai đoạn 0 (Windows, Claude Code 2.1.301)

- Hook `"type": "http"` chạy được, thử bằng `claude -p --settings <file tạm>`, không đụng `~/.claude/settings.json`.
  Nhận được đủ `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`, kèm `session_id`, `cwd`,
  `tool_name`, `tool_input`, `last_assistant_message`. Hook `SessionStart` kiểu http không gửi gì ở chế độ `-p`.
- Server tắt (Wisp không chạy): session vẫn chạy bình thường, exit 0. Nhưng mỗi hook lỗi in ra stderr một dòng
  `... hook [http://127.0.0.1:...] failed: connect ECONNREFUSED`. Vì vậy Wisp **không đăng ký `SessionEnd`**, vì
  dòng lỗi này hiện ngay lúc thoát. Việc session kết thúc vẫn biết được qua process chết.
- Bản 0.2 nhận biết "chờ duyệt" bằng `Notification` loại `permission_prompt`, không dùng `PermissionRequest`. Lý do:
  `Notification` không thể ảnh hưởng tới quyết định. `PermissionRequest` để dành cho 0.4 (Cho phép / Từ chối).
- Chưa thử được: hành vi ở chế độ tương tác (prompt duyệt quyền thật, `idle_prompt`), và lỗi hook có hiện trong
  giao diện tương tác khi Wisp tắt hay không. Thử khi làm 0.2, trước khi bật hỏi hooks.

## 10. Tham khảo (chỉ đọc README / trang giới thiệu, không cài)

| Sản phẩm | Ý tưởng lấy về |
|---|---|
| Vibe Island, CodeIsland, Atoll, NotchPal (macOS notch) | Trạng thái working / waiting / approval / done, duyệt từ island, nhảy đúng tab, smart suppress, giờ yên lặng, mascot |
| CodexBar | Lịch sử quota và burndown, icon mờ khi dữ liệu cũ, báo khi quota reset |
| Claude-Code-Usage-Monitor, Token Monitor, cc-usage | Burn rate, dự báo giờ chạm giới hạn, nhịp, báo ở 80% |
| ittop, AgentManager, Hive Light | Vòng màu theo trạng thái, badge chưa đọc, panel tự nổi khi có session chờ |
| Tài liệu Claude Code hooks | Kiểu hook `http`, matcher của `Notification`, `PermissionRequest` |
