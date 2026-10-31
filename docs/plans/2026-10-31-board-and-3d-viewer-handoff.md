# Handoff: board 2.5D và viewer 3D (lần 2)

Ngày ghi: 2026-10-31. Ghi bởi phiên Claude Code trên máy Windows 11 của người dùng. Nối tiếp
`docs/plans/2026-10-30-board-and-3d-viewer-handoff.md`; bản đó vẫn đúng cho mọi mục không nhắc lại ở đây (mục tiêu, tài
liệu nguồn, quyết định của người dùng, quyền hạn chưa có, môi trường macOS, rủi ro mở). Đọc bản cũ trước, rồi bản này.
Bản ghi này không cấp quyền: commit, push, mạng, cài gói cần người dùng cho phép lại trên phiên mới.

## Nhận diện repo

- Repo `hakienit/pet-tracker`, nhánh `main`. Phiên này commit (người dùng cho phép commit và push, 2026-10-31) bốn commit
  sau `e625117`: sửa S1, S2a-1, S2b, rồi docs (plan, evidence, bản ghi này). Kiểm bằng `git log --oneline -5`.

## Trạng thái slice

| Slice | Trạng thái | Bằng chứng |
|---|---|---|
| S0, Đ1, S1b | như bản 2026-10-30 | |
| S1 `office.py` | xong: F1 đến F4, F6, F7 và lỗi điểm cố định ở 4d; Review ba lượt, không còn High/Medium | `tests.test_office` 82 OK |
| S2a-1 Board phần thuần | xong: `board.py` (không Tk), tách `session_detail`/`subagent_detail`/`bgtask_detail` | 141 OK (`test_board` 27); Review hai lượt |
| S2b `viewer_payload` | xong: Review và Security hai lượt, không còn High/Medium; errata spec viewer E7, E8, E9 | `tests.test_viewer_payload` 40 OK |
| Đ2 | đạt: median 13,4 ms, p95 20,21 ms, body 189 333 byte | file bằng chứng |
| S2a-2, S2a-3, S3a-1, S3a-2, S3b, S4a, S4b, S4c, S5a, S5b | chưa bắt đầu | |

## Quyết định của người dùng trong phiên này (không mở lại)

- F1: bỏ điều kiện "mọi lane đều có chủ khác" ở 4d. F2: chỉ newcomer còn sống mới thay. F4, F6, F7 vá; F5 bỏ.
- Lỗi điểm cố định ở 4d: xét lại `more` theo luật a đến e tới khi một lượt không đặt thêm ai (có chặn trên số lượt).
- Viewer: tên bàn bằng `session_id[:8]` (tên dự phòng của `claude_data`) thành nhãn rỗng (E9). Board giữ nguyên (Tk cục bộ,
  không thuộc S21).

## Ghi chú cho slice kế

- S2a-2: đọc "Hợp đồng S2a-1 → S2a-2" trong plan: dòng `(câu, None)` panel in riêng nhãn, `""` vẫn ẩn dòng; khoá chip
  là tuple; soi thứ tự vẽ ô pod `(2, 0)` khi kiểm tay.
- S3a-1: `viewer_payload` ném `ValueError` khi `key_secret` không phải `bytes` >= 16 byte (ghi trong hợp đồng plan).
  p95 của Đ2 sát 20 ms: đo lại bằng `ViewerServer.publish`. Trang (S4c) hiện "+N bàn" từ `payload["more"]`, vì nút
  overflow toàn cục đứng cuối nên bị trần cắt trước.
- Khoá i18n `cr.f.name`, `cr.st.unknown` không có; S2a-1 dùng tên làm tiêu đề panel và `cr.unknown`.

## Việc đang treo

1. Toàn suite trên máy Windows này (Python 3.15.0, không có 3.13): 568 test, đúng 13 lỗi cũ ở `test_claude_data`
   (`ActiveSessions`, `TranscriptIngest`) và `test_session_ops` (`FilterTest`); không lỗi nào ở code mới. Chưa điều tra;
   chạy lại trên python.org 3.13 có Tk (máy macOS gốc). Vẫn lỗi trên Windows với 3.13 thì báo người dùng.
2. T-L12 trên Windows 134 đến 189 ms (M2: 67 ms); test không khẳng định thời gian.

## Việc kế tiếp (theo plan)

S2a-2 (lớp `Board` Tk và tab, cần S1b, Đ1 đã có), rồi S2a-3; song song được S3a-1 (đã có Đ2). S4a cần xin mạng. Review
sau mỗi slice; Security cho S2a-2, S3a-*, S3b, S4a, S4c; ghi số đo vào bằng chứng; xin commit riêng mỗi slice.

## Môi trường máy Windows

- `python` là 3.15.0 (`C:\Python315`), có Tk 9.0; `py -3.13` không có. Lệnh test: `python -m unittest discover -s tests`.
- Git cảnh báo LF sẽ đổi thành CRLF khi chạm file; file được ghi giữ LF như repo.
