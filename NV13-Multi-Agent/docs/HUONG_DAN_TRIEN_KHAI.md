# Triển khai NV13

1. Cài venv/dependencies theo README root; dùng `.env` mock mặc định.
2. Chạy `NV13-Multi-Agent/main.py --mode mock --topic AI --count 5` bằng Python venv.
3. Mở hai đường dẫn report CLI in ra, kiểm tra mode, source, quote và trace.
4. Chạy `--topic nonexistentxyz --count 5`: không có bài mẫu phù hợp, Analyst yêu cầu bổ sung, workflow dừng sau giới hạn với exit code 2.
5. Chuyển live khi đã tự điền key; chọn chủ đề phù hợp RSS tiếng Anh như `artificial intelligence`. Bài ít hơn yêu cầu là tình huống hợp lệ, không phải lý do dùng fixture trong live.

Collector gọi `fetch_rss(source)` hoặc `finish_collection(article_ids,rationale)` do LLM chọn. Tool result được trả về LLM. Analyst trả category/summary/quote và needs_more/followup_topic; các ID/quote sai bị loại. Code chung: `shared/llm.py`, `rss.py`, `agents.py`, `models.py`.

Đã chạy 8 test foundation/agents, tất cả pass. Tests dùng mock; [báo cáo cuối](../../docs/KET_QUA_KIEM_THU.md) bao gồm kiểm thử contract Gemini SDK. Xem [triển khai chung](../../docs/HUONG_DAN_TRIEN_KHAI.md) cho cấu hình và xử lý lỗi.
