# NV13 — Collector và Analyst phối hợp

Hai Agent sử dụng LLM thật ở chế độ live: Collector chọn tool qua Gemini function calling; Analyst suy luận và đưa yêu cầu bổ sung qua structured output. Coordinator giới hạn feedback, số bước và API budget. Mock mô phỏng quy trình để demo offline.

Cài môi trường từ [README root](../README.md). Từ root:

```powershell
.\.venv\Scripts\python.exe NV13-Multi-Agent/main.py --mode mock --topic AI --count 5
.\.venv\Scripts\python.exe NV13-Multi-Agent/main.py --mode live --topic "artificial intelligence" --count 5
```

Live cần `.env` có key. CLI chọn chủ đề/số lượng bằng tham số, output JSON/Markdown trong `reports/NV13/`. Exit 0 đủ kết quả, 2 incomplete, 1 lỗi. Không cần NV14 hoặc web. `main.py` thêm root vào import path để dùng `shared/` kể cả gọi từ thư mục khác.

Kiểm thử: `python -m pytest tests/test_foundation.py tests/test_agents.py -q` bằng venv. Kết quả đã chạy: **8 passed**. Chưa kiểm chứng API thật.

Xem [hướng dẫn](docs/HUONG_DAN_TRIEN_KHAI.md), [minh chứng](docs/MINH_CHUNG_CAN_CHUP.md), [kiến trúc chung](../docs/HUONG_DAN_TRIEN_KHAI.md).
