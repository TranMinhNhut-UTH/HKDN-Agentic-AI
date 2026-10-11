# Minh chứng cần chụp

Đây là hướng dẫn chụp **kết quả thực tế**, không phải bộ ảnh đã tạo. Phiên triển khai chưa chụp giao diện do không có trình duyệt khả dụng cho automation. Mỗi ảnh nên có thời điểm, lệnh/chủ đề, mode và kết quả; che API key, không chụp `.env` có key.

## NV13

1. Terminal CLI mock với `--topic AI --count 5`, log Coordinator/Collector/Analyst, complete=True.
2. JSON và Markdown: 5 mục, source, evidence_quote, limitation, mode=mock và trace.
3. CLI với chủ đề không có dữ liệu, thể hiện request_more và dừng sau 2 vòng.
4. Nếu đã cấu hình live: log/báo cáo mode=live có bài RSS thật; đối chiếu ít nhất một nguồn. Không dùng ảnh mock để khẳng định gọi Gemini thật.

## NV14

1. Chạy daily_job: báo cáo thư mục ngày và status=done.
2. Chạy lại cùng ngày/topic/mode: status=skipped.
3. Task Scheduler: chỉ chụp sau khi người dùng chủ động đăng ký; tabs Trigger (08:00), Action (Python + script), History/Last Run Result.
4. Đối chiếu báo cáo và log sau một lượt thực sự chạy qua Task Scheduler. Chạy tay không chứng minh scheduled execution.

## NV15

1. Trang web ban đầu, badge MOCK hoặc LIVE và lời giải thích mode.
2. Nhập yêu cầu; trace Planner plan, Collector fetch_rss, Analyst analyze, Planner evaluate; trạng thái đang chạy nếu kịp chụp.
3. Kết quả: summary, quote, limitation, link nguồn và count.
4. Lịch sử sau reload/restart, tải Markdown/JSON và mở file.
5. Swagger `/docs`: POST run + GET trạng thái/report.
6. Nhập yêu cầu thiếu dữ liệu, ghi incomplete hoặc budget_limit có căn cứ.

## Kiểm thử

Chạy `python -m pytest -q` bằng Python trong venv và chụp terminal của chính lần chạy đó. Kết quả đã ghi trong `KET_QUA_KIEM_THU.md` là từ phiên triển khai; không ghép hoặc sửa ảnh để thay kết quả. Xem thêm checklist riêng của từng nhiệm vụ.
