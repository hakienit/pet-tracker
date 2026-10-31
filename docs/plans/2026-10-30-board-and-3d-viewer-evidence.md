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

## S1 sửa theo Review (F1 đến F4, F6, F7), 2026-10-31
- commit: chưa (working tree sau `e625117`)  python: 3.15.0 (không có 3.13 trên máy này)  máy: Windows 11 Home
  10.0.26300
- người dùng chọn: F1 bỏ điều kiện "mọi lane đều có chủ khác" ở 4d; F2 giữ code, spec ghi "chỉ newcomer còn sống";
  vá F4, F6, F7; bỏ F5 (spec chấp nhận). Spec board lên rev 5.
- lệnh: `python -m unittest tests.test_office`; mutation tay trên `office.py` (khôi phục file sau mỗi lần).
- Review lần hai tìm ra lỗi High có từ trước (có cả ở `HEAD`, cap 12): 4d giải phóng cả lane nhưng chỉ đặt một
  worker, nên lần gọi sau với cùng đầu vào đặt phần dư và Layout đổi (không có điểm cố định). Người dùng chọn cách 1:
  xét lại `more` theo luật a đến e, lặp tới khi một lượt không đặt thêm ai. Spec bước 4 ghi theo.
- kết quả: `tests.test_office` 82 test OK (thêm test điểm cố định bắt đầu từ `prev` cũ, gồm ca cap 12 của Review và
  400 ca ngẫu nhiên). T-L12: 173 đến 189 ms (`prev=None`), 134 đến 166 ms (`prev=layout`), đo trên máy này, không so
  được với số M2. Mutation tay (khôi phục file sau mỗi lần): 9 đột biến đều bị bắt (F1 điều kiện cũ; F3 a, b, c, d, e,
  g; F4 device `started` None; vòng xét lại chỉ chạy một lượt). Đột biến "worker đã xong thay nhau" làm vòng lặp không
  dừng; đã thêm chặn trên số lượt (`AssertionError`), nay đột biến đó làm 16 test fail ngay.
- toàn suite trên máy này: 496 test chạy, 9 fail và 4 error, tất cả ở `test_claude_data` và `test_session_ops`, không
  đụng `office.py`; nghi do Windows hoặc Python 3.15, chưa điều tra. Không tính là pass cho toàn suite.
- kết luận: S1 đạt phần `office.py`; toàn suite cần chạy lại trên Python 3.13 có Tk.

## S2a-1 Board phần thuần, 2026-10-31
- commit: chưa (working tree sau `e625117`, cùng phần sửa S1 chưa commit)  python: 3.15.0  máy: Windows 11 Home
- đỏ trước: `python -m unittest tests.test_board` lỗi import (module chưa có), 21 test đỏ.
- lệnh: `python -m unittest tests.test_board tests.test_control_room tests.test_ui_control_room`
- kết quả: 141 test OK (`test_board` 27). Review so `flatten()` của `control_room.py` ở `HEAD` và bản mới trên 3334 dòng
  (big_org, chuỗi độc, org hỏng tay, `None`/`{}`): bằng nhau tuyệt đối. Mutation của Review: 17/20 chết; 3 đột biến bỏ
  `sanitize` (tiêu đề subagent, id device, tên sàn) sống vì `org.build` đã làm sạch, Lead thêm ca chuỗi thô sau
  `org.build`, nay cả 3 chết.
- kết luận: đạt. Quy ước `(câu, None)`, khoá chip tuple và L5 (thứ tự vẽ ô pod `(2, 0)`) ghi vào plan, "Hợp đồng S2a-1 →
  S2a-2". Khoá i18n `cr.f.name`, `cr.st.unknown` không có: dùng tên làm tiêu đề panel và `cr.unknown`.

## S2b `viewer_payload` và Đ2, 2026-10-31
- commit: chưa  python: 3.15.0  máy: Windows 11 Home
- đỏ trước: `python -m unittest tests.test_viewer_payload` lỗi import, 33 test đỏ.
- kết quả: `tests.test_viewer_payload` 39 OK (thêm test E7 sau re-review); sau đó E9: nhãn `sid[:8]` thành rỗng, 40 OK. Review và Security: không High; sửa `tokens` kẹp `2**53 - 1` (Security
  Medium), `key_secret` bắt buộc `bytes` >= 16, lọc surrogate lẻ và ký tự vô hình, làm sạch rồi mới cắt, xếp sàn level
  trùng sau sàn hợp lệ, test C2 (loại cha), C3 (team), palette đủ 7 khoá. Mutation: 11/11 chết. Errata spec viewer E7
  (`surrogatepass`) và E8 (`live` chỉ cho nút còn sau trần, theo C9).
- Đ2 (lệnh của plan, máy rảnh, code cuối): median 13,4 ms, p95 20,21 ms, body 189 333 byte (786 nút, `hidden` 0). Lượt
  trước các sửa: median 12,62 ms, p95 20,07 ms; với `hmac.new` thay `hmac.digest`: median 16,47 ms. Lượt máy bận (CPU
  100%) 70 đến 95 ms, bỏ.
- kết luận: đạt ngưỡng median <= 20 ms và body < 1 MiB. p95 sát 20 ms: S3a-1 đo lại bằng `ViewerServer.publish`.
