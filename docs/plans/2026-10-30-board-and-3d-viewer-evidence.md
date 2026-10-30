# Bằng chứng: board 2.5D và viewer 3D

Plan: `docs/plans/2026-10-30-board-and-3d-viewer-plan.md`, mục "Bằng chứng". Lead là người ghi duy nhất.

## S0 Lỗi `type`/`agent_type` của Control room, 2026-10-30
- commit: `a498eb4`  python: 3.13.1 (`/usr/local/bin/python3.13`)  máy: Apple M2, 8 lõi
- lệnh: `$PY -m unittest tests.test_control_room tests.test_ui_control_room`; `$PY -m unittest discover -s tests`
- kết quả: hai test mới đỏ trên code cũ (`('Loại agent', '')` thay vì `les-engineering`; tên dòng `(subagent)` thay vì
  `les-engineering`), xanh sau khi sửa. Hai module: 114 test OK. Toàn bộ suite: 415 test OK, 0 skip trong đầu ra.
  Review: không có blocker (hai ghi chú Info). Chưa chạy thử giao diện Control room thật.
- kết luận: đạt.

## Đ1 Số đo PNG mascot lạnh, 2026-10-30
- commit: `a498eb4`  python: 3.13.1  máy: Apple M2, 8 lõi; tải 4,57 / 3,71 / 3,60 trước, 4,75 / 3,88 / 3,67 sau
  (không yên: Wisp.app, Chrome, WindowServer đang chạy)
- lệnh: lệnh của mục Đ1 trong plan, không đổi, lưu ở `<scratchpad>/d1.py`; mỗi cỡ gọi `mascots._shapes.cache_clear()` và
  dùng thư mục cache mới; 40 mascot, mood `run`, theme `dark`, hue 0; chạy 3 lượt. `kit.S` = 1,0 (từ dòng `dpi=1.00` trong
  `wisp.log` ngày 2026-10-27, không đo trực tiếp).
- kết quả (ms, lượt 1 / 2 / 3):

| cỡ | canvas_size | median | max | tổng 8 ảnh chậm nhất |
|---|---|---|---|---|
| 18 | 23 | 1,0 / 1,0 / 1,0 | 3,1 / 2,9 / 3,0 | 16,3 / 14,9 / 15,7 |
| 36 | 46 | 1,9 / 2,0 / 2,0 | 4,7 / 4,7 / 4,7 | 24,1 / 25,9 / 24,6 |
| 72 | 92 | 5,1 / 5,3 / 5,2 | 9,9 / 9,9 / 10,0 | 57,2 / 59,0 / 57,2 |
| 128 | 164 | 14,5 / 14,4 / 14,5 | 22,4 / 21,3 / 22,7 | 149,1 / 139,9 / 141,6 |
| 96 | 123 | 8,4 / 8,4 / 8,4 | 14,2 / 14,2 / 14,1 | 86,9 / 87,2 / 86,7 |
| 64 | 82 | 4,3 / 4,3 / 4,3 | 8,7 / 8,7 / 9,3 | 48,3 / 48,4 / 50,9 |

- kết luận: đạt cả hai ngưỡng. Viewer: cỡ 128 có median 14,5 ms và max 22,7 ms, thấp hơn nhiều so với 150 ms, nên giữ
  `SPRITE_SIZE = 128`, không lùi cỡ. Board: cỡ bàn 36 (`36 * kit.S`, S = 1) có tổng 8 ảnh chậm nhất 24,1 đến 25,9 ms,
  thấp hơn 100 ms, nên không đổi `MAX_SPRITES_PER_RENDER`. Máy tải nên số đo có thể cao hơn số thật một chút; biên rất lớn
  nên không đổi kết luận. Chưa đo trên Windows.

## S1 `office.py` và hai khoá config (T-L12), 2026-10-30
- commit: chưa (working tree sau `73c04df`)  python: 3.13.1  máy: Apple M2, macOS 27.0.1 arm64
- lệnh: `$PY -m unittest tests.test_office -v` (T-L12 in số đo ra stderr, test không khẳng định thời gian)
- kết quả: `office_layout` với 60 session x 500 worker: 67,4 ms (`prev=None`), 60,5 ms (`prev=layout`); các lượt khác
  khoảng 64 đến 71 ms (`prev=None`). `tests.test_office`: 76 test OK. Toàn bộ suite: 496 test OK. Mutation check của
  agent: 16 lỗi cố ý, 15 bị bắt, lỗi thứ 16 ("cụm mới lấy slot cao nhất") được thêm test và nay bị bắt.
- kết luận: đạt. Review S1 chưa báo khi commit; người dùng yêu cầu commit và push trước. Hai cách đọc spec của agent
  (thay thế chỉ khi newcomer còn sống ở bước 4c/4d/5; điều kiện 4d) đang chờ phán quyết của Review.
