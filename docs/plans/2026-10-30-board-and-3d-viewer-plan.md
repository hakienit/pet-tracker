# Plan: Board 2.5D và Viewer 3D

Trạng thái: rev 2 (2026-10-30). Rev 2 tích hợp review của `les-review`, quyết định của người dùng (mục "Quyết định") và
errata của hai spec (mục "Erratum spec").

Spec: `docs/specs/2026-10-30-board-2-5d-design.md` (rev 4, đã duyệt) và `docs/specs/2026-10-30-3d-viewer-design.md` (rev 6, đã
duyệt). Plan này không nhắc lại spec; mọi quyết định thiết kế lấy từ spec và được
trích bằng mã mục (T-L3, T-B6, H2, V17, C10, A4, M12, Quyết định B...). Mã slice của plan (S0, S1, S2a-1...) trùng dạng với
mã yêu cầu an toàn S1 đến S26 của spec viewer (mục "Lỗi và an toàn"); vì vậy trong plan mã yêu cầu an toàn luôn viết kèm
chữ "viewer" (ví dụ "viewer S16"), còn S0, S1... đứng một mình là slice.

Rủi ro: plan R1; công việc R2 (module thuần mới, tab mới trong Control room, một HTTP server local mới, vendor mã bên
thứ ba, sửa script build). Không có bước R3 (không phát hành, không push, không ký số).

## Ngoài phạm vi

Như mục "Ngoài phạm vi" của hai spec. Thêm:

- Không thêm dependency pip vào dự án, không thêm Node, jsdom hay công cụ JS nào (Quyết định W của viewer). Lệnh pip duy
  nhất trong plan là bước có sẵn của `build_macos.sh` ở M12, chạy chỉ khi người dùng cho phép lúc đó (xem S5a).
- Không sửa `pet_tracker/hooks.py`, `tests/test_hooks.py` (viewer S20, G1), `pet_tracker/org.py` (S0 sửa phía đọc),
  `pet_tracker/mascots.py`, `pet_tracker/theme.py`.
- Không sửa `Wisp.spec`: file này bị `.gitignore:4` (`*.spec`) bỏ qua, không được git theo dõi và được PyInstaller sinh lại
  mỗi lần build; đóng gói `assets/viewer` chỉ qua `build_macos.sh` và `build.ps1` (quyết định của người dùng; spec viewer
  rev 6, erratum E1).
- Không có `tools/check_bundle.py` (Quyết định I); không minify, không gzip three.js (rủi ro 10 của viewer).
- Không sửa lỗi có sẵn `test_mac_session.Fonts.test_archivo_registered_for_tk` trên Python Homebrew 3.12 thiếu
  `_tkinter` (xem "Môi trường kiểm"); nó không thuộc hai spec.
- CHANGELOG chỉ ghi `[Unreleased]`; không đổi `__version__`.

## Quy ước chung

- TDD: mỗi slice viết test trước, chạy thấy đỏ (ghi lệnh và số test đỏ vào báo cáo slice), rồi sửa code tới khi xanh.
- Test chỉ dùng stdlib (`unittest`, `unittest.mock`, `ast`, `socket`, `http.client`, `tempfile`). Không đọc
  `~/.claude` thật, không mạng ngoài (trừ bước tải tarball của S4a), không ghi ngoài thư mục tạm. Test mở file của repo
  bằng đường dẫn dựng từ gốc repo (`Path(__file__).resolve().parents[1] / ...`), không phụ thuộc thư mục hiện hành.
- Fixture `org` luôn dựng bằng `org.build(sessions_thô, cfg, now)` với worker thô có `agent_type` (rủi ro 8 của board,
  ghi chú phụ thuộc (1) của viewer); không dựng tay dict đầu ra, trừ các ca spec ghi rõ "Layout dựng tay" (C3, C14, C16).
- **Commit và rollback** (quyết định của người dùng, như plan Control room): mỗi slice là một commit riêng. Sau khi một
  slice qua Review (và Security khi bảng ghi), Lead xin người dùng cho phép commit slice đó một lần; chỉ commit khi người
  dùng nói. Không push. Rollback một slice bằng `git revert <commit>`. Slice chưa được commit thì chưa có điểm rollback
  riêng: slice sau không bắt đầu ghi vào file chung (mục "Tuần tự bắt buộc") khi slice trước nó chưa được commit.
- Slice sau không sửa file của slice trước, trừ các file nhiều slice cùng ghi được liệt kê ở "Tuần tự bắt buộc".
- Một chuỗi agent không bao giờ đi vào tag Tk, đường dẫn, URL, log (board "Lỗi và an toàn"; viewer S9, viewer S10,
  viewer S21).
- Số đo và kết quả kiểm tay ghi vào file bằng chứng (mục "Bằng chứng"), không vào PR (dự án không mở PR trong plan này).

### Môi trường kiểm (đã kiểm 2026-10-30, commit `59255f4`)

- `python3` của máy dev là Homebrew 3.12 (`/opt/homebrew/opt/python@3.12`), **thiếu `_tkinter`**. Trên nó,
  `python3 -m unittest discover -s tests` cho `Ran 413, FAILED (errors=1, skipped=22)`: lỗi duy nhất là
  `test_mac_session.Fonts.test_archivo_registered_for_tk` (`ModuleNotFoundError: No module named '_tkinter'`), 22 test
  Tk bị bỏ qua.
- `/usr/local/bin/python3.13` là Python 3.13.1 của python.org (Tk 8.6, cùng loại Python mà `build_macos.sh` khuyên dùng
  và bản build dùng). Trên nó cùng lệnh cho `Ran 413, OK`, không test nào bị bỏ qua (máy có display).
- Trình thông dịch kiểm chuẩn (P1, đã duyệt): `PY=/usr/local/bin/python3.13`. Mọi lệnh dưới đây viết `$PY`. Máy không có
  bản này thì cài `brew install python-tk@3.12` rồi dùng `python3.12`.
- Test bị bỏ qua vì thiếu Tk hoặc display được báo `unavailable` (lý do "không có Tk display"), **không** tính là pass
  (Quyết định AB của viewer). Báo cáo mỗi slice có test Tk ghi số test `skipped` và lý do.
- Lệnh test toàn bộ: `$PY -m unittest discover -s tests`. `tests/__init__.py` đã có, nên chạy một module bằng
  `$PY -m unittest tests.test_office -v` từ gốc repo.

### Thiết lập kiểm tay (Tay)

- Người chạy: AI (Lead hoặc department được giao) chạy được các mục chỉ cần app và lệnh shell (ví dụ M8, M13, M18, đọc
  `wisp.log`). Các mục cần trình duyệt Chrome và Safari, chuột, cảm ứng hay mắt người (M1 đến M7, M9 đến M11, M14 đến M17,
  M19, chín mục Tay của board) cần **người dùng**. Tới lúc đó Lead báo `PENDING_USER_ACTION` kèm danh sách mục và lệnh,
  và slice giữ trạng thái đó tới khi người dùng chạy và gửi kết quả.
- Trước khi chạy `$PY main.py` từ source: thoát bản Wisp đã cài đang chạy. `main.py:21-24` dùng `SingleInstance`: nếu đã
  có bản chạy, bản mới chỉ nhờ bản cũ mở rồi thoát, nên sẽ kiểm nhầm bản cũ.
- Hook của Claude Code: trước phiên Tay, chép `~/.claude/settings.json` vào thư mục tạm của phiên và ghi phần hook của
  Wisp (đường dẫn `/wisp/...` và cổng); sau phiên so lại bằng `diff`. `App._start_hooks` có thể ghi lại hook khi thấy hook
  cũ, nên khác biệt được ghi vào bằng chứng; chỉ khôi phục bản chép khi người dùng yêu cầu.
- Windows: `unavailable` ở mọi slice (rủi ro 1 của cả hai spec, đã chấp nhận).

### Tier

Tên tier của plan khác nhãn test của spec (T-L, T-B, V, C, W, A, M) và khác tier của LES:

- **U**: unit test, gồm test tĩnh `ast`/chuỗi. **U (Tk)**: unit test cần Tk display.
- **U+đo**: U cộng số đo ghi vào file bằng chứng.
- **Tay**: U cộng kiểm tay trên macOS theo "Thiết lập kiểm tay".

## Slice

| # | Kết quả | Owner | File sở hữu | Phụ thuộc | Tier | Review |
|---|---|---|---|---|---|---|
| S0 | dòng "Loại agent" của cây đọc `type` (lỗi có sẵn) | Engineering | `pet_tracker/control_room.py` (chỉ `_session_rows`), `tests/test_control_room.py` | không | U | Review |
| Đ1 | số đo dựng PNG mascot lạnh | Engineering | không file nào (số vào bằng chứng) | không | U+đo | không |
| S1 | `office.py` hàm thuần + hai khoá config | Engineering | `pet_tracker/office.py`, `pet_tracker/config.py` (chỉ `DEFAULTS`), `config.example.json`, `tests/test_office.py` | S0 | U+đo (T-L12) | Review |
| S1b | mọi khoá i18n mới (vi và en) | Engineering | `pet_tracker/i18n.py`, `tests/test_i18n_new_keys.py` | S0 | U | Review |
| S4a | vendor three r186 + `OrbitControls.js` đã vá | Engineering | `assets/viewer/vendor/` (5 file), `tests/test_viewer_assets.py` (A3, A4) | S0 | U | Review, Security |
| S2a-1 | Board: hàm thuần + hàm `detail` dùng chung | Engineering | `pet_tracker/board.py` (chỉ phần thuần), `pet_tracker/control_room.py` (tách hàm detail), `tests/test_board.py` | S1 | U | Review |
| S2b | `viewer_payload` hàm thuần | Engineering | `pet_tracker/viewer_payload.py`, `tests/test_viewer_payload.py` | S1 | U | Review, Security |
| Đ2 | số đo `publish` trên main thread | Engineering | không file nào (số vào bằng chứng) | S2b | U+đo | không |
| S2a-2 | lớp `Board` Tk + tab trong Control room | Frontend | `pet_tracker/board.py` (lớp `Board`), `pet_tracker/control_room.py`, `tests/test_ui_board.py` | S2a-1, S1b, Đ1 | U (Tk) | Review, Security |
| S2a-3 | App nối Board: palette, `mascot_image`, `cfg` | Frontend | `pet_tracker/ui/app.py` (`_control_room_theme`, `_open_control_room`, hàm mới `_board_mascot_image`), `tests/test_ui_board_app.py` | S2a-2 | U + Tay | Review |
| S3a-1 | `ViewerServer`: định tuyến, header, token, Host/Origin, slot, `publish`, sprite, vòng đời, `page_strings` | Engineering | `pet_tracker/viewer.py`, `tests/test_viewer.py` | S2b, S1b, Đ1, Đ2 | U+đo | Review, Security |
| S3a-2 | cứng hoá kết nối H1 đến H3 | Engineering | `pet_tracker/viewer.py` (lớp `ViewerHTTPServer`, đọc dòng và header), `tests/test_viewer_limits.py` | S3a-1 | U | Review, Security |
| S3b | vòng đời viewer trong App + menu | Engineering | `pet_tracker/ui/app.py` (`_open_3d_viewer`, `_viewer_tick`, xử lý kết quả mở trình duyệt, `_pump`, `quit`), `pet_tracker/ui/menus.py`, `tests/test_ui_viewer_app.py`, `tests/test_viewer_wiring_static.py` | S3a-1, S2a-3 | U (Tk) | Review, Security |
| S4b | `tools/viewer_demo.py` | Engineering | `tools/viewer_demo.py`, `tests/test_viewer_demo.py` | S3a-1 | U | Review |
| S4c | trang web `assets/viewer/` | Frontend | `assets/viewer/index.html`, `assets/viewer/app.js`, `assets/viewer/style.css`, `tests/test_viewer_assets.py` (A1, A2, A8, kiểm chéo vendor) | S3a-2, S3b, S4a, S4b | U + Tay | Review, Security |
| S5a | đóng gói | DevOps | `build_macos.sh`, `build.ps1`, `tests/test_viewer_assets.py` (A5) | S4c | U + Tay (M12) | Review |
| S5b | tài liệu | Engineering | `docs/GUIDE.md`, `CHANGELOG.md`, `README.md`, `README.vi.md` | S4c | U (test vẫn xanh) | Review |

File bằng chứng `docs/plans/2026-10-30-board-and-3d-viewer-evidence.md` do Lead ghi (mục "Bằng chứng"); không slice nào sở
hữu nó.

Song song được (file sở hữu không giao nhau):
- Sau S0: S1 ‖ S1b ‖ S4a ‖ Đ1 (Đ1 không ghi file nên chạy được cả lúc S0 đang làm).
- Sau S1: S2a-1 ‖ S2b. S4a ‖ mọi slice tới trước S4c.
- S3a-1 và S3a-2 ‖ S2a-1, S2a-2, S2a-3 (chúng chỉ chạm `viewer.py` và test riêng).
- S3a-2 ‖ S3b ‖ S4b (sau S3a-1, file không giao nhau). S5a ‖ S5b.

Tuần tự bắt buộc, theo file nhiều slice cùng ghi:
- `pet_tracker/control_room.py`: S0 → S2a-1 → S2a-2.
- `pet_tracker/board.py`: S2a-1 → S2a-2.
- `pet_tracker/viewer.py`: S3a-1 → S3a-2.
- `pet_tracker/ui/app.py`: S2a-3 → S3b.
- `tests/test_viewer_assets.py`: S4a → S4c → S5a.
- `pet_tracker/i18n.py`: chỉ S1b ghi (P7). Slice sau cần đổi một khoá thì báo Lead; Lead giao một sửa nhỏ khi không slice
  nào khác đang mở file đó.

So với thứ tự đề xuất bởi review (S0, S1, S2a ‖ S2b, S3, S4, S5), plan **đổi** hai điểm: vendor (S4a) tách khỏi S4 và chạy
sớm, song song từ sau S0; và các slice được tách nhỏ như sau, kèm lý do:
- S2a thành ba: phần thuần (không Tk), lớp Tk, và phần nối App. Lý do: `ui/app.py` chỉ chạm ở S2a-3, nên chuỗi sửa
  `ui/app.py` (S2a-3 → S3b) ngắn; lớp Tk lớn nhất nằm riêng một lượt review.
- S3 thành S3a-1 (server: định tuyến và chính sách), S3a-2 (cứng hoá kết nối H1 đến H3) và S3b (nối dây App). Lý do: S3a
  gộp quá lớn cho một lượt review; H1 đến H3 là phần socket và thread khó nhất, Security cần soát riêng; S3b chạm
  `ui/app.py` nên phải chờ S2a-3.
- S4 thành S4a (vendor), S4b (công cụ demo), S4c (trang). Lý do: vendor là dữ liệu bên thứ ba cần Security soát riêng và
  cần mạng; demo chỉ cần S3a-1 nên chạy song song; trang là phần JS chỉ kiểm tay, một lượt review riêng.
- S5 thành S5a (đóng gói, DevOps) và S5b (tài liệu).

S3a-* **không** phụ thuộc S4a: test server dựng file vendor giả trong thư mục tạm và vá `viewer.VENDOR_SHA256` bằng băm
của file giả (xem S3a-1). Nhờ vậy S4a `BLOCKED` (không có mạng) chỉ chặn S4c và các slice sau nó, không chặn server.

### Hợp đồng giữa các slice

**Hợp đồng S1 → S2a-1, S2b, S3a-1 (Layout).** S1 sở hữu `pet_tracker/office.py`; không slice nào khác sửa file này. Đầu ra
đúng mục "Layout chung", "Hình dạng", "Hệ toạ độ", "Khoá nhận dạng", "Cam kết cho consumer" và "Bảng state" của spec
board:
- `office_layout(org_out, cfg, prev=None) -> Layout`; `valid_org(org_out) -> bool`; `mascot_index(seed, count)`;
  `max_floor_h(desks)`.
- Hằng: `FLOOR_CLUSTER_COLS == 2`, `CLUSTER_W == 15`, `CLUSTER_H == 10`, `POD == 4`, `POD_STRIDE == 5`, `CLUSTER_PODS`,
  `LANES`, `DEVICE_SLOTS == 3`, `STATE_STYLE` (hai phần `desk`, `worker`), `ALERT_STYLE` (T-L17, T-S1).
- Layout chỉ gồm kiểu JSON; `ref` chỉ có nghĩa với đúng `org_out` của lần gọi; `styles` là bản sao sâu.
- S2a-1, S2a-2 và S2b chỉ đọc các tên trên; cần đổi hình dạng hay tên thì báo Lead, không tự sửa `office.py`.

**Hợp đồng S2a-1 → S2a-2 (ghi 2026-10-31 sau Review S2a-1).** `board.node_detail` trả `(tiêu đề, rows)`; trong `rows`,
giá trị `None` nghĩa là dòng là một câu đầy đủ (`cr.board.cap`, `cr.board.stuck_desks`): panel in riêng nhãn; giá trị `""`
vẫn nghĩa là ẩn dòng như panel của cây. Khoá chip là tuple (`board.chip_key(desk)`, `board.MORE_DESKS_KEY`), chỉ dùng làm
khoá dict/lựa chọn, không thành tag Tk. Nơi gọi chịu trách nhiệm ghép đúng Layout với `org_out` của cùng lần dựng
(`node_detail` không đối chiếu `session_id`). Kiểm tay S2a-2 soi thứ tự vẽ: worker ở ô pod `(2, 0)` cùng `x+y` với bàn
nên được vẽ sau và có thể đè góc mặt bàn vài px (Review S2a-1 L5, đúng spec).

**Hợp đồng S2a ‖ S2b (hai consumer độc lập của Layout).** Hai nhánh không gọi nhau và không chia sẻ trạng thái:
- Mỗi nơi gọi giữ `prev` riêng (L-S5, Quyết định O của viewer). Board giữ `self._layout` trong `Board`; viewer giữ
  `self._prev` trong `ViewerServer` (S3a-1). Không đối tượng Layout nào được truyền giữa hai nơi.
- Cả hai áp cùng luật nơi gọi `valid_org` (board "Layout chung"; viewer V28), nhưng hiển thị khác nhau: Board hiện
  `cr.board.nodata` và không vẽ Layout cũ; viewer giữ payload cũ (Quyết định X).
- Đọc từ `org_out`: Board đọc `type` (sau S0) và các khoá của "Chi tiết" board; `viewer_payload` chỉ đọc `department`,
  `description`, `tokens`, `started`, `last_activity`, `state` qua `ref`, không đọc `type`/`agent_type`.
- Màu: Board tra `th["palette"][token]` (khoá `palette` do S2a-2/S2a-3 thêm); `viewer_payload` nhận `theme` qua đối số
  (`theme.DARK`) và đổi token thành hex. Cả hai dùng đúng token của `STATE_STYLE`; không slice nào thêm bảng màu thứ hai.
- Mascot: cả hai dùng `mascot_index(seed, len(ids))` với `ids = [m["id"] for m in mascots.all_mascots()]`; Board dựng
  ảnh qua `mascot_image` (S2a-3), viewer qua endpoint sprite (S3a-1).
- `config.py`: chỉ S1 ghi (`board_max_desks`, `board_max_workers`); Board và viewer đọc `cfg` của app, không thêm khoá.
- Test: S2a-1 chỉ ghi `tests/test_board.py`; S2b chỉ ghi `tests/test_viewer_payload.py`. Fixture `org` lớn dùng chung
  là hàm `big_org(...)` trong `tests/test_office.py` (S1 viết, hai nhánh chỉ import).

**Hợp đồng S2b → S3a-1 (bộ chuyển đổi).** `viewer_payload(layout, org_out, theme, mascot_ids, key_secret) -> dict`, đầu ra
đúng mục "Bộ chuyển đổi" (allowlist C9), `ValueError` khi `layout["version"] != 1` hoặc `layout` không phải dict (C14), hoặc khi `key_secret` không phải `bytes`
dài tối thiểu 16 byte (thêm 2026-10-31 sau Security S2b; `ViewerServer` phải có khoá trước lần `publish` đầu, test và
fake không truyền khoá ngắn),
hằng `MAX_NODES = 1000`, `FLOOR_GAP = 6`. S3a-* không sửa `viewer_payload.py`.

**Hợp đồng S3a-1 → S3a-2, S3b, S4b, S4c (server).** Giao diện module của viewer ("Giao diện module" và "Trang" của spec
viewer rev 6, errata E3):
- `ViewerServer(*, assets_dir, cache_dir, strings, hue, cfg, theme, mascot_ids, log, clock=time.monotonic,
  key_secret=None)`, **không có `lang`**; `start() -> bool`; `error: str`; `url: str`; `publish(org, ts)`;
  `idle_for() -> float`; `stop()`.
- `PAGE_STRING_KEYS` (39 khoá, danh sách đóng ở mục "Trang") và `page_strings(lang) -> dict[str, str]` là hằng và hàm thuần
  cấp module của `viewer.py`: đọc `i18n.VI`/`i18n.EN`, giữ khoá tiền tố `v3d.page.`, bỏ tiền tố đó, trả đúng tập
  `PAGE_STRING_KEYS`. Khoá của App (`v3d.open_fail`, `v3d.link_copied`, `isl.view3d*`) không bao giờ ra trình duyệt. App gọi
  `viewer.page_strings(i18n.lang())` và truyền kết quả làm `strings`; server phục vụ đúng dict đó ở `/api/strings`. `app.js`
  (S4c) tra chuỗi bằng hàm duy nhất `str("<tên>")` với tên trong `PAGE_STRING_KEYS` (A8).
- **Điểm vá cho test và demo**: `viewer.py` import `from . import office` và `from .viewer_payload import viewer_payload`
  ở cấp module, và trong `publish` gọi `office.office_layout(...)` và tên cấp module `viewer_payload(...)` tại thời điểm
  gọi (không gán vào thuộc tính, mặc định đối số hay closure). Nhờ vậy `mock.patch.object(viewer, "viewer_payload", f)` và
  `mock.patch.object(office, "office_layout", f)` thay được hàm thật (V16, V25, V28) và demo đặt được payload tay.
- `VENDOR_SHA256` là dict cấp module; test vá nó bằng `mock.patch.dict`.
- Endpoint, payload `/api/layout`, header và mã lỗi đúng mục "Endpoint" và "Payload `/api/layout`". S4c chỉ dựa vào các
  mục đó; S3b chỉ dùng API trên (test của S3b thay `viewer.ViewerServer` bằng lớp giả có đúng các tên này).
- S3a-2 không đổi API công khai; nó chỉ thay lớp server, handler đọc dòng và header bên trong `viewer.py`.

**Hợp đồng S3a-1 → S4b (`--hostile`).** Demo đặt payload tự dựng bằng cách vá tên cấp module
`viewer.viewer_payload` thành hàm trả `scene` độc của M16 (bỏ qua bộ chuyển đổi thật), rồi gọi `publish` bình thường. Vì
vậy payload độc vẫn đi qua lớp bọc `{"v", "ts", "ready", "refresh_sec", "scene"}`, mã hoá JSON và slot thật. Demo không ghi
thẳng vào slot và không dùng thuộc tính riêng (`_slot`, `_prev`) của `ViewerServer`.

## Chi tiết từng slice

### S0 Lỗi `type`/`agent_type` của Control room

- Test trước (`tests/test_control_room.py`, dựng bằng helper `build()` có sẵn, tức `org.build`): (1) dòng subagent của
  `flatten` có cặp detail `(t("cr.f.agent_type"), "les-engineering")` cho worker thô `agent_type="les-engineering"`;
  (2) worker có `description` rỗng thì tên dòng là type, không phải `cr.anon_subagent`. Hai test này đỏ trên `main`.
- Không có test "department rỗng thì nhóm theo type": qua `org.build` ca đó không tạo được, vì `org.department` trả
  `name or agent_type` (rủi ro 8 của spec board rev 4).
- Sửa: hai chỗ đọc ở `_session_rows` (`control_room.py:299`, `:311`) đọc `w.get("type")`. Không sửa `org.py`: Board và
  viewer đọc `type` đúng hợp đồng của org.
- Kiểm: `$PY -m unittest tests.test_control_room tests.test_ui_control_room -v`; `$PY -m unittest discover -s tests`.

### Đ1 Số đo PNG mascot lạnh (trước S2a-2 và S3a-1)

Chạy trên `main` chưa sửa, `$PY`, máy yên (ghi tải máy). `mascots._shapes` có `lru_cache` không phụ thuộc cỡ, nên mỗi cỡ
xoá cache đó và dùng một thư mục cache đĩa mới (lạnh cả RAM lẫn đĩa); đủ 40 mascot, mood `run`:

```
$PY -c "import time,tempfile,statistics as st
from pathlib import Path
from pet_tracker import mascots
ids=[m['id'] for m in mascots.all_mascots()]
for size in (18,36,72,128,96,64):
    mascots._shapes.cache_clear();d=Path(tempfile.mkdtemp());r=[]
    for mid in ids:
        t=time.perf_counter();mascots.png(mid,'run',size,'dark',0.0,d);r.append((time.perf_counter()-t)*1000)
    print(size,mascots.canvas_size(size),'median',round(st.median(r),1),'max',round(max(r),1),'worst8',round(sum(sorted(r)[-8:]),1))"
```

Ghi vào bằng chứng: bảng cỡ / median / max / tổng 8 ảnh chậm nhất, phiên bản Python, commit hash, `kit.S` của máy (dòng
`start ... dpi=` trong `wisp.log`). Số dò sơ bộ khi lập plan rev 1 không xoá `_shapes` nên không dùng làm bằng chứng.

Ngưỡng và hành động (P3, đã duyệt):
- Viewer: ở cỡ 128 cần **median ≤ 150 ms và không ảnh nào > 150 ms** (rủi ro 3 của viewer). Đạt thì giữ
  `SPRITE_SIZE = 128`. Không đạt thì lùi `96`, rồi `64`, lấy cỡ lớn nhất đạt cả hai điều kiện; S3a-1 đặt hằng theo đó. Không
  dùng pre-warm trong thread nền. Cả 64 vẫn không đạt: dừng S3a-1, Lead báo `PENDING_USER_ACTION` kèm số.
- Board (ngưỡng ở rủi ro 3 của spec board rev 4): tổng 8 ảnh chậm nhất ở cỡ mascot bàn thật (`36 * kit.S`, và `72` nếu
  `kit.S` là 2) ≤ 100 ms. Vượt thì không tự đổi
  `MAX_SPRITES_PER_RENDER`: Lead báo `PENDING_USER_ACTION` với đề xuất hạ hằng đó bằng một rev spec.

### S1 `office.py` và hai khoá config

- Test trước (`tests/test_office.py`, `unittest` thuần, không Tk, không đĩa ngoài file của repo): đủ T-L1 đến T-L17 và
  T-S1. Thêm:
  - `config.DEFAULTS["board_max_desks"] == 48`, `config.DEFAULTS["board_max_workers"] == 12`; `config.example.json` (mở
    bằng đường dẫn từ gốc repo, `Path(__file__).resolve().parents[1] / "config.example.json"`) có hai khoá đó với cùng giá trị.
  - Hàm dựng fixture `big_org(projects=2, teams=8, desks=48, subs=12, tasks=3, now=...)` trả `org.build(...)` của các session
    thô tổng hợp (mỗi team tối đa 6 session; tên phòng ban lấy từ 4 `agent_type` có tiền tố `les-`). T-L12 và Đ2 dùng nó.
  - T-L12 in số đo (60 session x 500 worker) ra stderr; Lead chép số vào bằng chứng; test không khẳng định thời gian.
- Thứ tự đỏ → xanh gợi ý: T-L17, T-S1 (hằng) → T-L1, T-L2 (thuần, đầu vào hỏng) → T-L9, T-L14 (hình học) → T-L3, T-L10,
  T-L11 (khoá, seed, xác định) → T-L4, T-L5, T-L6, T-L7 (ổn định, lane, device) → T-L8, T-L15 (trần, đếm) → T-L13, T-L16
  (cam kết consumer, tái nhập, hai thread) → T-L12.
- Sửa: `office.py` mới; kẹp `board_max_desks` vào [1, 200], `board_max_workers` vào [0, 12] nằm trong `office.py` (spec
  "Cấu hình"); `config.py` chỉ thêm hai giá trị vào `DEFAULTS`; `config.example.json` thêm hai khoá.
- Kiểm: `$PY -m unittest tests.test_office -v`; `$PY -m unittest discover -s tests`.

### S1b Khoá i18n

- Test trước (`tests/test_i18n.py` có sẵn không sửa; thêm `tests/test_i18n_new_keys.py`): `i18n.VI` và `i18n.EN` có đủ khoá
  Board (`cr.tab.tree`, `cr.tab.board`, `cr.board.floor`, `cr.board.more_desks`, `cr.board.more_detail`, `cr.board.hint`,
  `cr.board.nodata`, `cr.f.workers`, mục "Cấu hình" của board), khoá App của viewer (`isl.view3d`, `isl.view3d.sub`,
  `v3d.open_fail`, `v3d.link_copied`) và đúng 39 khoá `v3d.page.<tên>` của danh sách đóng ở mục "Trang" của viewer (danh sách
  tên chép trong test vì `viewer.PAGE_STRING_KEYS` chưa có; S3a-1 thêm test so hằng với danh sách này); placeholder chỉ
  `{n}` ở khoá trang, `{i}`/`{n}` ở khoá Board như spec ghi; mọi giá trị không rỗng.
- Làm: thêm các khoá vào `i18n.py` (vi và en). Chữ theo các mô tả trong hai spec.
- Kiểm: `$PY -m unittest tests.test_i18n tests.test_i18n_new_keys -v`.
- **P7 (chi tiết plan):** mọi khoá mới ở một slice. Lý do: V24 của S3a-1 cần đủ 39 khoá `v3d.page.*` có sẵn, Board cần khoá
  `cr.*`; gom vào một slice sớm thì `i18n.py` chỉ có một người ghi và S2a ‖ S3a không phải chờ nhau vì file này.

### S4a Vendor three.js r186

- Điều kiện: mạng tới `registry.npmjs.org`. Không có mạng thì S4a `BLOCKED`; chỉ S4c và các slice sau nó bị chặn. Không
  lấy file từ nguồn khác.
- Test trước (`tests/test_viewer_assets.py`): A3 và A4. Ở slice này A4 so SHA-256 ba file `.js` và `LICENSE` với hằng ghi
  trong test (lấy từ bảng "Dữ kiện đã kiểm" của spec viewer) và với `VERSION.txt`; phần "bằng `viewer.VENDOR_SHA256`" được
  thêm ở S4c (khi cả `viewer.py` lẫn file vendor đều có).
- Làm: chạy năm bước "Lệnh tái lập checksum" của mục "Đóng gói assets" trong thư mục tạm mới, ghi đầu ra từng bước vào bằng
  chứng. Bước 3 theo spec viewer rev 6 (erratum E4): `LICENSE` được so với SHA-256 trong bảng "Dữ kiện đã kiểm" và
  `VERSION.txt`, không so với `viewer.VENDOR_SHA256` (dict đó không có `LICENSE`, và `viewer.py` chưa có lúc S4a). Chép `three.module.js`, `three.core.js`,
  `OrbitControls.js` (đã vá đúng một dòng), `LICENSE` vào `assets/viewer/vendor/`; viết `VERSION.txt` (phiên bản `0.186.0`,
  nguồn, SHA-256 tarball, SHA-512 integrity, SHA-256 từng file, SHA-256 bản gốc và bản đã vá của `OrbitControls.js`, dòng
  vá, và nguyên văn "Lệnh tái lập checksum").
- Kiểm: `$PY -m unittest tests.test_viewer_assets -v`; `shasum -a 256 assets/viewer/vendor/*` khớp bảng spec.
- Security soát: nguồn, checksum, bản vá đúng một dòng (`diff` ra một dòng), không có `eval(`/`new Function`.

### S2a-1 Board phần thuần

- Bước 1, tách hàm detail (rủi ro 9 của board; P4): trong `control_room.py` thêm `session_detail(s, now)`,
  `subagent_detail(w, now)`, `bgtask_detail(w, now)` trả list `(nhãn, giá trị)`; `_session_rows` gọi chúng thay cho list
  nội tuyến. Hành vi cây giữ nguyên: toàn bộ `tests/test_control_room.py` và `tests/test_ui_control_room.py` xanh, không
  sửa test cũ.
- Test trước (`tests/test_board.py`, không Tk): đúng danh sách `tests/test_board.py` của spec board (`paint_order`, ba chữ
  ký, chọn sàn mặc định, `floor_alerts`, chi tiết của bàn, subagent, device, chip, chuỗi độc). Thêm: chi tiết subagent của
  Board và của cây bằng nhau vì cùng gọi `subagent_detail` (một test so hai đầu ra); `ast` quét `board.py` phần thuần
  không gọi `subprocess`, `open`, `os`.
- `board.py` import `tkinter` bọc `try` như `control_room.py`, để test thuần chạy không cần Tk.
- Kiểm: `$PY -m unittest tests.test_board tests.test_control_room -v`.

### S2b `viewer_payload`

- Test trước (`tests/test_viewer_payload.py`): C1 đến C16, với `office_layout` thật trên `big_org` và các fixture nhỏ dựng
  bằng `org.build`, `theme.DARK`; Layout dựng tay chỉ cho C3, C14, C16. Phần C10 về `ViewerServer.start()` và V29 thuộc
  S3a-1.
- Thứ tự đỏ → xanh gợi ý: C1, C14, C15 (thuần, rỗng, `ValueError`) → C2, C3, C4 (làm phẳng, toạ độ tuyệt đối, `bounds`)
  → C6, C16 (legend, ép enum) → C7, C8, C11, C13 (nhãn, mascot, alert, live) → C9, C10 (allowlist, HMAC) → C12 (trần) →
  C5 (ổn định qua `prev`).
- Kiểm: `$PY -m unittest tests.test_viewer_payload -v`.
- Security soát: allowlist khoá (viewer S21), làm sạch và cắt chuỗi (viewer S22), ép enum (viewer S25 phía server), HMAC
  có khoá (Quyết định P, AA).

### Đ2 Số đo `publish` (sau S2b, trước S3a-1)

Đo phần việc mà `publish` sẽ làm trên main thread ở trần mặc định của board đầy (48 bàn, 12 subagent, 3 thiết bị mỗi bàn):

```
$PY -c "import time,json,hashlib,statistics as st
from tests.test_office import big_org
from pet_tracker import office,viewer_payload as vp,theme,mascots,config
org=big_org();cfg=dict(config.DEFAULTS);ids=[m['id'] for m in mascots.all_mascots()];prev=None;r=[]
for i in range(201):
    t=time.perf_counter();l=office.office_layout(org,cfg,prev);prev=l
    b=json.dumps({'v':1,'ts':0.0,'ready':True,'refresh_sec':3,'scene':vp.viewer_payload(l,org,theme.DARK,ids,b'k'*16)},ensure_ascii=True,allow_nan=False).encode()
    hashlib.sha256(b).hexdigest();r.append((time.perf_counter()-t)*1000)
r=sorted(r[1:]);print('median',round(st.median(r),2),'p95',round(r[189],2),'bytes',len(b))"
```

Ghi vào bằng chứng: median, p95, cỡ body, số nút, Python, commit. Ngưỡng: median ≤ 20 ms (mục "Chia sẻ dữ liệu giữa
thread"); cỡ body < 1 MiB (viewer S16). Khi vượt (P5, đã duyệt): trước hết tối ưu bên trong `office.py` hoặc
`viewer_payload.py` mà không đổi hợp đồng (đo lại, ghi cả hai số); vẫn vượt thì dừng S3a-1 và Lead báo
`PENDING_USER_ACTION` kèm số. Plan không chuyển việc tính sang thread khác (trái viewer S15) và không tự hạ trần mặc định
của board. S3a-1 đo lại bằng `ViewerServer.publish` thật.

### S2a-2 Lớp `Board` và tab

- Test trước (`tests/test_ui_board.py`, cần Tk display, tự `skipTest` theo mẫu `tests/test_control_room.py`): T-B1 đến
  T-B8, T-B9 (`tests/test_i18n.py` vẫn đạt), và phần của T-B10 không cần App: `control_room._DEFAULT_THEME` có `palette`
  là `theme.DARK`; Board dựng với palette giả thiếu token dùng `palette["idle"]`, không `KeyError`.
- `mascot_image` trong test là stub đếm lời gọi (T-B6); chưa có App thật ở slice này.
- Sửa `control_room.py`: thanh tab `Cây`/`Board` giữa thanh tổng và thân; tham số tuỳ chọn `cfg`, `mascot_image` của
  `ControlRoom.__init__`; style `Cr.Horizontal.TScrollbar`; `render` chuyển `org` cho Board khi tab Board hiện; lỗi Board
  bắt, log `repr()` cắt 200, tab Cây không ảnh hưởng. Palette mặc định (theo spec board rev 4): `ControlRoom.__init__` có
  tham số tên `theme` che tên module `theme`, nên import ở cấp module dưới tên khác (`from .theme import DARK as _DARK`) và đặt
  `_DEFAULT_THEME["palette"] = _DARK` ở cấp module; không dùng module `theme` bên trong `__init__`.
- Khoá i18n `cr.*` đã có từ S1b; slice này không sửa `i18n.py`.
- Kiểm: `$PY -m unittest tests.test_ui_board tests.test_board tests.test_ui_control_room tests.test_i18n -v`; báo số test
  `skipped`. Bị bỏ qua thì slice chưa xong (`unavailable`, không pass).
- Security soát: T-B5 (tag chỉ `n<số>` và tag nhóm), mọi chuỗi qua `sanitize()`, `session_id` chỉ tới `focus_session`.

### S2a-3 App nối Board

- Test trước (`tests/test_ui_board_app.py`, file mới, chạy không cần display): dùng mẫu import của
  `tests/test_ui_control_room.py:11-24` (import `config`, `org` trước, rồi `pet_tracker.ui.app` thật nếu có `_tkinter`,
  ngược lại stub `tkinter` bằng `mock.patch.dict(sys.modules, ...)`) và lớp `_Stub` + `_bind`. Không đặt ở
  `tests/test_ui_board.py` vì file đó tự bỏ qua khi thiếu Tk (T-B10 của spec board rev 4).
  - Phần App của T-B10: `App._control_room_theme()` với `kit.P = theme.DARK` rồi `theme.LIGHT` có `palette is kit.P`,
    `palette["name"]` là `dark`/`light`, mọi token của `STATE_STYLE`, `ALERT_STYLE` và `surf track line bg fg mut` tra
    được; các khoá cũ giữ nguyên (`tests/test_ui_app_smoke.py:132-136` vẫn đạt).
  - `_open_control_room` truyền `cfg=self.cfg` và `mascot_image=self._board_mascot_image` cho `ControlRoom` (stub ghi đối số).
  - `_board_mascot_image` trả `None` khi `mascots.png` ném lỗi (không ném ra).
- Sửa `ui/app.py`: `_control_room_theme` thêm `"palette": self.kit.P`; `_board_mascot_image(mid, mood, size)` dựng
  `PhotoImage` từ `mascots.png(mid, mood, size, P["name"], self._hue(), STATE_DIR / "mascots")` (PNG có alpha thật, không
  qua `gfx.to_photo`); `_open_control_room` truyền hai tham số mới.
- Kiểm U: `$PY -m unittest tests.test_ui_board_app tests.test_ui_board tests.test_ui_app_smoke tests.test_ui_control_room -v`;
  thêm `python3 -m unittest tests.test_ui_board_app -v` (Python thiếu Tk) để chứng minh file chạy không cần display.
- Kiểm Tay (theo "Thiết lập kiểm tay", `$PY main.py`): chín mục Tay của spec board, người dùng chạy. Mục 7 ghi số dòng
  log `board rebuild` và so với mục tiêu 100 ms / 300 ms / 30 ms ("Lỗi và an toàn" của board); vượt thì theo spec: hạ trần
  mặc định bằng một rev spec, không thêm cơ chế. Mục 8 thất bại (viền chữ nhật quanh sprite) thì dừng nhánh Board, Lead báo
  `PENDING_USER_ACTION` (rủi ro 2 của board đòi sửa spec).

### S3a-1 `ViewerServer`: định tuyến và chính sách

- Hạ tầng test (`tests/test_viewer.py`): `ViewerServer` thật cổng 0, `http.client` và socket thô, `clock` giả. Thư mục
  assets là thư mục tạm có `index.html`, `app.js`, `style.css` giả nhỏ và ba file vendor giả (`three.core.js` giả dài
  1,4 MB byte ngẫu nhiên để đủ cỡ cho V18b ở S3a-2), cùng `mock.patch.dict(viewer.VENDOR_SHA256, {...băm của file giả...})`.
  Test không cần mạng và không cần S4a; kiểm chéo hằng thật với file thật nằm ở S4c.
- Test trước: V1 đến V16, V20 đến V29 và G1; V8 ở slice này phủ các mã `200 304 400 403 404 405 500 501 505` (mã `414`, `431`
  thuộc S3a-2); H4 đến H7 nằm ở slice này (V8, V11, V12, V27). V24 theo spec viewer rev 6 (không cần Tk: `page_strings`,
  `PAGE_STRING_KEYS`, `/api/strings`, không có tham số `lang`), cộng một test so `viewer.PAGE_STRING_KEYS` với danh sách tên
  trong `tests/test_i18n_new_keys.py` của S1b.
- Thứ tự đỏ → xanh gợi ý: V27, V1, V2, V3 (lớp, bind) → V4, V5, V9, V10, V22 (bảng định tuyến, file nạp một lần) → V6,
  V7, V8, V11 (Host, Origin, header, phương thức, H4, H5) → V12 (log, H7) → V13, V14 (vòng đời) → V15, V16, V20, V23,
  V25, V26, V28, V29 (slot, `publish`) → V21 (sprite) → `page_strings`, V24.
- `SPRITE_SIZE` theo kết quả Đ1. V20 theo spec viewer rev 6 (erratum E2), bốn ca: (a) đã có payload thì giữ bytes, ETag,
  `ts` cũ và `prev` vẫn cập nhật; (b) chưa có thì HTTP 200 body cố định `ready:false, reason:"too_large"`; (c) đúng
  1 048 576 byte vẫn phục vụ; (d) không đáp ứng nào mang `scene` > 1 MiB.
- Đo U+đo: lặp lại phép đo Đ2 bằng `ViewerServer(...).publish(big_org(), ts)` thật (gồm khoá slot, mã hoá, ETag), 200 lần,
  median ≤ 20 ms; Lead ghi cạnh số Đ2.
- Kiểm: `$PY -m unittest tests.test_viewer -v` (không test nào của file này cần Tk);
  `git diff --stat main -- pet_tracker/hooks.py tests/test_hooks.py` rỗng; `$PY -m unittest tests.test_hooks -v`.
- Security soát: viewer S1 đến viewer S15, viewer S17 đến viewer S26 phía server, H4 đến H7, điểm vá cấp module.

### S3a-2 Cứng hoá kết nối H1 đến H3

- Test trước (`tests/test_viewer_limits.py`, cùng hạ tầng file giả của S3a-1, `CONNECTION_DEADLINE_SEC` hạ xuống 3 và
  `timeout` mỗi `recv` hạ xuống 1 trong test): V17, V17b, V18, V18b, V19, và phần `414`, `431` của V8 (header bảo mật và
  body cố định).
- Sửa `viewer.py`: lớp `ViewerHTTPServer` đếm kết nối trong `process_request` (giảm trên mọi đường, kể cả `Thread.start` ném
  `RuntimeError`), bảng hạn `{socket: hạn}` thi hành trong `service_actions()` bằng `shutdown(SHUT_RDWR)`, chỉ thread xử lý
  `close()`; handler đọc dòng yêu cầu và header với giới hạn H3. Không thêm thread, không thêm timer (Quyết định Y).
- Kiểm: `$PY -m unittest tests.test_viewer_limits tests.test_viewer -v`; chạy `tests.test_viewer_limits` ba lần liên tiếp
  để bắt test chập chờn theo thời gian, ghi thời gian chạy vào báo cáo.
- Security soát: viewer S16, H1 đến H3, Quyết định J và Y, và cách V11 (c), V17b, V18b chứng minh chúng.

### S3b Vòng đời viewer trong App

- Test trước:
  - `tests/test_ui_viewer_app.py` (Tk, hạ tầng của `tests/test_ui_app_smoke.py`, `viewer.ViewerServer` giả,
    `webbrowser.open` stub): W1 đến W8, W7b, W10.
  - `tests/test_viewer_wiring_static.py` (không Tk, không bao giờ bị bỏ qua): W9, W11, và một kiểm `ast` rằng
    `_open_3d_viewer` truyền `strings=viewer.page_strings(...)`.
- Sửa `ui/app.py`: `self.viewer = None` trong `__init__`; `_open_3d_viewer` (`strings = viewer.page_strings(i18n.lang())`,
  `hue` lấy một lần, `cache_dir = STATE_DIR / "mascots"`, `theme = theme.DARK`), thread mở trình duyệt chỉ
  `webbrowser.open` và `queue.put`, xử lý kết quả bằng `root.after(200, ...)` tối đa 10 lần (clipboard và toast ở main
  thread), `_viewer_tick` mỗi 5000 ms với hạn idle 120 giây, `_pump` gọi `publish` chỉ khi viewer có mặt và `ts` mới,
  `quit` gọi `viewer.stop()`. `ui/menus.py`: mục `isl.view3d` ngay dưới `isl.control`. Khoá i18n đã có từ S1b.
- Kiểm: `$PY -m unittest tests.test_ui_viewer_app tests.test_viewer_wiring_static tests.test_ui_app_smoke tests.test_i18n -v`.
  W1 đến W10 bị bỏ qua thì báo `unavailable` và slice chưa xong (Quyết định AB, N5).
- Không có Tay riêng: trang chưa có nên `start()` thật thất bại; kiểm tay đường mở viewer nằm ở S4c.
- Security soát: viewer S10 (W4, W9), viewer S15 (W4, W11), token và URL không vào log.

### S4b `tools/viewer_demo.py`

- Test trước (`tests/test_viewer_demo.py`, không Tk, không mạng ngoài): hàm dựng `org` của demo ở cỡ mặc định cho Layout 48
  bàn đầy; cờ cỡ nhỏ có chuỗi độc của M6 (`<img src=x onerror=alert(1)>`, bidi) trong `description` và tên; hàm dựng
  `scene` của `--hostile` có đủ khoá và giá trị liệt kê ở M16; với `--hostile`, sau `publish` đáp ứng `/api/layout` chứa
  `scene` đó (chứng minh cơ chế vá ở "Hợp đồng S3a-1 → S4b"); demo khởi động rồi dừng `ViewerServer` cổng 0 với thư mục assets
  giả như S3a-1.
- Làm: công cụ stdlib theo mục `tools/viewer_demo.py` của spec (cờ `--freeze`, `--hostile`, cỡ tuỳ chọn), in URL ra stdout;
  không đóng gói (Quyết định H).
- Kiểm: `$PY -m unittest tests.test_viewer_demo -v`.

### S4c Trang web

- Test trước (`tests/test_viewer_assets.py`): A1, A2 (gồm quy tắc `// idx` và `switch` theo `kind`), A7, A8 (mọi khoá
  `str("...")` của `app.js` thuộc `viewer.PAGE_STRING_KEYS` và ngược lại, không chuỗi giao diện viết cứng), và kiểm chéo vendor
  còn lại của A4: `viewer.VENDOR_SHA256` bằng SHA-256 của ba file thật trong `assets/viewer/vendor/` và bằng giá trị trong
  `VERSION.txt`. Thêm một test khởi động `ViewerServer` thật trên `assets/viewer/` thật: `start()` trả `True` (file thật đủ
  và đúng băm).
- Làm: `index.html`, `app.js`, `style.css` theo "Cảnh 3D" và "Trang". Chuỗi của trang chỉ lấy từ `/api/strings` (39 khoá
  đã có từ S1b); slice này không sửa `i18n.py`.
- Kiểm U: `$PY -m unittest tests.test_viewer_assets tests.test_viewer tests.test_i18n -v`.
- Kiểm Tay (theo "Thiết lập kiểm tay"; app từ source `$PY main.py` và `$PY tools/viewer_demo.py`): M1 đến M11, M13 đến
  M19. AI chạy M8, M13, M18; người dùng chạy phần còn lại trên Chrome và Safari. M10 ghi FPS, draw call, số texture; không
  đạt thì theo rủi ro 4 của viewer (chuyển sang `InstancedMesh` trong `app.js`, đo lại), vẫn không đạt thì xin hạ cỡ mục
  tiêu bằng rev spec. M2 thấy vi phạm Trusted Types, hoặc M18 thấy URL trong `argv`: Lead báo `PENDING_USER_ACTION` (Quyết
  định T và rủi ro 6 đòi rev spec).
- Security soát: CSP và trusted types (M2), sink HTML (A1, A2, M6), tra cứu bằng `Map`/`Object.hasOwn` (viewer S25, M16),
  `spriteUrl` allowlist, không điều hướng.

### S5a Đóng gói

- Test trước (`tests/test_viewer_assets.py`): A5 theo spec viewer rev 6 (erratum E1), tức chỉ `build_macos.sh` và
  `build.ps1` (không `Wisp.spec`): chuỗi `assets/viewer` trong chỉ thị `--add-data`, đoạn kiểm bảy file kèm `exit 1`/`throw`.
- Sửa: `build_macos.sh` thêm `--add-data "assets/viewer:assets/viewer"` và vòng `find` ngay sau PyInstaller, trước
  `codesign`; `build.ps1` thêm `--add-data "assets\viewer;assets\viewer"` và vòng `Get-ChildItem` sau dòng kiểm
  `$LASTEXITCODE`. Đúng nguyên văn mục "Đóng gói assets" (Quyết định I).
- Kiểm U: `$PY -m unittest tests.test_viewer_assets -v`.
- Kiểm Tay M12 (macOS; Windows `unavailable`):
  - Trước khi chạy, Lead xin người dùng cho phép **ngay lúc đó**, nêu rõ: `build_macos.sh:17` chạy
    `"$PY" -m pip install --upgrade "pyinstaller==6.22.3" certifi` (cần mạng; nếu `PYTHON` là Python python.org toàn cục thì
    đổi gói của interpreter đó). Đề xuất kèm theo: tạo venv từ `/usr/local/bin/python3.13` trong thư mục tạm và chạy với
    `PYTHON=<venv>/bin/python` để không đổi interpreter toàn cục. Người dùng chọn.
  - Chạy trên bản sao, không trên cây làm việc: các slice đã commit thì `git worktree add <thư mục tạm>/wisp-m12 HEAD`;
    còn file chưa commit thì chép repo bằng `rsync -a --exclude dist --exclude build ./ <thư mục tạm>/wisp-m12/`. Trong bản
    sao: build một lần (đạt, bảy file có mặt), xoá một file trong `assets/viewer` của bản sao rồi build lại (thất bại, ghi
    thông báo), mở `dist/Wisp.app` của lần build đạt và chạy M1, M3. Không xoá file nào trong cây làm việc gốc. Xong thì
    `git worktree remove` hoặc xoá bản sao.
  - Kết quả ghi vào bằng chứng.

### S5b Tài liệu

- `docs/GUIDE.md`: mục Board theo "Tài liệu" của spec board rev 4, và mục "3D office" theo "Tài liệu" của spec viewer.
- `CHANGELOG.md` `[Unreleased]`: Added (Board và hai khoá config, 3D office), Fixed (dòng "Loại agent", S0), Security (theo
  "Tài liệu" của viewer); ghi "chưa kiểm trên Windows". (`config.example.json` của "Tài liệu" board đã làm ở S1.)
- `README.md`, `README.vi.md`: một dòng giấy phép three.js (MIT) trỏ tới `assets/viewer/vendor/LICENSE`.
- Kiểm: `$PY -m unittest discover -s tests` vẫn xanh.

## Bằng chứng

File `docs/plans/2026-10-30-board-and-3d-viewer-evidence.md`, do **Lead** tạo khi có số đo đầu tiên và là người ghi duy
nhất (các slice song song không cùng ghi một file). Department gửi số và kết quả trong báo cáo; người dùng gửi kết quả Tay
cho Lead. Mỗi mục là một khối:

```
## <mã slice hoặc Đ> <tên>, <ngày>
- commit: <hash>  python: <phiên bản>  máy: <model, tải>
- lệnh: <lệnh đúng như đã chạy>
- kết quả: <số hoặc bảng; Tay: từng mục M/board kèm pass/fail/unavailable và một dòng ghi chú>
- kết luận: <đạt | vượt ngưỡng: hành động theo plan | PENDING_USER_ACTION: lý do>
```

Nội dung bắt buộc: Đ1, Đ2, T-L12 (S1), `publish` thật (S3a-1), thời gian chạy `tests.test_viewer_limits` (S3a-2), đầu ra
năm bước tái lập checksum (S4a), Tay của S2a-3 và S4c, M12 (S5a), `diff` của `~/.claude/settings.json` trước và sau mỗi
phiên Tay, và danh sách test `skipped` của mỗi slice có test Tk.

## Rủi ro mang từ spec

| Rủi ro | Phủ |
|---|---|
| Windows chưa kiểm (board 1; viewer 1, H6, viewer S23) | rủi ro đã chấp nhận trong spec. Logic đường dẫn `\` ở C7; V27 (b) tiêm hằng `SO_EXCLUSIVEADDRUSE`; `build.ps1` chỉ kiểm chuỗi (A5). Runtime: `unavailable`, ghi CHANGELOG (S5b). |
| PNG alpha trên Canvas (board 2) | Tay mục 8 ở S2a-3; thất bại thì dừng nhánh Board, rev spec. |
| Chi phí rasterize mascot, GIL (board 3, viewer 3, 15) | Đ1 trước code, kiểm median và max; T-B6 chứng minh ngân sách 8 ảnh; V21 chứng minh khoá dựng và cache. |
| Hiệu năng Board chưa đo (board 3, 7) | T-L12 (số vào bằng chứng); Tay mục 7 so mục tiêu 100/300/30 ms. |
| `publish` trên main thread (viewer 4) | Đ2 và đo lại ở S3a-1, ngưỡng 20 ms, hành động P5. |
| Hiệu năng cảnh 3D (viewer 4, 11, 12) | M10, M15 ở S4c; `InstancedMesh` là bước kế tiếp theo spec. |
| Lỗi `type`/`agent_type` (board 8) | S0 trước mọi slice; fixture `org.build` ở mọi test mới. |
| Detail trùng giữa Board và cây (board 9) | S2a-1 bước 1, test so hai đầu ra. |
| Board và viewer xếp bàn khác nhau (board 10, viewer 5) | T-L16 và V25 khẳng định là hành vi chấp nhận; M14 ghi nhận. |
| Mascot trùng giữa phòng ban, lane đủ 4 (board 4, 5) | chấp nhận như spec; T-L6 khoá hành vi. |
| Trần "đến trước được trước", không ân hạn (board 6) | T-L8 khoá hành vi. |
| Màu `done`/`running` trùng (board 12) | chấp nhận; Tay mục 1, 4 kiểm phân biệt bằng hình và mood. |
| DoS cục bộ, slowloris, desync (viewer 14, J, Y) | H4 ở S3a-1 (V11); H1 đến H3 ở S3a-2 (V17, V17b, V18, V18b, V19); M19. |
| Token lộ qua argv, lịch sử, clipboard (viewer 6, 16, E) | V12, W4, W9; M18 trên Python 3.13. |
| Trusted Types, three r186 (viewer 13, T) | M2; vi phạm thì rev spec. |
| Vendor đã vá một dòng (viewer 18, B) | S4a chạy lệnh tái lập; A4; kiểm chéo ở S4c. |
| `datas` trong `.app`, codesign (viewer 2) | vòng kiểm theo tên đường dẫn (S5a); M12 trên bản sao. |
| Logic JS chỉ kiểm tay (viewer 17, W) | M5, M7, M9, M14, M16, M17 ở S4c; phía server C1 đến C16. |
| Chuỗi agent không tin cậy (cả hai spec) | S2a-1, S2a-2 (`sanitize`, T-B5); S2b (C7, C9, C16); S4c (A1, A2, M6, M16); Security soát cả ba. |

## Erratum spec

Các lỗi tìm thấy khi lập plan và review plan; cả hai spec đã sửa (board rev 4, viewer rev 6). Mã trong cột "Mã spec" là mã
errata của chính spec viewer; spec board rev 4 không đánh mã errata.

| Lỗi | Spec, mục | Sửa | Mã spec | Trạng thái |
|---|---|---|---|---|
| chữ lặp "10. Chữ ký `office_layout`10. Chữ ký..." | board, "Rủi ro mở" số 10 | bỏ phần lặp | - | đã sửa trong board rev 4 |
| T-B10 đứng trước T-B9 | board, bảng `tests/test_ui_board.py` | đổi thứ tự | - | đã sửa trong board rev 4 |
| nói test cây dựng dữ liệu dạng đầu vào; thật ra fixture cây đã dựng bằng `org.build` (`tests/test_control_room.py:55`), và triệu chứng nhóm phòng ban không xảy ra vì `org.department` trả `name or agent_type`; chỉ dòng "Loại agent" rỗng | board, "Rủi ro mở" số 8 | sửa mô tả | - | đã sửa trong board rev 4 |
| phần App của T-B10 nằm trong file test bị bỏ qua khi thiếu Tk; tham số `theme` che module `theme`; không có ngưỡng rasterize; không có mục Tài liệu | board, T-B10, "Tab", rủi ro 3, "Tài liệu" | mẫu stub-import; import tên khác; ≤ 100 ms; thêm mục | - | đã sửa trong board rev 4 |
| sửa `Wisp.spec`, nhưng file này bị `.gitignore:4` bỏ qua và sinh lại mỗi lần build | viewer, "Đóng gói assets", A5 | bỏ `Wisp.spec`; chỉ hai script build | E1 | đã sửa trong viewer rev 6 |
| V20 đòi `too_large` còn "Chia sẻ dữ liệu giữa thread" nói "tương tự" (giữ payload cũ) | viewer, V20 | giữ payload cũ khi đã có; body cố định `too_large` khi chưa có; bốn ca | E2 | đã sửa trong viewer rev 6 |
| `lang` và `strings` chồng nhau; khoá nào ra trình duyệt chưa rõ | viewer, "Giao diện module", "Trang", V24, A7, A8 | bỏ `lang`; `page_strings`, `PAGE_STRING_KEYS` (39 khoá `v3d.page.*`) | E3 | đã sửa trong viewer rev 6 |
| bước 3 so `LICENSE` với `viewer.VENDOR_SHA256`, nhưng dict đó không có `LICENSE` | viewer, "Lệnh tái lập checksum" | so với bảng "Dữ kiện đã kiểm" và `VERSION.txt` | E4 | đã sửa trong viewer rev 6 |
| mã S1 đến S26 trùng dạng mã slice; nhãn "T2" của test assets trùng tier | viewer, "Lỗi và an toàn", "Kiểm thử" | ghi chú mã S; đổi nhãn thành "nhóm test assets" | E5, E6 | đã sửa trong viewer rev 6 |

## Quyết định

Đã duyệt bởi người dùng (2026-10-30):
- Bỏ `Wisp.spec` khỏi S5a và A5; đóng gói chỉ qua hai script build cộng vòng kiểm file.
- Commit từng slice khi người dùng cho phép sau mỗi lượt review; rollback `git revert`; không push.
- M12 được chạy `build_macos.sh` ở S5a, nhưng xin lại quyền mạng và pip ngay lúc đó; chạy trên bản sao hoặc worktree.
- P1. Trình thông dịch kiểm chuẩn `/usr/local/bin/python3.13`; thay thế `brew install python-tk@3.12`. Chấp nhận theo đề xuất.
- P3. Đ1 kiểm cả median và max: viewer median ≤ 150 ms và không ảnh nào > 150 ms, không đạt thì lùi `SPRITE_SIZE` 96 rồi 64
  (lùi cỡ đã được chấp nhận); Board tổng 8 ảnh lạnh ≤ 100 ms, vượt thì xin rev spec. Đo với `_shapes.cache_clear()` mỗi cỡ.
- P5. `publish` vượt 20 ms: tối ưu trong hợp đồng, vẫn vượt thì dừng và hỏi. Chấp nhận theo đề xuất.

Chi tiết của plan (không cần duyệt riêng, liệt kê để Review theo dõi):
- P2. Dùng đúng tên spec viewer rev 6 đề xuất: `viewer.page_strings(lang)` và `viewer.PAGE_STRING_KEYS`, tiền tố
  `v3d.page.`; `ViewerServer` không có `lang`. Plan không đổi tên.
- P4. Tách hàm detail dùng chung ở S2a-1, không gộp vào S0 (S0 là bản vá hẹp; hàm dùng chung chỉ có consumer thứ hai khi
  Board đến).
- P6. Body > 1 MiB theo V20 của spec viewer rev 6 (E2); không còn là lựa chọn của plan.
- P7. Mọi khoá i18n mới ở một slice sớm (S1b), vì V24 của S3a-1 cần đủ 39 khoá `v3d.page.*` và để `i18n.py` chỉ có một
  người ghi.
- P8. Tài liệu Board theo mục "Tài liệu" của spec board rev 4; không còn là lựa chọn của plan.
- P9. Test server dùng file vendor giả và băm vá, không phụ thuộc S4a; kiểm chéo hằng thật với file thật ở S4c.

## Điều kiện xong

Trạng thái cuối mong đợi:
- `$PY -m unittest discover -s tests` xanh, số test `skipped` bằng 0 trên máy dev; mọi test bị bỏ qua ở môi trường khác được
  báo `unavailable` kèm lý do.
- File bằng chứng có mọi nội dung bắt buộc ở mục "Bằng chứng"; mọi số trong ngưỡng, hoặc phần vượt đã có quyết định của
  người dùng.
- Tay đã chạy trên macOS: chín mục board (S2a-3), M1 đến M11 và M13 đến M19 (S4c), M12 (S5a). Khi các mục Tay còn chờ người
  dùng, trạng thái của plan là `PENDING_USER_ACTION`, không phải `COMPLETE`.
- `git diff --stat main` không có `pet_tracker/hooks.py`, `tests/test_hooks.py`, `pet_tracker/org.py` (G1, viewer S20).
- Review đã duyệt mọi slice; Security đã duyệt S2a-2, S2b, S3a-1, S3a-2, S3b, S4a, S4c; không còn finding mở.
- Không thêm dependency pip vào dự án; CHANGELOG chỉ `[Unreleased]`; không push, không phát hành; mọi commit có sự cho phép
  của người dùng.

Windows là rủi ro đã chấp nhận trong cả hai spec, không phải bằng chứng bắt buộc: mọi mục Windows ghi `unavailable` và không
chặn điều kiện xong.
