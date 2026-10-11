# Triển khai NV14 — 5 tin AI mỗi tuần

1. Cài venv/dependencies chung. Tự điền GEMINI_API_KEY trong `.env`, không in/chụp key.
2. Chạy `NV14-Automation/weekly_job.py` bằng Python venv; mặc định live/topic AI/5 tin. Dùng `--mode mock` để test offline, không cần đổi APP_MODE của NV13/NV15.
3. Kiểm tra JSON result done/incomplete/skipped, khóa tuần, report ID và đường dẫn.
4. Chạy lại cùng topic/mode/tuần: done phải skip, kể cả ngày khác trong tuần. Failed/incomplete retry được; tuần mới tạo khóa mới.
5. Khi muốn lịch thật, tự chạy register_task.ps1 theo README NV14: thứ Hai mỗi tuần lúc 08:00 theo giờ Windows, user đăng nhập; StartWhenAvailable hỗ trợ chạy bù.
6. Sau tự đăng ký, kiểm tra Weekly/Monday/every 1 week/08:00, action weekly_job.py + mode live và working directory root. Chờ scheduled execution thật, đối chiếu Last Run Result/History, log/report; không đánh đồng Start tay với chạy do trigger.

## Tuần ISO

Ngày hiện tại lấy theo Asia/Ho_Chi_Minh; dùng date.isocalendar() lấy **ISO year**, không dùng calendar year. Định dạng YYYY-Www, tuần hai chữ số:

| Ngày | Tuần |
|---|---|
| 31/12/2020, 01/01/2021, 03/01/2021 | 2020-W53 |
| 04/01/2021 | 2021-W01 |
| 29/12/2025, 04/01/2026 | 2026-W01 |
| 05/01/2026 | 2026-W02 |

Báo cáo: `reports/NV14/<ISO-year>-W<week>/<mode>/<topic-hash>/`. Topic hash giữ cách tính cũ. SQLite BEGIN IMMEDIATE bảo vệ atomic claim; lease ít nhất 1 giờ, tăng theo timeout/budget. Done hoặc active lease -> skip; crash chờ hết lease. Failed/incomplete được thử lại; báo cáo incomplete giữ riêng để audit.

Bảng SQLite còn tên lịch sử daily_jobs, khóa tuần thay khóa ngày. Không migrate/xóa bản ghi hoặc báo cáo daily cũ, không sửa storage/agents/config của NV13/NV15. daily_job.py còn hỗ trợ CLI cũ nhưng thực thi weekly, mặc định live.

Đây là thay đổi tần suất chạy; không thêm bộ lọc chỉ lấy bài xuất bản trong 7 ngày hoặc sửa RSS chung.

## Đăng ký lịch thủ công

Task mới mặc định HKDN-AI-News-Weekly. Nếu trước đó tự tạo task Daily, tự vô hiệu hóa/xóa trước khi đăng ký Weekly; script không tự sửa task cũ. Giờ 08:00 theo Windows, máy đặt Việt Nam thì là giờ Việt Nam. Không đổi timezone/policy máy, không ghi đè task cùng tên. Principal interactive, StartWhenAvailable/IgnoreNew/ExecutionTimeLimit một giờ giữ nguyên; máy không sẵn sàng có thể chạy bù muộn.

Phiên refactor không đăng ký/kích hoạt task thật. Test lịch dùng cmdlet giả. Live thiếu key/lỗi -> xem loại lỗi an toàn; không fallback mock. Incomplete do thiếu tin/căn cứ -> retry được. Kiểm thử NV14 **19 passed**, bao gồm ISO year/W53, timezone, concurrency/lease, retry và mặc định live; chưa kiểm chứng Gemini live hoặc scheduled execution cho phiên thay đổi này.
