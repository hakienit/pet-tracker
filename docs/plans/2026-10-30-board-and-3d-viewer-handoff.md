# Handoff: board 2.5D và viewer 3D

Ngày ghi: 2026-10-30. Ghi bởi phiên Claude Code trên máy macOS của người dùng, để làm tiếp trên thiết bị khác.
Bản ghi này chỉ nêu trạng thái và việc kế tiếp. Nó không cấp quyền: mọi hành động R3 (push, commit, mạng, cài gói) cần
người dùng cho phép lại trên phiên mới.

## Nhận diện repo

- Repo: `hakienit/pet-tracker` (Wisp), nhánh `main`.
- Commit của bản ghi này: lấy bằng `git log -1 -- docs/plans/2026-10-30-board-and-3d-viewer-handoff.md`. Commit ngay trước
  nó: `501be81` ("Record the office_layout timing and test evidence"). Cây sạch với mọi file của công việc này.
- Việc dở dang: S1 đã qua Review và còn findings chưa xử lý (xem "Việc đang treo").
- File chưa theo dõi trên máy gốc, không thuộc công việc này, không nên commit nếu người dùng không yêu cầu: `.DS_Store`,
  cấu hình LES cục bộ (`.agents/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `LES-AGENT.md`).

## Mục tiêu

Xây sub-project 3 (board 2.5D, tab trong Control room) và sub-project 4 (viewer 3D mở trong trình duyệt) của Wisp, dùng
lại org model của Control room.

## Tài liệu nguồn (đã duyệt, đã commit)

| File | Trạng thái |
|---|---|
| `docs/specs/2026-10-30-board-2-5d-design.md` | rev 4, người dùng duyệt 2026-10-30. Sở hữu hợp đồng Layout chung `office_layout` |
| `docs/specs/2026-10-30-3d-viewer-design.md` | rev 6, người dùng duyệt 2026-10-30. Dùng Layout qua `viewer_payload` |
| `docs/plans/2026-10-30-board-and-3d-viewer-plan.md` | rev 2: slice, thứ tự, hợp đồng giữa slice, quyết định, điều kiện xong |
| `docs/plans/2026-10-30-board-and-3d-viewer-evidence.md` | bằng chứng và số đo; Lead ghi (một người ghi) |

Đọc plan trước (mục "Quy ước chung", "Slice", "Chi tiết từng slice", "Quyết định", "Điều kiện xong").

## Trạng thái slice

| Slice | Trạng thái | Bằng chứng |
|---|---|---|
| S0 sửa `type`/`agent_type` của cây Control room | xong, commit `a498eb4`, Review không có blocker | 415 test OK |
| Đ1 đo PNG mascot lạnh | xong, đạt (viewer 128: median 14,5 ms, max 22,7 ms; Board cỡ 36: tổng 8 ảnh 24 đến 26 ms) | file bằng chứng |
| S1b khoá i18n (Board, App viewer, 39 khoá `v3d.page.*`, thêm `cr.board.cap` và `cr.board.stuck_desks`) | xong, commit `bfe9ba8`, Review duyệt bản đầu; bản thêm hai khoá chưa qua Review lần hai (chỉ thêm khoá, có test) | 8 test i18n OK |
| S1 `office.py` và hai khoá config | code xong, commit `37f149a`; Review xong: không blocker, 2 lệch spec medium (F1, F2) chờ người dùng quyết, lỗ test F3 chưa vá | `tests.test_office` 76 OK; toàn suite 496 OK; T-L12 67,4 ms (60 session x 500 worker) |
| S2a-1, S2b, Đ2, S2a-2, S2a-3, S3a-1, S3a-2, S3b, S4a, S4b, S4c, S5a, S5b | chưa bắt đầu | |

## Việc đang treo: findings của Review S1 chưa xử lý

`les-review` đã review S1 (R2): không có blocker; `tests.test_office` 76 test OK, toàn suite 496 OK. Mutation (28 đột biến
trên bản sao): bắt 18, sót 10 (3 tương đương, 7 lỗ test thật). Findings (vị trí trong `pet_tracker/office.py` ở commit
`37f149a`):

- **F1 (medium, spec):** bước 4d bị chặn khi chạm trần mà còn lane không chủ (`office.py:254`; chỉ xảy ra khi
  `board_max_workers` < 12). Ví dụ: `board_max_workers=4`, eng có 3 worker `done` ở lane 0, qa có 1 worker `done` ở lane
  1, thêm 1 worker `ops` đang `running`: worker `running` vào `more`, 4 worker `done` vẫn vẽ. Code đúng nguyên văn spec,
  nhưng spec tự mâu thuẫn ("chạm trần thì chỉ còn c và d" mà d không xảy ra được ở ca này). Đề xuất: bỏ điều kiện "mọi lane
  đều có chủ khác" (đột biến `elif True` qua hết test), sửa spec 4d theo, thêm test ở trần thấp.
- **F2 (medium, lệch spec):** thay thế ở bước 4c, 4d, 5 chỉ cho newcomer còn sống (`running`/`stuck` với worker,
  `running` với device), `office.py:244-264` và `:283-290`. Người viết code đúng về dao động: đọc nguyên văn spec thì cùng
  đầu vào vẫn làm worker đổi chỗ vòng tròn (đột biến theo nguyên văn làm hỏng `test_fixed_point_no_churn_with_same_input`).
  Hệ quả: worker xong sau, kể cả mới hơn, không thay được worker xong cũ. Có một phương án khác đã thử trên bản sao:
  newcomer đã xong thay worker đã xong khi `(last or 0, key)` của nó lớn hơn ứng viên; ổn định và qua mọi test trừ test cố
  định cách đọc cũ (chưa có chứng minh hình thức). Review đề xuất giữ code, sửa spec 4c/4d/5 thành "chỉ newcomer còn
  sống", hoặc dùng luật so `last` nếu muốn hiện worker mới nhất. **Cần người dùng chọn.** Comment `ponytail:` ở đó ghi
  "Spec không nói" là sai (spec 4c có nói); chuyển nội dung sang spec.
- **F3 (medium, test):** 7 đột biến sống sót: (a) bàn có `started_at` None phải nhận bàn sau; (b) device `running` phải
  được ưu tiên slot (fixture: 3 device done + 2 device running, kiểm slot và `more`); (c) 4c tính None là 0; (d) 4c tie-break
  theo khoá; (e) 4d trừ `drawn`; (f) điều kiện 4d (liên quan F1); (g) worker `started` None. Cần thêm test nhỏ vào T-L2,
  T-L6, T-L7.
- **F4 (low):** bàn `started_at` None nhận sau, nhưng device `started` None bị thay trước (`office.py:270` và `:284`); spec
  không nói: ghi vào spec hoặc thống nhất.
- **F5 (low, test):** quét `ast` của T-L16 (`tests/test_office.py` khoảng 967-987) còn hở với gọi qua thuộc tính
  (`collections.defaultdict()`), `AugAssign`, gán trong `if`/`try` cấp module, `lru_cache(fn)` không qua decorator.
  Chấp nhận được theo spec.
- **F6 (low):** `office_layout` dài 77 dòng (`office.py:302-378`); nên tách `_assign_desks`. Hai comment `ponytail:` thiếu
  giới hạn và đường nâng cấp.
- **F7 (nit):** `tests/test_office.py:378` có điều kiện thừa (`2 if ... else 5` luôn ra 5).

Phán quyết về hai cách đọc người viết đã chọn: (2) "không lane nào vô chủ và có lane chỉ chứa worker đã xong, giải phóng
lane số thấp nhất" được đồng ý. Các cách đọc nhỏ (state `ended` giữ cho cả worker, slot cụm/sàn chỉ giữ khi còn bàn vẽ,
`crc32` với `surrogatepass`, thiếu `last_activity` tính 0) được đồng ý.

S1 đã nằm trên `origin/main` theo yêu cầu của người dùng khi Review chưa báo. Sửa bằng commit mới, không viết lại lịch sử.
Spec không được đổi nếu người dùng chưa chọn F1 và F2.

## Quyết định của người dùng (đã ghi, không mở lại)

- Viewer: tab trình duyệt + three.js r186 (0.186.0) vendored, server riêng, cổng do OS cấp, không CDN, không pip.
- Board: sàn văn phòng isometric, vẽ bằng Tk Canvas, tab trong Control room.
- Mascot trong viewer: sprite billboard từ `mascots.png`, không dựng model 3D. SPRITE_SIZE giữ 128 (Đ1 đạt).
- B: vendor `OrbitControls.js` của three r186, vá đúng một dòng import (không tự viết orbit).
- I: không có `tools/check_bundle.py`; kiểm file sau PyInstaller bằng vài dòng trong `build.ps1` và `build_macos.sh`.
- `Wisp.spec` bị `.gitignore` (`*.spec`) và sinh lại mỗi lần build: không sửa, không dùng trong kiểm đóng gói.
- S0 (sửa lỗi `type`/`agent_type`) làm trước mọi slice: đã xong.
- P1 (python.org 3.13 làm trình thông dịch chuẩn), P3 (ngưỡng đo PNG, kiểm median và max), P5 (`publish` vượt 20 ms thì
  tối ưu trong hợp đồng; vẫn vượt thì dừng và hỏi): chấp nhận. P2, P4, P6 đến P9 là chi tiết plan.
- Rollback: mỗi slice một commit riêng khi người dùng cho phép; rollback bằng `git revert`.
- M12 (kiểm đóng gói bằng `build_macos.sh`): cho phép khi tới S5a, nhưng phải xin lại ngay lúc đó (script chạy
  `pip install --upgrade pyinstaller==6.22.3 certifi`, cần mạng, đổi interpreter toàn cục); chạy trên bản sao hoặc
  worktree, không xoá file gốc rồi `git restore`.

## Quyền hạn chưa có (xin lại, đừng suy ra)

- S4a (vendor three từ `registry.npmjs.org`) cần mạng: người dùng CHƯA cho phép. Không lấy file từ nguồn khác.
- Mọi commit và push cần người dùng nói rõ. Phiên này người dùng đã cho phép commit và push `main` nhiều lần; quyền đó
  không chuyển sang phiên mới.

## Môi trường

- Python để chạy test: python.org 3.13 có Tk (`/usr/local/bin/python3.13` trên máy gốc, Tk 8.6). Python Homebrew 3.12 trên
  máy gốc thiếu `_tkinter` nên một test nền (`test_mac_session.Fonts.test_archivo_registered_for_tk`) lỗi: lỗi môi
  trường, không phải code. Trên thiết bị mới dùng Python có Tk, hoặc cài `brew install python-tk@3.12`.
- Lệnh kiểm toàn bộ: `PY -m unittest discover -s tests` (stdlib, không framework). Kết quả ở commit `501be81` với
  python.org 3.13.1: 496 test OK.
- Kiểm tay (T3) cần macOS có display, bản Wisp đã cài phải thoát trước (`SingleInstance`), và Chrome + Safari cho viewer.
  Windows chưa có máy kiểm: ghi `unavailable`, không tính là pass.

## Kiểm tra lại khi nhận bàn giao

1. `git fetch && git log --oneline -3` thấy commit của bản ghi này và `501be81` trên `main`.
2. Chạy lại toàn bộ test trên Python có Tk; kỳ vọng 496 OK.
3. Chạy lại `tests.test_office`: kỳ vọng 76 OK; T-L12 in số đo ra stderr (60 đến 70 ms trên Apple M2).
4. Số đo Đ1 và T-L12 ghi trên máy Apple M2, tải máy không yên: coi là đo một lần trên máy đó, đo lại nếu máy khác.

## Việc kế tiếp (theo plan)

1. Hỏi người dùng chọn F1 và F2; sửa spec board theo lựa chọn (rev 5) và `office.py`; thêm test F3 và F4, vá F5 đến F7 nếu
   người dùng muốn; chạy lại hai bộ test; Review đọc lại phần đổi; xin phép commit.
2. Giao song song S2a-1 (Board phần thuần và hàm detail dùng chung: `board.py` phần thuần, tách `session_detail`,
   `subagent_detail`, `bgtask_detail` trong `control_room.py`, `tests/test_board.py`) và S2b (`viewer_payload.py`,
   `tests/test_viewer_payload.py`): cùng phụ thuộc S1, file khác nhau.
3. Đ2 (đo `publish` trên main thread, ngưỡng 20 ms) sau S2b.
4. S2a-2, S2a-3 (Board Tk và nối App), S3a-1, S3a-2, S3b (server viewer và nối App), S4a (cần mạng, xin quyền), S4b, S4c
   (trang web), S5a, S5b (đóng gói, docs), theo bảng slice của plan. Review sau mỗi slice; Security cho S2a-2, S2b, S3a-*,
   S3b, S4a, S4c.
5. Sau mỗi slice qua Review: ghi số đo vào file bằng chứng, xin người dùng cho commit riêng.

Điều kiện hoàn tất của cả công việc ở mục "Điều kiện xong" của plan. Trạng thái cuối mong đợi có phần Tay chờ người dùng
chạy, nên cuối cùng là `PENDING_USER_ACTION` tới khi người dùng chạy kiểm tay.

## Rủi ro mở

- Hiệu năng Board (chưa đo ngoài T-L12), alpha PNG trên Canvas (Tay mục 8), Trusted Types với three r186 (M2), hành vi
  `webbrowser`/argv trên Python 3.13 (M18), hiệu năng cảnh 3D (M10): có thể buộc rev spec, xem bảng rủi ro trong plan.
- Windows chưa kiểm ở mọi slice.
- Chữ trang viewer (39 khoá `v3d.page.*`) do người viết chọn, người dùng chưa duyệt giọng; sửa trong `pet_tracker/i18n.py`
  không đụng test.
