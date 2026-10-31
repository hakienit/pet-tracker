# Viewer 3D: xem "văn phòng" của các agent trong tab trình duyệt

Trạng thái: rev 6, **người dùng đã duyệt (2026-10-30), errata sau review plan** (E1 đến E6, không đổi quyết định nào; E7 `surrogatepass` ở quy tắc 7 và E8 `live` sau trần ở quy tắc 8 và C12, E9 nhãn `sid[:8]` ở quy tắc 5, ghi 2026-10-31 sau Review S2b): bỏ `Wisp.spec` khỏi đóng gói (E1), chốt payload > 1 MiB (E2), chốt `strings` và bỏ `lang` khỏi `ViewerServer` (E3), sửa bước 3 của lệnh tái lập checksum (E4), ghi chú mã S (E5), đổi nhãn "T2" (E6).
Rev 5: người dùng đã duyệt (2026-10-30). Mọi "Quyết định mới (cần duyệt)" A đến AB của rev 4 đã được duyệt; riêng **B và I theo phương án rẻ hơn của Review**:
B là vendor `OrbitControls.js` của three r186 (không tự viết orbit), I là vài dòng `test -f`/`Test-Path` trong script build (không có `tools/check_bundle.py`). Mục cuối đổi tên thành "Quyết định đã duyệt".
Rev 2 khớp spec với Layout thật của spec board 2.5D (lồng floors/clusters/desks, toạ độ cục bộ theo sàn, `prev`, `styles`, `seed`, `ref`). Rev 3 tích hợp báo cáo của `les-security`
(M1, M2, L1 đến L9) và `les-review` (M4, M5, M7, L5r, L6r, L9r): cứng hoá server, đưa việc Tk của đường mở trình duyệt về
main thread, cam kết của board thay cho "yêu cầu còn lại", test cho phần nối dây App. Rev 4 tích hợp lần kiểm lại của `les-security` (N1 đến N7): thi hành hạn tổng và bộ đếm kết nối,
trang vẫn poll ở `disconnected`, `key` HMAC có khoá, phủ tra cứu phía trang, báo `unavailable` khi test Tk bị bỏ qua. Rev 5 chỉ áp dụng quyết định của người dùng (B, I, trạng thái, phụ thuộc S0); các hành vi người dùng thấy giữ nguyên, trừ
những khác biệt phím tắt do dùng `OrbitControls` được liệt kê ở "Cảnh 3D".
Phạm vi: sub-project 4. Dùng lại org model (sub-project 1, `pet_tracker/org.py`) và **Layout chung** của spec board
2.5D (`docs/specs/2026-10-30-board-2-5d-design.md`, sub-project 3). Spec này không định nghĩa lại layout hay bảng
state; nó chỉ định nghĩa bộ chuyển đổi `viewer_payload` làm phần việc viewer cần mà Layout không có (mục "Dùng Layout
chung của board").
**Phụ thuộc: slice S0** (sửa lỗi `type`/`agent_type` giữa `org.py:187` và `control_room._session_rows` của Control room) **làm trước** slice viewer; người dùng đã duyệt thứ tự này. Viewer không đọc khoá `type` hay `agent_type`
(chỉ `department`, `description`, `tokens`, `started`, `last_activity`, `state`), nên S0 không đổi hợp đồng của spec này; nó chỉ bảo đảm fixture dựng bằng `org.build` giống dữ liệu thật.
Risk R1 (chỉ tài liệu), nhưng tính năng mở một server local nên spec đủ chặt để `les-security` review trước khi
code.

## Mục tiêu

Board 2.5D cho thấy cả "công ty IT" trên một mặt phẳng trong cửa sổ Tk. Viewer 3D cho cùng dữ liệu đó trong không
gian 3D xoay được, để nhìn tổng thể khi có nhiều dự án và nhiều session:

- Một mục "3D office" trong popup chuột phải của island mở một tab trình duyệt mặc định, hiện sàn văn phòng 3D:
  project là sàn, team là cụm bàn, session là bàn có mascot, subagent là mascot nhỏ theo phòng ban, task nền là vật
  nhỏ trên bàn.
- Camera xoay (orbit), zoom, kéo (pan); có bóng đổ đơn giản; mascot là sprite luôn quay về camera.
- Cảnh tự cập nhật theo dữ liệu thật của Wisp, chỉ xem, không điều khiển được agent.
- Wisp chỉ mở server khi người dùng mở viewer và tắt khi không còn tab nào xem. Mọi tài nguyên (kể cả three.js) đi
  kèm bản cài, không gọi mạng ngoài.

## Ngoài phạm vi

Âm thanh; chỉnh layout bằng tay (kéo bàn, đổi chỗ); lịch sử session đã đóng; điều khiển agent (focus cửa sổ, kill,
gửi lệnh) và mọi thao tác ghi; push realtime (SSE, WebSocket; chỉ polling); model 3D cho mascot (chỉ sprite 2D
billboard); truy cập từ máy khác hoặc từ mạng LAN; chia sẻ URL cho người khác; nhúng viewer vào Tk; đăng nhập,
cookie, phiên người dùng; thay đổi hành vi của `HookServer`; thay đổi ngôn ngữ của trang khi đang mở.

## Khái niệm

| Khái niệm | Nghĩa |
|---|---|
| Viewer | cả tính năng: server local + trang web + cảnh three.js |
| ViewerServer | HTTP server stdlib của Wisp, chạy trên thread riêng, tồn tại từ lúc mở viewer đến lúc không còn ai xem |
| Token | chuỗi ngẫu nhiên nằm trong đường dẫn, sinh mới mỗi lần ViewerServer được tạo |
| Layout chung | kết quả hàm thuần `office_layout(org_out, cfg, prev=None)` trong `pet_tracker/office.py`, do spec board 2.5D sở hữu: `Layout{version, limits, styles, floors[], more}` lồng sàn > cụm > bàn > worker/device, toạ độ ô cục bộ theo từng sàn |
| Bộ chuyển đổi | hàm thuần `viewer_payload(layout, org_out, theme, mascot_ids, key_secret) -> dict` trong `pet_tracker/viewer_payload.py` (spec này sở hữu): làm phẳng Layout thành payload cho trang |
| Payload | dict JSON của bộ chuyển đổi: `schema`, `nodes[]`, `legend`, `palette`, `bounds`, `more`, `hidden`, `live`; viewer sở hữu `schema` của nó |
| Node | một phần tử phẳng của payload: `project`, `team`, `session`, `subagent`, `bgtask` hoặc `overflow`; có `key` (HMAC-SHA256 có khoá bí mật của khoá Layout, cắt 16 hex) |
| Slot | ô nhớ có khoá giữa main thread (ghi) và thread của server (đọc), chỉ chứa bytes bất biến |
| Sprite | ảnh PNG của một mascot ở một mood (`mascots.png`), hiện bằng `THREE.Sprite` (luôn quay về camera) |
| Idle | khoảng thời gian không có request hợp lệ nào tới `/api/layout` |

## Dữ kiện đã kiểm

Trong repo (đã đọc, không kiểm lại):

- `hooks.HookServer` (`pet_tracker/hooks.py:151-209`): `ThreadingHTTPServer(("127.0.0.1", port), Handler)`, thread
  `daemon`, token trong đường dẫn `/wisp/<token>`, `log_message` bỏ trống, `stop()` gọi `shutdown()` rồi
  `server_close()`. Cổng cố định 47615 được ghi trong `settings.json` của Claude Code, server sống suốt đời app.
- `mascots.png(mid, mood, size, theme, hue, cache_dir)` (`pet_tracker/mascots.py:126`): 40 mascot (`m01`..`m40`) x
  5 mood (`idle run wait done quota`); ảnh có cạnh `canvas_size(size) = round(size * 1.28)`; khoá cache trên đĩa dựng
  từ `mid`, `mood`, `size`, `theme`, `int(hue)`; nếu `mid` lạ thì `mascots.get` lùi về mascot đầu (không lỗi).
- `Collector` chạy thread riêng, `_pump` (`ui/app.py`, khoảng dòng 995-1061) chuyển snapshot sang main thread; snapshot
  có khoá `org` (có thể `None`). `org.build` làm sạch mọi chuỗi từ agent (bỏ ký tự điều khiển, bidi, cắt 200 ký tự).
- Popup chuột phải: `ui/menus.py:138` (mục "Control room"), `App._open_control_room` (`ui/app.py:631`). `App.quit`
  (`ui/app.py:1063`) dừng `hook_server`.
- Đóng gói: `build.ps1` (`--add-data "assets\fonts;assets\fonts"`... ở `build.ps1:56-59`, Windows) và `build_macos.sh` (`--add-data "assets/fonts:assets/fonts"`... ở `build_macos.sh:36-38`, macOS) gọi PyInstaller bằng cờ CLI và liệt kê
  tay từng thư mục con hoặc file của `assets/` (`fonts`, `sounds`, `mascots.json`, và `wisp.ico` ở Windows), nên `assets/viewer/` mới phải được thêm vào **hai script này**. `Wisp.spec` là file **sinh ra** (PyInstaller ghi lại mỗi lần
  build) và bị git bỏ qua (`.gitignore:4`, `*.spec`): **không sửa và không kiểm** (errata E1, từ review plan).
- `assets.asset_path()` trả `sys._MEIPASS/assets/...` khi chạy bản PyInstaller và `<repo>/assets/...` khi chạy source.

three.js (đã kiểm ngày 2026-10-30 trên registry npm; tải về thư mục tạm và tính checksum):

- Phiên bản chọn: **three 0.186.0**, publish 2026-09-08T19:25:22Z (hơn 7 tuần trước ngày spec; bản `latest` lúc kiểm
  là 0.187.0, publish cùng ngày 2026-10-30, nên không dùng). Giấy phép MIT.
- Nguồn: `https://registry.npmjs.org/three/-/three-0.186.0.tgz`. SHA-256 của tarball
  `61eeff9d7616005c9a481c796f52287d81fbbbc0d55eaca5565322924252c1aa`; `dist.integrity` (SHA-512) của registry
  `sha512-cr/fIM2ddMSVbYVgkfD4jLJv7Fh/8ZTjvo+7gQeSVGUZHxpx9FDwoL5iC7hUz/LiRA8wMbqfnb90xKfm1/HHkQ==`, khớp với
  SHA-512 tự tính lại từ tarball đã tải.
- **Tarball npm không có bản minify** (không có `three.module.min.js`, không có `three.min.js`). Thư mục `build/` có
  `three.module.js`, `three.core.js`, `three.cjs`, `three.tsl.js`, `three.webgpu*.js`. `three.module.js` import
  `./three.core.js` bằng đường dẫn tương đối. Bản `.min.js` trên jsDelivr do jsDelivr tự minify (header file ghi
  "Minified by jsDelivr", cảnh báo không dùng SRI), checksum không do dự án three.js công bố: **không dùng**.
- File sẽ đóng gói (SHA-256 tính từ tarball ở trên):

  | File trong tarball | Đường dẫn trong Wisp | Kích thước | SHA-256 |
  |---|---|---|---|
  | `package/build/three.module.js` | `assets/viewer/vendor/three.module.js` | 662 772 B | `9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea` |
  | `package/build/three.core.js` | `assets/viewer/vendor/three.core.js` | 1 458 113 B | `9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6` |
  | `package/examples/jsm/controls/OrbitControls.js` (**đã vá đúng một dòng**, xem dưới) | `assets/viewer/vendor/OrbitControls.js` | 40 767 B (bản gốc 40 755 B) | `30386f7141d5ce5d5e0a3ab643e4eb16265f4564466108105ce449857f62fdda` (bản đã vá); SHA-256 của bản gốc trong tarball: `3d79d07ecb686b4e5d93232eedab255331c1beef711e13164eaa1f68655a5f2b` |
  | `package/LICENSE` | `assets/viewer/vendor/LICENSE` | 1 081 B | `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc` |

- **Không cần `eval`**: tìm trong ba file nguồn (`three.module.js`, `three.core.js`, `OrbitControls.js`) thấy 0 lần `eval(`, 0 lần `new Function`, 0 lần `import(`, 0 lần
  `innerHTML`, 0 lần `importScripts`. Có `fetch(` và `XMLHttpRequest` trong `three.core.js` (chỉ ở `FileLoader`, viewer
  không dùng loader nào ngoài `TextureLoader`). CSP vì thế không cần `unsafe-eval`. `PCFSoftShadowMap` đã bị gỡ ở
  r186 (code in cảnh báo và dùng `PCFShadowMap`): viewer dùng `PCFShadowMap`.
- Hệ quả của bản không minify: ba file nặng khoảng 2,2 MB (662 772 + 1 458 113 + 40 767 byte), phục vụ qua localhost nên chấp nhận. Hệ quả của
  `three.module.js`: nó import `./three.core.js`, nên trang phải nạp bằng `<script type="module">` và URL tương đối
  (không dùng importmap, vì importmap là script nội tuyến).
- **`OrbitControls.js`** (Quyết định B, đã chọn phương án vendor): nguồn `package/examples/jsm/controls/OrbitControls.js` trong **tarball npm đã ghim ở trên** (không lấy từ CDN). File nhập từ `'three'` bằng tên trần
  ở **đúng một chỗ** (câu `import { ... } from 'three';` ở dòng 1 đến 12; dòng 12 là `} from 'three';`; không có `import` nào khác), mà tên trần cần importmap nội tuyến (trái CSP "không inline script"). **Bản vá: đúng một dòng**,
  dòng 12: `} from 'three';` thành `} from './three.module.js';` (lệnh tái lập: `sed "s#^} from 'three';\$#} from './three.module.js';#" OrbitControls.js`). Các tên file nhập (`Controls`, `MOUSE`, `Quaternion`, `Spherical`,
  `TOUCH`, `Vector2`, `Vector3`, `Plane`, `Ray`, `MathUtils`) đều được `three.module.js` r186 xuất (đã kiểm). Bản đã vá khác bản gốc đúng một dòng (`diff` ra một dòng đổi). Không có `eval(`, `new Function`, `innerHTML`, `import(`; chỉ
  gán `domElement.style.cursor` và `style.touchAction` (CSSOM, CSP không chặn) và `addEventListener` trên `domElement` và `document`.

Chưa kiểm: mọi thứ trên Windows; layout thư mục của `.app` do PyInstaller 6.22.3 tạo trên macOS (nơi `datas` nằm);
thời gian dựng một PNG mascot trên máy thật; phiên bản tối thiểu của từng trình duyệt với three r186.

## Dùng Layout chung của board

Spec board 2.5D sở hữu `office_layout(org_out, cfg, prev=None)` và bảng `STATE_STYLE`; viewer dùng nguyên chúng, không định
nghĩa lại hình học hay bảng state. Layout của board không đủ cho một cảnh 3D tuyệt đối, vì: toạ độ chỉ có nghĩa cục bộ trong
từng sàn; không có danh sách phẳng, `parent`, `bounds`; màu là tên khoá của theme chứ không phải hex; mascot là `seed`
chứ không phải id; tên hiển thị và chi tiết nằm trong `org_out` sau `ref`; `more` không có vị trí. Bộ chuyển đổi
`viewer_payload` lo đúng các việc đó và không làm gì khác.

### Cách viewer gọi `office_layout`

- Viewer **giữ `prev` riêng** (thuộc tính của `ViewerServer`, chỉ main thread đọc và ghi, trong `publish`). Nó **không** chia
  sẻ Layout hay `prev` với tab Board: hai nơi gọi độc lập, mỗi nơi giữ bộ nhớ gán ô của mình.
- Hệ quả (L-S5 của board): `prev` không lưu xuống đĩa và mỗi nơi có lịch sử khác nhau (Board bắt đầu lại khi đóng cửa sổ Control
  room, viewer bắt đầu lại khi server tắt), nên **cùng một dữ liệu có thể xếp bàn khác nhau giữa Board và viewer**. Trong một
  lần mở viewer, vị trí bàn ổn định theo L-S1. Spec này chấp nhận hệ quả đó (rủi ro 5).
- `cfg` truyền vào là `cfg` của app; viewer dùng chung hai khoá `board_max_desks`, `board_max_workers` của board, không thêm khoá.
- **Luật cho nơi gọi của board** (mục "Layout chung" và "Vòng cập nhật" của spec board): khi `office.valid_org(org)` sai, viewer
  **không** gọi `office_layout` và **không** thay `prev` (các slot không bị giải phóng bởi một lỗi `org.build` tạm thời); khi `org` hợp
  lệ trở lại thì gọi với `prev` cũ; `org` hợp lệ nhưng không có session là dữ liệu thật và giải phóng slot. Khác Board (hiện
  `cr.board.nodata` và không vẽ Layout cũ), viewer **giữ payload cũ** khi org không hợp lệ (theo yêu cầu của Lead) và để trang
  tự báo `stale` theo `ts` cũ.
- Spec board rev 3 thêm khoá `"palette"` vào theme của Control room (`th["palette"]`, phía Tk) và giữ `STATE_STYLE` hai phần
  (`desk`, `worker`): **không ảnh hưởng viewer**, vì viewer nhận `theme.DARK` trực tiếp qua `ViewerServer(theme=...)` và đọc `styles`
  của Layout, không đi qua theme của Control room.
- Sau mỗi lần `office_layout` thành công, `prev` được đặt thành Layout đó (kể cả khi bước chuyển đổi hoặc mã hoá JSON lỗi, để vị
  trí không nhảy ở lần sau).
- Viewer yêu cầu `office_layout` thuần và tái nhập (không trạng thái module, không sửa `org_out`, `cfg`, `prev`), vì hai nơi gọi
  nó độc lập (khớp mục "Layout chung" của board).

### Bộ chuyển đổi `viewer_payload`

Chữ ký: `viewer_payload(layout, org_out, theme, mascot_ids, key_secret) -> dict`. Nằm trong **module thuần riêng**
`pet_tracker/viewer_payload.py`, không trong `viewer.py` (Quyết định N). Lý do: `viewer.py` import `http.server`,
`threading`, `hashlib`, `pathlib` và đọc đĩa; tách ra thì module chuyển đổi kiểm được bằng `ast` như `office.py` (không
`tkinter`, `os`, `subprocess`, `pathlib`, `socket`, `http`, `threading`, không đọc đĩa) và test không cần dựng server.

Đối số: `layout` là kết quả `office_layout`; `org_out` là đúng đối số đã truyền vào lần gọi đó (để tra `ref`); `theme` là một
dict giao diện (`theme.DARK`, đã chọn ở quyết định L; hàm không import `theme`, nhận qua đối số để test truyền bảng giả);
`mascot_ids` là danh sách id mascot (`[m["id"] for m in mascots.all_mascots()]`). Hue không đi qua bộ chuyển đổi: nó chỉ ảnh
hưởng endpoint sprite do `ViewerServer` giữ (xem "Sprite"), nên không có trong chữ ký.

Hàm thuần: không đọc đĩa, không sửa đối số, đầu ra chỉ phụ thuộc đối số, chỉ gồm `dict`, `list`, `str`, `int`, `float`, `bool`,
`None` (`json.dumps(out, allow_nan=False)` không lỗi: mọi số là hữu hạn). `layout["version"]` khác `1` hoặc không phải dict
Layout: ném `ValueError` (viewer bắt ở `publish`, xem "Chia sẻ dữ liệu giữa thread"); Layout rỗng hợp lệ cho payload rỗng hợp lệ
(`nodes: []`, `bounds {"w": 0, "h": 0}`).

**Đầu ra** (`schema = 1`, do viewer sở hữu; `version` của Layout board chỉ là đầu vào, kiểm ở trên):

```
{"schema": 1,
 "bounds": {"w": int, "h": int},
 "palette": {"bg": "#rrggbb", "floor": "#rrggbb", "team": "#rrggbb", "line": "#rrggbb", "fg": "#rrggbb",
             "warn": "#rrggbb", "danger": "#rrggbb"},
 "legend": {"desk": {state: {"color": "#rrggbb", "mood": str, "marker": "ring"|"cross"|null}},
            "worker": {state: {"color": "#rrggbb", "mood": str, "marker": "ring"|"cross"|null}}},
 "more": {"desks": int, "stuck_desks": int},
 "hidden": int,                       # nút bị cắt bởi trần MAX_NODES
 "nodes": [Node],                     # cha đứng trước con
 "live": {key: {"tokens": int, "started": float|null, "last_activity": float|null}}}

Node{"key": str, "kind": "project|team|session|subagent|bgtask|overflow", "parent": str|null,
     "x": int, "y": int, "w": int, "h": int,        # toạ độ ô TUYỆT ĐỐI, xem dưới
     "state": str|null, "label": str, "sub": str,   # state: enum đã ép (xem quy tắc 3); null với project/team/overflow
     "mascot": str|null,                            # chỉ session và subagent
     "alert": int,                                  # chỉ session (số subagent stuck) và overflow toàn cục (số bàn có stuck);
                                                    # vắng khi bằng 0
     "count": int,                                  # chỉ overflow
     "counts": {state: int}}                        # chỉ overflow của bàn (overflow toàn cục KHÔNG có `counts`: board không có)
```

Quy tắc chuyển đổi (mỗi dòng có test, xem "Kiểm thử" C1 đến C16):

1. **Làm phẳng, cha trước con.** Duyệt Layout theo thứ tự sàn (xem 2), trong mỗi sàn theo thứ tự `clusters`, rồi `desks`, rồi
   `workers`, rồi `devices`, rồi nút `overflow` của bàn đó:
   - Floor thành `project` (`w, h` của floor; `parent: null`); Cluster thành `team` (`parent` là project); Desk thành `session`
     (`w = h = 2` theo Layout; `parent` là team); Worker thành `subagent` và Device thành `bgtask` (Layout không cho `w, h`:
     bộ chuyển đổi đặt `w = h = 1`; `parent` là session).
   - **Overflow**: bàn có `more.n > 0` sinh một nút `overflow` (`key` suy ra từ khoá bàn, `parent` là session, `x, y, w, h`
     bằng của bàn, `count = more.n`, `counts` = `more.counts` đã chuẩn hoá: khoá ngoài enum state thành `unknown`, giá trị
     kẹp về int >= 0). Layout có `more.desks > 0` sinh thêm một nút `overflow` toàn cục (`parent: null`, `count = more.desks`,
     `alert = more.stuck_desks` nếu > 0, **không có `counts`**: `Layout["more"]` chỉ có `desks` và `stuck_desks`) đặt ngay sau
     sàn cuối, xem 2. Bàn không vẽ không có nút (chỉ có số đếm).
2. **Đặt các sàn trong không gian 3D (toạ độ tuyệt đối).** Mỗi sàn có gốc cục bộ `(0, 0)` ở góc sau-trái. Các sàn xếp **thành
   một hàng dọc trục `x`, theo `level` tăng dần**, cách nhau lề cố định:
   - `FLOOR_PITCH = FLOOR_CLUSTER_COLS * CLUSTER_W + FLOOR_GAP = 2 * 15 + 6 = 36` ô (hai hằng đầu xuất từ `office.py`;
     `FLOOR_GAP = 6` là hằng của `viewer_payload.py`).
   - Gốc tuyệt đối của sàn là `(level * FLOOR_PITCH, 0)`; nút có toạ độ tuyệt đối `x = level * 36 + x_cục_bộ`,
     `y = y_cục_bộ`. Board cam kết `level` là `int >= 0`, duy nhất và `Layout["floors"]` sắp theo `level` (mục "Cam kết của
     board"); bộ chuyển đổi vẫn sắp lại theo `level` và, nếu `level` không phải số nguyên >= 0 hoặc trùng với sàn đứng trước
     (Layout dựng tay hoặc board vi phạm cam kết), dùng `max(level đã dùng) + 1` để không chồng sàn.
   - Lý do chọn hàng dọc `x`: L-S4 của board nói sàn lớn lên chỉ thêm ô về phía nam (`y` tăng), nên đặt các sàn cạnh nhau theo
     `x` cho vị trí tuyệt đối của mọi nút **không đổi** khi sàn khác lớn lên hay nhỏ đi; xếp dọc trục `y` buộc dời cả các sàn
     phía sau mỗi khi một sàn đổi cao (Quyết định O). Giá phải trả: hàng ngang dài khi có nhiều project (8 project dài
     `8 * 36 = 288` ô); camera tự đặt lại bằng `bounds` và người dùng pan.
   - Nút `overflow` toàn cục đặt tại `x = (level lớn nhất + 1) * 36`, `y = 0`, `w = h = 2`.
   - `bounds = {"w": max(x + w), "h": max(y + h)}` trên mọi nút (kể cả overflow toàn cục), tối thiểu 0.
3. **Màu và bảng state.** `legend` lấy từ `layout["styles"]` (chính `STATE_STYLE` của board), đổi từng tên khoá màu thành hex
   bằng `theme[tên]`: giá trị phải khớp `^#[0-9a-fA-F]{6}$`, ngược lại dùng `theme["idle"]`; xuất chữ thường. `mood` và
   `marker` chép nguyên (board cam kết `mood` luôn là `str`; viewer vẫn ép: mood phải thuộc `mascots.MOODS`, ngoài tập thành
   `idle`; marker thuộc `ring|cross|null`, giá trị khác thành `null`). `palette` lấy `bg`, `floor` (`theme["surf"]`), `team`
   (`theme["track"]`), `line`, `fg`, `warn`, `danger` từ `theme`. **Trang không giữ bảng thứ hai**: màu bàn, vật task nền, chấm
   chờ tải sprite, mood và marker đều đọc từ `legend`; màu sàn, cụm, nền và chữ đọc từ `palette`.
   **Ép `state` về enum** (chống khoá lạ như `constructor`, `__proto__` đi tới trang): `state` của `session` thuộc
   `idle|run|wait|done`, ngoài tập thành `idle`; `state` của `subagent` và `bgtask` thuộc
   `running|stuck|done|failed|killed|ended|unknown`, ngoài tập thành `unknown`. Mọi khoá trong `legend` cũng chỉ là các enum đó
   (khoá lạ của `layout["styles"]` bị bỏ). Trang tra `legend` và `palette` bằng `Map` hoặc `Object.hasOwn`, không bằng `obj[chuỗi]`
   (xem "Trang"). Vì `state` luôn có hàng trong `legend`, nút không bao giờ thiếu hàng; trang vẫn dùng hàng `idle` (desk) hoặc
   `unknown` (worker) nếu thiếu.
4. **Mascot.** Với session và subagent: `ids = mascot_ids`; `i = office.mascot_index(seed, len(ids))`; `mascot = ids[i]` nếu
   `i` không phải `None`; ngược lại không có trường. `seed` lấy từ Desk/Worker của Layout (bộ chuyển đổi không tự băm). Id đưa
   ra phải thuộc `mascot_ids`; mood không nằm trên nút mà lấy từ `legend` theo `state`. Device không có mascot.
5. **Nhãn và chi tiết, từ `org_out` qua `ref`.** `label` (tối đa 60 ký tự) và `sub` (tối đa 120 ký tự) được dựng, mỗi chuỗi
   chạy lại bộ làm sạch của `org.py` (bỏ ký tự điều khiển C0/C1, bidi, U+200B-U+200F, U+2028/U+2029, U+FEFF) rồi mới cắt:
   - `project`: `label = floor.name`, `sub = ""`.
   - `team`: `label` là tên thư mục cuối của `top` (cắt dấu phân cách cuối; nếu rỗng thì `top`), `sub = branch` (hoặc `""`).
   - `session`: `label = desk.name`, `sub = ""`; nếu `desk.name` bằng `session_id[:8]` (tên dự phòng của `claude_data`
     cho phiên chưa có tên) thì `label = ""` (errata E9, người dùng chọn 2026-10-31: S21 cấm session id trong payload).
   - `subagent`: `label = department` (của Layout); `sub` là `description` của worker trong `org_out`, tra theo `ref`
     (`[pi, ti, si, wi]` trong `projects[pi].teams[ti].sessions[si].workers[wi]`), `""` nếu `ref` hỏng hoặc worker không phải
     subagent hoặc `description` không phải chuỗi.
   - `bgtask`: `label = ""` và `sub = ""` (trang hiện tên loại từ chuỗi giao diện).
   - `overflow`: `label = ""`, `sub = ""` (trang hiện `+N`).
   - Tra `ref` an toàn: chỉ số ngoài khoảng, kiểu sai, `org_out` là `None` thì bỏ trường, không ném lỗi.
   - `live[key]` cho `subagent`: `tokens` (int >= 0), `started`, `last_activity` (số hữu hạn hoặc `null`), lấy từ worker qua
     `ref`; cho `bgtask`: `started`. Các số đổi liên tục nằm trong `live`, **không** trong `nodes`, để một thay đổi
     `tokens` không làm thay đổi `nodes` (phần mà trang diff).
6. **Cờ cảnh báo.** `session.alert = desk.alert.stuck` (int >= 0) và chỉ có trường khi lớn hơn 0; trang vẽ ring `warn` quanh
   bàn như board.
7. **Khoá.** `key` trong payload là `hmac.new(key_secret, <khoá Layout>.encode("utf-8", "surrogatepass"), hashlib.sha256).hexdigest()[:16]`
   (errata E7: `surrogatepass` để khoá chứa surrogate lẻ do agent đưa vào không làm `encode` ném lỗi; với chuỗi hợp lệ
   kết quả không đổi), với `key_secret` là
   `bytes` (16 byte) do **`ViewerServer` chọn một lần cho mỗi vòng đời server bằng `secrets.token_bytes(16)`** và truyền vào `viewer_payload`
   qua tham số (nên hàm vẫn thuần: không tự sinh ngẫu nhiên, không đọc đĩa, test truyền khoá cố định); `parent` dùng cùng cách. Khoá của nút `overflow` là
   HMAC của `<khoá bàn>/more` (global: `more:desks`). Lý do dùng HMAC có khoá thay cho SHA-256 trần: khoá Layout chứa `root`, `top`, `session_id` và có thể
   chứa chuỗi do agent đặt (ví dụ `department`); SHA-256 không bí mật nên key của project và team (sinh từ đường dẫn đoán được) đảo ngược được bằng danh sách
   đường dẫn thường gặp, và nếu một phần khoá do agent kiểm soát thì tìm va chạm 64 bit chỉ cần khoảng 2^32 phép băm (khi đó quy tắc va chạm bên dưới sẽ ẩn nút thứ hai). Với
   khoá bí mật không rời Wisp (trang không bao giờ nhận `key_secret`), kẻ đứng ngoài không thể đảo ngược hay tạo va chạm có chủ đích. `key` chỉ cần ổn định **trong
   một vòng đời server** (cùng khoá Layout, cùng `key_secret` cho cùng `key`), vì `prev` cũng mất khi server dừng; qua hai lần mở viewer hoặc hai tiến trình `key` khác nhau
   (Quyết định P, AA). Hai nút ra cùng `key`: giữ nút đầu, bỏ nút sau (va chạm tình cờ 64 bit; có test).
8. **Trần.** Tối đa `MAX_NODES = 1000` nút (hằng của `viewer_payload.py`). Vượt thì giữ 1000 nút đầu theo thứ tự cha trước con
   (nên cắt từ cuối: bàn, worker của sàn sau cùng) và `hidden = số nút bị bỏ`. Các số liệu của `more` và `alert` không bị ảnh hưởng;
   `live` chỉ giữ khoá của nút còn lại, giá trị không đổi so với không cắt (errata E8, theo allowlist C9). 1000 vừa đủ cho trần mặc định của board (48 bàn x (1 bàn + tối đa 12 subagent + 3 thiết bị + 1
   overflow) cộng cụm và sàn, khoảng 830 nút) và vẫn chặn được `board_max_desks` đặt tới 200.
9. **Không có trong payload**: `ref`, `session_id`, `root`, `top`, `seed`, khoá Layout gốc, `limits`, đường dẫn, và bất kỳ trường
   nào ngoài danh sách ở "Đầu ra". Có test quét khoá của mọi nút theo allowlist.

### Cam kết của board mà viewer dựa vào

Spec board đã chốt các điểm viewer cần (mục "Cam kết cho consumer", T-L13 đến T-L16, và hình dạng `styles`). Viewer dựa vào
chúng, không lặp lại định nghĩa; nếu board đổi, bộ chuyển đổi và test C3, C6, C8 đổi theo:

1. `Layout["styles"]` có dạng `{"desk": {state: Style}, "worker": {state: Style}}`, `Style{color, mood, marker}`, `mood` luôn
   là `str`, bản sao sâu của `STATE_STYLE`.
2. `Floor.level` là `int >= 0` và duy nhất; `Layout["floors"]` sắp theo `level` tăng dần; `Floor.w` luôn bằng
   `FLOOR_CLUSTER_COLS * CLUSTER_W` (30); `Floor.h` là bội của 10 và tối đa `max_floor_h(limits.desks)`.
3. Worker và Device không có `w`, `h` (viewer dùng 1x1); Desk có `w = h = 2`.
4. `more.counts` của bàn có khoá thuộc enum state của worker và tổng bằng `n`; `Layout["more"]` chỉ có `desks`, `stuck_desks`.
5. `office_layout` thuần và tái nhập, không cache toàn cục, không sửa `org_out`, `cfg`, `prev`; hai nơi gọi độc lập (Board và
   viewer) không ảnh hưởng nhau.
6. Các hằng `FLOOR_CLUSTER_COLS`, `CLUSTER_W` và hàm `mascot_index` xuất từ `office.py` đúng tên; viewer import, không chép giá trị.
7. Hai khoá `board_max_desks` và `board_max_workers` thuộc phần `office.py` và config chung của board; viewer dùng chung chúng
   và không thêm khoá riêng (spec này không sở hữu chúng).

8. `office.valid_org(org_out) -> bool` (đúng khi `org_out` là dict có `projects` là list) và luật cho nơi gọi: org không hợp lệ thì không gọi `office_layout`
   và không thay `prev`; org hợp lệ nhưng `projects: []` là dữ liệu thật và giải phóng slot. Viewer áp dụng luật này trong `publish` (xem "Cách viewer gọi
   `office_layout`", V28).

Viewer **không** có yêu cầu nào còn treo với board ở rev 3.

## Kiến trúc

### Server riêng, không dùng chung `HookServer`

Chọn: **một `ViewerServer` riêng trong `pet_tracker/viewer.py`**, class `ThreadingHTTPServer` riêng, cổng riêng, thread
riêng. Lý do:

- `HookServer` sống suốt đời app, nghe trên cổng cố định đã ghi vào `settings.json` của Claude Code. Thêm tuyến GET
  phục vụ trang vào đó đổi bề mặt tấn công của luồng hooks và buộc viewer dùng cổng cố định.
- Vòng đời khác nhau: viewer chỉ tồn tại khi có người xem (yêu cầu của người dùng); hooks luôn bật.
- Chính sách khác nhau: viewer cần kiểm `Host`, `Origin`, CSP và chặn mọi phương thức ngoài GET; hooks nhận POST từ
  Claude Code (không có `Origin`) và trả body rỗng.
- Đổi `hooks.py` buộc test lại hành vi hooks; tách riêng thì `hooks.py` và `tests/test_hooks.py` không đổi (kiểm
  bằng diff, xem Kiểm thử).

### Giao diện module (đề xuất tên, plan có thể đổi)

`ViewerServer(*, assets_dir, cache_dir, strings, hue, cfg, theme, mascot_ids, log, clock=time.monotonic, key_secret=None)`
(**`ViewerServer` không nhận `lang`** (errata E3): ngôn ngữ chỉ ảnh hưởng `strings`, nên App tính `strings = viewer.page_strings(i18n.lang())` một lần lúc mở viewer và truyền vào; `strings` là `dict[str, str]` đã lọc, `ViewerServer` chỉ phục vụ nó ở `/api/strings` (JSON) mà không biết ngôn ngữ. `cfg` là `cfg` của app, chỉ đọc; `theme` là `theme.DARK`; `mascot_ids` là `[m["id"] for m in mascots.all_mascots()]`;
`hue` là `App._hue()` lấy một lần):

- `start() -> bool`: kiểm file tĩnh (đủ, đúng SHA-256 với vendor), đọc cả vào bộ nhớ, bind, chạy thread. Lỗi thì
  `False` và `error` là chuỗi ngắn không chứa token.
- `url -> str`: `http://127.0.0.1:<port>/v/<token>/`.
- `publish(org, ts)`: gọi từ main thread; chạy `office_layout` (với `prev` riêng của viewer), `viewer_payload`, mã hoá JSON và
  đặt vào slot (xem "Chia sẻ dữ liệu giữa thread").
- `idle_for() -> float`: giây kể từ request `/api/layout` hợp lệ gần nhất (hoặc từ lúc `start`).
- `stop()`: idempotent, đóng socket, vô hiệu token.

`clock` được tiêm để test vòng đời không phải ngủ thật.

### Cứng hoá server

`ThreadingHTTPServer` mặc định tạo một thread cho mỗi kết nối, không giới hạn; `BaseHTTPRequestHandler` đọc tới 64 KiB dòng yêu
cầu và 100 header trước mọi kiểm tra, và `timeout` là hạn **mỗi lần `recv`**, không phải hạn tổng. Một tiến trình local không
cần token vẫn giữ được hàng trăm thread bằng kết nối nhỏ giọt (slowloris). `ViewerServer` dùng một lớp con
(`ViewerHTTPServer`) và một lớp handler riêng với các yêu cầu sau (Quyết định J, S):

| Mã | Yêu cầu quan sát được |
|---|---|
| H1 | **Giới hạn kết nối đồng thời ngay lúc accept: `MAX_CONNECTIONS = 16`** (đếm kết nối đang sống, kể cả kết nối im lặng; đếm trong `process_request`). Kết nối thứ 17 bị **đóng ngay** (`shutdown_request`) mà không tạo thread và không gửi byte nào. **Bộ đếm giảm trên MỌI đường**: khi thread xử lý kết thúc bình thường, khi handler ném ngoại lệ (kể cả đường `500`), khi hạn H2 cắt kết nối, và khi **tạo hoặc khởi chạy thread xử lý ném `RuntimeError`** (ví dụ hết tài nguyên thread): `process_request` bọc việc khởi chạy thread trong `try/except`, ở nhánh lỗi giảm bộ đếm và đóng socket, để bộ đếm không rò rồi từ chối mọi kết nối về sau. Số thread của server không bao giờ vượt 16 cộng thread `serve_forever` |
| H2 | **Hạn tổng cho mỗi kết nối: `CONNECTION_DEADLINE_SEC = 10`**, tính từ lúc accept tới lúc đáp ứng gửi xong, **gồm cả phía ĐỌC lẫn phía GHI**: client nhỏ giọt, client im lặng, và client đọc chậm hoặc không bao giờ đọc (thread xử lý kẹt trong `send`/`sendall`) đều bị cắt. **Thi hành** trong `service_actions()` của `serve_forever` (chạy mỗi `poll_interval` = 0,1 giây trên thread server, **không thêm thread, không thêm timer**): `service_actions` duyệt bảng `{socket: hạn}` (dưới khoá) và với kết nối quá hạn gọi `socket.shutdown(socket.SHUT_RDWR)` (không gọi `close`), làm `recv`/`send` đang chặn ở thread xử lý trả về lỗi ngay. **Chỉ thread xử lý được `close()` socket của nó**, trong `finally` của nó (kể cả đường lỗi): không bao giờ đóng socket từ thread khác, vì fd đã đóng có thể được tái dùng cho kết nối khác và dữ liệu viewer sẽ bị ghi nhầm vào một kết nối không có token. Cộng thêm `timeout = 5` giây cho mỗi lần `recv`/`send` (bắt buộc đặt, vì mặc định là `None`). **Vì sao `timeout` mỗi lần `recv` không đủ**: `rfile.readline` có đệm và gọi `recv` nhiều lần; mỗi lần nhận được dữ liệu thì đồng hồ timeout bắt đầu lại, nên client gửi một byte mỗi 4 giây không bao giờ chạm 5 giây mà vẫn giữ thread vô hạn; timeout mỗi lần `send` cũng không giới hạn tổng thời gian ghi một đáp ứng 1,4 MB cho client chỉ đọc từng chút. Kết nối nhỏ giọt hoặc không đọc bị cắt trong <= 11 giây |
| H3 | **Giới hạn đọc dòng yêu cầu và header**: dòng yêu cầu tối đa 256 byte (đọc tối đa 257 byte, vượt thì `414` rồi đóng); tối đa 32 dòng header, mỗi dòng tối đa 4096 byte, tổng header tối đa 16 KiB (vượt thì `431` rồi đóng). Các giới hạn này thay giới hạn mặc định 64 KiB / 100 header của stdlib nên phải ghi đè phần đọc dòng đầu và header của handler (không dùng nguyên `parse_request`) |
| H4 | `protocol_version = "HTTP/1.0"` **và** `close_connection = True` sau **mọi** đáp ứng, kể cả đáp ứng lỗi (405, 400, 431...). Server không bao giờ đọc body của request và không phục vụ request thứ hai trên cùng kết nối, nên body còn sót (ví dụ sau `405` có body) không thể bị hiểu thành request mới (chống desync) |
| H5 | `send_error` bị ghi đè: mọi mã do stdlib tự sinh (`400`, `414`, `431`, `500`, `501`, `505`...) có **body cố định** (một dòng văn bản theo mã, không phản chiếu dòng yêu cầu, đường dẫn hay header của client) và mang **đủ header bảo mật** của mục "Endpoint" |
| H6 | `allow_reuse_address = False` (stdlib `HTTPServer` đặt `True`). Trên Windows, `server_bind` đặt `SO_EXCLUSIVEADDRUSE` trước `bind` để tiến trình khác không bind chồng cùng cổng; **chưa kiểm trên Windows: `unavailable`**. Test macOS: kiểm thuộc tính `allow_reuse_address is False` của lớp |
| H7 | `handle_error` chỉ ghi tên loại ngoại lệ, không ghi địa chỉ khách, đường dẫn hay nội dung ngoại lệ (S10) |

Bộ đếm H1 và hạn H2 áp dụng cho **mọi** kết nối, kể cả trước khi qua kiểm Host và token (chúng nằm ở lớp accept và đọc, trước khi
có đường dẫn để kiểm). Lý do tách khỏi `Semaphore(8)` ở rev 2: semaphore chỉ đếm request đã được parse, không chặn kết nối im
lặng; bộ đếm kết nối chặn từ cửa vào. Hạn H2 được thi hành ở một chỗ (`service_actions`) và dùng `shutdown`, không dùng `close` từ thread
khác (N1). Kẻ tấn công trong mô hình này là **bất kỳ tài khoản OS local nào kết nối được tới 127.0.0.1** (máy nhiều người dùng), không chỉ cùng người dùng.

### Vòng đời

1. Người dùng chọn "3D office". `App._open_3d_viewer` (main thread) tạo `ViewerServer` nếu chưa có (một server tại
   một thời điểm), `start()`, và `publish` snapshot hiện tại nếu có để lần poll đầu đã có dữ liệu.
2. Nếu server đang chạy thì **dùng lại server và token đó** và chỉ mở thêm một tab (nhiều tab cùng xem được; token đổi
   mỗi lần server được tạo, không đổi mỗi lần bấm menu; Quyết định D).
3. Mở tab: `webbrowser.open(url, new=2)` chạy trong một thread ngắn (để main thread không bị chặn), **thread đó không gọi Tk
   và không gọi toast**: nó chỉ đặt kết quả (`True`, `False`, hoặc tên loại ngoại lệ) vào một `queue.Queue`. Main thread đọc
   queue đó bằng `root.after(200, ...)` (cùng chỗ với `_viewer_tick`, tối đa 10 lần, rồi bỏ). Kết quả `False` hoặc ngoại lệ
   thì **main thread** chép URL vào clipboard (`root.clipboard_clear()` rồi `root.clipboard_append(url)`) và hiện toast
   `v3d.link_copied` (Quyết định E). Log chỉ ghi `viewer: browser open failed <TypeName>` (hoặc `... returned False`),
   **không** ghi nội dung ngoại lệ vì có thể chứa URL kèm token. Lưu ý: trên macOS `MacOSXOSAScript.open` gần như luôn trả
   `True` kể cả khi không mở được tab, nên nhánh dự phòng này hiếm chạy trên macOS và chỉ kiểm được bằng test có stub (W4).
4. Main thread đặt `root.after(5000, _viewer_tick)`; mỗi lần kiểm `idle_for()`. Quá **120 giây** thì `stop()` và bỏ
   tham chiếu; không đặt lại timer. 120 giây lớn hơn mức Chrome giới hạn timer của tab ẩn (một lần mỗi phút) cộng lề, nên
   tab ẩn đang sống không bị coi là đã đóng; đồng thời tab vừa đóng làm server tắt sau tối đa 125 giây. Hạn 120 giây
   cũng áp dụng cho lần mở đầu (trình duyệt khởi động chậm hay không mở được).
5. `App.quit` gọi `viewer.stop()` cùng chỗ với `hook_server.stop()`. `shutdown()` của `socketserver` không có tham số
   `poll_interval`; tham số đó thuộc `serve_forever(poll_interval=...)` (mặc định 0,5 giây). Thread server gọi
   `serve_forever(poll_interval=0.1)`, nên `stop()` (gọi `shutdown()` rồi `server_close()`) chặn main thread tối đa khoảng
   0,1 giây thay vì khoảng 0,5 giây.
6. Sau `stop()` mọi tab đang mở thấy lỗi kết nối và hiện trạng thái "mất kết nối" (xem "Trang").
7. Cổng: **do hệ điều hành cấp** (`bind(("127.0.0.1", 0))`), đọc lại bằng `server_address[1]`. Không thêm khoá config
   (Quyết định A). Vì cổng và token đổi mỗi lần, URL cũ trong lịch sử trình duyệt không bao giờ dùng lại được
   sau khi server tắt, kể cả khi hệ điều hành cấp lại đúng cổng đó (token khác thì 404).

### Chia sẻ dữ liệu giữa thread

- Main thread là nơi duy nhất gọi Tk và duy nhất ghi slot. `_pump` gọi `viewer.publish(org, ts)` sau khi đặt
  `self.snap = got`, chỉ khi viewer đang chạy và chỉ khi `got["ts"]` đổi.
- `publish(org, ts)`, **ngay trên main thread**, theo thứ tự: (1) **`office.valid_org(org)`** (hàm thuần của board: `org` là dict có
  `projects` là list, kể cả list rỗng) **sai** (`org.build` lỗi nên `snap["org"]` là `None`, hoặc snapshot lỗi không có khoá `org`) thì
  **không gọi `office_layout`, không thay `prev`, không đổi slot**: giữ nguyên payload hiện có (kể cả `ts` cũ của nó, nên trang tự
  chuyển sang `stale` khi quá ngưỡng, không tưởng dữ liệu còn sống), và chỉ khi **chưa có payload nào** thì đặt payload
  `ready:false, reason:"no_data"`; rồi dừng. `org` hợp lệ nhưng `projects: []` là dữ liệu thật (không có session nào): đi tiếp bước
  (2), Layout rỗng thay `prev` và mọi slot được giải phóng. (2) `layout = office_layout(org, cfg, prev=self._prev)`, rồi
  `self._prev = layout`; (3) `data = viewer_payload(layout, org, theme, mascot_ids, self._key_secret)`; (4) `json.dumps(wrapper,
  ensure_ascii=True, allow_nan=False)` mã hoá UTF-8; (5) đặt `(seq, body_bytes, etag)` vào slot dưới `threading.Lock`.
  Chi phí này nằm trên main thread nên phải nhỏ: mục tiêu <= 20 ms ở trần mặc định của board (48 bàn, đo trong plan, ghi
  vào PR).
- `self._prev` là Layout của lần `publish` trước **của riêng viewer**; chỉ main thread đọc và ghi; không chia sẻ với tab Board
  (xem "Cách viewer gọi `office_layout`"). Nó mất khi `ViewerServer` bị bỏ.
- Thread server chỉ đọc bộ ba bất biến đó dưới khoá và gửi đi. Nó không chạm `org`, snapshot, Layout, `prev`, payload, Tk hay
  `Collector`. Không dict hoặc list nào của Wisp được chia sẻ qua thread.
- Bước (2), (3) hoặc (4) ném lỗi: slot **giữ payload cũ**, ghi log `viewer: layout error <TypeName>` (không ghi nội dung, vì có
  thể chứa chuỗi agent), và slot nhận payload `ready:false, reason:"layout_error"` nếu chưa có payload nào. Layout có
  `version` lạ cũng đi đường này (`ValueError` của bộ chuyển đổi).
- **Body vượt 1 MiB** (errata E2, từ plan P6; thay câu "tương tự" ở rev 5): sau bước (4), nếu body UTF-8 của payload mới dài hơn 1 048 576 byte thì **không thay slot nếu đã có payload** (giữ nguyên bytes, ETag và `ts` cũ; trang tự báo `stale` theo `ts` cũ);
  `prev` **vẫn** được cập nhật (vì `office_layout` đã thành công); ghi log `viewer: payload too large` (không ghi kích thước chứa dữ liệu agent, chỉ ghi số byte). **Chưa có payload nào** thì slot nhận đúng body cố định
  `{"v": 1, "ts": <ts>, "ready": false, "reason": "too_large", "refresh_sec": <refresh_sec>}`, phục vụ với mã HTTP `200` như mọi payload `ready:false` khác (trang đọc `reason` từ JSON, không dựa vào mã HTTP). Server không bao giờ phục vụ một `scene` dài hơn 1 MiB.
- Trong request handler **không đọc đĩa** ngoài hai thứ: file tĩnh đã nạp sẵn vào RAM lúc `start` (không đọc lại), và PNG
  mascot qua `mascots.png` (cache RAM rồi cache đĩa, xem "Sprite").

### Endpoint

Mọi đường dẫn nằm dưới `/v/<token>`. Mọi endpoint chỉ nhận **GET**. Danh sách cố định:

| Đường dẫn (sau `/v/<token>`) | 200 trả | Content-Type | Ghi chú |
|---|---|---|---|
| `/` | `index.html` | `text/html; charset=utf-8` | không chứa script hoặc style nội tuyến |
| `/app.js` | `app.js` | `text/javascript; charset=utf-8` | script module của trang |
| `/style.css` | `style.css` | `text/css; charset=utf-8` | |
| `/vendor/three.module.js` | three.js | `text/javascript; charset=utf-8` | |
| `/vendor/three.core.js` | three.js core | `text/javascript; charset=utf-8` | |
| `/vendor/OrbitControls.js` | OrbitControls đã vá một dòng | `text/javascript; charset=utf-8` | import tương đối `./three.module.js` |
| `/api/strings` | chuỗi giao diện theo ngôn ngữ lúc mở | `application/json; charset=utf-8` | dựng một lần lúc `start` |
| `/api/layout` | payload (xem dưới) | `application/json; charset=utf-8` | `ETag`; `If-None-Match` khớp thì 304 |
| `/api/sprite/<mid>/<mood>.png` | PNG mascot | `image/png` | `mid`, `mood` phải thuộc danh sách cho phép |

Bảng định tuyến là một `dict` chuỗi cố định -> bytes dựng lúc `start`. Server **không** ghép tham số của client vào đường
dẫn file, không `open()` theo đường dẫn từ request, không `os.path.join` với phần nào của request, không liệt kê thư mục,
không phục vụ file ngoài bảng trên (`vendor/LICENSE` và `vendor/VERSION.txt` có trong bản cài nhưng không có trong bảng
này, vì trang không dùng).

Thứ tự cho mỗi kết nối (dừng ở bước đầu tiên không đạt; mọi đáp ứng lỗi đóng kết nối, H4):

0. Lúc accept: kết nối thứ 17 bị đóng không đáp ứng (H1); khởi động hạn 10 giây (H2).
1. Đọc dòng yêu cầu: dài hơn 256 byte `414`; sai cú pháp `400`; phiên bản HTTP không phải `HTTP/1.0` hoặc `HTTP/1.1` `505`.
2. Đọc header: quá 32 dòng, dòng quá 4096 byte hoặc tổng quá 16 KiB `431`; header sai cú pháp `400`.
3. Phương thức không phải GET: `405` với `Allow: GET` cho `HEAD POST PUT DELETE PATCH OPTIONS`; phương thức khác: `501`.
4. `Host`: phải có **đúng một** header `Host` (đọc bằng `headers.get_all("Host")`, độ dài 1) và giá trị bằng **chính xác**
   `127.0.0.1:<port>` (so sánh chuỗi, không cắt khoảng trắng, không phân biệt gì khác). Thiếu, hai lần trở lên, khác một ký tự
   (kể cả khoảng trắng thừa ở đầu hoặc cuối giá trị): `403`.
5. Đường dẫn không bắt đầu bằng `/v/`, hoặc đoạn token không khớp (so `hmac.compare_digest` trên bytes UTF-8), hoặc phần còn
   lại không có trong bảng định tuyến, hoặc có ký tự `?`, `#`, `%` hay `\`: `404` (cùng một đáp ứng cho "sai token" và "sai
   đường dẫn", để không lộ token đúng hay sai).
6. Riêng `/api/*`: `Origin`, nếu có, phải xuất hiện **đúng một lần** và bằng **chính xác** `http://127.0.0.1:<port>`;
   `Sec-Fetch-Site`, nếu có, phải xuất hiện **đúng một lần** và bằng chính xác `same-origin` (cùng cách `get_all`, so sánh chính
   xác, không cắt khoảng trắng). Một trong hai header lặp lại hoặc sai: `403`. Không có cả hai (curl, trình duyệt cũ): chấp
   nhận, vì vẫn cần token.
7. `/api/sprite`: `mid` thuộc tập id đọc từ `mascots.all_mascots()` lúc `start` và `mood` thuộc `mascots.MOODS`; ngoài tập: `404`.
8. Đáp ứng.

Không còn `Semaphore(8)` và mã `503`/`Retry-After`: trần là 16 kết nối ở lớp accept (H1). Trang tối đa 3 ảnh sprite đồng thời mỗi
tab, cộng 1 lượt poll: hai tab dùng tối đa 8 kết nối, thấp hơn trần 16 nên poll `/api/layout` không bị đóng khi khởi động nguội
(Quyết định S).

Header có trên **mọi** đáp ứng, kể cả lỗi:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self';
    connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';
    require-trusted-types-for 'script'; trusted-types 'none'
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Cross-Origin-Resource-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cache-Control: no-store            (layout, strings, lỗi)
Cache-Control: private, max-age=3600   (file tĩnh, sprite; URL đã có token riêng mỗi lần server tạo)
Server: Wisp
```

Không bao giờ gửi `Access-Control-*` (không CORS mở). `send_error` và `handle_error` của stdlib bị ghi đè: body lỗi là một
dòng văn bản cố định (không phản chiếu đường dẫn hay header của client), `handle_error` chỉ ghi tên loại ngoại lệ.

### Payload `/api/layout`

```json
{"v": 1, "ts": 1761800000.5, "ready": true, "refresh_sec": 3, "scene": { "...payload của viewer_payload..." }}
{"v": 1, "ts": 1761800000.5, "ready": false, "reason": "no_data", "refresh_sec": 3}
```

- `v`: phiên bản của lớp bọc này. `scene` là payload của `viewer_payload` (mục "Bộ chuyển đổi"), có `schema` riêng; trang chỉ vẽ
  khi `scene.schema` bằng giá trị trang hỗ trợ (hiện là 1). `ts`: thời điểm snapshot (giây epoch, từ `snap["ts"]`).
  `refresh_sec`: `cfg["refresh_sessions_sec"]` lúc mở, để trang suy ra ngưỡng "dữ liệu cũ". `config.py` không kiểm kiểu giá trị
  này, nên server **ép** trước khi gửi: không phải số (kể cả `bool`, `None`, chuỗi), không hữu hạn (`NaN`, `inf`) hoặc <= 0 thì
  dùng 3; ngoài khoảng thì kẹp vào [1, 60]. Trang không bao giờ nhận `NaN` làm ngưỡng.
- `scene.nodes` đổi khi cấu trúc hoặc state đổi; `scene.live` (token, thời gian) đổi mỗi chu kỳ. Nên cùng ETag chỉ khi không có
  gì đổi, kể cả `live`.
- `reason` thuộc `no_data | layout_error | too_large`; trang ánh xạ sang chuỗi trong `/api/strings`, giá trị lạ dùng
  chuỗi chung.
- `ETag` là `"<16 hex đầu của SHA-256 body>"`. Cùng body thì cùng ETag, nên `If-None-Match` khớp trả `304`, không body.
- Mọi request `/api/layout` qua đủ các bước 1-6 (kể cả 304) đặt lại bộ đếm idle.

### Sprite

Trang lấy ảnh mascot bằng `GET /v/<token>/api/sprite/<mid>/<mood>.png`:

- Định dạng PNG RGBA do `mascots.png(mid, mood, SPRITE_SIZE, "dark", hue, cache_dir)` sinh. `SPRITE_SIZE = 128`
  (ảnh cạnh `canvas_size(128) = 164` px; GPU dùng 164 x 164 x 4 = 107 KB mỗi texture). `theme` cố định `"dark"` vì cảnh có
  nền tối. `hue` là `App._hue()` (tức `prefs["hue"]` toàn cục, cùng nguồn với Board) lấy **một lần lúc `start`**; đổi hue
  trong Cài đặt có hiệu lực ở lần mở viewer sau.
- Đường dẫn file không bao giờ lấy từ request: `mid` và `mood` được **so khớp với tập cho phép** (bước 7) rồi mới đưa vào
  `mascots.png`; hàm này tự dựng tên file cache từ chính các giá trị đó. Chuỗi do agent (label, department, description) không
  đi vào endpoint này: `mid` do bộ chuyển đổi chọn bằng số học (`office.mascot_index(seed, len(mascot_ids))`, `seed` là
  `crc32` của `session_id` hoặc phòng ban) từ danh sách mascot của Wisp, và chỉ phát ra khi thuộc `mascot_ids`; `mood` lấy từ
  `legend`, một tập đóng. Nếu nút không có `mascot` hoặc `mood` ngoài `mascots.MOODS`, trang không yêu cầu ảnh (nút hiện bằng
  chấm màu `state`).
- Cache: (1) RAM trong server, `dict` tối đa 200 mục (40 x 5 là toàn bộ không gian), khoá `(mid, mood)`; (2) đĩa qua tham số
  `cache_dir = STATE_DIR / "mascots"` (đã là cache của app); (3) trình duyệt (`Cache-Control: private, max-age=3600`).
- Một khoá dựng ảnh (`threading.Lock`) quanh `mascots.png` để các request cùng lúc không rasterize song song làm nghẽn GIL của
  Tk. Dựng lỗi: `500` (không có body chi tiết); trang giữ chấm màu.
- Giới hạn số ảnh: trang chỉ xin các cặp `(mid, mood)` đang xuất hiện trong Layout hiện tại (tối đa 200 cặp khác nhau), tối
  đa 3 ảnh đang tải cùng lúc, và dùng lại một texture cho mọi sprite cùng cặp.

### Đóng gói assets

Cấu trúc mới (một thư mục, mọi thứ viewer cần):

```
assets/viewer/index.html
assets/viewer/app.js
assets/viewer/style.css
assets/viewer/vendor/three.module.js
assets/viewer/vendor/three.core.js
assets/viewer/vendor/OrbitControls.js   (examples/jsm/controls/OrbitControls.js của r186, vá đúng một dòng import)
assets/viewer/vendor/LICENSE        (MIT, nguyên văn từ tarball)
assets/viewer/vendor/VERSION.txt    (phiên bản, nguồn, SHA-256 tarball, SHA-512 integrity, SHA-256 từng file)
```

- Giữ giấy phép: `vendor/LICENSE` là file `package/LICENSE` nguyên văn, nằm cạnh ba file vendor trong source và trong bản
  build (nó được chép cùng cả thư mục). `README.md` thêm một dòng ghi three.js MIT và đường dẫn tới file đó.
- Ghim phiên bản và checksum: `viewer.py` có hằng `VENDOR_SHA256 = {"three.module.js": "...", "three.core.js": "...", "OrbitControls.js": "..."}`
  bằng ba SHA-256 ở bảng "Dữ kiện đã kiểm" (với `OrbitControls.js` là SHA-256 của **bản đã vá**; SHA-256 của bản gốc và dòng vá nằm trong `VERSION.txt`). `start()` đọc **mỗi file vendor đúng một lần** vào một buffer `bytes`, băm **chính
  buffer đó**, so với hằng, và đưa **chính buffer đó** vào bảng định tuyến (không đọc lại file, không băm một lần rồi đọc lần hai: loại bỏ
  cửa sổ TOCTOU giữa kiểm và phục vụ). Thiếu file hoặc lệch checksum thì **từ chối chạy** (`error`, toast `v3d.open_fail`). Cùng cách
  cho `index.html`, `app.js` và `style.css` (đọc một lần lúc `start`, phục vụ buffer đó; ba file này không có hằng băm vì chúng là
  mã của Wisp, nhưng cùng quy tắc đọc một lần). Test kiểm hằng này khớp với `vendor/VERSION.txt` (hai nơi không được lệch
  nhau). Quy trình nâng cấp three.js: chọn phiên bản cũ hơn 14 ngày, tải tarball từ registry npm, đối chiếu `dist.integrity`,
  thay ba file và LICENSE (áp lại bản vá một dòng; nếu dòng `} from 'three';` không còn là chỗ nhập duy nhất thì dừng và sửa spec), cập nhật `VERSION.txt` và hằng, chạy lại test và T3. Không dùng CDN, không dùng bản do bên thứ ba
  minify.
- **Lệnh tái lập checksum** (reviewer chạy mỗi lần nâng cấp three.js; A4 chỉ so hai giá trị cùng nằm trong repo nên không thay
  được bước này). Ghi cả vào `vendor/VERSION.txt`:
  1. `V=<phiên bản>`; `curl -s https://registry.npmjs.org/three/$V` lấy `dist.integrity` và `dist.tarball`, và `time[$V]` từ
     `https://registry.npmjs.org/three` để xác nhận bản đó cũ hơn 14 ngày.
  2. `curl -o three.tgz "<dist.tarball>"`; `openssl dgst -sha512 -binary three.tgz | base64` phải bằng phần sau `sha512-` của
     `dist.integrity`; `shasum -a 256 three.tgz` phải bằng SHA-256 tarball trong `VERSION.txt`.
  3. Giải nén vào thư mục mới và trống (`mkdir x && tar -xzf three.tgz -C x package/build package/LICENSE package/examples/jsm/controls/OrbitControls.js`); `shasum -a 256
     x/package/build/three.module.js x/package/build/three.core.js` phải bằng hằng `viewer.VENDOR_SHA256` **và** bằng `VERSION.txt`; `shasum -a 256 x/package/LICENSE` phải bằng bảng checksum trong spec (mục "Dữ kiện đã kiểm") và `VERSION.txt`, **không** so với `viewer.VENDOR_SHA256`
     (hằng đó chỉ có ba file `.js`, LICENSE không nằm trong đó; và ở lần vendor đầu `viewer.py` chưa tồn tại, nên bước vendor đầu tiên chỉ đối chiếu bảng spec và `VERSION.txt`); `shasum -a 256 x/package/examples/jsm/controls/OrbitControls.js` phải bằng SHA-256 **bản gốc** trong `VERSION.txt`; `grep -c -E 'eval\(|new Function|innerHTML'` trên ba file `.js` phải là 0.
  4. Áp bản vá: `grep -c "^} from 'three';\$" OrbitControls.js` phải là **1** và `grep -c "from 'three'"` phải là **1**; `sed "s#^} from 'three';\$#} from './three.module.js';#"` ra file có SHA-256 bằng SHA-256 **bản đã vá** trong `viewer.VENDOR_SHA256`; `diff` giữa bản gốc và bản đã vá ra đúng một dòng đổi.
  5. `cmp` ba file trong `assets/viewer/vendor/` với ba file vừa giải nén (với OrbitControls: với bản đã vá ở bước 4).
- Bản build PyInstaller (**hai** script cùng sửa; không đụng `Wisp.spec`, xem "Dữ kiện đã kiểm"):
  - `build_macos.sh`: thêm `--add-data "assets/viewer:assets/viewer"`.
  - `build.ps1`: thêm `--add-data "assets\viewer;assets\viewer"`.
- Cách kiểm file có mặt trong bản build (Quyết định I, phương án rẻ hơn): **không có `tools/check_bundle.py`**. Ngay sau lệnh PyInstaller (và trước `codesign` ở macOS), mỗi script build kiểm sự có mặt của bảy file bằng vài dòng, tìm theo tên đường dẫn
  `*/assets/viewer/<file>` trong thư mục `dist` mà không giả định vị trí `datas` (chưa kiểm cho PyInstaller 6.22.3 trên macOS `.app` hay `_internal` của bản Windows). Thiếu một file thì script thoát khác 0 và build thất bại. Bảy file:
  `index.html`, `app.js`, `style.css`, `vendor/three.module.js`, `vendor/three.core.js`, `vendor/OrbitControls.js`, `vendor/LICENSE`.
  - `build_macos.sh`: `for f in index.html app.js style.css vendor/three.module.js vendor/three.core.js vendor/OrbitControls.js vendor/LICENSE; do [ -n "$(find dist -path "*/assets/viewer/$f" -print -quit)" ] || { echo "thiếu assets/viewer/$f" >&2; exit 1; }; done`.
  - `build.ps1`: cùng danh sách bảy file; với mỗi file `Get-ChildItem -Path dist -Recurse -File | Where-Object { $_.FullName -like "*assets\viewer\$f" }` phải có kết quả, nếu không `throw "thiếu assets/viewer/$f"` (cùng kiểu `throw` như dòng kiểm `$LASTEXITCODE` hiện có).
  - Chỉ kiểm có mặt, không kiểm checksum trong build: checksum ba file three.js được `start()` kiểm lúc chạy (S24), `VENDOR_SHA256` được kiểm trên nguồn ở A4, và M12 mở bản build thật.
- Kiểm chạy được trong bản build: mở `Wisp.app` đã build, chọn "3D office", cảnh hiện (T3). Trên macOS làm tay; Windows:
  `unavailable` (chưa có máy kiểm).

## Cảnh 3D

Mọi hằng số dưới đây là hằng của `app.js`, không phải khoá config.

- **Thế giới**: 1 ô lưới = 1 đơn vị; toạ độ `(x, y)` của nút trong payload (đã là **tuyệt đối**, xem "Bộ chuyển đổi" quy tắc 2)
  thành mặt phẳng `(X, Z)`; trục Y hướng lên. Nút `w x h` ô chiếm `[x, x + w) x [y, y + h)`; vật 1x1 đặt ở tâm ô
  `(x + 0,5, y + 0,5)`. Các sàn nằm thành một hàng ngang theo `X`, mỗi sàn dài thêm về phía `Z` khi có thêm cụm.
  - `project`: tấm sàn dày 0,2 phủ `(x, y, w, h)`, màu `palette.floor`, nhãn tên dán trên mặt sàn ở góc sau-trái.
  - `team`: tấm mỏng 0,05 nổi trên sàn project, màu `palette.team`.
  - `session`: khối "bàn" cao 0,5 phủ ô 2x2 của bàn, màu theo `legend.desk[state].color`. Mascot ngồi trên ô `(x, y)` của bàn
    (đúng như board: ô đầu của bàn là chỗ mascot ngồi), sprite cao 1,2. Có `alert` > 0: vòng `ring` màu `palette.warn` quanh bàn và
    một chip (canvas texture) ghi số `alert`.
  - `subagent`: sprite cao 0,6 đứng trên sàn ở tâm ô 1x1; `legend.worker[state]` cho `mood`, màu chấm chờ tải và `marker`.
  - `bgtask`: hộp nhỏ 0,25 trên mặt bàn ở tâm ô 1x1 của nó, màu `legend.worker[state].color`; `marker` vẽ như subagent.
  - `overflow`: chip phẳng quay về camera (sprite) có chữ `+N` (canvas texture) nổi cao 2,2 phía trên bàn (hoặc ở rìa hàng sàn
    cho nút toàn cục), màu `palette.warn` khi có `alert`, ngược lại `palette.line`.
  - `marker` `ring`: vành phẳng (`RingGeometry`) màu `palette.warn` quanh ô của worker; `cross`: hai nét chéo (canvas texture
    trên một sprite nhỏ) màu `palette.danger` ở góc trên phải sprite. Cả hai thuộc `legend`, trang chỉ hiện thực hình.
- **Camera**: `PerspectiveCamera` fov 45. Lần có dữ liệu đầu tiên, camera tự đặt nhìn trọn `bounds` (góc nghiêng cao 35
  độ so với mặt sàn); **không** tự đặt lại ở các lần cập nhật sau (khỏi giật khi poll). Phím `R` hoặc nút "Đặt lại" đưa
  camera về vị trí ban đầu.
- **Điều khiển = `OrbitControls` của three r186** (`import { OrbitControls } from './vendor/OrbitControls.js'`, Quyết định B), gắn vào `renderer.domElement`; xoay, pan, zoom và hành vi cảm ứng là hành vi mặc định của nó
  (kéo chuột trái hoặc một ngón là xoay quanh tâm; chuột phải hoặc hai ngón là pan; cuộn chuột hoặc pinch là zoom). **Chỉ những cấu hình Wisp đặt** (mọi thứ khác để mặc định):
  - `enableDamping = false` (không có quán tính, nên không cần vòng `requestAnimationFrame`; giữ render theo yêu cầu, Quyết định G); `controls.addEventListener("change", requestRender)` là lúc cảnh được vẽ khi camera đổi.
  - Kẹp góc để không chui xuống sàn: `minPolarAngle = 10°` và `maxPolarAngle = 80°` tính từ trục dọc (tương ứng độ nghiêng của camera so với mặt sàn từ 10° đến 80°); `minDistance = 4` và `maxDistance = 3 x đường chéo bounds`
    (cập nhật khi `bounds` đổi).
  - Tâm (target) kẹp trong `bounds` mở rộng 20%: trong handler `change`, kẹp `controls.target` vào `Box3` đó và dời `camera.position` cùng đoạn (OrbitControls không có sẵn kẹp tâm).
  - `controls.saveState()` ngay sau khi đặt camera ban đầu; phím `R` hoặc nút "Đặt lại" gọi `controls.reset()`.
  - Bàn phím: `controls.listenToKeyEvents(renderer.domElement)` với canvas có `tabindex="0"` (khai báo tĩnh trong `index.html`): **mũi tên pan** camera (hành vi mặc định của OrbitControls); phím `+` và `-` **không còn** (zoom bằng cuộn chuột, pinch hoặc
    nút giao diện nếu plan thêm); đây là khác biệt so với rev 4 (mũi tên xoay, `+`/`-` zoom) do dùng OrbitControls nguyên bản. `R` là phím của trang (handler `keydown` riêng gọi `controls.reset()`).
  - Không có điều khiển nào gửi gì về server. `OrbitControls.js` không bị `A1` quét (nó là mã vendor); các quy ước của `app.js` (A2) áp dụng cho mã của Wisp.
- **Ánh sáng và bóng**: `AmbientLight` (cường độ 0,6) + một `DirectionalLight` (cường độ 0,9) hướng chéo, `castShadow`, shadow map
  2048 x 2048, `renderer.shadowMap.type = THREE.PCFShadowMap`; vùng bóng của đèn khớp `bounds`. Sàn, tấm và bàn nhận và đổ bóng.
  Sprite **không** đổ bóng (`THREE.Sprite` không hỗ trợ), nên mỗi sprite có một "vệt bóng" giả: đĩa phẳng tròn đen
  độ mờ 0,35 ngay dưới nó.
- **Sprite**: `THREE.Sprite` với `SpriteMaterial` có `map` là texture của `(mascot, mood)` và `depthWrite = false`; luôn quay về
  camera. Trong lúc ảnh chưa tải (hoặc tải lỗi hoặc không có `mascot`) sprite là chấm tròn màu `state`. Texture dùng chung cho
  mọi sprite cùng cặp, giữ suốt đời trang (tối đa 200).
- **Nhãn**: nhãn project và session vẽ bằng `CanvasTexture` (`CanvasRenderingContext2D.fillText`, văn bản thuần, không DOM), dán
  lên sàn hoặc cạnh bàn; cắt ở 24 ký tự kèm "…"; cache theo chuỗi, giải phóng khi nút biến mất. Team và subagent không có nhãn
  cố định (xem hover).
- **Hover và chọn (chỉ xem)**: `Raycaster` trên sprite và bàn, chạy tối đa một lần mỗi khung hình khi con trỏ di chuyển. Hover:
  viền sáng và một chú thích nhỏ (`textContent` của một phần tử có sẵn) gồm `label` và tên state. Bấm chọn một nút: khung
  chi tiết bên phải hiện `kind`, `label`, `sub`, state (đều bằng `textContent`). Bấm chỗ trống hoặc `Esc` bỏ chọn. Lựa chọn giữ
  theo `key` qua các lần poll; key biến mất thì bỏ chọn. Không có hành vi ghi nào, bấm đúp không làm gì.
- **Vẽ theo yêu cầu (render on demand)**: không có vòng `requestAnimationFrame` chạy liên tục. Cảnh được vẽ khi camera đổi, khi
  dữ liệu đổi, khi hover/chọn đổi, khi texture tải xong và khi cỡ cửa sổ đổi (`ResizeObserver`); nhiều yêu cầu trong cùng một
  khung được gộp thành một lần vẽ. Tab ẩn hoặc không có thay đổi thì GPU rảnh. `renderer.setPixelRatio(min(devicePixelRatio, 2))`.
  Không có hiệu ứng chuyển động tự chạy (hợp với `prefers-reduced-motion`; Quyết định G).
- **Trần và hiệu năng mục tiêu** (đạt hay không được ghi lại ở T3):
  - Trần an toàn: **1000 nút** mỗi payload, do `viewer_payload` cắt (`MAX_NODES`); thanh trạng thái hiện `+hidden` ("đã ẩn N
    nút"), `more.desks` ("+N bàn không vẽ") và số `stuck_desks`. Trần số bàn và subagent là của board (`board_max_desks` 48,
    `board_max_workers` 12 mặc định); 1000 nút là chốt chặn khi người dùng đặt trần board cao hơn. Trang không cắt thêm.
  - Cỡ mục tiêu = **trần mặc định của board đầy**: 48 bàn, 12 subagent mỗi bàn (576 sprite subagent), 3 thiết bị mỗi bàn
    (144 bgtask), 8 cụm, 2 sàn, khoảng 830 nút và khoảng 625 sprite.
  - Khi xoay camera ở cỡ mục tiêu: **trung bình >= 30 FPS**, không khung nào dài hơn 100 ms, trên MacBook Apple Silicon
    (loại M1 trở lên), Chrome bản stable hiện hành. Số draw call <= 2000 (đọc `renderer.info.render.calls` trong DevTools;
    ước lượng: mỗi sprite một vệt bóng nên khoảng 1250 cho sprite và vệt bóng). Số texture sprite <= 200, texture nhãn <= 120.
  - Poll không đổi (304): không dựng lại, không vẽ lại. Poll có đổi một phần: thời gian JS cập nhật cảnh <= 16 ms ở cỡ mục tiêu.
  - Chưa có số đo thật; T3 ghi số đo thật vào PR, không đạt thì hạ cỡ mục tiêu hoặc xin điều chỉnh spec, không bỏ qua.
- **Dọn dẹp**: nút biến mất thì `geometry.dispose()`, `material.dispose()` của vật riêng và giải phóng texture nhãn của nó.
  Texture sprite dùng chung không bị dispose giữa chừng.
- **WebGL**: tạo renderer lỗi (không có WebGL2): trang hiện thông báo cố định "trình duyệt không hỗ trợ WebGL2" thay vì canvas.
  Sự kiện `webglcontextlost`: `preventDefault()` và hiện thông báo "mất ngữ cảnh WebGL, hãy tải lại trang".
- **Trình duyệt**: bản stable hiện hành của Chrome, Edge, Safari và Firefox (cần ES module và WebGL2). Không cam kết bản cũ
  hơn. Đã kiểm trong T3: Chrome và Safari trên macOS (Quyết định K).

## Trang

### Cấu trúc

`index.html` chỉ có: `<canvas>`, một thanh trạng thái (`role="status"`, `aria-live="polite"`), một banner kết nối
(`role="alert"`), khung chi tiết, nút "Đặt lại", và `<script type="module" src="app.js">`. Không có script hay style nội
tuyến, không có thuộc tính `style=` hay `on*=`; bố cục dùng class trong `style.css`. `app.js` đặt kích thước và màu bằng
CSSOM (`el.style.x = ...`; CSP không chặn CSSOM). `<link rel="icon" href="api/sprite/m01/idle.png">` dùng đúng endpoint sprite
(URL tương đối nên token đi theo).

Mọi chuỗi từ agent (label, sub, tên state lạ) chỉ vào trang bằng `textContent`, `CanvasRenderingContext2D.fillText` hoặc
`setAttribute` của thuộc tính văn bản cố định (ví dụ `aria-label`); **không bao giờ** `innerHTML`, `outerHTML`,
`insertAdjacentHTML`, `document.write`, `DOMParser`, `createContextualFragment`, `srcdoc`, `eval`, `new Function`, hay
`setTimeout`/`setInterval` kiểu chuỗi. Lớp phòng thủ chính là CSP (không `unsafe-inline`, không `unsafe-eval`,
`require-trusted-types-for 'script'`, `trusted-types 'none'`, nên sink HTML và script bị trình duyệt Chromium từ chối kể cả khi mã
lỡ dùng chúng; Firefox và Safari bỏ qua hai chỉ thị trusted types nhưng vẫn thi hành phần còn lại của CSP) cộng quy ước
`textContent`; test quét chuỗi (A1, A2) chỉ là lưới phụ, vì quét chuỗi con dễ bị lách (nối chuỗi, thuộc tính tính toán).

Quy ước thêm cho `app.js` (có test quét A2 và kiểm tay M16):

- Không điều hướng và không gán URL: không dùng `location`, không gán `.href`, `.src`, `.action`, `window.open`; `setAttribute` chỉ
  nhận tên thuộc tính trong allowlist cố định (`aria-label`, `aria-live`, `role`, `tabindex`) với giá trị là chuỗi cố định hoặc chuỗi
  qua `textContent`. Việc nạp ảnh sprite dùng `THREE.TextureLoader` với URL tương đối dựng bởi **một** hàm `spriteUrl`.
- `spriteUrl(mascot, mood)` chỉ dựng URL khi `mascot` khớp `^m[0-9]{2}$` và `mood` thuộc danh sách cố định
  `["idle", "run", "wait", "done", "quota"]` (allowlist phía trang, độc lập với server); ngược lại trả `null` và nút hiện chấm màu.
  Trang không bao giờ nối chuỗi từ payload (label, sub, key, state) vào URL.
- Tra bảng bằng dữ liệu không tin cậy chỉ qua `Map` (`legend` và `palette` được nạp vào `Map` khi nhận payload) hoặc
  `Object.hasOwn`; không bao giờ `obj[chuỗi_từ_payload]` (tránh `constructor`, `__proto__`, `toString`). State lạ dùng hàng `idle`
  (desk) hoặc `unknown` (worker).

Chuỗi giao diện của trang (nhãn nút, thông báo, tên state, mô tả `reason`) lấy từ `/api/strings` (Quyết định F), chốt như sau (errata E3):

- **Hàm thuần `viewer.page_strings(lang) -> dict[str, str]`** (trong `viewer.py`, không import `tkinter`, không đọc đĩa, không gọi `i18n.set_lang`): đọc thẳng các bảng `i18n.VI` hoặc `i18n.EN` (`lang` là `"vi"` hoặc `"en"`, giá trị khác dùng `"en"`), giữ các khoá có tiền tố **`v3d.page.`**, bỏ tiền tố đó khỏi khoá
  trả về, và trả đúng tập `PAGE_STRING_KEYS` (hằng trong `viewer.py`, bên dưới). Khoá `v3d.open_fail` và `v3d.link_copied` (toast của App) và `isl.view3d*` (menu) là khoá **của App**, **không** nằm trong `page_strings` và không gửi ra trình duyệt.
  `ViewerServer` không nhận `lang`; App gọi `page_strings(i18n.lang())` ở `_open_3d_viewer` và truyền kết quả làm `strings`.
- **Danh sách khoá của trang** (`PAGE_STRING_KEYS`, 39 khoá, mọi khoá có ở cả `vi` lẫn `en`; tên trong `i18n.py` là `v3d.page.<tên>`): `title`, `reset`, `loading`;
  trạng thái trang: `status.nodes` (`{n}` nút), `status.hidden` (`{n}` nút bị ẩn), `status.more_desks` (`{n}` bàn không vẽ), `status.stuck_desks` (`{n}` bàn có agent treo);
  banner: `banner.stale` (`{n}` giây), `banner.expired`, `banner.disconnected`, `banner.schema`, `retry`;
  `reason`: `reason.no_data`, `reason.layout_error`, `reason.too_large`, `reason.generic`; WebGL: `webgl.missing`, `webgl.lost`;
  loại nút: `kind.project`, `kind.team`, `kind.session`, `kind.subagent`, `kind.bgtask`, `kind.overflow`;
  state bàn: `state.idle`, `state.run`, `state.wait`, `state.done`; state worker: `state.running`, `state.stuck`, `state.failed`, `state.killed`, `state.ended`, `state.unknown` (state worker `done` dùng chung khoá `state.done`);
  khung chi tiết: `detail.kind`, `detail.label`, `detail.sub`, `detail.state`, `detail.tokens`. Placeholder chỉ có dạng `{n}`.
- **Kiểm không cần Tk (V24, A8)**: `tests/test_i18n.py` giữ kiểm hai ngôn ngữ cùng bộ khoá; V24 kiểm `page_strings("vi")` và `page_strings("en")` đều có **đúng** tập `PAGE_STRING_KEYS`, mọi giá trị là `str` không rỗng, cùng tập placeholder `{n}` giữa hai ngôn ngữ, và không có khoá `v3d.open_fail`, `v3d.link_copied`, `isl.*`; A8 kiểm mọi khoá literal mà `app.js` tra trong bảng chuỗi thuộc `PAGE_STRING_KEYS`. Đổi ngôn ngữ khi viewer đang mở có hiệu lực ở lần mở sau.

### Polling

- Chu kỳ: **2 giây** khi tab hiện (`document.visibilityState === "visible"`), **30 giây** khi tab ẩn. Mỗi lượt là một `fetch`
  (`cache: "no-store"`, `credentials: "omit"`, `referrerPolicy: "no-referrer"`, timeout 5 giây bằng `AbortController`), lượt sau
  chỉ được hẹn sau khi lượt trước xong (không chồng lượt). Dùng `If-None-Match` với ETag lần trước. Khi tab đổi từ ẩn sang
  hiện, poll ngay một lượt.
- Dữ liệu do Collector đổi mỗi `refresh_sessions_sec` (mặc định 3 giây); 2 giây là để độ trễ hiển thị <= một chu kỳ
  Collector cộng 2 giây. 30 giây khi ẩn nằm dưới mức Chrome giới hạn timer của tab ẩn (một lần mỗi phút) và dưới hạn idle
  120 giây của server, nên tab ẩn vẫn giữ server sống.

### Diff, không dựng lại cảnh

- Trang giữ `Map<key, {json, objects}>`; `key` là `key` của nút trong payload (băm ổn định theo session, không phải khoá Layout
  thô) và `json` là `JSON.stringify` của nút đã nhận.
- Mỗi payload mới (200 với body mới; 304 thì bỏ qua hết): nút mới thì tạo; key có mặt nhưng `json` khác thì dựng lại riêng
  nút đó; key không còn thì dọn dẹp và xoá. Nút không đổi không bị đụng. Camera, hover và lựa chọn không bị đặt lại. `legend` và
  `palette` đổi thì dựng lại nút bị ảnh hưởng (đổi màu); `live` chỉ cập nhật khung chi tiết của nút đang chọn.
- Một bàn tới hay đi không làm bàn khác nhảy chỗ (L-S1 của board, giữ qua `prev` của viewer): nút khác có `x, y` không đổi nên
  `json` giống hệt và không bị dựng lại. Sàn khác lớn lên không đổi toạ độ tuyệt đối của sàn này (quy tắc xếp sàn theo `x`).
- Payload có `schema` không hỗ trợ: giữ cảnh cũ và hiện banner "phiên bản dữ liệu không hỗ trợ".
- Thanh trạng thái hiện số nút, `scene.hidden` (nút bị cắt bởi `MAX_NODES`), `scene.more.desks` và `scene.more.stuck_desks` (bàn
  không vẽ, theo trần của board), kèm đếm theo `state` (đếm từ `nodes`, không cần server tính).

### Mất kết nối và dữ liệu cũ

Trang có bốn trạng thái, hiện ở banner; cảnh cuối cùng luôn được giữ (làm mờ bằng một class, không xoá):

| Trạng thái | Điều kiện | Hiển thị | Hành vi tiếp |
|---|---|---|---|
| `live` | lượt poll cuối 200/304 và `now - ts <= max(3 x refresh_sec, 15)` | không banner | poll tiếp |
| `stale` | server trả lời nhưng `now - ts` lớn hơn ngưỡng trên, hoặc `ready:false` | banner vàng "Dữ liệu cũ N giây" hoặc chuỗi theo `reason` | poll tiếp |
| `expired` | `404` hoặc `403` | banner đỏ "Phiên đã hết hạn, mở lại từ menu 3D office của Wisp" | **dừng poll** |
| `disconnected` | lỗi mạng hoặc timeout liên tiếp 3 lần (hẹn lại sau 2, 4, 8 giây) | banner đỏ "Mất kết nối với Wisp (có thể Wisp đã thoát)" kèm nút "Thử lại" | **vẫn poll, mỗi 30 giây**; về `live` hoặc `stale` ngay khi một lượt thành công (banner biến mất); chuyển sang `expired` và dừng hẳn khi nhận `403` hoặc `404`; "Thử lại" chạy một lượt ngay |

Server không bao giờ trả `503`; kết nối bị đóng ngay lúc accept khi quá 16 kết nối (H1) hiện ra ở trang như lỗi mạng và đi theo hàng
`disconnected`. Vì trang **vẫn poll mỗi 30 giây** ở `disconnected` (nhỏ hơn hạn idle 120 giây của server), một nhiễu ngắn (ví dụ 16 kết nối
bị chiếm khoảng 14 giây) chỉ làm banner đỏ hiện tạm rồi tự về `live`, **không** làm server tắt (N2). `now` là `Date.now() / 1000` của trình duyệt (cùng máy với
Wisp nên cùng đồng hồ). Wisp thoát hoặc server hết hạn idle thì tab thấy lỗi mạng (kết nối bị từ chối), vào `disconnected` và tiếp tục poll mỗi 30 giây tới khi
người dùng đóng tab hoặc một lượt nhận `403`/`404`. Khi viewer được mở lại, URL (cổng và token) đổi: tab cũ (còn poll URL cũ) nhận `404` ở lượt poll kế tiếp (<= 30 giây) và vào `expired`;
người dùng mở lại từ menu.

## Lối vào UI

- Mục "3D office" trong popup chuột phải của island, ngay dưới "Control room" (`ui/menus.py`, cùng danh sách mục), gọi
  `act(app._open_3d_viewer)`. Không thêm nút trên header hay panel.
- Khoá i18n mới (vi và en): `isl.view3d` ("3D office"), `isl.view3d.sub`, `v3d.open_fail` (không mở được viewer, xem
  `wisp.log`), `v3d.link_copied` (đã chép liên kết 3D vào clipboard), cùng các khoá `v3d.page.*` cho trang (danh sách đóng `PAGE_STRING_KEYS` ở mục "Trang", tên state, `reason`, banner, nút); chỉ `v3d.page.*` đi qua `viewer.page_strings` ra trình duyệt.
- `App.quit` dừng viewer. Đổi theme hoặc ngôn ngữ trong Cài đặt **không** đóng viewer (khác Control room): trang có theme tối
  cố định của riêng nó.
- Log (`wisp.log`): `viewer: started on port <n>`, `viewer: stopped (idle|quit|error)`, `viewer: layout error <TypeName>`.
  **Không log token, URL đầy đủ, đường dẫn request, header, chuỗi từ agent**.

## Cấu hình

**Không thêm khoá config.** Cổng do hệ điều hành cấp (Quyết định A). Chu kỳ poll (2 giây, 30 giây), hạn idle (120 giây),
`SPRITE_SIZE` (128) là hằng trong `viewer.py` và `app.js`; `MAX_NODES` (1000) và `FLOOR_GAP` (6) là hằng trong
`viewer_payload.py`. Viewer dùng lại `refresh_sessions_sec` (đã có) cho ngưỡng dữ liệu cũ, và dùng lại hai khoá của board
`board_max_desks` (48) và `board_max_workers` (12) cho trần bàn và subagent (một nguồn cấu hình cho cả Board lẫn viewer; viewer
không thêm trần riêng ngoài `MAX_NODES`). Hai khoá này **thuộc slice `office.py`/config chung của board** (do spec board sở hữu và
thêm vào `config.py`); slice của viewer phụ thuộc vào slice đó, không tự thêm chúng. Cũng như vậy, `refresh_sessions_sec` được ép
trước khi vào payload (mục "Payload"). Nếu sau này cần đặt cổng hoặc tắt viewer, thêm khoá lúc đó.

## Lỗi và an toàn

**Lưu ý về mã (errata E5):** mã `S1` đến `S26` ở đây là mã **yêu cầu bảo mật của viewer** (và `H1` đến `H7` của mục "Cứng hoá server"); chúng **không liên quan** tới các slice `S0` đến `S5` của plan. Mã không đổi để các báo cáo review cũ vẫn khớp.

Mỗi dòng là một yêu cầu quan sát được; cột "Kiểm" trỏ tới test ở mục Kiểm thử. Mã `H1` đến `H7` nằm ở mục "Cứng hoá server".

| # | Yêu cầu | Kiểm |
|---|---|---|
| S1 | Chỉ bind `127.0.0.1` bằng socket `AF_INET`: `server.server_address[0] == "127.0.0.1"`; không bao giờ `0.0.0.0`, `""`, `::`, `localhost`; kết nối tới `::1:<port>` bị từ chối; chuỗi nguồn của `viewer.py` không chứa `"0.0.0.0"` | V1, V2 |
| S2 | Token sinh bằng `secrets.token_urlsafe(24)` (192 bit, 32 ký tự); khác nhau giữa hai lần `ViewerServer` được tạo và khác token hooks | V3 |
| S3 | So token bằng `hmac.compare_digest` (trên bytes UTF-8); sai token, thiếu token, token cắt cụt hoặc dài hơn: đều `404` cùng một body | V4, V5 |
| S4 | `Host` phải có **đúng một** header và bằng **chính xác** `127.0.0.1:<port>` (so chuỗi, không cắt khoảng trắng). Thiếu, hai header `Host`, `localhost:<port>`, `evil.example:<port>`, `127.0.0.1` không cổng, `[::1]:<port>`, giá trị có khoảng trắng thừa ở đầu hoặc cuối: `403`, ở **mọi** đường dẫn kể cả khi token đúng (chống DNS rebinding) | V6 |
| S5 | `/api/*`: `Origin`, nếu có, phải xuất hiện **đúng một lần** và bằng chính xác `http://127.0.0.1:<port>`; `Sec-Fetch-Site`, nếu có, đúng một lần và bằng `same-origin`. Hai `Origin`, hai `Sec-Fetch-Site`, `Origin: null`, `http://evil.example`, `http://localhost:<port>`, giá trị có khoảng trắng thừa: `403`; không có cả hai: `200` khi token đúng | V7 |
| S6 | CSP đúng chuỗi ở "Endpoint" (gồm `require-trusted-types-for 'script'; trusted-types 'none'`) trên **mọi** đáp ứng, kể cả đáp ứng do stdlib sinh (`400`, `414`, `431`, `500`, `501`, `505`) và `200`, `304`, `403`, `404`, `405`; không có `unsafe-inline` hay `unsafe-eval`; `default-src 'self'`; three.js r186 không cần eval (đã kiểm nguồn) | V8, A3 |
| S7 | Danh sách file cố định: các đường dẫn như `/v/<token>/../app.js`, `/v/<token>/vendor/`, `/v/<token>/vendor/LICENSE`, `/v/<token>/vendor/VERSION.txt`, `/v/<token>/api/sprite/../x`, `%2e%2e`, `app.js?x=1`, `//` đều `404`; không directory listing; request handler không gọi `open`/`Path.read_*` với bất kỳ phần nào của request | V9, V10 |
| S8 | Chỉ GET: `HEAD POST PUT DELETE PATCH OPTIONS` trả `405` kèm `Allow: GET`; phương thức khác `501`; server không đọc body. Mọi đáp ứng (kể cả lỗi) đóng kết nối (`HTTP/1.0` và `close_connection = True`): `405` có body rồi request thứ hai trên cùng kết nối không được phục vụ (chống desync) | V11, V27 |
| S9 | Chuỗi từ agent chỉ vào trang bằng `textContent`/`fillText`; `app.js`, `index.html`, `style.css` không chứa `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `DOMParser`, `createContextualFragment`, `srcdoc`, `eval(`, `new Function`; `index.html` không có `<script>` thiếu `src`, không có `style=` hay `on*=`; không có URL `http://` hoặc `https://` trong ba file này. Đây là lưới phụ; lớp chính là CSP và trusted types | A1, A2 |
| S10 | Token không vào log: không dòng nào ghi bởi `viewer.py`, `app.py` (đường mở viewer, kể cả nhánh `webbrowser.open` lỗi) hay `handle_error`/`log_message` chứa token hoặc URL; log chỉ ghi tên loại ngoại lệ, kể cả khi ngoại lệ có thông điệp chứa URL | V12, W4, W9 |
| S11 | `Referrer-Policy: no-referrer` trên mọi đáp ứng; trang không có liên kết ra ngoài | V8, A2 |
| S12 | Không nhúng được: `frame-ancestors 'none'` (trong CSP) và `X-Frame-Options: DENY` trên mọi đáp ứng | V8 |
| S13 | Không CORS mở: không đáp ứng nào có header `Access-Control-*`; `OPTIONS` là `405` | V8, V11 |
| S14 | Token lộ qua lịch sử trình duyệt: token mới mỗi lần `ViewerServer` được tạo; sau `stop()` URL cũ không kết nối được; server mới (kể cả cùng cổng) trả `404` cho token cũ; server tự tắt sau 120 giây idle | V3, V13, V14 |
| S15 | Slot giữ bytes bất biến; thread server không gọi Tk, không chạm snapshot/`org`/Layout/`prev`/payload; `office_layout` và `viewer_payload` chỉ chạy ở main thread trong `publish`; request handler không đọc đĩa ngoài `mascots.png`. **Thread của `webbrowser.open` không gọi Tk, clipboard hay toast**: nó chỉ đặt kết quả vào `queue.Queue`; clipboard và toast chạy ở main thread | V15, V16, V25, V28, W4 |
| S16 | Giới hạn tài nguyên từ cửa vào: tối đa **16 kết nối đồng thời** (kết nối thứ 17 bị đóng ngay, không tạo thread; bộ đếm giảm trên mọi đường, kể cả khi tạo thread lỗi); **hạn tổng 10 giây mỗi kết nối** tính từ accept, gồm cả phía đọc lẫn phía ghi, thi hành ở `service_actions` bằng `shutdown` (chỉ thread xử lý được `close`), cộng `timeout` 5 giây mỗi lần `recv`/`send`; dòng yêu cầu tối đa 256 byte (`414`), tối đa 32 header, mỗi dòng <= 4096 byte, tổng <= 16 KiB (`431`); payload `scene` > 1 MiB không bao giờ được phục vụ: giữ payload cũ nếu đã có, ngược lại `ready:false, reason:"too_large"` (HTTP 200) | V17, V17b, V18, V18b, V19, V20 |
| S17 | Sprite: chỉ `mid` thuộc `mascots.all_mascots()` và `mood` thuộc `mascots.MOODS` được dựng; ngoài tập `404` và `mascots.png` không được gọi | V21 |
| S18 | Mỗi request hợp lệ ghi nhận hoạt động chỉ khi qua đủ Host, token, Origin; request bị từ chối không làm chậm hạn idle | V13 |
| S19 | Viewer chỉ đọc: không có route ghi, không có nút điều khiển agent trong `index.html`/`app.js` (không `fetch` với `method` khác GET, không `sendBeacon`, không `WebSocket`, không `XMLHttpRequest`) | A2 |
| S20 | `hooks.py` và `tests/test_hooks.py` không đổi: `git diff --stat` của thay đổi không có hai file này | G1 |
| S21 | Payload gửi ra trình duyệt chỉ có các trường trong allowlist của "Bộ chuyển đổi" (kể cả khoá lồng); **không** có `ref`, `session_id`, `root`, `top`, `seed`, khoá Layout thô, đường dẫn hay `limits`; `key` là HMAC có khoá bí mật theo vòng đời server, không chứa `session_id` hay đường dẫn và không đảo ngược được bằng SHA-256 trần | C9, C10, V29 |
| S22 | `viewer_payload.py` thuần: không import `tkinter`, `os`, `subprocess`, `pathlib`, `socket`, `http`, `threading`; không đọc đĩa; mọi chuỗi qua bộ làm sạch rồi cắt (60 và 120 ký tự); `json.dumps(..., allow_nan=False)` không lỗi; chuỗi agent không bao giờ đi vào đường dẫn, `mid` hay `mood` | C1, C6, C7 |
| S23 | `allow_reuse_address = False`; trên Windows `SO_EXCLUSIVEADDRUSE` trước `bind` (**chưa kiểm: `unavailable`**) | V27 |
| S24 | Không có TOCTOU ở file tĩnh: mỗi file đọc **một lần** vào buffer lúc `start()`; hằng băm tính trên chính buffer đó; bytes phục vụ chính là buffer đó. Sửa file trên đĩa sau `start()` không đổi bytes phục vụ; file vendor bị sửa trước `start()` thì `start()` thất bại | V22 |
| S25 | `state` và khoá `legend` của payload là enum đóng; trang tra bằng `Map`/`Object.hasOwn`, chỉ dựng URL sprite khi `mascot` khớp `^m[0-9]{2}$` và `mood` thuộc 5 giá trị cố định; không điều hướng và không gán `.href`/`.src` | C16, A2, M16 |
| S26 | `refresh_sec` trong payload luôn là số hữu hạn trong [1, 60] (giá trị config lạ thành 3) | V26 |

Lỗi khác:

- Thiếu file asset, lệch checksum, bind lỗi: `start()` trả `False`; Wisp ghi log, toast `v3d.open_fail`, không có server, không
  mở tab. Không lỗi nào làm hỏng island hay Control room.
- `webbrowser.open` lỗi hoặc trả `False`: main thread chép URL vào clipboard, toast `v3d.link_copied`; server vẫn chạy và tắt theo
  idle nếu không ai dùng.
- Mất kết nối, dữ liệu cũ, hết hạn: xem "Mất kết nối và dữ liệu cũ".
- Giới hạn đã biết (chấp nhận, ghi ở Rủi ro mở): lộ URL qua tham số tiến trình và lịch sử trình duyệt (theo từng nền tảng, rủi ro 6);
  tiến trình khác của cùng người dùng đọc được token từ bộ nhớ hoặc lịch sử trình duyệt thì vượt ngoài mô hình đe doạ của spec này;
  một tiến trình local vẫn có thể chiếm 16 kết nối mỗi lần tối đa 10 giây (làm trang báo mất kết nối), giảm nhưng không loại bỏ (rủi ro 14).

## Kiểm thử

Lệnh chạy: `python -m unittest discover -s tests` (stdlib, không cần trình duyệt). Test server dùng `ViewerServer` thật với
cổng 0, `http.client` và socket thô (để đặt tuỳ ý `Host`, `Origin`, gửi nhiều header trùng, nhỏ giọt), `clock` giả cho vòng đời, và
hằng `CONNECTION_DEADLINE_SEC` hạ xuống vài giây để test không chờ 10 giây.

Ghi chú về phụ thuộc: (1) fixture của test viewer dựng bằng `org.build` (không dùng dict `org` viết tay), và viewer chỉ đọc các khoá
`department`, `description`, `tokens`, `started`, `last_activity`, `state` của worker; nó **không đọc `type` hay `agent_type`**. Lỗi
có sẵn `org.py:187` (xuất `type`) so với `control_room._session_rows` (đọc `agent_type`) được sửa ở slice S0, làm trước slice viewer (đã duyệt), và không
thuộc spec này. (2) Hai khoá `board_max_desks`, `board_max_workers` thuộc slice `office.py`/config chung của board; test viewer đặt
chúng qua `cfg` truyền vào, không sửa `config.py`.

**`tests/test_viewer.py` (T1, server)**

- V1: `server_address[0] == "127.0.0.1"`, `server.socket.family == socket.AF_INET`.
- V2: kết nối `::1:<port>` bị từ chối; chuỗi `"0.0.0.0"` không có trong `viewer.py`.
- V3: hai server liên tiếp có token khác nhau, mỗi token dài >= 32 ký tự bảng chữ cái urlsafe, khác token của `hooks.new_token`.
- V4: token đúng thì `/`, `/app.js`, `/style.css`, `/vendor/three.module.js`, `/vendor/three.core.js`, `/vendor/OrbitControls.js`, `/api/strings`,
  `/api/layout` đều `200` với đúng `Content-Type` ở bảng endpoint.
- V5: token sai, rỗng, cắt cụt (31 ký tự), thêm ký tự, khác hoa thường: `404`, body giống hệt nhau.
- V6: `Host` trên ba đường dẫn khác nhau (kể cả `/api/layout` với token đúng): mọi giá trị ở S4 đều `403`, gồm **hai header `Host`
  cùng giá trị đúng** và giá trị đúng có một khoảng trắng ở cuối; `Host` đúng duy nhất thì `200`.
- V7: bảng `Origin` và `Sec-Fetch-Site` ở S5 trên `/api/layout`, `/api/strings`, `/api/sprite/...`, gồm **hai `Origin`** (một đúng, một
  sai; hai đúng) và hai `Sec-Fetch-Site`: đều `403`; `/app.js` không bị kiểm `Origin`.
- V8: mọi đáp ứng `200`, `304`, `400` (dòng yêu cầu sai cú pháp), `403`, `404`, `405`, `414`, `431`, `500` (patch handler ném lỗi), `501`
  (`FOO`), `505` (`GET / HTTP/2.0`) có đủ CSP chính xác (kể cả `require-trusted-types-for 'script'; trusted-types 'none'`),
  `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Cross-Origin-*`, `Permissions-Policy`;
  không có header nào bắt đầu bằng `Access-Control-`; CSP không chứa `unsafe-inline`, `unsafe-eval`, `data:`, `blob:`, `*`. Với các
  mã do stdlib sinh (`400`, `414`, `431`, `500`, `501`, `505`), body là **chuỗi cố định theo mã** và **không chứa** dòng yêu cầu,
  đường dẫn hay giá trị header đã gửi (gửi `GET /<script>alert(1)</script> HTTP/1.1` và header `X-Test: <script>`, rồi tìm các chuỗi
  đó trong body: không thấy).
- V9: danh sách đường dẫn tấn công ở S7 đều `404` và body không chứa nội dung file nào.
- V10: patch `builtins.open`, `pathlib.Path.read_bytes` và `Path.read_text` để ghi lại lời gọi trong lúc xử lý request; ngoài đường
  dẫn tới cache PNG, không có lời gọi nào từ thread handler.
- V11: sáu phương thức chuẩn trả `405` có `Allow: GET`; phương thức tự đặt (`FOO`) trả `501`. **Đóng kết nối (H4)**: (a) `POST` có `Content-Length: 100` kèm đủ 100 byte là một request `GET /v/<token>/api/layout` hoàn chỉnh trên cùng kết nối: client **thấy `405`** rồi EOF (`recv` trả `b""`) và **không** có đáp ứng thứ hai; (b) hai request `GET` liên tiếp trong một gói: chỉ có đáp ứng của request đầu rồi đóng; (c) `POST` với body 1 MB gửi liên tục: server trả lời và đóng mà không đọc body; vì server đóng khi body chưa đọc hết, TCP của client **có thể nhận reset và không bao giờ thấy `405`**, nên test khẳng định chỉ "kết nối bị đóng (EOF hoặc `ConnectionResetError`) và không có đáp ứng thứ hai chứa dữ liệu viewer", **không** khẳng định thấy `405` ở trường hợp (c) (ca (a) vẫn khẳng định thấy `405`); mọi đáp ứng lỗi có `Connection: close` hoặc kết nối bị đóng sau đáp ứng.
- V12: ghi lại mọi `log` truyền vào `ViewerServer`, `stderr` và logger của `viewer.py` khi chạy cả luồng thường và luồng lỗi
  (handler ném lỗi do patch `publish` trả dữ liệu hỏng, `handle_error`); không chuỗi nào chứa token, `/v/` hay địa chỉ khách.
- V13: vòng đời với `clock` giả: `idle_for()` tăng theo `clock`; request `/api/layout` hợp lệ (200 và 304) đặt lại về 0; request bị
  `403`/`404` không đặt lại; `/app.js` không đặt lại. Mô phỏng `_viewer_tick`: idle > 120 thì `stop()`.
- V14: `stop()` idempotent; sau `stop()` kết nối tới cổng cũ bị từ chối; khởi tạo server mới (có thể cùng cổng) trả `404` cho
  token của server cũ.
- V15: `publish` gọi từ thread chính, thread server đọc; đặt 1000 payload liên tiếp trong khi 4 thread client poll: mọi đáp ứng
  là một body JSON nguyên vẹn của đúng một lần `publish` (không lẫn, không rách).
- V16: `publish` với `office_layout` hoặc `viewer_payload` bị patch ném lỗi (kể cả `ValueError` do Layout `version` lạ) giữ nguyên
  payload cũ; khi chưa có payload nào thì `ready:false, reason:"layout_error"`; log không chứa nội dung lỗi. (Trường hợp org không hợp lệ có test riêng ở V28.)
- V17: **trần kết nối (H1)**: mở 16 kết nối TCP rồi giữ im lặng: `threading.active_count()` tăng không quá 16 so với trước; kết nối
  thứ 17 bị server đóng ngay (đọc được EOF/reset trong < 1 giây, không nhận byte nào); đóng một kết nối thì kết nối mới được nhận; một
  `GET` hợp lệ trên kết nối thứ 17 không bao giờ được phục vụ trong lúc 16 kết nối kia còn mở.
- V18: **hạn tổng (H2)**: với `CONNECTION_DEADLINE_SEC` hạ xuống 3, gửi dòng yêu cầu hợp lệ rồi nhỏ giọt một byte header mỗi 0,5 giây
  (không bao giờ im quá `timeout` mỗi `recv`): server đóng kết nối trong <= 3 giây cộng 1 giây dung sai, dù từng `recv` đều có dữ
  liệu; kết nối im hoàn toàn bị đóng bởi `timeout` mỗi `recv` (hạ xuống 1 giây trong test); sau khi nhỏ giọt bị cắt, số thread trở về mức cũ.
- V17b: **bộ đếm không rò (H1)**: (1) gây 20 lỗi `500` liên tiếp (patch handler ném lỗi) rồi mở 16 kết nối `GET` hợp lệ đồng thời: cả 16 được phục vụ `200`, và kết nối thứ 17 mới bị đóng; (2) patch `threading.Thread.start` ném `RuntimeError` cho 20 kết nối (mỗi kết nối bị đóng, client nhận EOF), rồi bỏ patch: 16 kết nối `GET` hợp lệ mới đều `200`; bộ đếm nội bộ về 0 khi mọi kết nối đã đóng; (3) kết nối bị hạn H2 cắt cũng làm bộ đếm về 0.
- V18b: **hạn tổng phía ghi (H2) và chỉ thread xử lý đóng socket**: với `CONNECTION_DEADLINE_SEC` hạ xuống 3, client gửi một `GET` hợp lệ tới `/v/<token>/vendor/three.core.js` (1,4 MB), đặt `SO_RCVBUF` nhỏ và **không bao giờ đọc**: thread xử lý kẹt ở `send`; trong <= 3 giây cộng 1 giây dung sai kết nối bị cắt (client đọc được EOF hoặc reset sau khi bắt đầu đọc, thread xử lý kết thúc, `threading.active_count()` về mức cũ, bộ đếm về 0). Ghi lại thread gọi `socket.shutdown` và `socket.close` (patch bọc): `shutdown` đến từ thread `serve_forever`, `close` **chỉ** đến từ thread xử lý của chính kết nối đó, không lần nào từ thread `serve_forever`.
- V19: **giới hạn dòng và header (H3)**: dòng yêu cầu 257 byte `414`; 33 dòng header `431`; một dòng header 4097 byte `431`; tổng header 16 KiB + 1 `431`;
  và server **không đọc quá** giới hạn + 1 byte của dòng yêu cầu (gửi dòng 1 MiB không xuống dòng: server trả lời và đóng sau khi nhận
  không quá khoảng 300 byte của nó, kiểm bằng socket thô đếm byte server đã tiêu thụ hoặc thời gian trả lời không phụ thuộc kích thước).
- V20: **payload > 1 MiB (E2)**: (a) khi **đã có** payload hợp lệ: `publish` một `org` làm body UTF-8 > 1 048 576 byte (fixture lớn, hoặc hạ hằng giới hạn bằng patch) thì đáp ứng `/api/layout` **vẫn là bytes, ETag và `ts` của payload cũ** (không `ready:false`, không `scene` mới), `prev` đã được cập nhật
  (lần `publish` sau với `org` nhỏ cho vị trí không nhảy), log có `viewer: payload too large` và không chứa dữ liệu agent; (b) khi **chưa có** payload nào: đáp ứng là HTTP `200` với body JSON đúng `{"v":1,"ts":<ts>,"ready":false,"reason":"too_large","refresh_sec":<số>}` (không có khoá `scene`); (c) body đúng 1 048 576 byte
  được phục vụ bình thường (ranh giới); (d) trong mọi trường hợp không có đáp ứng nào mang `scene` dài hơn 1 MiB.
- V21: `/api/sprite/<mid>/<mood>.png` với cặp hợp lệ trả PNG (chữ ký `\x89PNG\r\n\x1a\n`), `Content-Type: image/png`; `mid` hoặc
  `mood` lạ, rỗng, chứa `..`, `/`, `%2f`, `m01.png`, `M01`, hoặc dài 1000 ký tự: `404` và `mascots.png` (patch) không được gọi; gọi lần 2 cùng cặp không
  gọi lại `mascots.png` (cache RAM); nhiều request sprite cùng lúc không chạy `mascots.png` song song (khoá dựng).
- V22: `start()` với thiếu một file asset, hoặc một trong ba file vendor (`three.module.js`, `three.core.js`, `OrbitControls.js`; kiểm lần lượt từng file) bị sửa một byte trước `start()` (thư mục assets tạm): trả `False`, không bind socket,
  `error` không chứa đường dẫn đầy đủ của người dùng. **TOCTOU (S24)**: `start()` thành công rồi sửa/ghi đè `three.core.js` và `OrbitControls.js` trên đĩa:
  bytes `/vendor/three.core.js` và `/vendor/OrbitControls.js` phục vụ vẫn có SHA-256 bằng `viewer.VENDOR_SHA256` tương ứng; patch `open`/`Path.read_bytes` đếm lượt
  đọc mỗi file vendor trong `start()`: đúng 1 lần.
- V23: ETag: hai lần gọi cùng payload cho cùng ETag; `If-None-Match` khớp trả `304` không body.
- V24: **`viewer.page_strings` (E3, không cần Tk)**: `page_strings("vi")` và `page_strings("en")` đều trả đúng tập `PAGE_STRING_KEYS` (39 khoá), mọi giá trị `str` không rỗng, cùng tập placeholder (`{n}`) giữa hai ngôn ngữ, không có khoá `v3d.open_fail`, `v3d.link_copied` hay `isl.*`; `page_strings("xx")` cho bảng của `en`;
  hàm không đổi `i18n.lang()` (so trước và sau) và không import `tkinter` (quét `ast`); `ViewerServer(strings=page_strings("en"), ...)` phục vụ ở `/api/strings` đúng dict đó (JSON, so bằng nhau) và `ViewerServer.__init__` **không có tham số `lang`** (`inspect.signature`).
- V25: `prev`: `publish` gọi `office_layout` với `prev` là Layout của lần `publish` trước (đối chiếu bằng patch ghi đối số); `prev`
  của viewer là đối tượng riêng, không phải đối tượng truyền cho Board (hai bản độc lập: sửa một bản không ảnh hưởng bản kia);
  `prev` vẫn được cập nhật khi `viewer_payload` ném lỗi; hai lần `publish` liên tiếp cùng `org` cho cùng `nodes` (vị trí không nhảy).
- V26: `refresh_sec`: cfg `"abc"`, `None`, `True`, `float("nan")`, `float("inf")`, `-1`, `0` cho `3`; `0.5` cho `1`; `1000` cho `60`; `5` cho `5`;
  `json.loads` của body thấy số hữu hạn (không có `NaN`).
- V27: thuộc tính của lớp: `ViewerHTTPServer.allow_reuse_address is False`; lớp handler có `protocol_version == "HTTP/1.0"` và đặt
  `close_connection = True` sau mỗi đáp ứng; `timeout` của handler khác `None`; `daemon_threads is True`. **`SO_EXCLUSIVEADDRUSE` không có trên macOS** (`socket.SO_EXCLUSIVEADDRUSE` không tồn tại): (a) import `viewer.py` trên macOS không lỗi (hằng không được tham chiếu lúc import); (b) nhánh theo nền tảng được quyết định **lúc `server_bind`**, không lúc import: test tiêm hằng bằng `mock.patch.object(socket, "SO_EXCLUSIVEADDRUSE", -5, create=True)` và patch `sys.platform = "win32"`, với socket giả, rồi kiểm `server_bind` gọi `setsockopt(SOL_SOCKET, -5, 1)` **trước** `bind`; (c) với `sys.platform = "darwin"` `server_bind` không gọi `setsockopt` với hằng đó và không tham chiếu thuộc tính `SO_EXCLUSIVEADDRUSE`. Trên Windows thật: `unavailable`.
- V28: **`office.valid_org`**: `publish` với `org` là `None`, `{}`, `{"projects": 5}`, `[]`, chuỗi: **không gọi `office_layout`** (patch ghi lời gọi), `prev` không đổi
  (cùng đối tượng trước và sau), slot không đổi (đáp ứng `/api/layout` vẫn là bytes và ETag cũ, kể cả `ts` cũ); khi **chưa có payload nào** thì đáp ứng là
  `ready:false, reason:"no_data"`. Sau đó `publish` với `org` hợp lệ gọi `office_layout` với đúng `prev` cũ (bàn giữ nguyên `x, y` so với trước lúc lỗi).
  `publish` với `{"projects": []}` (hợp lệ, không session) **gọi** `office_layout`, thay `prev` bằng Layout rỗng, và lần `publish` kế tiếp với session cũ quay lại cấp
  ô theo quy tắc "ô trống thấp nhất" (slot đã được giải phóng); payload ra `nodes: []`.
- V29: `key_secret`: `ViewerServer.start()` sinh `key_secret` (16 byte) đúng một lần (patch `secrets.token_bytes` đếm lượt gọi) và truyền cho mọi lần `viewer_payload`; hai server khác nhau có `key_secret`
  khác nhau (cùng dữ liệu cho `key` khác nhau trong payload phục vụ); trong một vòng đời, hai lần `publish` cùng `org` cho cùng `key`; `key_secret` không xuất hiện ở bất kỳ đáp ứng, log hay `ViewerServer.url`.

**`tests/test_viewer_payload.py` (T1, bộ chuyển đổi thuần; dùng `office_layout` thật của board trên `org_out` do `org.build` dựng và
`theme.DARK` cho C1, C2, C4 đến C13, C15; **Layout dựng tay** cho C3 (`level` trùng hoặc sai kiểu), C14 (`version` lạ) và C16 (khoá lạ), vì
`office_layout` thật không bao giờ sinh các trường hợp đó)**

- C1: `ast` quét `viewer_payload.py`: không import `tkinter`, `os`, `subprocess`, `pathlib`, `socket`, `http`, `threading`;
  đầu vào (`layout`, `org_out`, `theme`, `mascot_ids`) không bị sửa (so bản sao sâu); đầu ra chỉ gồm `dict`, `list`, `str`, `int`,
  `float`, `bool`, `None`; `json.dumps(out, allow_nan=False)` không lỗi trên mọi fixture (kể cả `tokens` quá lớn, `started`
  là `NaN`/`inf` trong `org_out`: thành `null`).
- C2: làm phẳng: số nút và `kind` khớp Layout (mỗi floor, cluster, desk, worker, device đúng một nút; `more.n > 0` sinh đúng một
  `overflow` có `count` và `counts` đã chuẩn hoá, khoá lạ thành `unknown`; `more.desks > 0` sinh nút `overflow` toàn cục **không có
  `counts`**, có `alert` bằng `stuck_desks` khi > 0); cha đứng trước con trong `nodes`; mọi `parent` trỏ tới một `key` có mặt và đứng
  trước; `alert` chỉ có ở `session` và `overflow` toàn cục.
- C3: toạ độ tuyệt đối (Layout dựng tay): với hai sàn `level` 0 và 1, mọi nút của sàn 1 có `x = 36 + x_cục_bộ`; `y` không đổi; sàn `level` 3
  (khuyết 2) ở `x = 108`; `level` trùng hoặc sai kiểu (`"1"`, `-1`, `True`, `None`) dùng `max + 1` và không chồng sàn; sàn đưa vào sai thứ
  tự `level` vẫn ra cùng toạ độ; nút overflow toàn cục ở `x = (level lớn nhất + 1) * 36`, `y = 0`; hằng `36` suy ra từ
  `office.FLOOR_CLUSTER_COLS`, `office.CLUSTER_W` cộng `FLOOR_GAP`, không chép số.
- C4: `bounds` bằng `max(x + w)` và `max(y + h)` trên mọi nút kể cả overflow toàn cục; Layout rỗng cho `bounds {"w": 0, "h": 0}` và
  `nodes: []`; không có nút nào ngoài `bounds`.
- C5: ổn định: dùng `prev` qua các lần gọi (thêm và bớt session, thêm cụm làm sàn 0 cao thêm): `x, y` tuyệt đối của mọi nút còn lại
  không đổi, kể cả nút trên các sàn khác sàn vừa lớn lên (quy tắc xếp sàn theo `x`); cùng đầu vào hai lần cho `nodes` giống hệt.
- C6: `legend` đúng bảng: với `Layout["styles"]` thật của board và `theme.DARK`, mỗi `color` là hex `#rrggbb` chữ thường bằng
  `theme.DARK[tên]`; tên không có trong `theme` hoặc giá trị không phải hex thì thành `theme["idle"]`; `mood` là `str` thuộc
  `mascots.MOODS` (ngoài tập thành `idle`); `marker` thuộc `ring|cross|null`; hai nhóm `desk` và `worker` đều có hàng cho mọi state
  enum của board; `palette` đủ bảy khoá hex; chuỗi `theme` giả (một giá trị `"javascript:..."`) không ra khỏi hàm dưới dạng màu.
- C7: nhãn: `label` <= 60 và `sub` <= 120 ký tự; chuỗi độc (`<img onerror>`, `{ } \ [ $ %`, xuống dòng, bidi U+202E, U+200B, ký tự
  điều khiển, chuỗi 10 000 ký tự) ra văn bản đã làm sạch và cắt; `sub` của subagent lấy đúng `description` của worker qua `ref`;
  `ref` ngoài khoảng, kiểu sai, trỏ vào BgTask, hoặc `org_out = None` cho `sub = ""`, không ném lỗi; team: `label` là thư mục cuối
  của `top` (kiểu `/` lẫn `\`).
- C8: mascot: `mascot = mascot_ids[office.mascot_index(seed, len(mascot_ids))]`; cùng `session_id` ở hai worktree cùng `mascot`;
  cùng phòng ban cùng `mascot`; `mascot_ids` rỗng thì không có trường `mascot` ở mọi nút; mọi `mascot` xuất ra thuộc `mascot_ids`;
  device không có `mascot`.
- C9: không rò thông tin: mọi nút chỉ có khoá thuộc allowlist (`key kind parent x y w h state label sub mascot alert count counts`) và `kind` thuộc đúng 6 giá trị;
  không khoá top-level ngoài (`schema bounds palette legend more hidden nodes live`); **kiểm đệ quy khoá lồng**: `bounds` chỉ có `w`, `h`; `palette` đúng bảy khoá; `legend` chỉ có `desk`, `worker`, mỗi nhóm chỉ có khoá thuộc enum state tương ứng
  và mỗi `Style` chỉ có `color`, `mood`, `marker`; `more` chỉ có `desks`, `stuck_desks`; `live` chỉ có khoá bằng `key` của một nút `subagent`/`bgtask` có mặt, giá trị chỉ có `tokens`, `started`, `last_activity`; `counts` chỉ có khoá thuộc enum state của worker;
  **không có khoá nào ở bất kỳ cấp lồng nào bằng `__proto__`, `constructor`, `prototype` hay `hasOwnProperty`** (quét đệ quy mọi khoá của đầu ra); không giá trị nào trong JSON đầu ra chứa
  `session_id`, `root` hay `top` đầy đủ của fixture (tìm chuỗi trong JSON); không có `ref`, `seed`, `limits`.
- C10: `key`: là chuỗi 16 ký tự hex; duy nhất trong payload; **cùng `key_secret` thì cùng khoá Layout cho cùng `key`** giữa hai lần gọi; **`key_secret` khác thì `key`
  khác** cho cùng khoá Layout (không có giá trị `key` cố định dùng chung giữa các tiến trình, nên không có kiểm "cố định theo tiến trình"); `parent` dùng cùng cách; không chứa
  `session_id`; khoá Layout trùng (hậu tố `#1`) vẫn ra `key` khác nhau; không đảo ngược được bằng SHA-256 trần: `key` của một project **không** bằng
  `sha256(<khoá>)[:16]` (kiểm với `key_secret` ngẫu nhiên); va chạm giả (patch HMAC) giữ nút đầu, bỏ nút sau; `viewer_payload` không tự sinh ngẫu nhiên (hai lần gọi cùng đối số cho
  cùng đầu ra). `ViewerServer.start()` gọi `secrets.token_bytes(16)` đúng một lần, và hai server khác nhau có `key_secret` khác nhau (V29).
- C11: `alert`: session có `alert.stuck = 2` ra `alert: 2`; `0` thì không có trường; `stuck_desks` của `more` toàn cục đi vào `alert` của
  overflow toàn cục; giá trị âm, không phải số thì thành `0` (bỏ).
- C12: trần: fixture có 1200 nút Layout (đặt `board_max_desks` cao) cho `len(nodes) == 1000` và `hidden == 200`; cắt từ cuối theo thứ tự
  cha trước con (không nút nào mất cha); `more`, `alert` không đổi so với không cắt; `live` chỉ còn khoá của nút còn lại,
  giá trị bằng bản không cắt (E8).
- C13: `live`: có `tokens` (int >= 0), `started`, `last_activity` cho subagent và `started` cho bgtask, khoá bằng `key` của nút; số lạ thành
  `null`/`0`; `nodes` giống hệt nhau khi chỉ `tokens` hoặc `last_activity` đổi (nên diff của trang không dựng lại).
- C14: (Layout dựng tay) `layout["version"]` khác `1`, hoặc `layout` không phải dict, ném `ValueError`; `org_out` hỏng (sai kiểu) không ném lỗi.
- C15: Layout rỗng (`office_layout(None, cfg)`) cho payload rỗng hợp lệ (`schema 1`, `nodes []`, `legend` và `palette` đầy đủ) và
  `json.dumps` thành công.
- C16: **ép enum (L5)**, Layout dựng tay: `state` của desk bằng `"constructor"`, `"__proto__"`, `"toString"`, `"run "`, `None`, `5`, `"RUN"` thành
  `idle`; `state` của worker và device bằng các giá trị đó thành `unknown`; `state` hợp lệ giữ nguyên; `layout["styles"]` có thêm khoá `"constructor"`
  hoặc `"__proto__"` thì `legend` không có khoá đó; `mood` ngoài `mascots.MOODS` thành `idle`; `marker` lạ thành `null`; `json.dumps` của đầu ra
  không chứa `"__proto__"` làm khoá ở bất kỳ cấp nào.

**`tests/test_viewer_assets.py` (nhóm test assets, tĩnh; nhãn "T2" ở rev 5 bị bỏ vì dễ nhầm với tier đo của plan, errata E6)**

- A1: quét `app.js`, `index.html`, `style.css` (không quét `vendor/`) không có chuỗi cấm của S9: `innerHTML`, `outerHTML`,
  `insertAdjacentHTML`, `document.write`, `DOMParser`, `createContextualFragment`, `srcdoc`, `eval(`, `new Function`, `setTimeout("`,
  `setInterval("`. Đây là lưới phụ: quét chuỗi con không bắt được mã bị làm rối; không dùng A1 làm bằng chứng duy nhất cho S9.
- A2: `index.html` không có `<script>` thiếu `src`, không có thuộc tính `style=`, không có `on[a-z]+=`, không có
  `http://`/`https://`; `app.js` không có `http://`, `https://`, `sendBeacon`, `WebSocket`, `XMLHttpRequest`, `method:` khác GET,
  `localStorage`, `document.cookie`, **`location`, `window.open`, `.href =`, `.src =`, `.action =`**; mọi lời gọi `setAttribute(` có đối số đầu là một
  literal thuộc `{aria-label, aria-live, role, tabindex}`; có đúng một định nghĩa `spriteUrl` và regex `^m[0-9]{2}$` cùng danh sách 5 mood nằm trong nó.
  **Tra cứu theo khoá động (N4)**: không có `legend[`, `palette[`, `live[`, `counts[`, `more[`, `nodes[`, `kinds[` hay `builders[`; **mọi truy cập thuộc tính bằng biểu thức không phải literal (`x[biến]`, kể cả `[k]`, `[key]`, `[state]`, `[kind]`)
  phải nằm trên dòng có chú thích `// idx` (chỉ số nguyên do mã tự sinh, ví dụ chỉ số vòng lặp trên mảng)**, test liệt kê từng dòng vi phạm; mọi tra cứu theo giá trị lấy từ payload (`key`, `kind`, `state`, khoá `live`/`counts`/`more`/`legend`) đi qua `Map.get`
  hoặc `Object.hasOwn`; việc chọn hàm dựng theo `kind` dùng `switch` với `case` literal và nhánh `default` bỏ nút (không bao giờ `builders[kind]`); phải có ít nhất một `Object.hasOwn(` hoặc `new Map(` trong `app.js`.
- A3: `vendor/three.module.js`, `vendor/three.core.js` và `vendor/OrbitControls.js` không chứa `eval(`, `new Function` (kiểm CSP không cần `unsafe-eval`
  vẫn đúng sau khi nâng cấp phiên bản).
- A4: SHA-256 ba file vendor bằng `viewer.VENDOR_SHA256` và bằng giá trị trong `vendor/VERSION.txt`; `vendor/LICENSE` tồn tại và chứa
  "MIT License"; `VERSION.txt` ghi `0.186.0`, SHA-256 bản gốc và bản đã vá của `OrbitControls.js`, và chứa "Lệnh tái lập checksum". **Bản vá đúng một dòng**: trong `vendor/OrbitControls.js` có đúng một dòng `} from './three.module.js';`, không dòng
  nào còn `from 'three'`; thay dòng đó về `} from 'three';` rồi băm cho SHA-256 bằng SHA-256 **bản gốc** trong `VERSION.txt` (chứng minh khác bản tarball đúng một dòng); chỉ có đúng một câu `import` ở đầu file (không có `import` thứ hai). A4 chỉ so các giá trị cùng nằm
  trong repo: nó **không** chứng minh file trùng với bản trên npm; việc đó là lệnh tái lập ở mục "Đóng gói assets", reviewer chạy mỗi lần nâng cấp.
- A5: `build_macos.sh` và `build.ps1` (chỉ hai file này; `Wisp.spec` bị git bỏ qua nên không kiểm) đều chứa `assets/viewer` trong chỉ thị `--add-data` (kiểm bằng
  tìm chuỗi; không chạy PyInstaller); `build_macos.sh` và `build.ps1` đều chứa đoạn kiểm file sau PyInstaller (chuỗi `assets/viewer`, cả bảy tên file kể cả `vendor/OrbitControls.js`, và lệnh thoát khác 0 hoặc `throw` ở nhánh thiếu).
  Đây là kiểm chuỗi trên script; việc kiểm file thật chạy khi build (M12).
- A6: (đã bỏ cùng `tools/check_bundle.py`, Quyết định I; mã A7 giữ nguyên để không đánh số lại.)
- A7: `tests/test_i18n.py` (có sẵn) vẫn đạt với các khoá `isl.view3d*`, `v3d.open_fail`, `v3d.link_copied` và `v3d.page.*`.
- A8: mọi khoá literal mà `app.js` tra trong bảng chuỗi (qua một hàm duy nhất `str("<khoá>")`) thuộc `viewer.PAGE_STRING_KEYS`, và ngược lại mọi khoá của `PAGE_STRING_KEYS` được `app.js` dùng ít nhất một lần (không khoá chết); `app.js` không tự định nghĩa chuỗi văn bản tiếng Việt hay tiếng Anh nào khác ngoài các giá trị cố định kỹ thuật (tên phím, tên sự kiện).

**`tests/test_ui_viewer_app.py` (T1b, nối dây App; cùng hạ tầng và cùng điều kiện bỏ qua với `tests/test_ui_app_smoke.py`: dựng `App` thật
không `mainloop`, các patch `_start_hooks`, `_start_update_checker`, `_show_anchor`, `_poll_right_click`, `Collector.start`, `log`, `save_state`;
tự `skipTest` khi không có Tk display; thay thêm `viewer.ViewerServer` bằng lớp giả và `webbrowser.open` bằng stub). **Quy tắc báo cáo (N5)**: cả bộ W1 đến W8 và W10
tự bỏ qua khi không có Tk display, nên ở CI headless chúng **không được kiểm**; một lần `skip` phải được báo `unavailable` trong PR (kèm lý do "không có Tk display"), **không bao giờ tính là pass**,
và S15 (W4), S10 (W4) chỉ được coi là đã kiểm khi bộ này chạy thật ít nhất một lần trên máy có display (macOS) trước khi phát hành. W9 (quét `ast`, không cần Tk) được tách ra `tests/test_viewer_wiring_static.py` (bên dưới) để luôn chạy.

- W1: mục menu: popup chuột phải của island (hàm dựng popup trong `ui/menus.py`, với `_item` bị thay bằng bản ghi lời gọi) có đúng một lời gọi
  với nhãn `t("isl.view3d")` đứng ngay sau lời gọi của `t("isl.control")`, và `cmd` của nó gọi `app._open_3d_viewer` sau `close()`.
- W2: `_open_3d_viewer` lần 1 tạo đúng một `ViewerServer` (giả), gọi `start()` và `publish` snapshot hiện tại (nếu `app.snap` có) rồi gọi
  `webbrowser.open(url, new=2)` ở một thread; lần 2 **dùng lại** server (không tạo mới, `start()` không gọi lại) và gọi `webbrowser.open` với cùng `url` (Quyết định D).
- W3: `start()` trả `False`: toast `v3d.open_fail` (`toast_info` đã bị thay trong smoke test), `app.viewer is None`, không gọi `webbrowser.open`, không có
  timer `_viewer_tick`; lỗi dựng không làm hỏng island hay Control room (mở Control room sau đó vẫn chạy).
- W4: `webbrowser.open` trả `False` và (lần khác) ném ngoại lệ có thông điệp chứa URL kèm token: `root.clipboard_get()` ở main thread bằng URL, toast
  `v3d.link_copied`; **mọi** lời gọi `clipboard_*` và `toast_info` đến từ thread chính (so `threading.get_ident()`); thread mở trình duyệt chỉ gọi stub
  và `queue.put`; log chỉ chứa `viewer: browser open failed <TypeName>` (không token, không URL, không thông điệp ngoại lệ).
- W5: `App.quit` gọi `viewer.stop()` đúng một lần khi viewer có mặt, và không lỗi khi `app.viewer is None`.
- W6: `_viewer_tick` với `idle_for()` = 119: đặt lại `after`; với 121: gọi `stop()` đúng một lần, `app.viewer is None`, không đặt lại `after`.
- W7: `_pump` khi `app.viewer is None` **không** gọi `office.office_layout` (patch ghi lời gọi) cho mọi snapshot; khi viewer có mặt gọi `viewer.publish(org, ts)` đúng một lần cho mỗi `ts` mới và không gọi lại với `ts` cũ.
- W7b: snapshot lỗi `{"ts": ..., "error": ...}` (không có khoá `org`) hoặc `snap["org"] is None` (`org.build` lỗi): `_pump` gọi `viewer.publish` một lần cho `ts` đó và kết quả là không-làm-gì (`office_layout` không chạy, V28); `app.viewer` và token không đổi.
- W8: `publish` ném lỗi trong `_pump`: ghi log `viewer: layout error <TypeName>`, `_pump` vẫn chạy tiếp (Control room vẫn nhận snapshot).
- W10: thoát khỏi `quit` rồi `_open_3d_viewer` lần nữa (cùng tiến trình sau khi `viewer` bị bỏ) tạo server mới với `url` khác (token khác).
- **Chỉ kiểm tay, vì sao**: logic bốn trạng thái kết nối của `app.js` (`live`, `stale`, `expired`, `disconnected`), polling 2 giây/30 giây, diff theo `key` và
  render on demand. Ngăn xếp test của Wisp là stdlib thuần và không có môi trường chạy JS; thêm Node hoặc jsdom là thêm phụ thuộc mới ngoài phạm vi. Các hành vi
  đó được kiểm ở M7, M9, M14, M17 và M16 (tải payload độc), và phần trang nhận từ server được bảo vệ ở phía server bằng C1 đến C16.

**`tests/test_viewer_wiring_static.py` (T1c, không cần Tk, không bao giờ bị bỏ qua)**

- W9: quét `ast` của `ui/app.py` (parse nguồn, **không import** `tkinter`, nên chạy ở CI headless): trong thân hàm `_open_3d_viewer`, `_viewer_tick` và hàm xử lý kết quả mở trình duyệt, không lời gọi `log(...)` nào có đối số tham chiếu
  (trực tiếp hoặc trong f-string) tên `url`, `token`, `.url` hay `.token`; không lời gọi `log(...)` nào truyền ngoại lệ trần `e`/`exc` hoặc `str(e)`/`repr(e)` (chỉ `type(e).__name__`).
- W11: quét `ast`: thread mở trình duyệt (hàm đích của `threading.Thread` trong `_open_3d_viewer`) không chứa lời gọi tới `root`, `toast_info`, `clipboard_*` hay bất kỳ thuộc tính nào của `self.root`; nó chỉ gọi `webbrowser.open` và `queue.put`.
**Kiểm giữ nguyên hành vi hooks (G1)**: `git diff --stat` của thay đổi không đụng `pet_tracker/hooks.py` và `tests/test_hooks.py`; toàn bộ
`tests/test_hooks.py` đạt.

**Kiểm tay (T3, macOS, Chrome và Safari bản stable hiện hành; Windows: `unavailable`)** - mỗi mục ghi pass/fail vào PR:

- M1: chọn "3D office" từ popup chuột phải: tab mới mở với URL `http://127.0.0.1:<port>/v/<token>/`; cảnh hiện; bấm lần hai: thêm một tab,
  cùng URL.
- M2: tab Network của DevTools chỉ có request tới `127.0.0.1:<port>`, không có tên miền nào khác; console không có lỗi CSP và (Chrome) không có
  vi phạm Trusted Types của `require-trusted-types-for 'script'`; cảnh vẫn chạy với chỉ thị đó (three r186 chưa được kiểm dưới trusted types: nếu vi phạm,
  ghi lại và xin bỏ hai chỉ thị này bằng một rev spec, không bỏ ngầm).
- M3: xoay, pan, zoom bằng chuột và cảm ứng (hành vi của OrbitControls) đúng; camera không chui xuống sàn (góc cực kẹp 10° đến 80°, khoảng cách kẹp [4, 3 x đường chéo bounds]); tâm không trôi ra ngoài `bounds` mở rộng 20%; mũi tên pan khi canvas được focus; `R` và nút "Đặt lại" đưa camera về vị trí ban đầu; không có quán tính sau khi thả chuột; mascot luôn quay mặt về camera ở mọi góc.
- M4: bóng đổ của bàn và vệt bóng mascot hiện; mood sprite đổi khi session đổi state (chạy một session thật qua các trạng thái).
- M5: hover hiện chú thích, bấm chọn hiện khung chi tiết, bấm chỗ trống bỏ chọn; thêm và bớt một session thật: cảnh cập nhật
  mà camera và lựa chọn của nút khác không đổi.
- M6: một session có chuỗi giả chứa `<img src=x onerror=alert(1)>` và ký tự bidi trong `description`/tên (dùng
  `tools/viewer_demo.py`): hiện nguyên văn như chữ, không chạy mã, không phần tử nào mới xuất hiện trong DOM.
- M7: thoát Wisp: trong vài giây tab hiện banner "Mất kết nối" và **tiếp tục poll mỗi 30 giây** (Network); "Thử lại" vẫn báo mất kết nối. Mở lại viewer: tab cũ chuyển sang "hết hạn" ở lượt poll kế tiếp (<= 30 giây) và dừng poll,
  tab mới chạy; mở lại URL cũ ở tab mới: "hết hạn".
- M8: đóng mọi tab viewer, chờ 125 giây: `wisp.log` có `viewer: stopped (idle)`; cổng không còn lắng nghe (`lsof -i`).
- M9: tab ẩn 3 phút rồi hiện lại: viewer vẫn chạy, không mất kết nối.
- M10: hiệu năng: `tools/viewer_demo.py` dựng `org` giả ở cỡ mục tiêu (trần mặc định của board đầy: 48 bàn, 12 subagent mỗi bàn, 3 thiết bị
  mỗi bàn); đo FPS khi xoay (DevTools Performance) và số draw call, ghi số vào PR; chạy thêm với `board_max_desks` = 200 (vượt trần 1000
  nút): thanh trạng thái báo "đã ẩn N nút" và cảnh vẫn dùng được.
- M11: kiểm tra WebGL: tắt WebGL trong trình duyệt (cờ hoặc cài đặt): thông báo "không hỗ trợ WebGL2", không lỗi trắng trang.
- M12: bản build macOS (`build_macos.sh`): đoạn kiểm file sau PyInstaller đạt (bảy file có mặt; thử xoá tạm một file trong `assets/viewer` rồi build lại để thấy build thất bại, ghi vào PR); mở `Wisp.app` ra, chạy M1 và M3 (xoay, pan, zoom bằng OrbitControls trong bản build).
- M13: `curl -H 'Host: evil.example' http://127.0.0.1:<port>/v/<token>/` trả `403` (xác nhận ngoài test tự động); `curl` hai header `Host` cũng `403`.
- M14: ổn định vị trí: mở viewer, ghi lại vị trí bàn, đóng một session ở giữa và mở session mới: các bàn còn lại không đổi chỗ; bàn mới vào
  ô trống thấp nhất. Mở Board cùng lúc: ghi nhận (không phải lỗi) nếu một số bàn xếp khác Board vì hai `prev` độc lập.
- M15: nhiều project: mở viewer với 3 project trở lên: các sàn nằm thành hàng dọc trục `x`, không chồng nhau, camera ban đầu nhìn trọn; một
  sàn thêm cụm (dài thêm về phía nam) không làm sàn khác nhúc nhích; `ring` hiện cho worker stuck và quanh bàn có `alert`.
- M16: payload độc ở phía trang: `tools/viewer_demo.py --hostile` **bỏ qua `viewer_payload`** và đặt vào slot một payload tự dựng có: `state` là `constructor` và `__proto__`; **`key`, `kind` và `parent` là `__proto__`, `constructor`, `hasOwnProperty`**;
  **khoá của `live`, `counts` (trong nút overflow), `more` và `legend` (nhóm và state) là `__proto__`, `constructor`, `hasOwnProperty`**; `mascot` là `../x` và `m01/../../x`, `mood` là `x/../y`, `key` rất dài, `label` dài 100 000 ký tự và `<script>`:
  Network chỉ có các URL trong danh sách endpoint (không có request tới đường dẫn dựng từ `mascot`/`mood`), console không có ngoại lệ, nút hiện bằng chấm màu hàng `idle`/`unknown` hoặc bị bỏ (`kind` lạ), không có phần tử DOM mới, trang không điều hướng,
  và `Object.prototype` không bị thay đổi (trong console: `({}).polluted === undefined` và `Object.keys(Object.prototype)` rỗng).
- M17: bốn trạng thái kết nối: (a) `live` khi bình thường; (b) `tools/viewer_demo.py --freeze` (ngừng `publish`): sau ngưỡng `max(3 x refresh_sec, 15)` giây banner
  vàng "dữ liệu cũ" và cảnh còn nguyên, tiếp tục poll; (c) dừng server (Ctrl-C hoặc thoát Wisp): trong khoảng 2+4+8 giây cộng timeout banner đỏ "mất kết nối" kèm nút
  "Thử lại"; Network **vẫn poll mỗi 30 giây** sau đó (không dừng); (d) mở URL có token sai: banner "hết hạn" ngay và **không** có poll nào sau lần đầu.
- M18: (macOS, Python 3.13 của bản build, N6) kiểm bằng `ps` cách URL tới trình duyệt: trong khi chọn "3D office", chạy vòng lặp `while true; do ps -ww -axo pid,args | grep -F '127.0.0.1'; sleep 0.05; done` (hoặc `log stream` của `osascript`) suốt 5 giây
  quanh lúc mở; ghi vào PR phiên bản Python và việc có hay không dòng `args` nào chứa `/v/<token>` (kể cả của `osascript`). Kết quả có (URL nằm trong argv) thì sửa lại rủi ro 6 và xem xét cách mở khác bằng một rev spec; không có thì ghi "stdin, không argv" cho 3.13.
- M19: nhiễu ngắn (N2): một script ngắn mở 16 socket tới cổng viewer và giữ 15 giây rồi thả: tab đang mở vào banner "mất kết nối" khoảng 14 giây, **sau khi thả** về `live` trong <= 30 giây mà không cần bấm "Thử lại"; `wisp.log` **không** có `viewer: stopped (idle)`;
  server vẫn trả lời; kiểm lại với tab ẩn.

`tools/viewer_demo.py` (stdlib, mới): dựng `org` giả bằng `org.build` từ phiên làm việc tổng hợp (cỡ tuỳ chọn, gồm chuỗi độc ở M6), rồi `publish` vào một
`ViewerServer` thật (chạy cổng 0, đi qua `office_layout` và `viewer_payload` như app thật), in URL ra stdout; không dùng dữ liệu thật của `~/.claude`. Hai cờ dev:
`--freeze` (ngừng `publish` sau lần đầu) và `--hostile` (đặt payload tự dựng, xem M16). Là công cụ phát triển, không đóng gói vào bản phát hành (Quyết định H).

Hiệu năng của Wisp: `_pump` có `publish` không làm tăng thời gian trung bình của `_pump` quá 20 ms khi viewer mở ở cỡ mục tiêu; khi viewer
đóng, `_pump` không gọi `office_layout` (không tốn thêm gì; W7).

## Tài liệu

`docs/GUIDE.md` thêm mục "3D office" (cách mở, điều khiển, ý nghĩa màu và bóng, vì sao cần trình duyệt, token và việc tự tắt). `CHANGELOG.md` mục
Unreleased: Added (3D office viewer), Security (server local `127.0.0.1`, token, kiểm Host/Origin, CSP, three.js ghim phiên bản và checksum, không
mạng ngoài, giới hạn kết nối). `README.md` và `README.vi.md`: một dòng giấy phép three.js (MIT) và đường dẫn tới `assets/viewer/vendor/LICENSE`. Windows chưa có
máy kiểm: ghi rõ trong CHANGELOG khi phát hành.

## Quyết định đã duyệt

Người dùng đã duyệt toàn bộ các quyết định A đến AB dưới đây (2026-10-30); **B và I đã đổi theo phương án rẻ hơn của Review** (xem hai mục đó). Nội dung giữ nguyên như lúc đề xuất, trừ B và I:

- **A. Cổng do hệ điều hành cấp (cổng 0), không thêm khoá config.** Lý do: tránh xung đột cổng và tránh thêm khoá; URL đổi mỗi
  lần nên không dùng bookmark (token cũng đổi mỗi lần). Phương án khác: khoá `viewer_port` mặc định 0.
- **B. three.js 0.186.0 không minify (ba file: `three.module.js`, `three.core.js`, `OrbitControls.js` đã vá một dòng; khoảng 2,2 MB), vendor `OrbitControls.js` của r186 thay cho bộ orbit tự viết. ĐÃ ĐỔI ở rev 5: người dùng chọn phương án rẻ hơn của Review.** Lý do: tarball npm không có bản minify, bản jsDelivr do bên thứ ba tạo; `OrbitControls` nhập `'three'` bằng tên trần (cần importmap nội tuyến, trái CSP), nên vá đúng một dòng import (`} from 'three';` thành `} from './three.module.js';`), ghi SHA-256 bản gốc và bản đã vá trong `VERSION.txt`, SHA-256 bản đã vá trong `VENDOR_SHA256`. Ít mã Wisp hơn; đổi lại thêm một file vendor đã vá và phím tắt khác (mũi tên pan, không còn `+`/`-`). Phương án khác (không chọn): bộ điều khiển orbit tự viết trong `app.js` (rev 4), hoặc CSP `script-src 'sha256-...'` cho importmap.
- **C. Hạn idle 120 giây; poll 2 giây khi tab hiện, 30 giây khi tab ẩn; hoãn dừng tới 125 giây sau khi đóng tab.** Phương án khác: ngắn hơn (60
  giây) nhưng tab ẩn bị coi là đã đóng khi trình duyệt giãn timer.
- **D. Dùng lại server và token khi bấm menu lần hai** (token đổi mỗi lần server được tạo, không đổi mỗi lần bấm). Phương án khác: đổi token mỗi
  lần bấm, làm chết các tab đang mở.
- **E. `webbrowser.open` lỗi thì chép URL vào clipboard (ở main thread, thread mở trình duyệt chỉ trả kết quả qua queue).** Clipboard có thể bị chương trình khác đọc; chấp nhận vì là hành động
  của người dùng và token chết khi server tắt. Nhánh này hiếm chạy trên macOS (xem rủi ro 16).
- **F. Chuỗi giao diện của trang nằm trong `i18n.py` (tiền tố `v3d.`) và đi qua `/api/strings`** thay vì nhúng cứng trong `app.js`. Phương án
  khác: chuỗi cứng trong JS, chỉ tiếng Anh.
- **G. Vẽ theo yêu cầu (không vòng `requestAnimationFrame` liên tục).** Lý do: pin và GPU rảnh khi viewer chỉ để mở. Hệ quả: không có hoạt ảnh chuyển
  tiếp giữa các lần cập nhật.
- **H. `tools/viewer_demo.py`** (công cụ dev, Layout tổng hợp, cờ `--freeze` và `--hostile`) để kiểm hiệu năng, chuỗi độc và trạng thái kết nối ở T3.
- **I. Kiểm file trong bản build bằng vài dòng `test -f`/`Test-Path`-kiểu trong `build_macos.sh` và `build.ps1`, không có `tools/check_bundle.py`. ĐÃ ĐỔI ở rev 5: người dùng chọn phương án rẻ hơn của Review.** A5 vẫn kiểm chuỗi đóng gói và chuỗi đoạn kiểm trong ba script; test A6 bỏ cùng công cụ. Hệ quả: không kiểm checksum trong build (đã kiểm lúc chạy ở `start()`, A4 và M12). Phương án khác (không chọn): `tools/check_bundle.py` kiểm đúng một lần mỗi file và checksum.
- **J. Giới hạn tài nguyên từ cửa vào** (thay cho `Semaphore(8)` ở rev 2): tối đa 16 kết nối đồng thời tại accept; hạn tổng 10 giây mỗi kết nối cộng 5 giây mỗi `recv`;
  dòng yêu cầu <= 256 byte, <= 32 header, mỗi dòng <= 4096 byte, tổng <= 16 KiB; body layout <= 1 MiB (H1 đến H3). Phương án khác: giữ stdlib mặc định (không giới hạn,
  không đạt yêu cầu an toàn).
- **K. Trình duyệt hỗ trợ: bản stable hiện hành của Chrome, Edge, Safari, Firefox;** chỉ cam kết đã kiểm Chrome và Safari trên macOS. Không nêu số
  phiên bản tối thiểu vì chưa kiểm với three r186.
- **L. `SPRITE_SIZE = 128` (ảnh 164 px), theme của cảnh và sprite cố định `"dark"` (`theme.DARK`, màu hex của `legend` và `palette` tính từ đó), hue
  là `App._hue()` lấy lúc mở.**
- **M. Các sàn xếp thành một hàng dọc trục `x`, bước 36 ô (30 ô sàn + lề 6), theo `level` tăng dần.** Lý do: L-S4 của board cho sàn chỉ lớn về phía
  nam, nên toạ độ tuyệt đối của mọi nút ổn định khi sàn khác đổi cao. Phương án khác: xếp dọc trục `y` (gọn hơn khi ít project nhưng dời cả sàn sau
  mỗi khi một sàn đổi cao), hoặc lưới nhiều hàng dùng `max_floor_h` của board làm bề cao ô lưới (ổn định nhưng khoảng cách rất lớn: 240 ô ở mặc định).
- **N. `viewer_payload` nằm trong module thuần riêng `pet_tracker/viewer_payload.py`**, không trong `viewer.py`; chữ ký bỏ `hue` (hue chỉ dùng ở
  endpoint sprite, do `ViewerServer` giữ). Phương án khác: để trong `viewer.py` (ít file hơn, nhưng test thuần phải import `http.server`/`hashlib`/`pathlib`).
- **O. Viewer giữ `prev` riêng và không chia sẻ Layout với Board.** Hệ quả: cùng dữ liệu có thể xếp bàn khác nhau giữa Board và viewer (L-S5 của board).
  Phương án khác: dùng chung một `prev` (cần chia sẻ trạng thái qua thread, trái "thread server không chạm dữ liệu Wisp", và buộc Board lẫn viewer
  đóng/mở cùng nhau).
- **P. `key` trong payload là HMAC-SHA256 có khoá, cắt 16 hex** (không gửi khoá thô, `ref`, `session_id`, đường dẫn); khoá bí mật `secrets.token_bytes(16)` chọn một lần mỗi vòng đời server (rev 4; rev 2 và 3 dùng SHA-256 trần,
  đảo ngược được bằng danh sách đường dẫn thường gặp và dễ tạo va chạm khi một phần khoá do agent đặt). Phương án khác: gửi khoá thô (đơn giản hơn, nhưng đưa `root`, `top` và `session_id` sang trình duyệt không cần thiết), hoặc
  SHA-256 trần (không đủ, xem N3).
- **Q. Trần `MAX_NODES = 1000` nút do `viewer_payload` cắt** (`hidden` báo số bị cắt), và viewer dùng chung hai khoá cấu hình của board thay vì thêm khoá riêng.
  Phương án khác: trần thấp hơn (500), nhưng trần mặc định của board đầy (48 bàn x 12 subagent) đã khoảng 830 nút.
- **R. Số đổi liên tục (`tokens`, `started`, `last_activity`) nằm trong `scene.live`, tách khỏi `scene.nodes`**, để diff của trang không dựng lại nút khi chỉ
  số liệu đổi (như `struct`/`live` của Control room).
- **S. Bỏ `Semaphore(8)`/`503`; sprite không có semaphore riêng; mỗi tab tối đa 3 ảnh sprite đồng thời** (giảm từ 6). Lý do: trần 16 kết nối ở accept (J) cộng 3 sprite + 1 poll mỗi
  tab (hai tab: 8 kết nối) bảo đảm `/api/layout` không bị từ chối lúc khởi động nguội; khoá dựng ảnh đã tuần tự hoá phần tốn CPU. Phương án khác: semaphore sprite riêng (4) cho
  riêng đường sprite và `503` cho phần thừa (thêm một đường lỗi và một nhánh trang).
- **T. CSP thêm `require-trusted-types-for 'script'; trusted-types 'none'`.** Chromium thi hành (chặn sink HTML và script kể cả khi mã lỡ dùng), Firefox và Safari bỏ qua hai chỉ thị.
  Chưa kiểm three r186 dưới trusted types (M2); nếu vi phạm thì bỏ hai chỉ thị bằng một rev spec.
- **U. Ép `refresh_sec` về [1, 60] (mặc định 3 khi giá trị config lạ)** thay cho gửi nguyên giá trị config.
- **V. `SO_EXCLUSIVEADDRUSE` trên Windows và `allow_reuse_address = False` ở mọi nền tảng.** Chưa kiểm trên Windows (`unavailable`).
- **X. Khi `office.valid_org` sai, viewer giữ payload cũ (kể cả `ts` cũ) thay vì hiện trạng thái trống như Board.** Lý do: giữ cảnh cuối và để trang tự báo `stale` theo `ts` cũ, không đổi
  `prev`; chỉ khi chưa có payload nào mới trả `ready:false, reason:"no_data"`. Phương án khác: như Board (xoá cảnh và hiện "chưa có dữ liệu" ngay), đổi lại việc mất cảnh vì một lỗi `org.build` thoáng qua.
- **W. Kiểm nối dây App bằng unit test với `App` thật dưới Tk display (tự bỏ qua khi không có display) và stub; logic JS chỉ kiểm tay** (không thêm Node/jsdom). Phương án khác:
  thêm một môi trường chạy JS (phụ thuộc mới) để test `app.js`.

- **Y. Thi hành hạn tổng và bộ đếm kết nối (N1):** hạn 10 giây (đọc và ghi) thi hành trong `service_actions()` của `serve_forever` (không thêm thread) bằng `socket.shutdown(SHUT_RDWR)`; **chỉ thread xử lý** `close()` socket của nó; bộ đếm 16 giảm trên mọi đường, kể cả khi tạo thread ném `RuntimeError`.
  Phương án khác: một `threading.Timer` hoặc một thread canh gác (thêm thread), hoặc `close()` từ thread canh gác (rủi ro tái dùng fd và ghi dữ liệu viewer vào kết nối khác).
- **Z. Ở `disconnected` trang vẫn poll mỗi 30 giây** cho tới khi nhận `403`/`404` (thay cho dừng poll sau ba lần thử lại ở rev 3); hệ quả: tab bị bỏ quên sau khi Wisp thoát vẫn poll mỗi 30 giây (rẻ) tới khi đóng tab. Phương án khác: dừng poll ở `disconnected` (rev 3; một nhiễu ngắn thành tắt hẳn server sau 120 giây).
- **AA. `key_secret` (16 byte) do `ViewerServer` sinh một lần mỗi vòng đời server và truyền cho `viewer_payload` qua tham số** (hàm vẫn thuần), thay cho SHA-256 trần; chữ ký `viewer_payload` thêm `key_secret`. Phương án khác: để `viewer_payload` tự sinh (không thuần, khó kiểm).
- **AB. Bộ test nối dây App tự bỏ qua khi không có Tk display và phải được báo `unavailable` trong PR; W9 và W11 (quét `ast`) tách ra `tests/test_viewer_wiring_static.py` không cần Tk.** Phương án khác: giữ cả bộ trong một file (W9 cũng bị bỏ qua ở CI headless).

## Rủi ro mở

1. **Chưa kiểm trên Windows** (đường dẫn, `webbrowser`/`os.startfile`, `shutdown` socket, `SO_EXCLUSIVEADDRUSE`). Trạng thái `unavailable`.
2. **Vị trí `datas` trong `.app` của PyInstaller 6.22.3 chưa kiểm**; đoạn kiểm file sau PyInstaller tìm theo tên đường dẫn nên không phụ thuộc, nhưng mã ký ad-hoc (`codesign --deep`) với
   thư mục dữ liệu mới chưa chạy thử.
3. **Chi phí dựng PNG mascot** (`mascots.png` là rasterize thuần Python) chưa đo; dựng trên thread server tranh GIL với Tk. Giảm thiểu: khoá dựng
   một ảnh một lúc, tối đa 3 ảnh đồng thời mỗi tab, cache RAM và đĩa, chỉ xin ảnh đang dùng, chấm màu trong lúc chờ. Nếu một ảnh > 150 ms ở cỡ 164 px thì khởi động nguội với nhiều
   mascot khác nhau thấy chậm; xử lý trong plan bằng pre-warm trong thread nền hoặc hạ `SPRITE_SIZE`. **Hệ quả của hạn tổng 10 giây (H2)**: yêu cầu sprite xếp hàng sau khoá dựng ảnh có thể chạm hạn 10 giây khi hàng đợi dài
   và dựng chậm; kết nối bị cắt, trang nhận lỗi, texture của cặp đó lỗi và nút **giữ chấm màu, không thử lại** (chỉ ảnh hưởng chức năng, không ảnh hưởng an toàn; mở lại hoặc tải lại trang thử lại).
4. **Hiệu năng ở cỡ mục tiêu chưa có số đo** (30 FPS, 2000 draw call, 20 ms cho `publish`; cỡ mục tiêu là trần mặc định của board đầy, khoảng 830 nút và 625 sprite).
   Nếu một `Mesh` riêng cho từng sprite, vệt bóng và bàn không đạt, chuyển sang `InstancedMesh` (đã có trong three r186). Các con số trên là mục tiêu, phải
   được thay bằng số đo ở T3.
5. **Bàn có thể xếp khác nhau giữa Board và viewer** cho cùng dữ liệu, vì mỗi nơi giữ `prev` riêng và `prev` không lưu qua lần khởi động (L-S5 của board); cũng
   vậy, mỗi lần viewer được mở lại, bàn có thể xếp khác lần trước. Chấp nhận (Quyết định O); người dùng nhận biết bàn bằng mascot và nhãn, không bằng ô.
6. **URL (kèm token) có thể lộ qua tham số dòng lệnh hoặc lịch sử, tuỳ nền tảng.** macOS với Python 3.12: `MacOSXOSAScript.open` ghi `open location "<url>"` vào **stdin** của
   `osascript`, nên URL **không** nằm trong `argv`; bản build dùng Python 3.13, hành vi này **chưa kiểm trên 3.13** (ghi nhận, kiểm trong plan bằng `ps` lúc mở). Windows:
   `os.startfile` (ShellExecute) đưa URL vào dòng lệnh của trình duyệt khi trình duyệt khởi động nguội, nên tiến trình khác của cùng người dùng đọc được URL qua danh sách tiến
   trình trong vài giây đó (chưa kiểm: `unavailable`). Biến môi trường `BROWSER` (nếu người dùng đặt) buộc `webbrowser` chạy lệnh đó với URL trong `argv`. Ở mọi nền tảng URL nằm
   trong lịch sử trình duyệt. Giảm thiểu chung: token chỉ sống cùng server (idle 120 giây), không có thao tác ghi, chỉ xem; chấp nhận. Tiến trình khác của cùng tài khoản người dùng ngoài mô hình đe doạ.
   Kiểm bằng `ps` cách Python 3.13 truyền URL tới `osascript` chưa chạy: là M18 (thủ công, macOS), kết quả ghi vào PR.
7. **Kiểm `Origin`/`Sec-Fetch-Site` chấp nhận request không có cả hai** (curl, trình duyệt rất cũ); chỉ dựa vào token và `Host`. Chấp nhận vì mọi
   request cross-site từ trình duyệt hiện hành đều mang ít nhất một trong hai header.
8. **Viewer không đọc được bằng trình đọc màn hình** (canvas 3D). Thanh trạng thái `aria-live` và điều khiển bàn phím giảm thiểu một phần; Control room là đường
   truy cập đầy đủ cho nội dung văn bản.
9. **Đồng hồ**: trang so `ts` (đồng hồ Wisp) với `Date.now()` cùng máy; nếu người dùng đổi giờ hệ thống khi đang xem, banner "dữ liệu cũ" có thể báo sai tạm thời.
10. **Giới hạn thư viện**: three.js và OrbitControls nặng khoảng 2,2 MB (không minify); thêm `gzip` hoặc bản minify tự build (có checksum riêng) là nâng cấp nếu cần, không làm ngay.
11. **Sàn xếp theo hàng ngang dài** khi có nhiều project (8 project dài 288 ô); camera tự đặt lại bằng `bounds` nhưng cảnh rất rộng và mỗi bàn nhỏ trên màn hình.
    Chưa có mẫu thật cỡ đó (người dùng thật thường có dưới 5 project đang chạy); nếu M15 thấy bất tiện thì đổi sang lưới nhiều hàng bằng một rev spec.
12. **`MAX_NODES` cắt các nút cuối (sàn cuối)**: trang chỉ thấy số `hidden`. Chấp nhận vì 1000 nút vượt trần mặc định của board; chỉ xảy ra khi người dùng đặt `board_max_desks` cao.
13. **Trusted Types chỉ có hiệu lực trên Chromium** và three r186 chưa được kiểm dưới chỉ thị đó (M2). Ở Firefox và Safari, bảo vệ sink HTML chỉ dựa vào quy ước `textContent`, CSP còn lại và test
    quét (lưới phụ). Chấp nhận.
14. **DoS cục bộ còn lại**: kẻ tấn công là **bất kỳ tài khoản OS local nào kết nối được tới 127.0.0.1** (máy nhiều người dùng, hoặc một tiến trình bị chiếm), không chỉ cùng người dùng, và **không cần token** cho việc này. Nó có thể liên tục mở 16 kết nối nhỏ giọt hoặc không đọc (mỗi kết nối giữ tối đa 10 giây)
    và làm trang thấy lỗi mạng. H1 và H2 giới hạn số thread và thời gian giữ, không loại bỏ việc làm gián đoạn. Giảm thiểu hậu quả (N2): trang vẫn poll mỗi 30 giây ở `disconnected` nên server **không** tắt vì nhiễu và trang tự về `live` khi hết nhiễu; chỉ một cuộc tấn công kéo dài mới
    giữ được banner "mất kết nối". Không ngăn được tấn công kéo dài; chấp nhận (server chỉ xem, tắt sau 120 giây không có poll hợp lệ khi người dùng đóng tab).
15. **Khởi động nguội nhiều mascot**: hai tab mở cùng lúc dùng tối đa 8 kết nối (3 sprite + 1 poll mỗi tab), thấp hơn trần 16, nên `/api/layout` không bị từ chối; nhưng ảnh sprite hiện
    chậm hơn nếu dựng PNG chậm (rủi ro 3).
16. **Nhánh dự phòng `webbrowser.open` hiếm chạy trên macOS**: `MacOSXOSAScript.open` gần như luôn trả `True` kể cả khi không mở được tab, nên người dùng có thể thấy không có tab mà không có toast và không có
    clipboard. Nhánh dự phòng chỉ được kiểm bằng test có stub (W4). Giảm thiểu: người dùng bấm lại mục menu (dùng lại server và token, Quyết định D).
17. **Logic bốn trạng thái kết nối, polling và diff của `app.js` chỉ kiểm tay** (M5, M7, M9, M14, M16, M17) vì không có môi trường chạy JS trong ngăn xếp test (Quyết định W).
18. **`OrbitControls.js` là file vendor đã vá một dòng** (Quyết định B): bản vá phụ thuộc việc file chỉ nhập `'three'` ở một chỗ (dòng 12 của r186). Nâng cấp phiên bản có thể đổi chỗ nhập hoặc thêm `import` thứ hai; lệnh tái lập (bước 4) và A4 dừng lại ngay khi số khớp khác 1. Phím tắt khác rev 4 (mũi tên pan,
    không còn `+`/`-`), và OrbitControls không có sẵn kẹp tâm trong `bounds` (Wisp tự kẹp trong handler `change`, kiểm ở M3). Hành vi cảm ứng trên Safari iOS chưa kiểm (viewer chạy trên máy tính, ngoài phạm vi T3).
