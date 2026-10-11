# Chẩn đoán NV14 LIVE ServerError

## Dữ kiện và giới hạn kết luận

Log được cung cấp: Coordinator mode=live; Collector fetch_rss techcrunch: 20 bài; Weekly job failed: ServerError. Task Scheduler Last Run Result=0x1.

Luồng: weekly_job → NewsWorkflow/Coordinator → CollectorAgent → GeminiProvider.collect → generate_content. Collector gọi Gemini để chọn nguồn, thực thi fetch_rss rồi đưa tool result vào history; quyết định kế tiếp lại gọi Gemini. Với log đã có, RSS thành công và lỗi xuất hiện khi xử lý bước sau đó. Không có trace analyze/finish nên khả năng lỗi ở quyết định Collector kế tiếp; không thể xác nhận tuyệt đối frame/mã HTTP của lượt cũ vì thông tin đã bị bỏ.

Code trước sửa ghi type(exc).__name__ ở weekly_job, lưu SQLite error cũng chỉ tên loại; CLI bắt exception và return 1. Do đó không có traceback, HTTP status hoặc message, và Last Run Result 0x1 là process exit code, không phải mã HTTP. SDK được cấu hình HttpRetryOptions(attempts=1), không có application retry.

Google SDK APIError cung cấp code/message; ServerError thuộc lỗi HTTP 5xx. Log cũ không cho biết chính xác 500/502/503/504 hay nguyên nhân server. Không khẳng định API key sai hoặc RSS lỗi. Xem [Google Gen AI SDK errors](https://googleapis.github.io/python-genai/).

## Sửa lỗi

- `shared/llm.py`: helper generate đếm từng HTTP attempt, retry chỉ APIError có code 500/502/503/504; NV14 bật tối đa 3 attempts, ngủ 1 rồi 2 giây. Cùng payload/history được dùng lại, không thêm prompt hoặc gọi RSS lần nữa cho mỗi retry. SDK retry vẫn attempts=1. Budget hết thì không retry/sleep thêm và giữ lỗi HTTP cuối.
- `shared/diagnostics.py`: lấy code/message thay vì serialize raw response; redact exact API key, Google key pattern, credentials trong URL/header/dictionary và Bearer. Traceback gồm stack frames/chained exception nhưng không locals; message/key được lọc trước khi tạo LogRecord. Không log raw request/response body.
- `shared/automation.py`: log chẩn đoán trước cập nhật SQLite, lưu safe summary và failed/lease_until=0. Cập nhật SQLite lỗi được log riêng và không che lỗi gốc; lease còn active phải đợi hết hạn. Cleanup lỗi được ghi riêng, không thay kết quả chính.
- `NV14-Automation/weekly_job.py`: stderr có safe HTTP summary, exit code vẫn 1 khi thất bại; lỗi cấu hình/claim trước workflow cũng có safe traceback.

Không có mock fallback trong live. NV13/NV15 vẫn mặc định một attempt. Lịch, task registration script, topic hash/weekly key, báo cáo và lịch sử cũ không đổi. Không gọi Gemini LIVE hoặc kích hoạt task trong phiên sửa.

## Kiểm thử offline

`tests/test_gemini_retry.py` mock Google Client trước khi khởi tạo provider và thay sleep bằng recorder, không gửi request thật. Kiểm tra 4 transient status, nonretry status, 3-attempt cap, API budget, Collector history, status/traceback/secret redaction, không log raw body, CLI exit1, failure sau RSS giải phóng lease/retry cùng tuần, cleanup không che saved result, NV13/NV15 defaults.

Integration test giả lập bước RSS thành công rồi 503 liên tiếp: tổng 4 lượt model (1 lần chọn RSS + 3 attempts cho quyết định kế tiếp), backoff 1/2 giây mô phỏng, failed với lease=0 và không có report mới. Sau đó test double thành công trên cùng LIVE weekly key, lần kế tiếp skipped. Đây là mock test, không chứng minh Gemini dịch vụ thật đã hồi phục.

Sau sửa, người dùng tự chạy lại khi muốn; nếu lỗi còn xảy ra, log mới có vị trí/status/message để chẩn đoán. Không sửa trạng thái failed hoặc report cũ trong phiên này.

Kết quả cuối thực tế ngày 11/10/2026: **66 passed, 1 warning in 2.24s** với lệnh `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.tmp/nv14-servererror-final-fixed`. Cảnh báo Starlette/httpx đã có trước. Suite retry/diagnostics mới gồm 20 test cases. Các lượt test ban đầu phát hiện stub RSS chưa restore và SDK thiếu message không có field response_json như giả định; đã sửa test isolation và kiểm tra APIError bằng kiểu SDK, rồi chạy lại toàn suite pass.
