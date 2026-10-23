# Control room: giám sát cả "công ty IT" của các agent

Trạng thái: rev 2, người dùng đã duyệt (2026-10-22). Rev 2 tích hợp báo cáo của Scout, Review và Security.
Bản vá `core.fsmonitor` của `git_state` được gộp vào plan của tính năng này (task riêng, commit riêng).
Phạm vi: sub-project 1 (org model) và sub-project 2 (Control room). Board 2.5D (sub-project 3) và viewer 3D
(sub-project 4) có spec riêng, chỉ dùng lại org model ở đây.

## Mục tiêu

Wisp hiện biết session nào đang chạy và đếm số file `subagents/*.jsonl`, nhưng không biết subagent nào đang
chạy hay đã xong, không biết session có bao nhiêu background task, và không gom được nhiều session thành
một dự án. Người dùng điều hành agent như một công ty IT (mỗi phòng ban là một loại subagent) cần một chỗ
nhìn được toàn cảnh:

- bao nhiêu dự án, mỗi dự án có những team (worktree) nào đang làm gì;
- mỗi session có bao nhiêu subagent, thuộc phòng ban nào, đang chạy, đã xong hay có vẻ kẹt;
- mỗi session có bao nhiêu background task đang chạy.

## Ngoài phạm vi

Điều khiển hoặc kill subagent, lịch sử của session đã đóng, thông báo khi kẹt, board 2.5D, viewer 3D, cấu hình
prefix theo từng repo, thanh tab (thêm ở sub-project 3).

Ghi nhận riêng: `git status` trong `session_ops.git_state` chạy `core.fsmonitor` lấy từ `.git/config` của repo
(Security đã tái hiện). Đây là lỗi của code đã phát hành, không thuộc spec này; xử lý bằng bản vá riêng khi
người dùng quyết định.

## Khái niệm

| Khái niệm | Nghĩa | Nguồn |
|---|---|---|
| Project | một repo git | thư mục cha của `git["common"]` (nếu tên là `.git`), ngược lại chính `git["common"]` |
| Team | một worktree của repo | `git["top"]` |
| Session | một process Claude Code đang chạy | `~/.claude/sessions/<pid>.json` (đã có) |
| Subagent | agent con do session hoặc subagent khác gọi | `projects/<proj>/<sid>/subagents/agent-*.jsonl` + `.meta.json` |
| Department | chức danh của subagent | `agentType` bỏ namespace và prefix |
| BgTask | lệnh Bash `run_in_background` | transcript chính |

Một repo là một dự án, mỗi worktree là một team nhỏ. Session không có `git` (không trong repo) thì project và
team đều lấy từ `cwd`. `cwd` có thể là thư mục con, nên team không bao giờ lấy từ `cwd` khi đã có `git["top"]`.
`session_ops.git_state` đã trả `common`, `top`, `branch` (`session_ops.py:50-53`, `:81-82`) và `Collector` đã
cache 30 giây (`ui.py:222-227`): không thêm lệnh git nào.

## Dữ kiện đã kiểm trên đĩa (macOS, Claude Code 2.1.301, 418 file, 607 MiB)

- `agent-*.meta.json`: `agentType`, `description`, `toolUseId`, `spawnDepth`, `requestShape`; chỉ một phần file
  có `finished: true` (20/43 ở lần quét cuối; con số đổi theo thời gian vì dữ liệu sống).
- Lệnh gọi subagent là `tool_use` tên `Agent` trong transcript chính (44 id; tên `Task` không xuất hiện).
  43/43 `meta.toolUseId` khớp một `Agent` tool_use trong transcript chính cùng session. Một lệnh gọi không có
  meta (bị từ chối quyền): bỏ qua.
- `tool_result` của lệnh `Agent` chạy nền là kết quả "đã khởi chạy", có ngay lập tức: **không dùng làm tín hiệu
  xong**.
- Tín hiệu xong: record `queue-operation` có `<task-notification>` chứa `<tool-use-id>` đúng bằng
  `meta.toolUseId`, kèm `<status>`. 43/43 subagent có notification: 39 `completed`, 4 `failed`. Gồm cả 22
  subagent không có `finished`.
- Background Bash: bắt đầu là record `user` có `toolUseResult.backgroundTaskId`; kết thúc là cùng loại
  notification với `<task-id>` khớp. Toàn bộ `status` quan sát được: `completed` 172, `failed` 45, `killed` 5.
  Notification của Monitor không có `<status>`: bỏ qua, không phải BgTask.
- `spawnDepth` đều bằng 1 trong dữ liệu thật: subagent lồng nhau chưa có mẫu thật, chỉ test bằng dữ liệu giả.
- Cùng một `toolUseId` có thể xuất hiện trong transcript của session tổ tiên (sabrefish). Parent phải tìm theo
  thư mục của chính session (`<sid>.jsonl` đứng cạnh `<sid>/subagents/`), không phải "transcript đầu tiên
  chứa id".
- Hook `SubagentStop` ở đuôi file là cấu hình của người dùng, không phải của Claude Code: không dựa vào nó.
- Chi phí: một lượt quét có lọc byte marker trên toàn bộ 607 MiB mất 1,9 giây (cache nóng).

Chưa kiểm: mọi thứ trên Windows; thời gian cache lạnh; giá trị `status` ngoài ba giá trị trên.

## Org model (`pet_tracker/org.py`)

Hàm thuần, không import tkinter, không đọc đĩa. `org.build(sessions, cfg, now)` nhận danh sách session đã có
`git` và `workers` (do `claude_data` thu thập), trả cây dict/list thuần JSON hoá được (viewer 3D sau này dùng
lại). `now` là tham số để test được.

```
Project{name, root, teams[], counts}
  Team{top, branch, sessions[], counts}
    Session{...khoá hiện có..., workers[]}
      Worker = Subagent | BgTask
```

`Subagent`: `id, kind="subagent", type, department, description, depth, parent, state, started, last_activity,
tokens`.
`BgTask`: `id, kind="bgtask", tool_use_id, state, started`.
`counts`: số worker theo `state` ở mỗi cấp, để thanh tổng và huy hiệu không phải duyệt lại cây.

### Department

`department(agent_type, prefixes)`: lấy phần sau dấu `:` cuối cùng (`rsplit(":", 1)[-1]`), rồi bỏ một prefix đầu
tiên khớp trong `prefixes`. `les-engineering` thành `engineering`, `hba:qa-engineer` thành `qa-engineer`,
`code-quality-reviewer` giữ nguyên. Kết quả rỗng thì dùng lại `agent_type`.

### State

Subagent:

- `done`: `meta.finished` là true, hoặc có notification cho `meta.toolUseId` với `status` khác rỗng.
  `status` `failed` hoặc `killed` cũng là kết thúc: `state` là `failed`/`killed` tương ứng, tính vào nhóm
  "ended" của `counts`.
- `running`: chưa kết thúc và một trong ba điều kiện: jsonl được ghi trong `stuck_after_sec` giây gần nhất; còn
  một subagent con đang `running`; hoặc còn `tool_use` chưa có `tool_result` (một công cụ đang chạy).
- `stuck`: chưa kết thúc, jsonl im quá `stuck_after_sec` giây, không có con đang chạy, không có tool đang chờ.

Giới hạn đã biết: công cụ treo vĩnh viễn không bao giờ hiện `stuck` (nó luôn có tool đang chờ). Chấp nhận;
nâng cấp bằng ngưỡng thứ hai dài hơn cho trường hợp có tool đang chờ nếu cần.

BgTask: `running` từ khi có `backgroundTaskId` cho tới khi có notification cùng `task-id`; sau đó theo `status`
(`done`, `failed`, `killed`). Task bắt đầu trước `started_at` của session (transcript được replay khi session
được resume, notification của lần chạy trước không còn) tính `ended`. Session đã thoát thì cả cây của nó biến
mất cùng session (Wisp chỉ hiện session còn sống).

### Cha và con

Mỗi `Transcript` ghi lại id các `tool_use` `Agent`/`Task` nó phát ra (nhận cả hai tên). Subagent trỏ về parent
bằng `meta.toolUseId`; chỉ tìm trong các transcript của cùng session (transcript chính và các subagent của nó).
Không thấy thì parent là session. Dùng tập `visited` và giới hạn độ sâu 8: gặp vòng lặp hoặc quá sâu thì quay
về parent là session. `spawnDepth` đi qua `int()` có bảo vệ và bị kẹp trong [0, 8].

## Thu thập (`claude_data.py`)

`Transcript` thêm các trường và cách ingest:

- `agent_calls`, `notifs` (`tool_use_id → status`), `bg_tasks` (`task_id → {tool_use_id, started, status}`),
  và, chỉ cho file subagent, tập `open_tools` = id `tool_use` trừ id `tool_result`, lấy bằng regex trên byte
  (không `json.loads` các dòng `user` lớn).
- Marker `"name":"Agent"`, `"name":"Task"`, `backgroundTaskId`, `<task-notification>` được kiểm **trước** nhánh
  `"type":"assistant"` của `_ingest` và nằm ngoài guard `usage`/`<synthetic>`. Dedupe theo `message.id` của
  `msgs` giữ nguyên.
- Khi file bị ghi lại từ đầu (`poll`, `st_size < offset`) các trường mới cũng được xoá cùng `msgs`.
- Mỗi lần `poll` đọc tối đa vài MB; dòng đang chờ dài hơn 1 MB bị bỏ; chuỗi lưu lại bị cắt ở 200 ký tự;
  `bg_tasks` và số worker mỗi session có trần (ví dụ 500).

`ClaudeDataStore.subagents_for` đọc `agent-*.meta.json` bằng đường dẫn dựng từ chính đường dẫn jsonl
(`jsonl[:-6] + ".meta.json"`); không bao giờ ghép `agentId`, `toolUseId` hay task id vào đường dẫn. Meta lớn
hơn 64 KB bị bỏ qua. Meta được đọc lại khi mtime đổi và ngừng đọc khi đã `finished` hoặc đã có notification,
vì `finished` chỉ được ghi lúc subagent kết thúc.

`active_sessions` giữ nguyên khoá cũ, kể cả `subagents` (số lượng), và thêm khoá `workers`: danh sách thô cho
`org.build`. Panel hiện tại không vỡ.

## Collector

`Collector.run` gọi `org.build(sessions, cfg, now)` sau khi gắn `git`, đặt kết quả vào khoá `org` của
snapshot. Không thêm thread, không thêm vòng poll, không thêm lệnh git; `_pump` đã đưa snapshot sang main
thread mỗi `refresh_sessions_sec`.

## Panel hiện tại (`ui.py`)

- Dòng `N subagent` (khoảng `ui.py:1268`) thành `3 agents · 1 task`; phần có worker `stuck` đổi màu cảnh báo.
- `live` trong `_card_key` (khoảng `ui.py:978`) thêm số worker theo state, và `_update_card` cập nhật nhãn và
  màu; nếu không, `_patch_sessions` bỏ qua thay đổi.
- Lối vào duy nhất: mục "Control room" trong popup chuột phải của island. Không thêm nút trên header.
- `_pump` (khoảng `ui.py:1958-1978`) gọi `control_room.render(snap)` khi cửa sổ đang mở, kể cả lúc panel ẩn.
- Chưa truy vết: panel đóng khi mất focus (`ui.py:663`); cần kiểm panel không tự đóng gây khó chịu khi chuyển
  sang Control room, và Control room không bị kéo theo.

## Control room (`pet_tracker/control_room.py`)

`Toplevel` riêng, đổi kích thước được, vị trí và kích thước lưu trong `state.json`. Chỉ tạo khi mở lần đầu.

- Thanh tổng: số dự án, team, subagent đang chạy, task nền đang chạy, số `stuck`.
- Trái: cây Project → Team (tên worktree + branch) → Session → nhóm Department → Worker. Phải: chi tiết node
  đang chọn (description, loại agent, thời gian chạy, token, state).
- Bấm session thì focus cửa sổ của nó bằng logic có sẵn. Subagent và task nền chỉ xem.
- Chữ ký tách hai phần theo mẫu `_card_key`: `struct` (cây, tên, state) và `live` (`last_activity`, token,
  thời gian chạy). Đổi `struct` mới dựng lại cây; đổi `live` chỉ cập nhật nhãn tại chỗ.
- `ttk.Treeview` dùng iid sinh tự động (bộ đếm, ánh xạ về node bằng dict) và tag cố định theo state. Mọi
  chuỗi từ agent (`description`, `agentType`) đi qua một hàm làm sạch: bỏ ký tự điều khiển và xuống dòng, cắt
  độ dài, hiển thị dạng văn bản thuần.
- Mọi thao tác UI chạy ở main thread; không gọi git hoặc đọc đĩa từ đây.

## Cấu hình (`config.py`, `config.example.json`)

| Khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `agent_prefixes` | `["les-"]` | prefix bị bỏ khỏi `agentType` khi tạo tên phòng ban |
| `stuck_after_sec` | `120` | jsonl im lặng quá ngần này giây (và không có việc đang chạy) thì subagent chưa xong là `stuck` |

Sau này có thể thêm prefix vào danh sách hoặc thay prefix bằng tên repo; chưa làm bây giờ.

## Lỗi và an toàn

- File meta hoặc transcript hỏng, thiếu, đang ghi dở: bỏ qua node đó, không làm hỏng cây.
- Chỉ đọc dữ liệu local trong `~/.claude`; không thêm kết nối mạng, không ghi vào `~/.claude`, không sửa
  `settings.json`. Vị trí cửa sổ ghi vào `state.json` như hiện nay.
- Mọi chuỗi từ transcript/meta là dữ liệu không tin cậy (agent có thể bị prompt injection): không đi vào đối số
  subprocess, không ghép vào đường dẫn, không vào lệnh Tk. Chuỗi do agent ghi chỉ vào log qua `repr()` cắt ngắn.
- Không còn lệnh git mới, nên không thêm bề mặt thực thi mã từ cấu hình repo.

## Kiểm thử

- `tests/test_org.py` (`unittest`, stdlib): `department()` với namespace (kể cả nhiều dấu `:`), prefix, tên
  không có prefix; state subagent theo `finished`, theo notification (`completed`/`failed`/`killed`), theo
  ngưỡng im lặng, theo con đang chạy và tool đang chờ; BgTask theo start/notification, status lạ, task của
  session được resume; cây lồng nhau, vòng lặp A→B→A, độ sâu quá trần; nhóm theo repo gốc và team theo
  `git["top"]`; session ngoài git.
- `tests/test_claude_data.py`: transcript và meta mẫu cho `agent_calls`, `notifs`, `bg_tasks`, `open_tools`;
  dòng assistant vừa có usage vừa có `Agent` tool_use; reset khi file bị ghi lại; meta đọc lại khi mtime đổi;
  meta quá lớn bị bỏ qua; dòng quá dài bị bỏ.
- Hiệu năng: `poll_all` trên thư mục `~/.claude` thật không chậm hơn quá 10% so với đo trước khi sửa (đo
  baseline trước, ghi số vào PR).
- Lớp UI kiểm tay trên macOS. Windows chưa có máy kiểm: ghi rõ trong CHANGELOG khi phát hành.
- Lệnh chạy: `python -m unittest discover -s tests`.

## Rủi ro mở

1. Hành vi trên Windows (đường dẫn, worktree) chưa kiểm.
2. Subagent lồng nhau (`spawnDepth` ≥ 2) chưa có mẫu thật; nơi notification của subagent lồng nhau được ghi
   (transcript của parent con hay của session) chưa xác minh. Thu notification từ mọi transcript của session.
3. Bản Claude Code khác có thể đổi định dạng notification hoặc tên tool; test giữ mẫu hiện tại để phát hiện.
4. Công cụ treo không hiện `stuck` (xem State).
