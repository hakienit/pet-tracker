# Plan: Control room

Spec: `docs/specs/2026-10-22-control-room-design.md` (rev 2, đã duyệt). Plan này không nhắc lại spec; mọi
quyết định thiết kế lấy từ spec.

Rủi ro: plan R1; công việc R2 (đổi ingest của `claude_data.py`, module mới, nối UI). Không có bước R3
(không phát hành, không push). Commit chỉ khi người dùng yêu cầu.

## Ngoài phạm vi

Như mục "Ngoài phạm vi" của spec. Thêm: không sửa `procenv.clean_env` (dùng chung với updater và deep link);
không thêm dependency; không phát hành bản mới (CHANGELOG chỉ ghi `[Unreleased]`).

## Quy ước chung

- TDD: mỗi slice viết test trước, chạy thấy đỏ, rồi sửa code tới khi xanh.
- Lệnh test toàn bộ: `python -m unittest discover -s tests` (stdlib, không framework).
- Không tạo `tests/__init__.py`: `python -m unittest discover -s tests` chạy từ gốc repo đã import được
  `pet_tracker`. Nhờ vậy các slice song song không ghi chung file nào.
- Test không đọc `~/.claude` thật, không cần Tk display: dữ liệu mẫu dựng trong `tempfile.TemporaryDirectory()`.
- Mỗi slice là một commit riêng, rollback bằng `git revert <commit>`; slice sau không sửa file của slice trước
  trừ khi bảng sở hữu ghi rõ.

Tier kiểm chứng: **T1** unit test; **T2** T1 + đo trên dữ liệu thật `~/.claude`; **T3** T1 + kiểm tay UI
trên macOS.

## Slice

| # | Kết quả | Owner | File sở hữu | Phụ thuộc | Tier | Review |
|---|---|---|---|---|---|---|
| S0 | số baseline `poll_all` + `active_sessions` | Engineering | không file nào (số ghi vào báo cáo và PR) | không | T2 | không |
| S1 | `_git` không chạy mã từ config repo | Engineering | `pet_tracker/session_ops.py`, `tests/test_session_ops.py` | không | T1 | Review, Security |
| S2 | ingest worker trong `Transcript` và meta | Engineering | `pet_tracker/claude_data.py`, `tests/test_claude_data.py`, `tests/fixtures/` | S0 | T2 | Review, Security |
| S3 | `org.py` hàm thuần | Engineering | `pet_tracker/org.py`, `tests/test_org.py` | không (chỉ hợp đồng dữ liệu của spec) | T1 | Review |
| S4 | config + `Collector` đưa `org` vào snapshot | Engineering | `pet_tracker/config.py`, `pet_tracker/ui.py` (chỉ class `Collector`), `tests/test_collector.py` | S2, S3 | T1 | Review |
| S5 | huy hiệu worker trên card | Frontend | `pet_tracker/ui.py` (`_card_key`, `_update_card`, dòng subagent), `tests/test_ui_badge.py` | S4 | T3 | Review |
| S6 | cửa sổ `control_room.py` | Frontend | `pet_tracker/control_room.py`, `tests/test_control_room.py` | S3 (hình dạng cây) | T1 + T3 | Review, Security |
| S7 | nối Control room vào ui | Frontend | `pet_tracker/ui.py` (popup menu, `_pump`) | S5, S6 | T3 | Review |
| S8 | tài liệu | Engineering | `docs/GUIDE.md`, `CHANGELOG.md`, `config.example.json` | S7 | T1 (test vẫn xanh) | Review |

Song song được: S1 ‖ S2 ‖ S3; S1 ‖ mọi slice khác; S6 ‖ S4 ‖ S5 (S6 chỉ chạm file mới).
Tuần tự bắt buộc: S4 → S5 → S7 vì cùng ghi `ui.py`. S0 xong trước khi S2 sửa code.

## Chi tiết từng slice

### S0 Baseline

Chạy trên `main` chưa sửa, cache nóng (chạy một lần bỏ qua, rồi 5 lần lấy trung vị):

```
python -c "import os,time,statistics as st;from pet_tracker.claude_data import ClaudeDataStore as S
r=[]
for _ in range(6):
    s=S(os.path.expanduser('~/.claude'));t=time.perf_counter();s.poll_all();s.active_sessions({'default':1000000});r.append(time.perf_counter()-t)
print('median',st.median(r[1:]))"
```

Đo thêm chi phí tăng dần (quyết định của người dùng, 2026-10-23): một `ClaudeDataStore` duy nhất, gọi
`poll_all()` một lần cho nóng, rồi 5 lần `poll_all()` + `active_sessions(...)` liên tiếp, lấy trung vị. Đây là chi
phí thật mỗi `refresh_sessions_sec`.

Ghi: hai trung vị (parse nguội và tăng dần), số file transcript, tổng dung lượng, commit hash.

Kết quả S0 (2026-10-23, commit `2c398b4`, 250 jsonl, 603 MiB, Python 3.12.11, máy tải trung bình ~4,5 nên
không yên tĩnh): parse nguội 0,72 đến 0,79 s (hai lượt, chênh ~9%); tăng dần ~0,3 ms (chỉ là quét `stat`,
file không đổi thì `poll` thoát sớm ở `claude_data.py:79`).

Ngưỡng của S2 (chỉnh theo kết quả S0, vì 10% của 0,3 ms nằm dưới nhiễu đồng hồ và nhiễu giữa hai lượt nguội
đã ~9%):
- Nguội: so A/B trong cùng một phiên, xen kẽ code cũ (`git show HEAD:pet_tracker/claude_data.py` nạp vào
  module riêng) và code mới, mỗi bên ≥ 5 lần, trung vị mới ≤ 1,10 × trung vị cũ. Không so với số tuyệt đối
  hôm nay.
- Tăng dần: ngưỡng tuyệt đối, trung vị của 200 lần `poll_all()` + `active_sessions()` ≤ 5 ms. Thêm một phép đo
  tail-parse: nối 1000 dòng giả (có `Agent`, `backgroundTaskId`, `<task-notification>`) vào bản sao của một
  transcript trong thư mục tạm rồi đo `poll()`; không so tỉ lệ, chỉ ghi số.

### S1 Hardening `_git`

- Test trước (`tests/test_session_ops.py`):
  - repo tạm có `core.fsmonitor` trỏ tới script tạo file đánh dấu; `git_state(repo)` không tạo file đó.
  - repo tạm có `core.hooksPath` trỏ tới thư mục hook tạo file đánh dấu; không file nào được tạo.
  - đặt `GIT_DIR`, `GIT_WORK_TREE`, `GIT_CONFIG_PARAMETERS` trong `os.environ`: `_git` vẫn đọc đúng repo tạm.
  - `git_state` vẫn trả `top`, `common`, `branch`, `dirty` đúng cho repo sạch và repo có file mới.
- Sửa: trong `_git` thêm `-c core.fsmonitor=false -c core.hooksPath=` trước subcommand; thêm
  `--no-optional-locks` cho `status`; env = `clean_env()` bỏ mọi khoá bắt đầu bằng `GIT_` (lọc tại `_git`,
  không sửa `procenv`). Áp cho mọi caller của `_git`, kể cả xoá worktree (một chỗ sửa cho tất cả).
- Kiểm: `python -m unittest tests.test_session_ops -v`; `git_state` vẫn chạy trên repo này:
  `python -c "from pet_tracker.session_ops import git_state;print(git_state('.'))"`.

### Hợp đồng dữ liệu S2 → S3 (Lead chốt 2026-10-23, để S2 và S3 chạy song song)

`active_sessions()` (S2) thêm hai khoá vào mỗi session; `org.build(sessions, cfg, now)` (S3) chỉ đọc hai khoá
này cùng các khoá cũ (`session_id`, `started_at`, `cwd`, `git`, `name`, `status`...). Mọi giá trị là kiểu
JSON thuần; chuỗi đã cắt 200 ký tự; thời gian là epoch giây (float).

- `session["agent_calls"]`: `list[str]`, id `tool_use` `Agent`/`Task` mà transcript chính của session đã phát ra.
- `session["workers"]`: `list[dict]`, mỗi phần tử một trong hai dạng:
  - subagent: `{"kind": "subagent", "id": str (stem của agent-*.jsonl), "tool_use_id": str|None (meta.toolUseId),
    "agent_type": str, "description": str, "depth": int (meta.spawnDepth, đã ép int, kẹp 0..8),
    "finished": bool (meta.finished), "notif_status": str|None (status của task-notification có
    tool-use-id == tool_use_id, tìm trong mọi transcript của session; None nếu chưa có),
    "mtime": float (mtime jsonl), "started": float|None, "last_activity": float|None,
    "tokens": int (output + input + cache của file đó), "open_tools": int (tool_use chưa có tool_result),
    "agent_calls": list[str] (id Agent/Task tool_use do chính subagent này phát ra)}`
  - bgtask: `{"kind": "bgtask", "id": str (task id), "tool_use_id": str|None, "started": float|None,
    "status": str|None}` (`status` None = chưa có notification; Monitor không có status bị bỏ ngay từ S2).
- Parent của subagent (S3 tính, không phải S2): worker hoặc session có `agent_calls` chứa `tool_use_id` của nó;
  không thấy thì parent là session.
- S2 và S3 không đổi hợp đồng này một mình: cần đổi thì báo Lead.

Hợp đồng đầu ra của S3 (S4 và S6 dựa vào; Lead chốt 2026-10-23 theo báo cáo S3):
- `org.build(sessions, cfg, now)` trả `{"projects": [Project...], "counts": {...}}`; `counts` gốc dùng cho thanh tổng.
- `counts` = `{"subagent": {...}, "bgtask": {...}}`, mỗi loại có `total, running, stuck, done, failed, killed,
  ended` (`ended` = mọi worker không còn sống, chồng lên `done/failed/killed` có chủ ý).
- Session trong cây giữ mọi khoá cũ, bỏ `agent_calls`, thêm `workers` phẳng theo thứ tự đầu vào; `parent` của
  subagent là id worker cha hoặc `None` (cha là session); bgtask không có `parent`.
- `notif_status` rỗng (`""`) coi như chưa có notification (theo spec "status khác rỗng").

### S2 Ingest

- Fixture (`tests/fixtures/`, JSONL tối thiểu viết tay theo định dạng thật, không chép dữ liệu thật):
  transcript chính có `Agent` tool_use chạy nền, `queue-operation` notification `completed`/`failed`/`killed`,
  notification Monitor không có `<status>`, `backgroundTaskId`; subagent jsonl có tool_use chưa có
  tool_result; `agent-x.meta.json` có và không có `finished`.
- Test trước (`tests/test_claude_data.py`), mỗi mục một test:
  - `agent_calls`, `notifs`, `bg_tasks`, `open_tools` đúng theo fixture; Monitor bị bỏ.
  - dòng assistant vừa có `usage` vừa có `Agent` tool_use: cả `msgs` và `agent_calls` đều có; dòng
    `<synthetic>` vẫn ghi `agent_calls`.
  - nhận cả tên `Task`.
  - ghi lại file ngắn hơn offset: mọi trường mới bị xoá cùng `msgs`.
  - dòng chờ > 1 MB bị bỏ, không làm hỏng dòng sau; chuỗi lưu bị cắt 200 ký tự; trần 500 của `bg_tasks`.
  - meta đọc lại khi mtime đổi; ngừng đọc khi `finished` hoặc đã có notification; meta > 64 KB bị bỏ;
    meta JSON hỏng bị bỏ; đường dẫn meta chỉ dựng từ đường dẫn jsonl (test với `agentId` chứa `../`).
  - `active_sessions` giữ mọi khoá cũ (so tập khoá), có thêm `workers`; session có subagent lồng nhau giả
    (`spawnDepth` 2, notification nằm trong transcript subagent cha) vẫn ra đủ notification.
- Kiểm: `python -m unittest tests.test_claude_data -v`; đo hiệu năng theo "Ngưỡng của S2" ở mục S0.

### S3 Org model

- Test trước (`tests/test_org.py`): đúng danh sách test org của spec (mục Kiểm thử). Thêm:
  `cfg["agent_prefixes"]` không phải list và `stuck_after_sec` không phải số thì dùng mặc định;
  `json.dumps(org.build(...))` không lỗi; worker thiếu trường không làm hỏng cây.
- Đường dẫn Windows (`C:\repo\.git`, worktree `C:\wt\a`) cho project/team: test bằng `ntpath` để chạy được
  trên macOS. Đây là phủ duy nhất cho rủi ro Windows ở mức logic.
- `org.py` không import `tkinter`, `os` hay `subprocess`; test kiểm bằng `ast` trên mã nguồn.
- Kiểm: `python -m unittest tests.test_org -v`.

### S4 Config + Collector

- Test trước (`tests/test_collector.py`): `DEFAULTS` có `agent_prefixes == ["les-"]`, `stuck_after_sec == 120`;
  một vòng `Collector.run` với store giả và `session_ops.git_state` giả cho snapshot có khoá `org`; `org.build`
  ném lỗi thì snapshot vẫn có `sessions` và `org` là `None` (lỗi chỉ vào log).
- Sửa: hai khoá trong `DEFAULTS`; `Collector.run` gọi `org.build` sau vòng gắn `git`, có `try` riêng.
- Kiểm: `python -m unittest tests.test_collector -v`; `python -m unittest discover -s tests`.

### S5 Huy hiệu card

- Test trước (`tests/test_ui_badge.py`): hàm thuần `worker_badge(workers) -> (text, warn)` trong `ui.py`;
  `3 agents · 1 task`, số ít/không có worker, có `stuck` thì `warn=True`.
- Sửa: dòng subagent dùng `worker_badge`; `_card_key` đưa số worker theo state vào `live`; `_update_card`
  cập nhật nhãn và màu.
- Kiểm T3 (macOS, `python main.py`): mở panel, chạy một subagent nền trong một session; huy hiệu đổi
  running → done mà không mở lại panel.

### S6 Cửa sổ Control room

- Test trước (`tests/test_control_room.py`, không tạo `Tk`): `sanitize()` bỏ ký tự điều khiển, `\n`, `\r`,
  ký tự bidi (U+202E), cắt độ dài, giữ Unicode thường; `struct_sig`/`live_sig` tách đúng (đổi token chỉ đổi
  `live`, đổi state đổi `struct`); duyệt cây sinh iid từ bộ đếm, không bao giờ dùng chuỗi agent làm iid.
- Sửa: `render(snap)` và hàm tạo cửa sổ; lưu vị trí/kích thước qua cơ chế `state.json` sẵn có; bấm session
  dùng lại logic focus có sẵn (import từ `ui`/`session_ops`, không sao chép).
- Kiểm: `python -m unittest tests.test_control_room -v`; T3 sau S7.

### S7 Nối UI

- Mục "Control room" trong popup chuột phải của island; `_pump` gọi `control_room.render(snap)` khi cửa sổ mở.
- Kiểm T3 (macOS): mở Control room từ popup; panel ẩn mà cửa sổ vẫn cập nhật; panel đóng khi mất focus không
  kéo Control room đóng theo; đóng rồi mở lại giữ vị trí; nhãn running/stuck/done khớp thực tế với một subagent
  và một `run_in_background`.
- Không có unit test mới (chỉ nối dây); phủ bằng T3 và test của S4–S6.

### S8 Tài liệu

- `docs/GUIDE.md`: mục Control room (mở thế nào, ý nghĩa state, hai khoá config).
- `CHANGELOG.md` `[Unreleased]`: tính năng, bản vá `_git` (S1), ghi "chưa kiểm trên Windows".
- `config.example.json`: hai khoá mới. Kiểm: `python -c "import json;json.load(open('config.example.json'))"`.

## Rủi ro mang từ spec

| Rủi ro | Phủ |
|---|---|
| Windows chưa kiểm | S3 test đường dẫn bằng `ntpath`; S1 test dùng `git` thật nên chạy được trên Windows sau này; CHANGELOG ghi rõ (S8). Không có kiểm runtime: `unavailable`, không tính là pass. |
| Subagent lồng nhau chưa có mẫu | S2 fixture `spawnDepth` 2 với notification ở transcript subagent cha; S3 test cây lồng, vòng A→B→A, độ sâu quá 8. Mẫu giả, không chứng minh định dạng thật. |
| Định dạng notification/tên tool đổi | fixture S2 giữ mẫu hiện tại; test đỏ khi parser đổi hành vi. |
| Công cụ treo không hiện `stuck` | chấp nhận như spec; S3 có test khẳng định hành vi này để thay đổi sau là cố ý. |
| Chi phí ingest | S0 baseline, S2 đo lại, ngưỡng 10%. |
| Chuỗi agent không tin cậy | S2 (đường dẫn meta), S6 (sanitize, iid); Security review cả hai. |

## Điều kiện xong

- `python -m unittest discover -s tests` xanh trên trạng thái cuối.
- Số S0 và số đo S2 có trong báo cáo, trong ngưỡng.
- T3 của S5 và S7 đã chạy trên macOS; Windows ghi `unavailable`.
- Review đã duyệt mọi slice; Security đã duyệt S1, S2, S6; không còn finding mở.
