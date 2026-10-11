# NV14 — Tổng hợp 5 tin tức AI mỗi tuần

Task Scheduler chạy **08:00 sáng thứ Hai hằng tuần theo giờ Windows**. Máy đặt múi giờ Việt Nam thì đây là 08:00 Asia/Ho_Chi_Minh. CLI và script đăng ký mặc định **live**, cho phép mock để kiểm thử; tái sử dụng Collector/Analyst chung.

## Chạy độc lập

Cài môi trường theo [README root](../README.md); tự điền `GEMINI_API_KEY` trong `.env`, không đưa key vào source/log/CLI. Từ root:

```powershell
# Mặc định live, chủ đề AI, 5 tin
.\.venv\Scripts\python.exe NV14-Automation/weekly_job.py
# Chỉ định rõ mode
.\.venv\Scripts\python.exe NV14-Automation/weekly_job.py --mode live --topic AI
# Kiểm thử offline
.\.venv\Scripts\python.exe NV14-Automation/weekly_job.py --mode mock
```

Mặc định live của NV14 ghi đè APP_MODE=mock nếu có trong `.env`; không đổi mặc định NV13/NV15. Live lỗi/thiếu key không tự dùng mock. `daily_job.py` giữ làm entrypoint tương thích, nhưng nay cũng chạy **theo tuần và mặc định live**; ưu tiên `weekly_job.py`.

## Chống trùng và kết quả

Tuần ISO tính theo ngày hiện tại tại Asia/Ho_Chi_Minh, từ thứ Hai đến Chủ nhật. Khóa `<ISO-year>-W<week>:<mode>:<topic-hash>`; ISO year có thể khác calendar year. Ví dụ 01/01/2021 thuộc 2020-W53, 29/12/2025 thuộc 2026-W01. Topic hash giữ SHA-256 của topic strip/casefold, lấy 12 ký tự đầu.

Báo cáo ở `reports/NV14/<ISO-year>-W<week>/<mode>/<topic-hash>/<report-id>.json` và `.md`. Week luôn có hai chữ số. Cùng topic/mode/tuần đã done hoặc có lease active -> skipped; tuần mới có thể chạy. Database vẫn `data/news.sqlite3`, log vẫn `logs/agents.log`.

Giữ atomic lease, logging, timeout/budget và retry: failed/incomplete cho phép thử lại cùng tuần, crash chờ lease hết hạn. Các lần incomplete có thể có báo cáo riêng để audit; sau done không tạo thêm báo cáo thành công cùng tuần. Exit 0 done/skipped, 2 incomplete, 1 lỗi.

Bảng/phương thức SQLite còn tên lịch sử daily_jobs/claim_daily/finish_daily, nhưng ghi khóa tuần mới; không sửa shared/storage.py hoặc xóa lịch sử daily. Khóa daily cũ khác khóa tuần, báo cáo cũ giữ nguyên. Chỉ shared/automation.py được refactor cho NV14.

## Task Scheduler — người dùng đăng ký thủ công

Phiên chỉnh sửa **không đăng ký hoặc kích hoạt task**. Khi bạn sẵn sàng:

```powershell
# Xem trước, mặc định live, không đăng ký
.\NV14-Automation\register_task.ps1 -WhatIf
# Đăng ký: thứ Hai 08:00, mỗi tuần, live
.\NV14-Automation\register_task.ps1
# Tùy chọn mock để tự kiểm tra
.\NV14-Automation\register_task.ps1 -Mode mock
```

Task mặc định HKDN-AI-News-Weekly, action weekly_job.py, working directory root. Trigger `-Weekly -WeeksInterval 1 -DaysOfWeek Monday -At '08:00'`, theo [Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger?view=windowsserver2025-ps). Không đổi timezone/policy hoặc ghi đè task cùng tên. Chỉ chạy khi user đăng nhập; StartWhenAvailable giữ chạy bù, nên có thể chạy muộn khi máy ngủ/tắt hoặc chưa đăng nhập.

Nếu bạn từng đăng ký HKDN-AI-News-Daily, hãy tự vô hiệu hóa/xóa task cũ trước khi đăng ký lịch tuần. Script không tự sửa task cũ. Nếu policy chặn script, xử lý theo quy trình máy của bạn; chương trình không tự đổi policy.

Sau đăng ký, kiểm tra Task Scheduler hoặc `Get-ScheduledTaskInfo -TaskName HKDN-AI-News-Weekly`, đối chiếu History/Last Run Result và báo cáo đúng tuần.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_automation.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

NV14: **19 passed**, kiểm tra tuần ISO/chuyển năm/W53, timezone, cùng tuần/ngày khác, tuần mới, topic/mode, concurrency, lease/stale owner, retry failed/incomplete, CLI live và lịch thứ Hai 08:00. Test lịch thay toàn bộ cmdlet Scheduler bằng hàm giả; không đăng ký/kích hoạt task. Xem [hướng dẫn](docs/HUONG_DAN_TRIEN_KHAI.md), [minh chứng](docs/MINH_CHUNG_CAN_CHUP.md).

Toàn suite sau refactor: **46 passed, 1 warning** (Starlette/httpx cũ). Smoke mock ngày 11/10/2026: done với key `2026-W41:mock:32e83e92d45d`, xuất 5 mục đúng thư mục tuần; gọi lại qua daily_job.py trả skipped. Script parse syntax OK; checksum xác nhận 23 file NV13/NV15/shared ngoài automation.py không đổi. Không gọi Gemini live hoặc tạo scheduled execution trong phiên này.

## Xử lý ServerError khi chạy LIVE

NV14 cho tối đa **3 HTTP attempts mỗi quyết định Gemini** đối với HTTP **500/502/503/504**, exponential backoff **1 rồi 2 giây**. SDK retry nội bộ vẫn tắt để không có lượt gọi ẩn. Mỗi attempt, kể cả thất bại, đều tính vào MAX_API_CALLS chung; hết budget thì dừng và giữ lỗi HTTP cuối cùng. Không retry lỗi 400/401/403/404/429/501 hoặc lỗi schema, không fallback mock. Chính sách mới chỉ được bật khi NV14 khởi tạo provider; NV13/NV15 vẫn mặc định một attempt.

Log failed ghi key tuần/mode, exception type, HTTP status, message đã redact và traceback theo file/hàm/dòng. Không log traceback locals, request headers hay raw API error body. Retry log ghi operation/attempt/calls/backoff. SQLite lưu error summary đã lọc, chuyển failed và giải phóng lease để lần chạy thủ công tiếp theo có thể retry cùng tuần; nếu việc cập nhật SQLite cũng lỗi, log riêng và chờ lease hết hạn. Provider cleanup lỗi không che mất lỗi chính hoặc biến báo cáo done thành lỗi CLI.

Last Run Result 0x1 là exit code 1 của CLI khi job thất bại; không đủ để biết HTTP status. Log ServerError cũ không lưu đủ chi tiết để truy nguyên HTTP code của lượt cũ. Không đổi lịch/kích hoạt lại task hoặc xóa báo cáo/log cũ. Kiểm thử sửa lỗi dùng Gemini/RSS giả, không gọi Gemini LIVE; xem [phân tích lỗi](docs/SERVER_ERROR_DIAGNOSTICS.md).
