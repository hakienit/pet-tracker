<p align="center"><img src="assets/wisp.png" width="112" alt="Wisp"></p>

<h1 align="center">Wisp</h1>

<p align="center">
  <b>Đốm lửa nhỏ canh các agent Claude Code của bạn.</b><br>
  Quota, session và context window, luôn nổi ở mép trên màn hình.
</p>

<p align="center">
  <a href="https://github.com/hakienit/pet-tracker/releases/latest"><img src="https://img.shields.io/github/v/release/hakienit/pet-tracker?label=b%E1%BA%A3n%20m%E1%BB%9Bi%20nh%E1%BA%A5t" alt="Bản mới nhất"></a>
  <img src="https://img.shields.io/badge/Windows%2010%2F11-ok-3fb950" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/macOS-th%E1%BB%AD%20nghi%E1%BB%87m-e3b341" alt="macOS thử nghiệm">
</p>

<p align="center"><img src="assets/island.svg" width="360" alt="Wisp dạng Dynamic Island"></p>

## Cài bằng một lệnh

**Windows 10/11**, dán vào PowerShell:

```powershell
irm https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.ps1 | iex
```

**macOS** (thử nghiệm), dán vào Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.sh | bash
```

Lệnh tải bản mới nhất, kiểm SHA256, cài rồi mở app, không vướng cảnh báo SmartScreen hay Gatekeeper.
Chạy lại để cập nhật; trên Windows, nút **Cập nhật** trong app cũng làm việc này. Cần Claude Code đã
cài và đăng nhập trên máy.

Muốn tải tay: [Windows .zip](https://github.com/hakienit/pet-tracker/releases/latest/download/wisp-win-x64.zip) ·
[macOS .dmg](https://github.com/hakienit/pet-tracker/releases/latest/download/wisp-macos-universal2.dmg) ·
[mọi bản](https://github.com/hakienit/pet-tracker/releases)

## Wisp cho bạn thấy gì

- **Quota tài khoản**: % đã dùng của cửa sổ 5 giờ và 7 ngày, giờ reset, đổi màu khi gần chạm giới hạn.
- **Mọi session đang chạy**: CLI lẫn Claude desktop, kèm model, thư mục và git branch, busy hay idle,
  context window đã dùng, số subagent.
- **Một click về đúng cửa sổ**: bấm vào session để đưa terminal, IDE hoặc Claude desktop đang chạy nó lên.
- **Dọn dẹp session** (Windows): handoff rồi đóng, đóng, xoá session, xoá worktree đã merge; mở lại session
  vừa đóng.
- **Tự cập nhật**: kiểm tra bản mới mỗi giờ, cập nhật một chạm có kiểm chữ ký.
- **Nhẹ**: Python + tkinter, khoảng 50 MB RAM, mở dưới một giây.

## Dùng

| Thao tác | Kết quả |
|---|---|
| Click vào island | mở / đóng panel |
| Click phải vào island | làm mới, kiểm tra cập nhật, chạy cùng Windows, đổi dạng island / bóng nổi, thoát |
| Click vào session | đưa cửa sổ của session lên trước |
| Click phải vào session, hoặc nút ⋯ | handoff, đóng, xoá session |

Thích bóng tròn kéo thả kiểu cũ? Click phải → **Dạng Dynamic Island** để tắt.

## Riêng tư

Wisp chỉ đọc dữ liệu Claude Code trên máy (`~/.claude`). Token đăng nhập chỉ được gửi tới
`api.anthropic.com` để lấy quota; tắt hẳn bằng `"quota_api_enabled": false` trong `config.json`.

## Tìm hiểu thêm

- [Hướng dẫn đầy đủ](docs/GUIDE.md): cấu hình, macOS, cách tính context và quota, focus cửa sổ, build và release.
- [Lịch sử thay đổi](CHANGELOG.md)

<sub>Wisp là dự án cá nhân, không phải sản phẩm của Anthropic. Quota lấy từ endpoint không chính thức mà lệnh
`/usage` của Claude Code dùng, có thể đổi bất kỳ lúc nào.</sub>
