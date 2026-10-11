# NV15 — Ứng dụng Agentic AI

FastAPI + SQLite + HTML/CSS/JS. Planner diễn giải ngôn ngữ tự nhiên, chọn `news_workflow`, tái sử dụng Collector/Analyst, đánh giá báo cáo và điều chỉnh tối đa một lần. Trace lưu trong SQLite; frontend poll để hiển thị quá trình. Không có login/payment/cloud deploy.

Cài đặt theo [README root](../README.md). Chạy độc lập từ root:

```powershell
.\.venv\Scripts\python.exe NV15-Agentic-AI/run.py --mode mock
```

Mở http://127.0.0.1:8000 và nhập “Tổng hợp 5 tin về AI”. Swagger ở `/docs`. Badge MOCK và DEMO cảnh báo dữ liệu mô phỏng; live dùng key `.env` và `--mode live`. Restart server sau đổi cấu hình. Ctrl+C để dừng. Một server/worker cho mỗi database.

Frontend có yêu cầu, trạng thái, trace, cards summary/quote/source, lịch sử và tải Markdown/JSON. API có POST `/api/runs`, GET `/api/runs/{id}`, `/api/reports/{id}`, `/api/reports/{id}/download?format=md`. Response POST 202 trả ID ngay; poll trạng thái cho đến completed/incomplete/failed. Một lượt active; lượt thứ hai trả 409.

SQLite lưu bài báo/báo cáo/lịch sử. BackgroundTasks chạy trong tiến trình; crash/restart chuyển lượt cũ thành failed, không tiếp tục tự động. Giới hạn API dùng chung cho Planner và workflow. Bản tin dựa trích đoạn RSS, không tự chứng minh fact-check.

Test: `python -m pytest tests/test_web.py -q` bằng venv. Xem [hướng dẫn](docs/HUONG_DAN_TRIEN_KHAI.md), [minh chứng](docs/MINH_CHUNG_CAN_CHUP.md), [kết quả thực tế](../docs/KET_QUA_KIEM_THU.md). HTTP và server đã kiểm chứng; visual QA và Gemini thật chưa kiểm chứng.

## LIVE: retry và xử lý lỗi

NV15 bật cơ chế chung đã dùng cho NV14: tối đa **3 attempts** mỗi quyết định Gemini khi gặp HTTP **500/502/503/504**, exponential backoff **1s, 2s**. Planner, Collector, Analyst và evaluation cùng dùng một provider/budget; mỗi request thất bại/retry cũng tính vào MAX_API_CALLS. SDK retry nội bộ vẫn tắt, không retry vô hạn hoặc tự chuyển LIVE sang MOCK. NV13 giữ mặc định một attempt, NV14 giữ chính sách hiện tại.

Lượt failed lưu error type/HTTP status/message đã lọc trong API/history/trace. Log agents.log có traceback đã lọc, không locals/raw API response/key. Lỗi budget trước báo cáo đầu tiên -> failed; nếu đã có report và gặp BudgetExceeded -> incomplete, giữ report gần nhất. Cleanup lỗi được log riêng, không che mất kết quả chính.

Frontend thay placeholder bằng lỗi khi run failed/no report, lỗi poll hoặc tải report; dừng polling, ẩn nút tải, mở lại nút chạy. Thông báo dùng textContent, không render HTML từ error message. Report incomplete còn có căn cứ vẫn hiển thị và tải được.

Lượt sửa này: **75 tests passed, 0 failed**, một cảnh báo Starlette/httpx cũ. Test SDK/RSS dùng mock, frontend chạy JavaScript thật với DOM/fetch fixture bằng Node, không phải visual QA trình duyệt. Không gọi Gemini LIVE, không khởi chạy server mới, không đổi Task Scheduler. Xem [chẩn đoán và kiểm thử LIVE tiếp theo](docs/LIVE_ERROR_DIAGNOSTICS.md).

**Cần restart server đang chạy** để nạp backend mới: run.py không bật autoreload. Tự dừng instance NV15 hiện tại trong terminal của bạn rồi chạy lại `python NV15-Agentic-AI/run.py --mode live` bằng venv, giữ cổng đang sử dụng. Sau đó hard reload trình duyệt (Ctrl+F5). Không chạy thêm instance cùng database.
