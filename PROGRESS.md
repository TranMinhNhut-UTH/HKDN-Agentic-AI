# Tiến độ AI News Intelligence System

## Phase 1 — hoàn thành
- Tạo Git, `.venv`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `.env.example`.
- `shared/config.py`, `models.py`, `rss.py`: timeout, allowlist, giới hạn 2MB, chuẩn hóa, lọc/chống trùng.
- `samples/articles.json`: dữ liệu mô phỏng gắn nhãn DEMO, chỉ dùng mock.
- Kiểm thử thực tế: `python -m pytest tests/test_foundation.py -q`: **3 passed**.
- Sandbox chặn ensurepip và pytest cache; cài môi trường bằng quyền được duyệt. Cảnh báo cache không ảnh hưởng test. Chưa kiểm chứng Gemini/RSS live.

## Phase 2 — hoàn thành
- `shared/llm.py`: Gemini SDK, manual function calling + function response, structured JSON, budget; provider mock tách biệt.
- `shared/agents.py`: Collector/Analyst/coordinator, kiểm tra ID/trích dẫn, feedback và giới hạn; JSON/Markdown.
- `NV13-Multi-Agent/main.py`: CLI độc lập.
- Thực tế: **8 passed** (foundation + agents); CLI mock `AI --count 5` thành công, 5 findings, 3 nguồn mô phỏng, 5 lượt model mô phỏng.
- Báo cáo local trong `reports/NV13/`; không coi mock là minh chứng gọi Gemini. Chưa có kiểm thử API thật.

## Phase 3 — hoàn thành
- `shared/storage.py`, `automation.py`: SQLite atomic claim, lease, trạng thái thất bại/retry, lưu bài/báo cáo.
- `NV14-Automation/daily_job.py`, `register_task.ps1`: 5 tin/ngày; script đăng ký 08:00 theo giờ Windows, chưa thực thi đăng ký.
- Thực tế: **11 passed**; daily mock ngày 2026-10-11 trả `done`, chạy lại trả `skipped`.
- Cần quyền test được duyệt do sandbox Windows chặn thư mục tạm pytest. Không có lỗi nghiệp vụ còn tồn tại qua test hiện tại.

## Phase 4 — hoàn thành (kiểm thử tự động)
- `shared/service.py`, `web.py`: Planner lập kế hoạch/chọn tool, evaluate/revise tối đa 2 kế hoạch, background job, trace SQLite, tải báo cáo.
- `NV15-Agentic-AI/run.py`, `backend/app.py`, `frontend/`: giao diện responsive, nhập ngôn ngữ tự nhiên, mode badge, trace, bản tin, lịch sử, tải JSON/Markdown.
- Thực tế: **15 passed**. Uvicorn đã khởi động tại `http://127.0.0.1:8000`.
- TestClient xác minh web/API, không phải kiểm tra hiển thị trình duyệt. Công cụ browser báo `Browser is not available: iab`, inventory không có browser; visual QA chưa thực hiện.
- Có một cảnh báo deprecation từ Starlette TestClient dùng httpx; test vẫn pass.

## Phase 5 — hoàn thành
- README root và README riêng mỗi NV; từng nhiệm vụ có `docs/HUONG_DAN_TRIEN_KHAI.md` và `docs/MINH_CHUNG_CAN_CHUP.md` bằng tiếng Việt.
- Docs chung kiến trúc/REST/config/troubleshooting/minh chứng, `docs/KET_QUA_KIEM_THU.md` ghi kết quả thực tế và giới hạn.
- `requirements-lock.txt` khóa dependencies thực tế, `scripts/setup.ps1`, `.env` mock (được Git ignore).
- **21 passed, 1 warning** ở lần chạy cuối: foundation, agents, automation, web, contract Gemini SDK/RSS mock.
- HTTP smoke trên Uvicorn: completed, 5 findings, 7 lượt model mô phỏng, 9 bước trace. `pip check`: không xung đột.
- PowerShell 5.1 gặp lỗi parse tiếng Việt do encoding; sửa thông báo scripts thành ASCII, parser kiểm tra lại cả hai script syntax OK. Python compileall thành công.
- Git ignore đã xác minh `.env`, venv, database, logs. Chưa commit, chưa đăng ký Task Scheduler, không đổi cấu hình hệ thống.

## Phần cần kiểm chứng trên máy/tài khoản người dùng
- Gemini/RSS end-to-end live với key riêng; không dùng mock làm minh chứng live.
- Visual QA trên trình duyệt và chụp ảnh thật (browser automation không có browser khả dụng).
- Chạy Task Scheduler thật sau khi người dùng chủ động đăng ký bằng script.
- Warning Starlette TestClient/httpx vẫn còn; test pass. Đánh giá lại khi nâng dependencies.

Source và offline workflow đã hoàn thành. Khi tiếp tục, đọc file này và kiểm tra code hiện có; không xây lại từ đầu. Tham khảo README để chạy riêng từng NV.

## Mở rộng YouTube — hoàn thành ngày 11/10/2026
- Yêu cầu mới: dùng `YOUTUBE_API_KEY` trong `.env`, không lộ key, tối đa 100 bình luận thật, kiểm tra CSV/date/abbreviation/dedup; không commit/push.
- Tạo `shared/youtube.py`, `YouTube-Comments/main.py`, README riêng và `tests/test_youtube.py`; thêm biến trống vào `.env.example`, không sửa key `.env`.
- API thật xác nhận video `ukHK1GVyr0I` public: Đen – Nấu ăn cho em, Đen Vâu Official; metadata 33.287 bình luận.
- 100 thu thập, 100 hợp lệ, 0 duplicate tự nhiên. 95 text có dấu tiếng Việt. 6 bình luận/6 lượt ứng viên viết tắt, 4 dạng: k=2, ko=2, mn=1, ntn=1.
- Lọc ngày Việt Nam 2026-10-10 trên chính mẫu thật: giữ 1, loại 99. Replay cùng 100 bản ghi giữ 100 ID duy nhất; không thêm dữ liệu giả vào output.
- Output thật: `reports/YouTube/ukHK1GVyr0I_20261011T101205570268Z/`, CSV UTF-8 BOM + raw JSON + summary. Đã đọc lại CSV kiểm tra số dòng/text và scan exports/source/log không chứa key.
- Network trong sandbox thất bại; quyền mạng được duyệt cho lần chạy lại, 2 API calls thành công. Không log raw lỗi/header/key.
- Sửa thứ tự xử lý: lọc ngày trước dedup, thêm regression test tránh bài ngoài ngày làm mất bài trong ngày cùng text.
- Toàn suite **30 passed, 1 warning** (Starlette/httpx cũ). Không commit hoặc push; không lấy replies. Đây là kiểm chứng YouTube live, không thay thế kiểm chứng Gemini/RSS live còn thiếu phía trên.

## NV14 refactor theo tuần — hoàn thành ngày 11/10/2026
- Yêu cầu hiện hành NV14 thay yêu cầu daily trong Phase 3 phía trên: tổng hợp 5 tin AI mỗi tuần, thứ Hai 08:00 theo giờ Windows, mặc định live, mock vẫn hỗ trợ.
- Sửa `shared/automation.py` (chỉ NV14 dùng): weekly_job, ISO year/week hai chữ số, weekly key, thư mục reports/NV14/YYYY-Www/mode/topic-hash. daily_job alias giữ tương thích nhưng nay có semantics weekly.
- Thêm `NV14-Automation/weekly_job.py`; `daily_job.py` chuyển thành wrapper. Mặc định CLI live ghi đè APP_MODE cho riêng NV14; đọc Gemini config/key từ .env qua Settings.load, không sửa .env/shared/config.py.
- Sửa `register_task.ps1`: Weekly/WeeksInterval 1/Monday/08:00, live, weekly_job.py, task HKDN-AI-News-Weekly. Giữ StartWhenAvailable/IgnoreNew/principal/timeout, không tự sửa task Daily cũ.
- Giữ Store/SQLite atomic claim/lease/logging/retry; bảng tên lịch sử daily_jobs dùng khóa tuần, không migrate/xóa dữ liệu cũ, không sửa shared/storage.py.
- Cập nhật README và hai tài liệu NV14. Root README/tài liệu lịch sử giữ nguyên theo phạm vi; entrypoint daily_job.py cũ vẫn hoạt động nhưng thực thi weekly. Hướng dẫn hiện hành là README NV14.
- Sửa/mở rộng `tests/test_automation.py`: **19 passed**. Bao gồm ISO-W53/chuyển năm, timezone UTC/Vietnam, khóa ngày khác cùng tuần/tuần mới, topic/mode, concurrent jobs, stale owner/lease, retry failed/incomplete, CLI live/mock, script trigger/action với toàn bộ cmdlet Scheduler giả.
- Lượt test đầu: 2 test fail do kỳ vọng fixture AI agents và execution policy Windows; sửa harness test bằng scriptblock + cmdlet giả, không đổi policy hay gọi Scheduler thật. Chạy lại 19 pass.
- Toàn suite thực tế: **46 passed, 1 warning in 2.18s**, lệnh `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.tmp/nv14-weekly-regression`. Warning Starlette/httpx có từ trước.
- Smoke mock: key 2026-W41:mock:32e83e92d45d, done, 5 findings, report 82e23793ef31476eb64224c47677762d tại reports/NV14/2026-W41/mock/32e83e92d45d/; gọi lại qua daily_job.py -> skipped.
- Parser script syntax OK. Checksum xác nhận 23 file NV13/NV15/shared ngoài automation.py không thay đổi; regression tests NV13/NV15 pass.
- Không đăng ký hoặc kích hoạt scheduled task, không thay cấu hình Windows. Chưa gọi Gemini live hoặc kiểm chứng scheduled execution cho lần refactor này. Không commit/push.

## NV14 LIVE ServerError — sửa logging/retry ngày 11/10/2026
- Log người dùng: techcrunch RSS thành công rồi ServerError; Last Run Result=0x1. Code chỉ ghi tên exception và CLI trả 1; SDK retries=1. Log cũ không đủ xác định HTTP status/thông báo phía dịch vụ, không khẳng định nguyên nhân server cụ thể.
- Sửa shared/llm.py: generate helper, mọi HTTP attempt tính MAX_API_CALLS; NV14 bật tối đa 3 attempts cho APIError 500/502/503/504, backoff 1 rồi 2 giây, SDK retry nội bộ vẫn tắt. NV13/NV15 mặc định một attempt; không fallback mock.
- Thêm shared/diagnostics.py: safe summary HTTP/message, traceback/chained exceptions không locals/raw response body; redact key exact/Google pattern/header/query/Bearer/token trước LogRecord.
- Sửa shared/automation.py: log safe traceback, SQLite failed + safe error summary/lease=0; failure-state update và cleanup lỗi ghi riêng, không che lỗi gốc hoặc làm saved/done thành failed.
- Sửa NV14-Automation/weekly_job.py: safe CLI status/message/traceback, exit1 khi lỗi; lỗi trước workflow cũng được log.
- Thêm tests/test_gemini_retry.py, 20 cases offline: transient/nonretry/budget/backoff, history, redaction/chained/no-message errors, CLIexit1, failure sau RSS và retry cùng tuần, cleanup/defaults.
- Toàn suite **66 passed, 1 warning in 2.24s**; lệnh `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.tmp/nv14-servererror-final-fixed`. Warning Starlette/httpx cũ.
- Hai case test ban đầu phát hiện stub RSS chưa restore và SDK message=None không có field response_json như giả định. Đã sửa test isolation và isinstance(APIError), chạy lại pass.
- Cập nhật README NV14 và docs/SERVER_ERROR_DIAGNOSTICS.md. Không sửa register_task.ps1/lịch, không gọi Gemini LIVE, không kích hoạt task, không xóa/sửa báo cáo hoặc trạng thái SQLite production cũ; integration DB nằm trong .tmp riêng.
- Không commit/push. Lỗi dịch vụ thật chưa được kiểm chứng đã hồi phục; người dùng tự chạy lại khi muốn và log mới sẽ cung cấp status/message/frame hữu ích.

## NV15 LIVE ServerError / UI chờ kết quả — hoàn thành ngày 11/10/2026
- Planner plan thành công rồi Coordinator failed ServerError: service.py chỉ ghi tên loại, provider mặc định retry_attempts=1. NV15 có generate helper chung nhưng chưa bật 3 attempts/diagnostics của NV14; log cũ không đủ xác định HTTP status chính xác.
- Sửa shared/service.py: provider mặc định bật 3 attempts cho 500/502/503/504, backoff 1/2s, cùng MAX_API_CALLS qua helper chung. NV13 default một attempt và NV14 logic không đổi. Log safe traceback/status/message; SQLite/trace/UI chỉ safe summary; cleanup không che lỗi chính, không fallback mock.
- Sửa NV15-Agentic-AI/frontend/app.js: failed/no-report/network/report-fetch thay placeholder bằng lỗi, ngừng poll, ẩn download/mở nút chạy; guard response cũ sau await report; incomplete có report vẫn xem/tải.
- Thêm tests/test_nv15_live_errors.py (8 cases), tests/frontend_error_state.cjs + test_frontend_error_state.py (1 pytest với nhiều scenarios), đổi tên một test base-provider trong tests/test_gemini_retry.py cho đúng phạm vi.
- Targeted tests: 14 passed. Toàn suite: **75 passed, 0 failed, 1 warning in 3.08s**; lệnh `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.tmp/nv15-error-regression`. Warning Starlette/httpx cũ. Không gọi SDK/RSS thật; frontend kiểm tra bằng Node VM/DOM fixture, chưa visual QA.
- Cập nhật README, HUONG_DAN_TRIEN_KHAI và thêm LIVE_ERROR_DIAGNOSTICS.md của NV15 với hướng dẫn lần kiểm thử LIVE tiếp theo.
- Kiểm tra read-only tiến trình: run.py có hai nhóm khởi động 15:49 và 20:41, không autoreload; cần người dùng restart instance đang dùng và Ctrl+F5 browser. Không dừng hoặc khởi động thêm server, không thay Task Scheduler, không gọi Gemini LIVE, không sửa báo cáo/production DB. Không commit/push.
