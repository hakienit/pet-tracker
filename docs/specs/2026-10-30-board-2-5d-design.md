# Board 2.5D: văn phòng isometric của các agent

Trạng thái: rev 5 (2026-10-31, người dùng chọn F1 và F2 của Review S1: sửa bước 4 và 5 của "Quy tắc xếp").
Rev 4 người dùng đã duyệt (2026-10-30, errata sau review plan). Rev 3 tích hợp báo cáo của Review; rev 4
chỉ sửa errata (lặp chữ, thứ tự test, mô tả lỗi `type`/`agent_type`, cách test phần App, che tên `theme`, mục Tài liệu, ngưỡng
rasterize), không đổi quyết định nào. Mọi mục đánh dấu "Quyết định mới (cần duyệt)" đã được người dùng duyệt nguyên văn;
tổng hợp ở cuối file. Slice S0 (sửa lỗi `type`/`agent_type` của Control room) làm trước, người dùng đã duyệt.
Phạm vi: sub-project 3 (tab Board trong Control room) và hợp đồng dữ liệu chung `office_layout`. Nền là
`docs/specs/2026-10-22-control-room-design.md` (org model, Control room), không nhắc lại ở đây. Viewer 3D
(sub-project 4) có spec riêng và chỉ dùng lại Layout ở mục "Layout chung".

## Mục tiêu

Cây của Control room trả lời được "có gì" nhưng không cho thấy "ai đang làm gì, chỗ nào kẹt" trong một cái nhìn.
Board vẽ cùng dữ liệu `org.build` thành một văn phòng isometric:

- mỗi project là một sàn, mỗi team (worktree) là một cụm bàn, mỗi session là một bàn có mascot ngồi;
- subagent là mascot nhỏ đứng quanh bàn, xếp theo phòng ban; task nền là thiết bị nhỏ trên bàn;
- state hiện bằng màu, biểu cảm mascot và dấu hiệu "stuck", theo một bảng duy nhất;
- vị trí ổn định: cùng một session luôn ở cùng một ô, worker đến hoặc đi không làm bàn khác nhảy chỗ.

Board chỉ xem. Bấm bàn session thì focus cửa sổ của session đó bằng đúng logic Control room đang dùng.

## Ngoài phạm vi

Âm thanh; chỉnh layout bằng tay (kéo bàn, đổi sàn); lịch sử session đã đóng; điều khiển agent (dừng, xoá, gửi lệnh);
thông báo khi kẹt; viewer 3D; hoạt ảnh (Board là ảnh tĩnh, vẽ lại khi dữ liệu đổi, không có timer `after` riêng).
Board không hiện quan hệ cha con giữa các subagent (độ sâu, `parent`): quan hệ đó xem ở cây. Board không hỗ trợ
trình đọc màn hình; cây vẫn là đường truy cập thay thế. Slot không lưu qua lần khởi động lại app (xem "Ổn định").

## Khái niệm

| Khái niệm | Nghĩa | Nguồn |
|---|---|---|
| Layout | dữ liệu trung tính (lưới nguyên) mô tả sàn, cụm, bàn, vị trí worker | `office_layout` |
| Floor (sàn) | một project | `Project` của org |
| Cluster (cụm bàn) | một team (worktree) | `Team` |
| Desk (bàn) | một session, mascot ngồi ở bàn | `Session` |
| Pod | vùng 4x4 ô quanh một bàn: bàn 2x2 ở giữa, 12 ô vòng ngoài cho subagent | hình học của Layout |
| Lane | một cạnh của vòng 12 ô, 3 ô; một phòng ban sở hữu lane | Layout |
| Device | một BgTask, vẽ như hộp nhỏ trên mặt bàn | `BgTask` |
| Slot | vị trí đã gán cho một khoá nhận dạng (số tầng, ô cụm, ô pod, lane, ô trong lane) | Layout |

## Dữ kiện đã kiểm

- Control room là `Toplevel` với thanh tổng ở hàng 0 và thân (cây trái, chi tiết phải) ở hàng 1
  (`control_room.py`, `_build_ui`). `render(snap)` nhận `snap["org"]` (có thể `None`) từ `_pump`; mẫu cập nhật là
  `struct_sig`/`live_sig` + `_rebuild`/`_update_live` (`control_room.py:349-356`, `:586-637`).
- Focus: `ControlRoom._activate` gọi `focus_session(session_id)` chỉ khi dòng là session có `session_id`, chỉ khi bấm
  đúp hoặc Enter (`control_room.py:662-669`). `App._focus_from_control_room` tra session live bằng
  `find_live_session` (không khớp hoặc trùng id thì không làm gì) rồi `App.focus_session` (`ui/app.py:656-660`).
- Mascot hiện KHÔNG gán theo session. `App.prefs["mascot"]` và `prefs["hue"]` là cấu hình toàn cục cho island, bóng
  nổi và header panel (`ui/app.py:383-401`). Có 40 mascot (`assets/mascots.json`, `m01`..`m40`), 8 hue, 5 mood
  (`mascots.MOODS`). Quy tắc gán mascot cho bàn và subagent ở dưới là quy tắc mới.
- `mascots.png(mid, mood, size, theme, hue, cache_dir)` trả PNG RGBA có alpha và cache trên đĩa. `gfx.to_photo` với
  `bg` trộn sẵn ảnh lên màu nền đặc (cả Windows lẫn macOS, `ui/gfx.py:88-106`) nên không dùng được cho sprite nằm
  trên sàn nhiều màu và chồng lên nhau. Board dùng PNG có alpha thật (xem "Vẽ").
- `org.build` xuất subagent với khoá `type` (`pet_tracker/org.py:187`); Control room đọc `agent_type` (`control_room.py:299`,
  `:311`). Hai bên lệch nhau, xem "Rủi ro mở" số 8: task S0 của plan sửa lỗi này TRƯỚC mọi task Board. Board dùng `type`
  đúng theo hợp đồng của org.
- Chưa kiểm: mọi thứ trên Windows; thời gian dựng và thời gian rasterize mascot lạnh (chưa đo).

## Layout chung (`pet_tracker/office.py`)

Hàm thuần: `office_layout(org_out, cfg, prev=None) -> Layout`.

- Không import `tkinter`, `os`, `subprocess`, `pathlib`; không đọc đĩa; chỉ dùng stdlib thuần (`zlib` cho seed).
- Không sửa `org_out`, `cfg`, `prev`; đầu ra chỉ phụ thuộc vào ba đối số (cùng đầu vào thì cùng đầu ra).
- Layout chỉ gồm `dict`, `list`, `str`, `int`, `bool`, `None`: `json.loads(json.dumps(layout)) == layout`.
- `org_out` là đầu ra của `org.build` (hợp đồng ở `org.py` và plan Control room, mục "Hợp đồng đầu ra của S3").
  `None`, sai kiểu hoặc phần tử hỏng thì bỏ nhánh hỏng; đầu vào hoàn toàn hỏng cho Layout rỗng (không ném lỗi).
- `cfg` đọc hai khoá `board_max_desks`, `board_max_workers` (mục "Cấu hình").
- `valid_org(org_out) -> bool`: đúng khi `org_out` là dict có `projects` là list (kể cả list rỗng). `office_layout` với
  `org_out` không hợp lệ trả Layout rỗng (hàm thuần không tự giữ `prev`). **Luật cho nơi gọi:** khi `valid_org` sai
  (`org.build` lỗi nên `snap["org"]` là `None`, `app.py:175-179`; hoặc snapshot lỗi không có khoá `org`, `app.py:187`),
  nơi gọi KHÔNG gọi `office_layout` và KHÔNG thay `prev`: giữ `prev` cũ để các slot không bị giải phóng, và hiển thị
  trạng thái "chưa có dữ liệu" (không vẽ Layout cũ, để trạng thái cũ không bị tưởng là còn sống). Khi `org` hợp lệ
  trở lại thì gọi với `prev` cũ. `org_out` hợp lệ nhưng không có session (`projects: []`) là dữ liệu thật: Layout rỗng
  thay `prev` và mọi slot được giải phóng. Mọi nơi gọi (tab Board, viewer 3D) áp dụng luật này.
- `prev` là Layout của lần gọi trước (hoặc `None`). **Quyết định mới (cần duyệt):** hàm có thêm đối số `prev` so với
  chữ ký `office_layout(org_out, cfg)`, vì "cùng session luôn ở cùng ô, ô giải phóng được tái dùng" cần bộ nhớ gán
  ô mà hàm thuần không giữ được. Bộ nhớ này nằm ngay trong Layout (không có trạng thái ẩn); người gọi giữ Layout cũ và
  truyền lại. `prev` không phải dict Layout hợp lệ, hoặc có `limits` khác `limits` hiện tại, thì coi như `None`.

### Hình dạng

```
Layout{version=1, limits, styles, floors[], more}
  limits{desks, workers, devices}           # sau khi kẹp; devices luôn là 3
  styles{desk{state: Style}, worker{state: Style}}   # bản sao sâu của STATE_STYLE (mục "Bảng state"); Style{color, mood, marker}
  more{desks, stuck_desks}                  # đúng hai khoá này (không có counts); bàn không vẽ vì cụm đầy hoặc hết trần;
                                            # stuck_desks: số bàn trong đó có subagent stuck
  Floor{key, level, name, root, w, h, ref, clusters[]}   # level: int >= 0, duy nhất; w luôn 30 (cam kết ở "Cam kết cho consumer")
    Cluster{key, slot, top, branch, x, y, w, h, ref, desks[]}
      Desk{key, session_id, slot, x, y, w, h, name, state, seed, alert, ref, workers[], devices[], more}
        Worker{key, id, department, slot, lane, x, y, state, seed, ref}     # subagent
        Device{key, id, slot, x, y, state, ref}                             # bgtask
        more{n, counts{state: n}}                                           # worker và device của bàn không vẽ
```

Worker và Device không có khoá `w`, `h`: mỗi cái chiếm đúng một ô 1x1 tại `(x, y)`. Chỉ floor, cluster và desk có
`w`, `h`.

- `name` (floor, desk) và `department`, `top`, `branch`, `root`: chuỗi y nguyên từ `org_out` (đã làm sạch bởi
  `org.py`); Layout không ghép, cắt hay diễn giải chúng. Chỗ hiển thị phải `sanitize()` lại. Tên rỗng giữ `""` trong Layout; `cr.anon_session` và `cr.anon_subagent` chỉ thay
  lúc hiển thị, để `office.py` không phụ thuộc ngôn ngữ.
- `state` của desk: `idle|run|wait|done` (state của session; `error` chuẩn hoá thành `wait`, mọi giá trị khác thành
  `idle`). `state` của worker và device: `running|stuck|done|failed|killed|ended|unknown` (giá trị ngoài enum của org
  thành `unknown`). `alert`: `{"stuck": n}`, n là số subagent `stuck` của session tính trên MỌI worker, kể cả worker
  không vẽ.
- `ref`: danh sách chỉ số vị trí gốc trong `org_out` (floor `[pi]`, cluster `[pi, ti]`, desk `[pi, ti, si]`, worker và
  device `[pi, ti, si, wi]`, `wi` là chỉ số trong `session["workers"]`). Chỉ có nghĩa với đúng `org_out` đã truyền vào
  lần gọi đó; người dùng Layout tra chi tiết (mô tả, token, thời gian) qua `ref`, Layout không chép số liệu đổi liên tục.
- `seed`: số nguyên không âm. Desk: `zlib.crc32(session_id.encode("utf-8")) & 0xFFFFFFFF`
  (session_id rỗng thì crc32 của `key` của desk). Worker (subagent): crc32 của `department`. Device không có `seed`.
  `office.mascot_index(seed, count)` trả `seed % count` (hoặc `None` khi `count <= 0`).
- `more.counts` của bàn (và `counts` ở mọi nơi Layout xuất) chỉ dùng khoá thuộc enum state của worker
  `running|stuck|done|failed|killed|ended|unknown`, chỉ gồm khoá có giá trị > 0, nên `sum(counts.values()) == n`.
  Subagent và device cùng được đếm vào đó theo state của chúng.
- Không có pixel, màu hex hay đường dẫn trong Layout.

### Hệ toạ độ

Toạ độ ô là số nguyên, cục bộ theo sàn. Gốc `(0, 0)` là ô góc sau-trái của sàn. `x` tăng về phía đông, `y` tăng về
phía nam, `z` hướng lên (Layout không lưu `z`; độ cao vật thể do bên vẽ quyết định). `w`, `h` là số ô theo `x`, `y`.
Chiếm ô: một desk chiếm khối 2x2 của nó, gồm cả ô mascot ngồi `(desk.x, desk.y)` và ba ô device (device là tập con
ô của desk, không chiếm thêm ô); một worker chiếm đúng một ô. Bất biến: mọi desk và worker nằm hoàn toàn trong
`[0, floor.w) x [0, floor.h)`; các khối 2x2 của desk và các ô của worker đôi một không giao nhau (desk với desk,
desk với worker, worker với worker); trong một desk, các device ở ba ô khác nhau và khác ô mascot ngồi.

Hằng số và hàm xuất từ `office.py` (viewer 3D dùng cùng giá trị). Tên xuất đúng như sau, và `office.py` phải có đủ
các tên này ở mức module: `FLOOR_CLUSTER_COLS`, `CLUSTER_W`, `CLUSTER_H`, `POD`, `POD_STRIDE`, `mascot_index`,
`STATE_STYLE`; ngoài ra `CLUSTER_PODS`, `LANES`, `DEVICE_SLOTS`, `ALERT_STYLE` (mục "Bảng state") và
`max_floor_h(desks)` (mục "Cam kết cho consumer") và `valid_org(org_out)`:

| Hằng | Giá trị | Ý nghĩa |
|---|---|---|
| `POD` | 4 | cạnh pod (ô) |
| `POD_STRIDE` | 5 | bước giữa hai pod (1 ô lối đi) |
| `CLUSTER_PODS` | 3 x 2 | pod theo `x` x `y` trong một cụm: tối đa 6 bàn |
| `CLUSTER_W`, `CLUSTER_H` | 15, 10 | bước giữa hai cụm (gồm lối đi) |
| `FLOOR_CLUSTER_COLS` | 2 | số cụm theo `x` trên một sàn, thêm cụm thì xuống hàng |
| `LANES` | 4 x 3 | 4 lane, mỗi lane 3 ô: tối đa 12 subagent quanh một bàn |
| `DEVICE_SLOTS` | 3 | thiết bị tối đa trên một bàn |

Công thức (mọi giá trị đều suy ra từ chỉ số slot, nên ô chỉ đổi khi slot đổi):

- Cụm slot `c`: gốc `(x, y) = ((c % 2) * 15, (c // 2) * 10)`, `w = 15`, `h = 10`. Sàn: `w = 30`,
  `h = 10 * số hàng cụm` (hàng cao nhất đang có cụm, tối thiểu 1 khi có cụm).
- Bàn slot `p` (0..5) trong cụm: gốc pod `= cụm.gốc + ((p % 3) * 5, (p // 3) * 5)`; bàn chiếm `desk.x = pod.x + 1`,
  `desk.y = pod.y + 1`, `w = h = 2`. Ô `(desk.x, desk.y)` là chỗ mascot ngồi.
- Device slot `d` (0..2): ô `(desk.x + 1, desk.y)`, `(desk.x, desk.y + 1)`, `(desk.x + 1, desk.y + 1)`.
- Worker `(lane, slot)`: ô tương đối so với gốc pod, theo bảng: lane 0 `(0,0) (1,0) (2,0)`; lane 1 `(3,0) (3,1) (3,2)`;
  lane 2 `(3,3) (2,3) (1,3)`; lane 3 `(0,3) (0,2) (0,1)`. Bốn lane phủ đúng 12 ô vòng ngoài pod, không chồng.

### Khoá nhận dạng

Khoá là chuỗi, ghép theo cùng kiểu với `flatten` của Control room (không cần khớp từng ký tự):

- floor `p:<root>`; cluster `<floor>/t:<top>`; desk `<cluster>/s:<session_id>`;
- worker `<desk>/w:sub:<id>`, device `<desk>/w:bg:<id>`.

Khoá trùng trong cùng cấp được thêm `#1`, `#2`... theo thứ tự đầu vào. Session không có `session_id` dùng `s:` rỗng
cộng hậu tố đó (bàn vẽ được nhưng không focus được, vì không có id). Ổn định chỉ được đảm bảo cho khoá không trùng:
khi hai mục trùng id đổi thứ tự trong đầu vào thì hậu tố, và vì vậy slot, có thể đổi.

Session đổi worktree thì khoá đổi (cụm khác), bàn cũ được giải phóng và bàn mới được cấp như session mới.

### Quy tắc xếp

Mọi cấp dùng chung một quy tắc: **giữ ô đã gán, chỉ cấp ô trống thấp nhất, giải phóng ngay khi khoá biến mất.**

1. Giữ: nút có khoá còn trong `org_out` và có trong `prev` giữ nguyên slot. Khoá biến mất thì ô được giải phóng
   ngay (không có thời gian ân hạn).
2. Nhận bàn mới, theo thứ tự `(started_at tăng dần, None cuối, khoá)` trên toàn bộ session chưa có bàn: được nhận khi
   cụm của nó còn pod trống VÀ tổng số bàn đã vẽ còn dưới `limits.desks`; ngược lại tính vào `more.desks`
   (và `more.stuck_desks` nếu có subagent stuck). Bàn đã giữ luôn được tính trước và không bị đẩy ra.
3. Slot mới: sàn lấy `level` trống thấp nhất (sàn mới theo thứ tự `root` tăng dần); cụm lấy `slot` trống thấp nhất
   (theo `top` tăng dần); bàn lấy pod trống thấp nhất (theo thứ tự nhận ở bước 2). Sàn hoặc cụm không còn bàn nào bị
   bỏ khỏi Layout và `level`/`slot` của nó được giải phóng. Sàn và cụm chỉ có bàn không vẽ không xuất hiện.
4. Worker (subagent) của một bàn, theo thứ tự xử lý `(running và stuck trước, started tăng dần với None cuối, id)`.
   Mỗi lane có tối đa một phòng ban sở hữu, một phòng ban có thể sở hữu nhiều lane; lane không còn worker nào thì hết
   chủ.
   Worker mới lấy, lần lượt, ô đầu tiên khớp (a và b chỉ khi số worker vẽ còn dưới `limits.workers`; c và d chỉ cho
   worker mới còn sống, state `running`/`stuck`):
   a. ô trống thấp nhất (lane tăng, ô tăng) trong lane do phòng ban của nó sở hữu;
   b. ô 0 của lane không chủ có số thấp nhất, lane đó thành của phòng ban của nó;
   c. thay thế một worker không còn sống (state khác `running`/`stuck`) trong lane do phòng ban của nó sở hữu, chọn
      `last_activity` nhỏ nhất (None tính 0), hoà thì theo khoá; worker bị thay vào `more` của bàn;
   d. nếu có lane chỉ chứa worker không còn sống: giải phóng cả lane (các worker đó vào `more`) và đặt worker mới vào
      ô 0 của lane đó, lane thành của phòng ban của nó; có nhiều lane như vậy thì giải phóng lane có số thấp nhất;
   e. không được thì vào `more` của bàn.
   Sau một lượt qua mọi worker mới, các worker trong `more` (kể cả worker vừa bị thay ở c, d) được xét lại theo đúng
   luật a đến e và theo thứ tự xử lý; lặp tới khi một lượt không đặt thêm worker nào. Lý do: d giải phóng cả lane nhưng
   chỉ dùng một ô, số worker vẽ giảm `số worker của lane - 1`; nếu không xét lại ngay thì lần gọi sau với cùng đầu vào
   sẽ đặt các worker đó vào ô trống và Layout đổi.
   Worker đang sống không bao giờ bị thay. Tổng số worker vẽ của bàn không vượt `limits.workers`; chạm trần thì chỉ
   còn c và d (thay, không thêm; d có thể làm số worker vẽ giảm), còn lại vào `more`. Worker mới đã xong không thay
   worker đã xong, kể cả khi nó mới hơn: nếu cho thay thì worker vào `more` ở lần gọi này lại là worker mới ở lần sau,
   và cùng đầu vào làm worker đổi chỗ vòng tròn (L-S2 hỏng).
5. Device (BgTask), theo thứ tự `(running trước, started tăng dần với None cuối, id)`: lấy device slot trống thấp
   nhất; hết chỗ thì device mới `running` thay device không `running` có `started` nhỏ nhất (None tính 0, nên bị thay
   trước; hoà thì theo khoá); không được thì vào `more` của bàn. Device `running` không bị thay; device mới không
   `running` không thay device nào (cùng lý do ở bước 4).
6. `desk.more.n` là số worker (subagent) và device không vẽ; `counts` đếm chúng theo `state`.

Lần gọi đầu (`prev=None`) cho cùng vị trí (slot và ô) với mọi thứ tự của đầu vào, nhờ thứ tự cố định ở bước 2, 3, 4, 5.
Phạm vi bảo đảm: chỉ cho đầu vào không có khoá trùng (hậu tố `#n` đi theo thứ tự đầu vào) và chỉ cho phần Layout
không phải `ref` (`ref` là chỉ số vị trí trong `org_out` nên đổi theo thứ tự đầu vào; consumer phải dùng `ref` của
đúng lần gọi). Thứ tự đầu vào thật sự đổi trong chạy thật: `states.merge` sắp lại session mỗi khi state đổi
(`states.py:177`); bảo đảm này cùng L-S1 (có `prev`) là thứ giữ bàn không nhảy.

### Ổn định

- (L-S1) Một bàn giữ nguyên `(floor.level, cluster.slot, desk.slot)`, vậy giữ nguyên toạ độ `x, y`, trong mọi lần
  gọi nối tiếp (mỗi lần truyền Layout trước làm `prev`) khi session còn trong đầu vào và còn được vẽ, bất kể session
  khác đến, đi hay đổi thứ tự.
- (L-S2) Một worker giữ `(lane, slot)` khi còn trong đầu vào và chưa bị thay theo bước 4c, 4d, 5.
- (L-S3) Ô giải phóng được tái dùng theo thứ tự thấp nhất trước.
- (L-S4) Sàn lớn lên (thêm hàng cụm) chỉ thêm ô ở phía nam; toạ độ ô đang có không đổi.
- (L-S5) Slot không lưu xuống đĩa và mỗi nơi gọi `office_layout` giữ `prev` riêng. Đóng cửa sổ Control room hoặc tắt
  server viewer thì bộ nhớ của nơi đó mất; lần dựng sau cho kết quả xác định theo bước 2 và có thể khác lần trước nếu
  session đã đến đi. Hệ quả: tab Board và viewer 3D (hai nơi gọi độc lập, mỗi nơi có lịch sử `prev` khác nhau) **có thể
  xếp bàn khác nhau cho cùng một dữ liệu**. Trong phạm vi một nơi gọi và một vòng đời của `prev`, L-S1 đến L-S4 vẫn đúng.

### Cam kết cho consumer

Các cam kết dưới đây là hợp đồng của `office.py` với mọi bên dùng Layout (Board, viewer 3D); mỗi cam kết có test ở T-L13
đến T-L16.

1. `Floor.level` là `int >= 0`, duy nhất trong một Layout, và `level <= limits.desks - 1` (sàn mới lấy `level` trống thấp
   nhất, mà mỗi sàn có ít nhất một bàn nên không quá `limits.desks` sàn cùng lúc). `Layout["floors"]` sắp theo `level`
   tăng dần.
2. `Floor.w` luôn bằng `FLOOR_CLUSTER_COLS * CLUSTER_W` (30). `Floor.h` luôn là bội của `CLUSTER_H` (10), tối thiểu
   10, và tối đa `max_floor_h(limits.desks) = CLUSTER_H * ceil(limits.desks / FLOOR_CLUSTER_COLS)`. Lý do: slot cụm
   thấp nhất còn trống luôn nhỏ hơn số cụm đang có, mà số cụm của một sàn không quá `limits.desks` (mỗi cụm có ít
   nhất một bàn), nên slot cụm lớn nhất là `limits.desks - 1` và hàng cụm lớn nhất là `ceil(limits.desks / 2)`. Với
   mặc định 48 bàn: `h <= 240`; ở trần cấu hình 200 bàn: `h <= 1000`. Consumer đặt nhiều sàn thành lưới có thể dùng
   `FLOOR_CLUSTER_COLS * CLUSTER_W` làm bề rộng và `max_floor_h(limits.desks)` làm bề cao của một ô lưới.
3. Worker và Device không có `w`, `h` (xem "Hình dạng"); Desk có `w = h = 2`.
4. `more.counts` của bàn dùng khoá thuộc enum state của worker, có `sum(counts.values()) == n`; `Layout["more"]` không
   có `counts` (chỉ `desks`, `stuck_desks`).
5. `office_layout` thuần và tái nhập: không cache toàn cục (không câu lệnh `global`, không decorator
   `functools.cache`/`lru_cache`), không biến module-level có thể thay đổi ngoài các hằng bất biến theo quy ước
   (`STATE_STYLE`, `ALERT_STYLE`, `LANES`, `CLUSTER_PODS`), không trạng thái ẩn, không sửa `org_out`, `cfg`, `prev`. `Layout["styles"]` là bản sao sâu: sửa Layout đã
   trả về không làm đổi `STATE_STYLE` hay Layout của lần gọi sau. Hai nơi gọi độc lập (tab Board và viewer) với `prev`
   riêng không ảnh hưởng nhau: kết quả của một chuỗi gọi không phụ thuộc việc chuỗi kia có chạy xen kẽ hay không.
   Hệ quả đã nêu ở L-S5.

### Trần

| Trần | Mặc định | Lý do | Khi vượt |
|---|---|---|---|
| bàn vẽ ra (mọi sàn) | 48 (`board_max_desks`) | ngân sách vẽ: một sàn đầy 48 bàn khoảng 2.900 item canvas tối đa (ước lượng, chưa đo); 48 là 8 cụm đầy, vượt xa cỡ sử dụng thực tế (1 đến 3 session mỗi worktree) | `more.desks` |
| session mỗi cụm | 6 (hình học) | một cụm 3x2 pod; hơn 6 session cùng một worktree là hiếm | `more.desks` |
| subagent vẽ mỗi bàn | 12 (`board_max_workers`) | 12 ô vòng ngoài của pod; subagent thật thường dưới 10 mỗi session | `desk.more` |
| device mỗi bàn | 3 (hằng) | 3 ô còn lại trên mặt bàn (ô thứ tư là chỗ mascot ngồi) | `desk.more` |

Số liệu không vẽ vẫn được đếm: `alert.stuck` của bàn và thanh tổng của Control room tính trên mọi worker, nên một
worker `stuck` bị gộp vào `+N` vẫn làm bàn của nó hiện cảnh báo.

### Mascot cho bàn và subagent

**Quyết định mới (cần duyệt):** vì app chưa gán mascot theo session, Board đặt quy tắc tối thiểu:

- Bàn: mascot `ids[mascot_index(desk.seed, len(ids))]` với `ids = [m["id"] for m in mascots.all_mascots()]`.
  Cùng `session_id` luôn ra cùng mascot (kể cả khi đổi worktree), miễn danh sách mascot không đổi.
- Subagent: cùng cách với `worker.seed` (theo phòng ban): mọi subagent cùng phòng ban có cùng mascot. Device không
  có mascot.
- Hue: `prefs["hue"]` toàn cục (`App._hue()`). Board bỏ qua `prefs["mascot"]` (mascot người dùng chọn cho island và
  bóng) và ảnh `custom`.
- Mood lấy từ bảng state. `mascots.all_mascots()` rỗng (thiếu `mascots.json`): vẽ hình tròn màu state thay mascot.
- Phương án thay thế nếu người dùng không muốn mascot khác nhau: mọi bàn dùng `prefs["mascot"]`, subagent dùng
  `prefs["mascot"]` với kích thước nhỏ; Layout không đổi (seed vẫn có, chỉ bên vẽ bỏ qua).

## Bảng state -> hiển thị

Một bảng duy nhất, `office.STATE_STYLE`; `Layout["styles"]` là bản sao sâu của nó. Hai khoá `done` của bàn và của
worker khác nhau (màu, mood) nên bảng có hai phần:

```
STATE_STYLE = {"desk":   {state: {"color": str, "mood": str, "marker": "ring"|"cross"|None}},
               "worker": {state: {"color": str, "mood": str, "marker": "ring"|"cross"|None}}}
```

- `desk` có đúng bốn khoá `idle`, `run`, `wait`, `done`; `worker` có đúng bảy khoá `running`, `stuck`, `done`, `failed`,
  `killed`, `ended`, `unknown`. Mọi `Style` có đủ ba khoá `color`, `mood`, `marker` (không thiếu khoá; "không có
  dấu hiệu" là `None`, JSON `null`).
- `color` là tên khoá của `theme.DARK`/`theme.LIGHT` (không phải hex; Board tra qua `th["palette"]`, xem "Tab"); `mood` thuộc `mascots.MOODS` (luôn là `str`, kể
  cả với device, nơi mood không dùng); `marker` là tên hình do bên vẽ hiện thực.
- Tra cứu: `STATE_STYLE["desk"][desk["state"]]` và `STATE_STYLE["worker"][node["state"]]`; `desk.state` và
  `worker.state` đã được chuẩn hoá vào các khoá trên nên tra cứu không bao giờ thiếu khoá.

Phần `desk`, khoá theo state của bàn:

| state | color | mood | marker |
|---|---|---|---|
| `run` | `run` | `run` | `None` |
| `wait` | `wait` | `wait` | `None` (mood `wait` đã có dấu "!") |
| `done` | `done` | `done` | `None` |
| `idle` | `idle` | `idle` | `None` |

Phần `worker` (subagent và device), khoá theo state của worker:

| state | color | mood | marker | Ý nghĩa |
|---|---|---|---|---|
| `running` | `ok` | `run` | `None` | đang chạy |
| `stuck` | `warn` | `wait` | `ring` | im quá `stuck_after_sec`, không còn việc đang chạy |
| `done` | `mut` | `done` | `None` | xong |
| `failed` | `danger` | `quota` | `cross` | kết thúc lỗi (mood `quota`: lo, mồ hôi) |
| `killed` | `idle` | `idle` | `None` | bị dừng |
| `ended` | `idle` | `idle` | `None` | task nền của lần chạy trước khi resume (chỉ BgTask) |
| `unknown` | `idle` | `idle` | `None` | state ngoài enum của org |

- Dấu hiệu cảnh báo của bàn có stuck không nằm trong `STATE_STYLE` (không phải state): hằng riêng
  `office.ALERT_STYLE = {"color": "warn", "marker": "ring"}`.
- Device chỉ dùng màu và marker (LED trên hộp); mood không áp dụng.
- Màu thật của `desk.done` (token `done`) và `worker.running` (token `ok`) trùng nhau (`#3fd0a4` ở DARK, `#0b7a5a` ở
  LIGHT). **Quyết định mới (cần duyệt):** chấp nhận, không đổi token. Bàn `done` và worker `running` phân biệt bằng
  hình dạng và vị trí (bàn là khối 2x2 có mascot lớn ngồi; worker là sprite nhỏ ở vòng ngoài pod), bằng mood (`done`
  có tia sáng, `run` không) và bằng ngữ cảnh. Lý do: đổi `ok` hay `done` sẽ lệch với island/panel (`done`) và với màu
  thẻ của cây (`ok`).
- Bàn có `alert.stuck > 0` thêm dấu hiệu cảnh báo: viền `ring` màu `warn` quanh bàn và huy hiệu `warn` ghi số stuck.
  Đây là thuộc tính của bàn, không phải state của session; mood của mascot ngồi vẫn theo state session.
- `ring`: viền kim cương nét đứt 2 px quanh ô của worker (hoặc quanh bàn). `cross`: hai nét chéo 2 px màu `danger` ở
  góc trên phải sprite. Cả hai chỉ cần `create_polygon`/`create_line`, không cần font.
- Màu `run` của bàn (xanh dương) và `ok` của worker đang chạy (xanh lá) khác nhau có chủ ý: bàn theo bảng màu island
  và panel; worker theo màu thẻ của cây Control room (`running` xanh lá, `stuck` vàng, `failed` đỏ, `done` xám, còn lại
  mờ). Không dựa riêng vào màu: stuck có `ring` và mood `wait`, failed có `cross` và mood `quota`.
- Mood `quota` của app là cảnh báo hạn mức toàn cục; Board chỉ mượn biểu cảm cho worker `failed`, không dùng ý nghĩa
  hạn mức.

## Board (`pet_tracker/board.py`, tab trong `control_room.py`)

Hai lớp như `control_room.py`: hàm thuần (không Tk, kiểm bằng unit test) và lớp `Board` chạy ở main thread, không I/O,
git, subprocess. Import `tkinter` bọc `try` như `control_room.py`.

### Tab

- Thanh tab hai nhãn `Cây` và `Board` nằm giữa thanh tổng và thân. Mở cửa sổ luôn vào tab `Cây` (không lưu tab đã
  chọn). Thanh tổng và panel chi tiết bên phải dùng chung cho cả hai tab; tab `Board` ghi vào panel chi tiết đó.
- `ControlRoom.__init__` thêm hai tham số tuỳ chọn, mặc định `None`: `cfg` (dict, để đọc `board_max_*`) và
  `mascot_image(mid, mood, size) -> PhotoImage | None` (App truyền vào; Board không import `ui`). Không truyền thì
  Board vẽ hình tròn thay mascot. Các chỗ gọi hiện có không đổi.
- **Palette:** `STATE_STYLE`/`ALERT_STYLE` dùng token của `theme.DARK/LIGHT` (`run wait done idle ok warn mut danger`;
  sàn dùng `surf`, `track`; chữ và viền dùng `fg`, `mut`, `line`, `bg`), nhưng `ControlRoom.th` chỉ nhận các khoá
  `bg surface line fg fg2 muted faint green yellow red accent sel` (`App._control_room_theme`, `ui/app.py:623-629`, và
  `_DEFAULT_THEME`, `control_room.py:381`), nên tra `th["ok"]` sẽ `KeyError`. **Quyết định mới (cần duyệt):**
  `_control_room_theme` thêm một khoá `"palette"` bằng đúng dict `self.kit.P` (toàn bộ `theme.DARK` hoặc `theme.LIGHT`
  đang dùng); `_DEFAULT_THEME` thêm `"palette": theme.DARK` (`control_room.py` import `theme`, module thuần; `ControlRoom.__init__` có tham số tên `theme` che module này nên code Board phải import module dưới tên khác, ví dụ `from . import theme as _theme`, hoặc chỉ dùng nó ở cấp module, không bao giờ trong thân hàm có tham số `theme`). Board tra
  màu bằng `th["palette"][token]`; token không có trong palette thì dùng `palette["idle"]` (không bao giờ
  `KeyError`); tên theme cho mascot lấy từ `palette["name"]`. Lý do chọn khoá riêng thay vì mở rộng phẳng: mọi khoá
  cũ giữ nguyên (cây và test hiện có không đổi), không phải đặt bí danh mới cho từng token, và có một nguồn màu duy
  nhất cho cả hai theme. File sửa: `pet_tracker/ui/app.py` (`_control_room_theme`) và `pet_tracker/control_room.py`
  (`_DEFAULT_THEME`, import `theme`).
- `render(snap)` vẫn lưu `org`. Board chỉ tính Layout và vẽ khi cửa sổ đang mở và tab `Board` đang hiện; chuyển sang
  tab `Board` thì dựng ngay từ `org` mới nhất. Lỗi trong Board được bắt, ghi log (`repr()` cắt 200 ký tự) và giữ
  nguyên hình cũ; tab `Cây` không bị ảnh hưởng.

### Hiển thị

- Một lần hiện đúng một sàn. Thanh điều hướng phía trên canvas: nút `◀` `▶`, nhãn `Sàn i/n`, tên project, số liệu
  (`counts_text` của project: agent đang chạy, treo, task) và chú giải bốn chấm (`running`, `stuck`, `done`,
  `failed`) bằng đúng màu của bảng state. Phím `←` `→` đổi sàn khi canvas có focus.
- Sàn mặc định (khi người dùng chưa chọn): sàn đầu tiên có worker `stuck`; không có thì sàn đầu tiên có worker
  `running`; không có thì sàn `level` thấp nhất. Người dùng đã chọn một sàn thì giữ theo khoá `p:<root>`; sàn đó biến
  mất thì quay lại quy tắc mặc định. Nhãn `i/n` đổi màu `warn` kèm "!" khi một sàn khác có worker `stuck`.
- Phép chiếu isometric 2:1, ô `TW x TH = 32 x 16` px, một đơn vị `z` = 16 px (nhân `scale` của theme):
  `sx = (x - y) * TW/2`, `sy = (x + y) * TH/2 - z * 16`. Vì vậy `+x` chạy xuống-phải và `+y` chạy xuống-trái trên
  màn hình (viewer 3D tự chọn camera, miễn dùng cùng toạ độ ô).
- Vật thể: nền sàn (`surf`) là MỘT polygon cho cả sàn và vùng cụm (`track`) là MỘT polygon cho mỗi cụm (không vẽ từng ô, không kẻ
  lưới: ở trần 200 bàn sàn 30x1000 ô sẽ thành khoảng 30.000 polygon nếu vẽ từng ô); bàn 2x2 cao 0,5 đơn vị với viền màu theo state của bàn;
  mascot bàn cao 36 px (logic) đặt ở ô `(desk.x, desk.y)`; subagent mascot cao 18 px đặt giữa ô của nó; device là hộp
  0,6 x 0,6 ô, cao 0,3 đơn vị, có LED tròn bán kính 2 px ở mặt trước màu theo state (**BgTask hiện dạng này**: hộp
  "máy chủ" nhỏ với đèn; `failed` có `cross`, `ended` và `killed` đèn mờ).
- Chữ: tên cụm (`top` lấy phần cuối đường dẫn, kèm nhánh) phía trên góc sau của cụm; tên session dưới pod, cắt
  24 ký tự; chip `+N` của bàn (`desk.more.n`) ở ô lối đi `(pod.x + 4, pod.y + 4)`, màu `warn` khi `counts` có `stuck`,
  còn lại `mut`; chip `+N bàn` (`layout.more.desks`) ở góc trên-phải canvas, màu `warn` khi `stuck_desks > 0`. Mọi
  chuỗi đi qua `sanitize()`.
- Thứ tự vẽ (painter, hàm thuần `paint_order`): tăng dần theo `x + y`, hoà theo `x`; trong cùng một ô: mặt bàn trước,
  rồi device, rồi mascot. Mascot của bàn vẽ sau mặt bàn và trước device để device không bị che.
- Canvas có thanh cuộn dọc và ngang (`_style` hiện chỉ có `Cr.Vertical.TScrollbar`, `control_room.py:582`; cần thêm style `Cr.Horizontal.TScrollbar` cùng màu) và cuộn bằng con lăn; vùng cuộn là bbox của sàn
  cộng lề 24 px. Mở hoặc đổi sàn thì cuộn về góc trên-trái của sàn.
- Hai trạng thái trống: `org` không hợp lệ (`valid_org` sai) thì canvas hiện `cr.board.nodata`; `org` hợp lệ không có session thì hiện `cr.empty`; cả hai ẩn nút điều hướng.

### Vẽ

- Mascot là `PhotoImage` từ PNG RGBA có alpha thật (qua `mascots.png(..., cache_dir=<state>/mascots)`), giữ trong
  một dict tham chiếu (tránh bị GC) với trần 600 ảnh (vượt thì xoá hết, như `Kit.image`). Khoá ảnh
  `(mid, mood, kích thước, theme, hue)`: tối đa 40 x 5 x 2 = 400 ảnh. Mascot dựng lười ở lần vẽ đầu tiên, không có
  thread nền.
- `mascot_image` ném lỗi hoặc trả `None` cho một sprite thì sprite đó thành hình tròn màu state; lỗi ghi log một lần
  cho mỗi khoá ảnh. Một sprite hỏng không làm hỏng cả Board.
- Mỗi nút vẽ ra mang một tag hằng dạng `n<số>` (bộ đếm, ánh xạ về nút bằng dict) cộng tag nhóm cố định (`desk`, `worker`, `device`, `chip`, `marker`, `floor`, `cluster`). Không chuỗi agent nào đi vào tag hay tên item.

### Tương tác

Chỉ xem. Không có thao tác nào dừng, xoá hay gửi lệnh tới agent.

- Rê chuột lên một bàn, worker, device hoặc chip: panel chi tiết hiện thông tin mục đó; rời đi thì panel quay về mục
  đang chọn (hoặc chữ gợi ý). Hover không đổi lựa chọn.
- Bấm đơn chọn mục (bàn chọn có viền `fg` 2 px). **Quyết định mới (cần duyệt):** bấm đơn chỉ chọn, **bấm đúp bàn
  hoặc Enter khi đang chọn bàn** mới focus session, giống tab `Cây` (tránh cướp focus khi lỡ bấm). Bấm đúp worker,
  device hoặc chip không làm gì ngoài chọn.
- Focus: Board gọi đúng callback `focus_session(session_id)` của `ControlRoom` (cùng đường với `_activate`: chỉ khi bàn
  có `session_id`; lỗi thì ghi log bằng `repr()` cắt 200 ký tự). Phía App không đổi: `_focus_from_control_room` tra
  session live, trùng hoặc không thấy thì không làm gì.
- Lựa chọn giữ theo khoá nút qua các lần dựng lại; nút biến mất thì bỏ lựa chọn.

Chi tiết (panel bên phải), cùng nhãn i18n `cr.f.*` với cây:

- bàn: tên, `Phiên`, `Trạng thái`, `Mô hình`, `Thư mục`, `Nhánh`, `Đã chạy`, `Hoạt động cuối`, `Token`, và dòng worker
  (`counts_text` của session);
- subagent: `Mô tả`, `Loại agent` (từ `type`), `Phòng ban`, `Trạng thái`, `Đã chạy`, `Hoạt động cuối`, `Token`,
  `Độ sâu`; device: `Task id`, `Trạng thái`, `Đã chạy`, `tool_use`;
- chip `+N` của bàn: số worker không vẽ theo từng state (nhãn `cr.st.*`); chip `+N bàn`: số bàn chưa vẽ, trần đang
  dùng và số bàn có agent treo.

Số liệu lấy từ `org_out` qua `ref` của nút; cách tính giống cột "Chạy · token · hoạt động cuối" của cây
(`fmt_elapsed`, `fmt_tokens`, `sanitize`).

### Vòng cập nhật

Mẫu giống `_apply` của Control room. Mỗi `render(snap, now)` của tab `Board`:

1. Nếu `valid_org(org)` sai: hiện `cr.board.nodata`, giữ nguyên `self._layout`, dừng (xem "Layout chung"). Ngược lại
   `layout = office_layout(org, cfg, prev=self._layout)` và giữ `layout` làm `prev` cho lần sau (mất khi đóng cửa sổ).
2. Chọn sàn (quy tắc trên).
3. Ba chữ ký tính trên sàn đang hiện, tách theo việc phải làm:
   - `board_struct_sig`: khoá sàn đang hiện và, với mọi nút, khoá, `x`, `y`, `seed`, tên hiển thị; cộng `more.n` của
     từng bàn (chip `+N`) và `layout.more.desks`. KHÔNG chứa `state`, `alert`, `counts`. Đổi thì **dựng lại**:
     `canvas.delete("all")` và vẽ lại, giữ lựa chọn theo khoá và vị trí cuộn (đổi sàn thì cuộn về đầu).
   - `board_style_sig`: với mọi nút, `(khoá, state, alert.stuck)` và, với chip `+N`, việc `counts` có `stuck` hay
     không. Đổi mà struct không đổi thì **cập nhật tại chỗ** từng nút đổi, qua map `n<số>` → nút: `itemconfigure` màu
     (viền bàn, LED, nền chip, hình tròn dự phòng), `itemconfigure(image=...)` đổi mood của sprite, thêm hoặc xoá
     item marker (`ring`, `cross`) và huy hiệu stuck của riêng nút đó. Không tạo lại nút khác, không đổi `x`, `y`.
   - `board_live_sig`: văn bản thanh điều hướng (tên, số liệu, cảnh báo sàn khác) và văn bản chi tiết của mục đang
     hiện (số liệu `elapsed`, `ago`, `tokens` ở đây). Đổi mà hai chữ ký kia không đổi thì chỉ ghi lại nhãn điều hướng
     và panel chi tiết. Không tạo, xoá, di chuyển item canvas.
4. Thứ tự áp dụng: struct đổi thì dựng lại (đã gồm style và live); nếu không thì áp style rồi live. Cả ba chữ ký bằng
   nhau và không còn nút chờ sprite thì không làm gì.
5. Ngân sách sprite: một lần `render` gọi `mascot_image` cho tối đa `MAX_SPRITES_PER_RENDER = 8` ảnh chưa có trong dict
   ảnh của Board (ảnh đã có trong dict không tính). Sprite quá ngân sách tạm là hình tròn màu state mang cùng tag
   `n<số>`, và nút được ghi vào danh sách chờ. Mỗi lần `render` sau (`_pump` gọi mỗi `refresh_sessions_sec`, kể cả khi
   ba chữ ký không đổi) xử lý tiếp tối đa 8 nút chờ: xoá hình tròn, tạo ảnh tại cùng toạ độ và tag. Không timer riêng.
   Sprite mà `mascot_image` trả `None` hoặc ném lỗi là hình tròn vĩnh viễn (không vào danh sách chờ, không thử lại).
   Vì vậy một lần dựng lại không rasterize quá 8 ảnh.

Khác với `struct_sig` của cây (có `state`): ở Board `state` chỉ đổi màu, mood và marker nên tách thành chữ ký style và
cập nhật tại chỗ, để một worker đổi state không xoá và vẽ lại hàng nghìn item trên main thread (**Quyết định mới
(cần duyệt)**, vì spec Control room đặt `state` trong chữ ký struct của cây). Một lần dựng lại (chỉ khi cấu trúc đổi)
quá 100 ms thì ghi log một dòng chỉ gồm số (`board rebuild <ms>ms desks=<n> workers=<n>`).

## Cấu hình (`config.py`, `config.example.json`)

**Quyết định mới (cần duyệt):** hai khoá mới; không thêm khoá nào khác (kích thước pod, cụm, số lane là hằng của
`office.py`, không cấu hình).

| Khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `board_max_desks` | `48` | trần số bàn vẽ ra (mọi sàn cộng lại); kẹp vào [1, 200]; không phải số thì dùng 48 |
| `board_max_workers` | `12` | trần số subagent vẽ quanh mỗi bàn; kẹp vào [0, 12] (12 là số ô vòng ngoài); không phải số thì dùng 12 |

Lý do thêm khoá: người dùng có máy yếu hoặc rất nhiều session cần hạ trần vẽ mà không sửa code, và test của trần cần
đặt trần nhỏ thay vì dựng 49 session. Không có UI Cài đặt cho hai khoá này (chỉnh `config.json`). Không thêm khoá
`state.json` và không thêm tuỳ chọn trong `prefs`.

Chuỗi i18n mới (cả `vi` lẫn `en`, giữ test đối chiếu khoá): `cr.tab.tree`, `cr.tab.board`, `cr.board.floor`
(`Sàn {i}/{n}`), `cr.board.more_desks` (`+{n} bàn`), `cr.board.more_detail`, `cr.board.hint`, `cr.board.nodata` (`Chưa có dữ liệu`), `cr.f.workers`.

## Lỗi và an toàn

- `org` không hợp lệ (`valid_org` sai: `org.build` lỗi cho `snap["org"] = None`, `app.py:175-179`; hoặc snapshot lỗi
  không có khoá `org`, `app.py:187`): Board giữ `prev`, hiện `cr.board.nodata`, không ném lỗi; cây vẫn trống như hiện
  nay. `org` hợp lệ không có session hiện `cr.empty`. Khi `org` hợp lệ trở lại, bàn về đúng ô cũ nếu session còn.
- Dữ liệu thiếu hoặc sai kiểu (tên rỗng, `session_id` thiếu, `workers` không phải list, state lạ, `started_at` không
  phải số): nhánh hỏng bị bỏ hoặc dùng giá trị thay thế đã nêu (state lạ thành `idle`/`unknown`, tên rỗng giữ `""` trong Layout và chỉ được thay bằng `cr.anon_session`/`cr.anon_subagent` lúc hiển thị); Layout không ném lỗi. Trần 500 worker mỗi session (`CAP_ITEMS`, `claude_data.py:45`) và độ sâu 8 (`org.MAX_DEPTH`) giữ nguyên.
- Mọi chuỗi từ agent là dữ liệu không tin cậy: `org.py` đã làm sạch; Board `sanitize()` lại và chỉ đưa chuỗi vào
  `create_text(text=...)` và panel chi tiết. Không chuỗi agent nào đi vào tag, tên item, đối số subprocess, đường
  dẫn hay lệnh Tk. Đường dẫn cache mascot chỉ dựng từ id mascot trong `assets/mascots.json`, mood từ bảng state, hue
  từ `prefs` (không từ chuỗi agent). Seed và `% count` chỉ là số học. `session_id` chỉ đi đến callback
  `focus_session`, nơi App kiểm độ dài và trùng id như hiện nay.
- Board không ghi đĩa (ngoài PNG cache mascot sẵn có), không mạng, không subprocess, không đụng `~/.claude`.
- Hiệu năng (main thread của Tk): chỉ tính và vẽ khi tab `Board` hiện; chỉ vẽ một sàn; không timer; mỗi sàn đúng một
  polygon nền và mỗi cụm đúng một polygon; dựng lại toàn bộ chỉ khi cấu trúc đổi (khoá, ô, tên, `+N`, đổi sàn); đổi
  state chỉ `itemconfigure` tại chỗ; tối đa 8 sprite rasterize mỗi lần render; ảnh có cache; Layout tính bằng
  O(n log n) trên số worker và bị chặn bởi `CAP_ITEMS` (500 worker mỗi session, `claude_data.py:45`). Mục tiêu cần đo
  ở T3 (chưa đo): dựng lại một sàn 12 bàn, 40 subagent (ảnh đã cache) trong 100 ms; một sàn đầy 48 bàn, mỗi bàn 12
  subagent trong 300 ms; cập nhật tại chỗ do 10 nút đổi state trong 30 ms. Vượt mục tiêu thì hạ trần mặc định,
  không thêm cơ chế khác.
- Windows chưa có máy kiểm: ghi `unavailable`, không tính là pass; ghi rõ trong CHANGELOG khi phát hành.

## Kiểm thử

Chạy bằng `python -m unittest discover -s tests`.

`tests/test_office.py` (`unittest` thuần, không Tk, không đĩa):

| Mã | Kiểm |
|---|---|
| T-L1 | JSON hoá: `json.loads(json.dumps(l)) == l` (chỉ list, không tuple); `ast` quét import của `office.py` không có `tkinter`, `os`, `subprocess`, `pathlib`; đầu vào và `prev` không bị sửa (so bản sao sâu) |
| T-L2 | `None`, `{}`, `{"projects": 5}`, phần tử không phải dict, `workers` hỏng, `started_at` kiểu lạ: không ném lỗi, Layout rỗng hoặc bỏ nhánh hỏng |
| T-L3 | xác định: cùng đầu vào hai lần cho Layout giống hệt; xáo thứ tự session, team, project, worker (không `prev`) trên fixture KHÔNG có khoá trùng cho Layout bằng nhau sau khi bỏ mọi khoá `ref` (so sánh có loại `ref`); fixture có khoá trùng chỉ kiểm không ném lỗi và khoá vẫn duy nhất (không bảo đảm vị trí) |
| T-L4 | ổn định bàn (L-S1): thêm session, bớt session ở giữa, đổi thứ tự đầu vào qua nhiều vòng có `prev`: bàn còn lại giữ `x, y`; session mới lấy ô trống thấp nhất; session khoá cũ trở lại không đẩy bàn khác; `valid_org` đúng với `{"projects": []}` và sai với `None`, `{}`, `{"projects": 5}`; `office_layout(None, cfg, prev)` trả Layout rỗng; chuỗi mô phỏng luật nơi gọi (hợp lệ, rồi không hợp lệ giữ `prev`, rồi hợp lệ lại): bàn trở về đúng ô cũ; chuỗi hợp lệ rồi `{"projects": []}` rồi hợp lệ lại: slot đã được giải phóng và cấp lại theo bước 2 |
| T-L5 | ổn định worker (L-S2): thêm và bớt worker không làm worker hoặc bàn khác đổi `x, y`; lane giữ chủ khi còn worker; lane hết worker thì thành không chủ và được tái dùng |
| T-L6 | quy tắc lane: cùng phòng ban cùng lane; phòng ban thứ hai lane khác; phòng ban có hơn 3 worker lấy thêm lane trống; phòng ban thứ 5 (hết lane) vào `more`; 4c thay worker `done` cũ nhất; 4d giải phóng lane toàn worker đã xong, và khi có nhiều lane như vậy thì giải phóng lane có số thấp nhất (ca hai lane đều toàn worker đã xong: chỉ lane thấp bị giải phóng, lane cao giữ nguyên); worker `running`/`stuck` không bao giờ bị thay |
| T-L7 | device: 3 ô, thay device không `running` cũ nhất, device `running` không bị thay, phần dư vào `more` |
| T-L8 | trần: cụm đầy 6 bàn, bàn thứ 7 vào `more.desks`; `board_max_desks`=3, `board_max_workers`=5 hiệu lực; khoá cfg sai kiểu hoặc ngoài khoảng được kẹp (kiểm `limits`); `prev` có `limits` khác bị bỏ; `alert.stuck` và `more.stuck_desks` tính trên cả worker không vẽ |
| T-L9 | hình học: mọi desk và worker nằm trong khung sàn; khối 2x2 của desk và ô của worker đôi một không giao nhau (so tập ô, device không tính riêng); mỗi device nằm trong khối 2x2 của desk của nó, ba device ở ba ô khác nhau và khác ô `(desk.x, desk.y)`; công thức khớp bảng (cụm, bàn, device, worker) trên một fixture; hàng cụm tăng chỉ thêm ô phía nam (L-S4) |
| T-L10 | khoá và `ref`: khoá trùng có hậu tố, khoá duy nhất; `org_out` truy theo `ref` ra đúng dict nguồn; sàn đổi `level` được tái dùng khi sàn cũ biến mất |
| T-L11 | seed: `crc32("abc")` ra `891568578`; `mascot_index` đúng và `None` khi `count <= 0`; session cùng id ở hai worktree cùng seed |
| T-L12 | khói hiệu năng: 60 session x 500 worker xong, tổng vẽ không vượt trần (không khẳng định thời gian; ghi số đo vào PR) |
| T-L13 | cam kết 1 và 2: qua nhiều vòng thêm/bớt project và worktree (có `prev`), `level` là int >= 0, duy nhất, `<= limits.desks - 1`, `floors` sắp theo `level`; `Floor.w == FLOOR_CLUSTER_COLS * CLUSTER_W == 30` ở mọi sàn; `Floor.h` là bội của 10, `>= 10`, `<= max_floor_h(limits.desks)`; ca xấu nhất với `board_max_desks`=4: tạo 4 cụm một bàn rồi bỏ 3 cụm thấp, cụm còn lại ở slot 3 cho `h == 20 == max_floor_h(4)`; `max_floor_h(48) == 240` và `max_floor_h(200) == 1000` |
| T-L14 | cam kết 3: Worker và Device không có khoá `w` hay `h` (kiểm bằng tập khoá chính xác), Desk có `w == h == 2` |
| T-L15 | cam kết 4: ở mọi `desk.more`, khoá `counts` là tập con của `running stuck done failed killed ended unknown`, mọi giá trị > 0 và `sum == n`; worker với state ngoài enum (chuỗi lạ, `None`) rơi vào `unknown`; subagent và device cùng được đếm; tập khoá của `Layout["more"]` bằng đúng `{desks, stuck_desks}` |
| T-L16 | cam kết 5: `ast` quét `office.py` không có câu lệnh `global`, không có decorator `functools.cache` hay `lru_cache` (cả dạng `@cache`, `@lru_cache(...)`, `@functools.cache`; không cấm tên `cache` xuất hiện ở chỗ khác như tên biến hoặc chú thích), không có phép gán cấp module nào cho `list`/`dict`/`set` ngoài bốn hằng `STATE_STYLE`, `ALERT_STYLE`, `LANES`, `CLUSTER_PODS`; so sánh sâu bốn hằng đó trước và sau nhiều lần gọi (không đổi); sửa sâu `layout["styles"]` rồi gọi lại không làm đổi `STATE_STYLE` và Layout sau; hai chuỗi gọi độc lập A (nơi gọi Board) và B (nơi gọi viewer) với cùng chuỗi đầu vào: kết quả của A khi xen kẽ với B bằng kết quả của A chạy riêng, và ngược lại; hai chuỗi có lịch sử `prev` khác nhau (B bắt đầu muộn sau khi session đã đến đi) cho Layout có thể khác nhau về vị trí bàn nhưng cùng tập session (hệ quả L-S5, được kiểm là hành vi chấp nhận, không phải lỗi); gọi từ hai thread song song không lỗi và cho đúng kết quả từng chuỗi |
| T-L17 | xuất tên: `office` có đủ `FLOOR_CLUSTER_COLS == 2`, `CLUSTER_W == 15`, `CLUSTER_H == 10`, `POD == 4`, `POD_STRIDE == 5`, `mascot_index`, `STATE_STYLE`, `CLUSTER_PODS`, `LANES`, `DEVICE_SLOTS`, `ALERT_STYLE`, `max_floor_h`, `valid_org` |
| T-S1 | bảng state: `STATE_STYLE` có đúng hai khoá `desk`, `worker`; `desk` có đúng `idle run wait done`, `worker` có đúng `running stuck done failed killed ended unknown`; mọi `Style` có đúng ba khoá `color mood marker` với `marker` thuộc `{"ring","cross",None}`; mọi state của org (`running stuck done failed killed ended`, session `idle run wait done error`) tra được; giá trị lạ ra `unknown` (worker) hoặc `idle` (desk); mọi `mood` thuộc `mascots.MOODS`; mọi `color` là khoá của cả `theme.DARK` lẫn `theme.LIGHT`; `Layout["styles"] == STATE_STYLE` và không cùng đối tượng; mọi `desk.state` và `worker.state` trong Layout có trong phần tương ứng của `styles`; `ALERT_STYLE` có `color` hợp lệ |

`tests/test_board.py` (hàm thuần của Board, không cần display): `paint_order` (thứ tự đúng, ổn định);
`board_struct_sig` đổi khi đổi khoá/vị trí/tên/`+N` và không đổi khi chỉ đổi `state` hay số liệu; `board_style_sig` đổi khi đổi `state` hoặc `alert.stuck` và không đổi khi chỉ đổi số liệu; `board_live_sig` ngược lại; chọn sàn
mặc định (stuck, rồi running, rồi level thấp nhất; giữ lựa chọn theo khoá; sàn chọn biến mất); `floor_alerts`;
chi tiết của bàn, subagent, device và chip đúng nhãn và giá trị, chuỗi độc (`{ } \ [ $` %, xuống dòng, bidi) ra
văn bản sạch.

`tests/test_ui_board.py` (cần Tk display, tự `skipTest` khi không có, theo mẫu `tests/test_control_room.py`):

| Mã | Kiểm |
|---|---|
| T-B1 | mở cửa sổ vào tab `Cây`; chuyển `Board` dựng đúng số bàn, subagent, device (đếm item theo tag nhóm); đúng 1 item tag `floor` và đúng bằng số cụm item tag `cluster` (không polygon theo ô); chuyển lại `Cây` rồi `Board` giữ chọn |
| T-B2 | struct đổi (thêm bàn, thêm hoặc bớt worker, đổi tên, đổi `+N`): bộ đếm dựng lại tăng 1; chỉ `state` đổi (worker running sang stuck sang failed, bàn có stuck): bộ đếm dựng lại không đổi, id item canvas của mọi nút không đổi, màu, ảnh mood và marker của nút đó đổi (marker `ring`/`cross` xuất hiện rồi mất), nút khác không đổi; chỉ số liệu đổi (token, `last_activity`): bộ đếm dựng lại không đổi, danh sách id item canvas không đổi, panel chi tiết và nhãn điều hướng đổi |
| T-B3 | bấm đơn bàn không gọi `focus_session`; bấm đúp bàn và Enter gọi đúng một lần với `session_id` của bàn; bấm đúp worker, device, chip, và bàn không có `session_id` không gọi; `focus_session` ném lỗi thì ghi log, Board vẫn dùng được |
| T-B4 | `org` hợp lệ, rồi `None`, rồi hợp lệ lại: ở trạng thái `None` hiện `cr.board.nodata`, không ném lỗi, không item thừa, `prev` giữ nguyên; khi hợp lệ trở lại mọi bàn về đúng ô cũ (so toạ độ canvas); snapshot lỗi không có khoá `org` xử lý như `None`; `org` hợp lệ không có session hiện `cr.empty` |
| T-B5 | chuỗi độc trong tên, mô tả, phòng ban, id: mọi `canvas.gettags` khớp `^(n[0-9]+|desk|worker|device|chip|marker|floor|cluster)$`; không item nào mang chuỗi agent làm tag; không có `TclError` |
| T-B6 | `mascot_image` trả `None`, ném lỗi, hoặc không truyền: vẽ hình tròn thay vĩnh viễn, log một lần cho mỗi khoá, không thử lại; các sprite khác không đổi. Ngân sách: 20 sprite khác nhau với stub đếm lời gọi: lần render đầu gọi tối đa 8, phần còn lại là hình tròn chờ; mỗi lần render sau gọi tối đa 8 cho tới khi đủ rồi không gọi nữa, hình tròn chờ được thay bằng ảnh cùng toạ độ và tag; ảnh đã có trong dict không tính vào ngân sách |
| T-B7 | đổi sàn bằng nút và phím `←` `→`, sàn chọn giữ qua cập nhật, nhãn `Sàn i/n` và cảnh báo sàn khác đúng; sàn mặc định theo quy tắc |
| T-B8 | `ControlRoom` dựng lại sau `close()` không rò tham chiếu Board cũ; lỗi cố ý trong `Board.render` không làm hỏng tab `Cây` |
| T-B9 | `tests/test_i18n.py` vẫn đạt với các khoá mới |
| T-B10 | palette: với `P = theme.DARK` rồi `P = theme.LIGHT`, dict theme mà ControlRoom thực sự nhận (kết quả của `App._control_room_theme()` trên self giả, gắn như test hiện có ở `tests/test_ui_control_room.py:547-550`, và `control_room._DEFAULT_THEME`; phần App dùng mẫu stub-import tkinter ở `tests/test_ui_control_room.py:11-24`, không cần display, và KHÔNG đặt trong file test bị skip khi thiếu Tk, nên T-B10 nằm trong `tests/test_ui_control_room.py` hoặc một file mới dùng cùng mẫu import, không nằm trong `tests/test_ui_board.py`) có khoá `palette`; mọi `color` của `STATE_STYLE["desk"]`, `STATE_STYLE["worker"]`, `ALERT_STYLE`, cùng các token Board dùng cho nền (`surf`, `track`, `line`, `bg`, `fg`, `mut`) tra được trong `th["palette"]` (không `KeyError`); `palette["name"]` là `dark`/`light`; các khoá cũ của dict theme không đổi (`test_ui_app_smoke.py:132-136` vẫn đạt); Board dựng bằng dict đó vẽ đủ mọi state không `KeyError`; Board dựng với palette thiếu token (dict giả) dùng `palette["idle"]` |

T3, kiểm tay trên macOS (ghi kết quả vào PR):

1. Mở Control room từ popup của island: vào tab `Cây`, chuyển `Board`: thấy sàn của project đang chạy, mỗi worktree một
   cụm, mỗi session một bàn có mascot khác nhau theo session, subagent đứng theo phòng ban, task nền là hộp có đèn.
2. Ổn định: chụp màn hình, đóng thêm một session và mở một session mới, để subagent mới chạy rồi xong; so sánh ảnh: các
   bàn còn lại không đổi vị trí; bàn mới vào ô trống.
3. Stuck: đặt `stuck_after_sec` nhỏ (ví dụ 5), để một subagent im lặng: thấy `ring` và mood `wait` trên subagent, viền
   và huy hiệu `warn` trên bàn, thanh tổng tăng "Treo"; sàn khác có stuck thì `i/n` đổi màu.
4. Failed: subagent `failed` có `cross` và mood `quota`; `killed` mờ.
5. Bấm đơn một bàn chỉ chọn và hiện chi tiết; bấm đúp mở đúng cửa sổ terminal của session; bấm đúp subagent không làm gì.
6. Giao diện sáng và tối; con lăn và thanh cuộn; đổi cỡ cửa sổ về cỡ tối thiểu 640 x 380 vẫn dùng được.
7. Hiệu năng: đọc dòng log `board rebuild` với 12 bàn / 40 subagent và (nếu dựng được) 48 bàn đầy; so với mục tiêu.
8. Kiểm sprite có alpha đúng trên sàn nhiều màu (không có viền chữ nhật quanh mascot).
9. Windows: `unavailable`.

## Tài liệu

- `docs/GUIDE.md`: thêm mục cho Board (cạnh mục "Control room"): cách mở tab Board, ý nghĩa màu và dấu hiệu (bảng state, `ring`, `cross`, huy hiệu stuck, chip `+N`), hai khoá cấu hình `board_max_desks` và `board_max_workers` (kèm mặc định và khoảng kẹp), và giới hạn đã biết (chỉ xem, một sàn mỗi lần, slot không lưu qua lần khởi động, mascot gán theo hash, Windows chưa kiểm).
- `CHANGELOG.md`: một dòng dưới `[Unreleased]` cho tab Board và hai khoá cấu hình; ghi Windows chưa kiểm.
- `config.example.json`: thêm hai khoá (mục "Cấu hình").

## Rủi ro mở

1. Windows chưa kiểm: PNG alpha trên Canvas, hiển thị chữ, cuộn bằng con lăn (`<MouseWheel>` khác macOS). Không tính
   là pass.
2. PNG alpha thật của mascot trên Canvas nền đặc chưa kiểm trên cả hai hệ điều hành (mới biết `gfx.to_photo` có `bg`
   trộn sẵn nên không dùng được; ảnh alpha trên Canvas nền `systemTransparent` đã biết là không hiện). Nếu T3 mục 8
   thất bại thì phải vẽ mascot bằng `mascots.items` + `gfx.draw_items` (đa giác), tốn nhiều item hơn: cần sửa spec và
   hạ trần mặc định.
3. Các con số hiệu năng (số item, thời gian dựng, thời gian rasterize mascot lạnh bằng rasterizer Python thuần) là
   ước lượng chưa đo; mục tiêu ở "Lỗi và an toàn". Lần đầu mở, sprite chưa cache hiện tạm hình tròn và được bù dần (tối đa 8 ảnh mỗi lần render, mỗi lần cách nhau `refresh_sessions_sec`); mỗi lượt rasterize 8 ảnh vẫn chặn main thread (chưa đo). Ngưỡng chấp nhận: tổng 8 ảnh mascot lạnh cỡ Board ≤ 100 ms (đo ở plan, slice Đ1); vượt thì xin rev spec về `MAX_SPRITES_PER_RENDER`.
4. Mascot gán theo hash (quyết định mới) khiến hai phòng ban có thể trùng mascot (40 mascot, thường dưới 10 phòng ban,
   nhưng sinh nhật vẫn xảy ra); tên phòng ban chỉ xem được ở panel chi tiết. Mascot này không phải mascot người dùng
   đã chọn cho island.
5. Mô hình lane cho tối đa 4 phòng ban hiển thị đầy đủ mỗi bàn; phòng ban thứ 5 và worker ngoài 12 chỉ còn trong `+N`.
   Cảnh báo stuck vẫn hiện ở bàn nhờ `alert`, nhưng không chỉ ra worker nào.
6. Trần bàn "đến trước được trước": một project ồn có thể chiếm hết 48 bàn và đẩy project khác vào `+N bàn`; sàn chỉ
   có bàn không vẽ không xuất hiện. Slot không có thời gian ân hạn nên session chớp tắt một chu kỳ có thể mất ô.
7. Dựng lại toàn sàn chạy trên main thread của Tk và chặn cả giao diện (island, panel và Control room dùng chung một
   vòng lặp sự kiện) trong thời gian dựng; ước lượng tới khoảng 2.900 item ở sàn đầy (chưa đo). Chỉ khi cấu trúc đổi
   (worker hay session đến hoặc đi, đổi tên, đổi sàn) mới dựng lại, nên dự đoán vài lần mỗi phút ở dự án bận; đổi
   state không còn gây dựng lại. Nếu T3 đo vượt mục tiêu thì bước kế tiếp là cập nhật tăng dần theo nút (chưa có trong
   spec này) hoặc hạ trần, bằng một rev spec.
8. Lỗi đã có ở Control room, không thuộc spec Board: `org.build` xuất subagent với khoá `type` nhưng
   `control_room._session_rows` đọc `agent_type` (`control_room.py:299`, `:311`), nên dòng "Loại agent" trong chi tiết của cây
   luôn rỗng. Nhóm phòng ban của cây KHÔNG bị ảnh hưởng: `org.department` trả `name or agent_type` nên `department` không
   rỗng khi `type` có. Fixture của cây đã dựng bằng `org.build` (`tests/test_control_room.py:55`) nhưng không kiểm dòng
   "Loại agent" nên không bắt được lỗi. Task S0 của plan sửa lỗi này TRƯỚC mọi task Board (kèm test dùng đầu ra thật của `org.build`).
   Board đọc `type`. Fixture test Board dựng bằng `org.build(sessions_thô, cfg, now)` (worker thô theo dạng đầu vào
   có `agent_type`), không dựng worker tay theo dạng đầu ra, và test kiểm dòng "Loại agent" có giá trị, để loại đúng lớp
   lỗi lệch dạng này.
9. Chi tiết của Board và của cây là hai chỗ định dạng giống nhau. Plan phải tách hàm dựng `detail` dùng chung; hàm
   đó lấy `type`, không sao chép đoạn `agent_type`, và chỉ làm sau S0.
10. Chữ ký `office_layout` có thêm `prev`, và Layout không lưu qua lần khởi động lại: tab Board và viewer 3D gọi hàm
    độc lập với `prev` riêng nên có thể xếp bàn khác nhau cho cùng dữ liệu (chỉ giống nhau khi cùng lịch sử `prev`).
    Người dùng nhìn hai nơi cùng lúc sẽ thấy bàn ở chỗ khác nhau; chấp nhận, không đồng bộ `prev` giữa hai nơi.
11. Subagent lồng nhau chưa có mẫu thật (rủi ro 2 của spec Control room): Board phẳng theo phòng ban nên không bị ảnh
    hưởng, nhưng không hiện được quan hệ cha con.
12. Màu `desk.done` và `worker.running` trùng nhau (xem "Bảng state"); chỉ phân biệt bằng hình dạng, vị trí và mood.

## Quyết định mới (cần duyệt)

1. Chữ ký `office_layout(org_out, cfg, prev=None)`: thêm `prev` để có bộ nhớ gán ô trong khi hàm vẫn thuần.
2. Mascot gán theo hash của `session_id` (bàn) và của phòng ban (subagent), hue toàn cục; bỏ qua mascot người dùng chọn.
   Phương án thay thế đã nêu ở mục "Mascot cho bàn và subagent".
3. Bấm đơn chọn, bấm đúp hoặc Enter mới focus session (giống tab `Cây`), thay vì focus ngay khi bấm.
4. Hai khoá cấu hình `board_max_desks` (48) và `board_max_workers` (12).
5. Mô hình hình học: pod 4x4, cụm 6 bàn, mỗi lần hiện một sàn với điều hướng `◀ ▶`, bốn lane x ba ô cho subagent, ba
   device mỗi bàn (hộp có đèn), quy tắc thay thế worker đã xong; tab mặc định `Cây` và không lưu tab đã chọn.
6. Không hoạt ảnh (Board tĩnh, không timer) và không hiện quan hệ cha con.
7. Bảng màu: bàn theo màu island/panel, worker theo màu thẻ của cây, nên "đang chạy" là xanh dương ở bàn và xanh lá ở
   worker.
8. Dạng `STATE_STYLE` chốt theo viewer 3D: `{"desk": {...}, "worker": {...}}`, mỗi `Style` đủ `color`, `mood`,
   `marker` (`None` khi không có dấu hiệu); `Layout["styles"]` là bản sao sâu; dấu hiệu cảnh báo bàn là hằng riêng
   `ALERT_STYLE`, không nằm trong bảng.
9. Cam kết cho consumer: `level` duy nhất và `<= limits.desks - 1`; `Floor.w` = 30; `Floor.h` là bội của 10 và
   `<= max_floor_h(limits.desks)` (hàm mới xuất từ `office.py`, 240 ở mặc định); Worker và Device không có `w`, `h`;
   `counts` chỉ chứa khoá có giá trị > 0; `office_layout` tái nhập, không cache, không trạng thái ẩn. Hệ quả L-S5 nêu rõ:
   Board và viewer có thể xếp bàn khác nhau cho cùng dữ liệu.
10. Palette cho Board: thêm khoá `"palette"` (dict `kit.P` đầy đủ) vào dict theme của ControlRoom, `_DEFAULT_THEME` mặc
    định `theme.DARK`; sửa `ui/app.py` và `control_room.py`. Token thiếu rơi về `idle`.
11. Luật `valid_org` cho nơi gọi: `org` không hợp lệ thì giữ `prev` và hiện "chưa có dữ liệu" (không vẽ Layout cũ);
    hàm `office.valid_org` và khoá i18n `cr.board.nodata`. Viewer 3D cần áp dụng cùng luật.
12. Tách `board_style_sig` khỏi `board_struct_sig`: đổi `state` cập nhật tại chỗ, khác với `struct_sig` của cây; một polygon
    cho mỗi sàn và mỗi cụm; ngân sách `MAX_SPRITES_PER_RENDER = 8` ảnh mascot mỗi lần render (còn lại là hình tròn chờ).
13. Chấp nhận `desk.done` và `worker.running` cùng màu thật, phân biệt bằng hình dạng, vị trí và mood.
14. Quy ước chiếm ô: device là tập con ô của khối desk 2x2; bất biến không giao nhau áp cho desk (gồm device) và worker.
15. Thanh cuộn ngang: thêm style `Cr.Horizontal.TScrollbar`.
