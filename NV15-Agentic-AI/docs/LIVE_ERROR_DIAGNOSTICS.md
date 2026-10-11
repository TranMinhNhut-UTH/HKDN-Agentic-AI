# NV15 LIVE — chẩn đoán lỗi và lần kiểm thử tiếp theo

## Nguyên nhân mất thông tin

Log người dùng cho thấy Planner plan thành công, Coordinator bắt đầu rồi failed ServerError trước Collector fetch/analyze. Theo workflow, khả năng lỗi tại lời gọi Gemini đầu tiên của Collector; không thể xác nhận mã HTTP của lượt cũ do thiếu traceback/status.

NV15 đã đi qua GeminiProvider.generate chung nhưng service gọi make_provider(settings) với retry_attempts mặc định 1. Chính sách 3 attempts trước đó chỉ được bật từ NV14. service.py chưa dùng diagnostics, chỉ type(exc).__name__ trong trace/error. SDK ServerError do đó bị rút xuống tên loại, không còn status/message.

Frontend watchRun đặt placeholder Đang tải kết quả; updateRun terminal chỉ render nếu có report_id. Khi failed không có report, placeholder không được thay. Nhánh lỗi mạng/report-fetch cũng chỉ thay banner lỗi, nên phần bản tin tiếp tục chờ.

## Sửa

- service.py bật make_provider(settings,retry_attempts=3) cho provider mặc định của NV15. Custom factory cho test vẫn nhận settings như trước. Planner/Collector/Analyst/Evaluation chia sẻ API budget; generate chung tính từng HTTP attempt, retry chỉ 500/502/503/504, chờ 1 rồi 2 giây, SDK internal retry tắt. Không sửa mặc định provider của NV13 hoặc logic NV14.
- Tái sử dụng exception_summary/log_exception: log full stack frames và error message/status đã redact; API/SQLite/trace chỉ có safe summary, không stack/locals/raw response. Cleanup lỗi log riêng, không che lỗi chính.
- app.js thêm renderFailure/handleRunError cho failed/no-report/network/download, dừng poll, ẩn downloads, mở lại run button. Guard selectedRun sau khi chờ report để response cũ không ghi đè lượt vừa chọn. Incomplete có report vẫn render/tải bình thường.

## Kết quả kiểm thử

Lệnh thực tế: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.tmp/nv15-error-regression`.

**75 passed, 0 failed, 1 warning in 3.08s**. Warning Starlette/httpx có từ trước.

- 8 cases test_nv15_live_errors.py: transient 500/502/503/504 rồi thành công, 3 attempts thất bại với status/traceback/redaction, thử request mới sau failed, budget trước report, budget sau report/incomplete, 403 không retry.
- 1 frontend pytest chạy frontend_error_state.cjs: JavaScript thật trong Node VM + DOM/fetch fixture. Kiểm tra failed/error/null-error, incomplete/no-report, network/report-fetch failure và incomplete/có report. Không khẳng định đã visual QA trên trình duyệt.
- Các tests NV13/NV14/YouTube/SDK diagnostics hiện có vẫn pass. Test SDK/RSS đều thay transport/client bằng mock, không gọi Gemini LIVE, không khởi chạy server.

## Server cần restart

Kiểm tra read-only tiến trình thấy hai nhóm run.py đã khởi động lúc 15:49 và 20:41 ngày 11/10/2026, không có reload flag. run.py cũng cấu hình uvicorn.run không autoreload. Cần tự restart instance bạn đang dùng để nạp backend mới; phiên sửa không dừng/khởi động tiến trình nào. Chỉ giữ một instance cho cùng database theo thiết kế ứng dụng. Không suy đoán cổng từ PID.

## Kiểm thử LIVE tiếp theo — người dùng thực hiện

1. Trong terminal đang chạy NV15, Ctrl+C dừng server hiện tại; xác nhận không còn instance khác dùng cùng database/cổng.
2. Giữ GEMINI_API_KEY trong .env; không copy/chụp key vào log hay chat.
3. Từ root, chạy `.venv\Scripts\python.exe NV15-Agentic-AI/run.py --mode live` (thêm --port với cổng bạn đang dùng nếu khác 8000). Đây là hướng dẫn, chưa được thực thi trong phiên sửa.
4. Mở URL tương ứng, Ctrl+F5 để nạp app.js mới. Xác nhận badge GEMINI/LIVE.
5. Nhập “Tổng hợp 1 tin về artificial intelligence” trước để giảm số lượt cần xử lý; sau khi thành công thử 5 tin AI. Count ít không bảo đảm dịch vụ sẽ không lỗi.
6. Nếu transient error, xem logs/agents.log có operation/attempt/calls/backoff/status; tổng gọi không vượt MAX_API_CALLS. Nếu retry thành công, report mode live và trace có các Agent.
7. Nếu vẫn failed: UI phải hiện HTTP/status/message đã lọc, phần báo cáo không còn Đang tải kết quả, nút chạy mở lại, download ẩn. Log có safe traceback; /api/runs/{id} status failed và error summary.
8. Nếu budget hết sau khi đã có report, UI incomplete vẫn hiển thị report; tăng budget chỉ khi bạn chủ động muốn thêm quota/lượt xử lý. Không đổi mode thành mock để che lỗi LIVE.
9. Ghi lại run ID/HTTP status/message đã lọc nếu cần chẩn đoán; không gửi raw response/header/key. Không cần thay đổi Task Scheduler.

Thành công của tests mock không chứng minh dịch vụ Gemini đã hết lỗi. HTTP status của lần lỗi cũ không thể khôi phục từ log chỉ có ServerError.
