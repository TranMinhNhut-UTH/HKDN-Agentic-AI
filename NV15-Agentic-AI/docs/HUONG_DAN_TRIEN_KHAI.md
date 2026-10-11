# Triển khai NV15

1. Cài venv chung, giữ `.env` mock; chạy `NV15-Agentic-AI/run.py` bằng Python venv.
2. Mở local URL in trên terminal; mode badge phải MOCK/OFFLINE.
3. Nhập “Tổng hợp 5 tin về AI” và chạy. Xem Planner plan, Collector fetch, Analyst analyze, Planner evaluate.
4. Xem count, summary, quote, limitation, nguồn demo. Tải Markdown và JSON.
5. Reload lịch sử, chọn lại report. Restart server để kiểm tra persistence; lượt chưa xong chuyển failed.
6. Mở Swagger, POST `{"request":"Tổng hợp 5 tin về AI"}`, lấy ID rồi GET run/report. Request rỗng trả 422; ID không tồn tại trả 404.
7. Với live: tự cấu hình key/model, khởi động bằng `--mode live`, kiểm tra RSS nguồn thật và đối chiếu. Không đánh đồng TestClient với Gemini end-to-end.

Backend `shared/web.py` cung cấp API, `shared/service.py` dispatch tool do Planner chọn, trace callback update SQLite. Planner có tối đa 2 kế hoạch; workflow có MAX_ROUNDS feedback, mỗi Collector MAX_STEPS, tất cả chia sẻ MAX_API_CALLS. Lỗi trước báo cáo đầu tiên -> failed; budget hết sau báo cáo -> incomplete và giữ căn cứ cũ.

Giao diện responsive, render textContent, link HTTP/HTTPS; không dùng framework hay CDN. Ở mock chỉ có 6 bài AI mẫu; yêu cầu quá số bài hoặc chủ đề khác cần hiện thiếu dữ liệu, không phải tự tạo thêm bài.

Đã chạy API/TestClient, persistence/download/revision/budget tests, khởi động Uvicorn. Chưa có browser visual QA và Gemini thật. Xem [kiến trúc/cấu hình chung](../../docs/HUONG_DAN_TRIEN_KHAI.md) và [kết quả cuối](../../docs/KET_QUA_KIEM_THU.md).

## Cập nhật xử lý lỗi LIVE

NV15 nay bật tối đa 3 attempts cho 500/502/503/504, backoff 1s/2s, mọi attempt tính vào MAX_API_CALLS. Dùng diagnostics chung: log safe traceback/status/message, API chỉ trả safe summary. Không fallback MOCK. UI failed/no report hoặc lỗi fetch phải thay trạng thái chờ bằng lỗi và mở lại nút chạy; incomplete có report vẫn cho xem/tải.

Toàn suite sau sửa: **75 passed, 0 failed, 1 warning**. Không gọi LIVE/khởi chạy server/kích hoạt task trong phiên sửa. Để áp dụng, tự restart instance đang dùng (run.py không autoreload), giữ một server cho mỗi database và hard reload browser. Xem [hướng dẫn LIVE chi tiết](LIVE_ERROR_DIAGNOSTICS.md).
