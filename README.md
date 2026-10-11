@All  Nhiệm vụ 13: mỗi bạn build ít nhất 2 ai agents, để 2 agents  thực hiện công việc A (tự chọn). Soạn tài liệu hướng dẫn triển khai.
-> Multi-Agent	Hai AI Agents thu thập, phân tích và tóm tắt tin tức

@All  Nhiệm vụ 14: Mỗi bạn triển khai một Automation thực hiện công việc tự động có tính lặp đi lặp lại nhiều lần. Soạn tài liệu hướng dẫn triển khai.
-> Chương trình tự động tổng hợp 5 tin mỗi ngày

@All  Nhiệm vụ 15: Mỗi bạn triển khai 1 dự án nhỏ liên quan đến Agentic AI
-> Agentic AI   Website AI nhận yêu cầu, lập kế hoạch, gọi công cụ và xuất báo cáo



# AI News Intelligence System

Repository Python chạy local trên Windows cho **NV13 (Multi-Agent)**, **NV14 (Automation)** và **NV15 (Agentic AI)**. Ba nhiệm vụ tái sử dụng `shared/`, không sao chép logic.

**Mặc định MOCK/OFFLINE**: mô phỏng quyết định Agent và 6 bài mẫu có nhãn DEMO. Đây không phải bằng chứng Agent đã gọi LLM thật. Chế độ **LIVE** dùng Gemini để quyết định và RSS thật; lỗi không tự chuyển sang dữ liệu mẫu.

## Cài đặt

Cần Python 3.11+ (đã kiểm thử Python 3.12.10), kết nối mạng để cài dependencies. Mở PowerShell tại thư mục repository:

```powershell
.\scripts\setup.ps1
```

Hoặc cài thủ công, không cần activate venv:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
```

Chỉ copy `.env` nếu chưa có; tránh ghi đè key hiện tại. `requirements-lock.txt` là phiên bản thực tế đã kiểm thử; `requirements.txt` chứa khoảng phiên bản cho lần nâng cấp chủ động. `.env`, `.venv`, logs, SQLite và báo cáo runtime nằm trong `.gitignore`. Git đã được khởi tạo; chưa tạo commit.

## Chạy từng nhiệm vụ độc lập

Chạy các lệnh sau từ root; không cần chạy NV13 trước để dùng NV14 hoặc NV15:

```powershell
# NV13: Collector + Analyst, xuất JSON/Markdown
.\.venv\Scripts\python.exe NV13-Multi-Agent/main.py --mode mock --topic AI --count 5

# NV14: 5 tin mỗi ngày, khóa SQLite chống chạy trùng
.\.venv\Scripts\python.exe NV14-Automation/daily_job.py --mode mock --topic AI

# NV15: Planner + workflow + giao diện web
.\.venv\Scripts\python.exe NV15-Agentic-AI/run.py --mode mock
```

NV15: mở **http://127.0.0.1:8000**, Swagger **http://127.0.0.1:8000/docs**. Chạy một server, một worker; Ctrl+C để dừng. Có thể đổi cổng bằng `--port 8001`. Nhập “Tổng hợp 5 tin về AI”. Chủ đề khác không có trong fixture có thể trả kết quả thiếu dữ liệu, đúng hành vi demo.

| Nhiệm vụ | Điểm chạy | Kết quả |
|---|---|---|
| [NV13](NV13-Multi-Agent/README.md) | `main.py` | `reports/NV13/<id>.json`, `.md` |
| [NV14](NV14-Automation/README.md) | `daily_job.py` | `reports/NV14/<ngày>/<mode>/<topic-hash>/` |
| [NV15](NV15-Agentic-AI/README.md) | `run.py` | Web, SQLite, `reports/NV15/` |

## Gemini / RSS thật

Tạo API key trong Google AI Studio và tự điền vào `.env`:

```dotenv
APP_MODE=live
GEMINI_API_KEY=YOUR_KEY_HERE
GEMINI_MODEL=gemini-flash-latest
```

Sau đó chạy với `--mode live`. Không đưa key vào CLI, source hay ảnh chụp. Tên model cấu hình được; availability/quota phụ thuộc tài khoản. RSS công khai không cần key. Gemini có thể có quota miễn phí theo chính sách tài khoản, dự án không bảo đảm mọi lượt gọi đều miễn phí. Xem [Gemini SDK](https://googleapis.github.io/python-genai/) và [function calling](https://ai.google.dev/gemini-api/docs/generate-content/function-calling).

Collector dùng manual function calling `fetch_rss`/`finish_collection`; tool result được đưa lại vào hội thoại Gemini. Analyst dùng structured output để phân loại, tóm tắt, yêu cầu bổ sung. Planner dùng structured output để chọn `news_workflow`, rồi đánh giá và sửa kế hoạch tối đa một lần. `MAX_API_CALLS` dùng chung cho toàn lượt thực thi, SDK retry tắt; `MAX_STEPS` giới hạn mỗi Collector, `MAX_ROUNDS` giới hạn feedback Collector/Analyst.

Nguồn allowlist: BBC Technology, TechCrunch, The Verge. RSS có thể đổi endpoint/chặn truy cập; Collector ghi lỗi rồi thử nguồn khác. Mặc định HTTP timeout 20 giây, tối đa 2MB mỗi feed; không theo redirect ngoài allowlist. Dữ liệu chỉ gồm tiêu đề/trích đoạn RSS. Kiểm tra ID và quote nguyên văn giúp loại mục không có căn cứ; **không chứng minh mọi diễn giải của LLM đều chính xác**, không phải fact-check độc lập.

## Kiểm thử và giới hạn đã biết

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Kết quả thực tế hiện tại: **21 passed, 1 warning**. Xem [báo cáo kiểm thử](docs/KET_QUA_KIEM_THU.md). Tất cả test chạy offline; test Gemini kiểm tra SDK bằng mock, không gọi dịch vụ thật. Chưa kiểm chứng end-to-end live với API key. Server và REST API đã chạy được; chưa kiểm tra trực quan trên trình duyệt vì browser automation không có browser khả dụng trong phiên triển khai.

NV14 đã kiểm chứng chạy tay và chống trùng; Task Scheduler chưa đăng ký. Script đăng ký chỉ do người dùng chủ động chạy. FastAPI BackgroundTasks chạy trong tiến trình local; restart đánh dấu lượt chưa xong là failed, không tự tiếp tục. SQLite lưu lịch sử, bài báo, báo cáo; chưa có chức năng quản lý dữ liệu ngoài phạm vi.

Xem [hướng dẫn triển khai](docs/HUONG_DAN_TRIEN_KHAI.md), [minh chứng cần chụp](docs/MINH_CHUNG_CAN_CHUP.md), và [tiến độ](PROGRESS.md). Khi tiếp tục phiên làm việc, đọc `PROGRESS.md` trước.

## Mở rộng: bình luận YouTube thật

Module [YouTube-Comments](YouTube-Comments/README.md) dùng `YOUTUBE_API_KEY` trong `.env`, độc lập với mode Gemini. Thu thập tối đa 100 bình luận cấp đầu từ video public, lọc ngày/từ viết tắt/chống trùng và xuất CSV UTF-8:

```powershell
.\.venv\Scripts\python.exe YouTube-Comments/main.py --video ukHK1GVyr0I --limit 100
```

Đã chạy API thật ngày 11/10/2026: 100 thu thập/100 hợp lệ, 6 lượt ứng viên viết tắt thuộc 4 dạng; output trong `reports/YouTube/`. Toàn suite sau mở rộng: **30 passed, 1 warning**. Xem README module cho kết quả, tùy chọn lọc và giới hạn.
