# Kết quả kiểm thử thực tế

Ngày thực hiện: **2026-10-11**, múi giờ người dùng Asia/Saigon. Python **3.12.10**, Windows. Dependencies chính thực tế: FastAPI 0.143.0, httpx 0.28.1, google-genai 2.29.0, pytest 9.1.1; đầy đủ trong `requirements-lock.txt`.

## Test từng phase

| Phase | Test suite | Kết quả thực tế |
|---|---|---|
| 1 | test_foundation.py | 3 passed; cảnh báo cache do sandbox |
| 2 | foundation + test_agents.py | 8 passed |
| 3 | trên + test_automation.py | 11 passed |
| 4 | trên + test_web.py (ban đầu) | 15 passed, 1 warning |
| 5 | toàn bộ + test_live_contract.py + budget retention | 21 passed, 1 warning |

Lệnh cuối đã thực thi (quyền được duyệt vì sandbox Windows chặn thư mục tạm pytest):

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.tmp/pytest-final
```

Output thực tế:

```text
.....................                                                    [100%]
21 passed, 1 warning in 1.66s
```

Cảnh báo từ Starlette: dùng httpx với TestClient bị deprecate, đề xuất httpx2. Chưa chuyển dependency test vì bộ lock hiện tại chạy thành công.

## Test cases

| Nhóm | Kiểm tra |
|---|---|
| Foundation | fixture, lọc liên quan, không có kết quả, clean HTML, canonical URL, chống trùng, chặn scheme/nguồn không hợp lệ, live không có key |
| Multi-Agent | 3 nguồn fallback, 5 findings, analyst feedback 2 vòng, budget/step limit, loại ID/quote không có căn cứ, nguồn timeout vẫn thử nguồn khác |
| Automation | lưu ngày/report, skip ngày trùng, ngày khác chạy, concurrent claims chỉ một thắng, lease expired, stale owner, retry sau lỗi |
| Web | home/static/config, POST 202, Planner evaluate, JSON/MD download, lịch sử sau restart, validation 422, 404, busy 409, lỗi model, recovery, revise tối đa 1 lần, giữ báo cáo khi hết budget |
| Gemini/RSS contract | SDK types/function declarations/config, function response history, structured JSON hợp lệ/không hợp lệ, HTTP mock feed parse, timestamp UTC, HTTP 503 không fallback demo |

## Smoke test đã thực hiện

- NV13 mock `AI --count 5`: complete=True, 5 findings, báo cáo `reports/NV13/3309b43d2045439f9accac9dba136391.*`.
- NV14 mock ngày 2026-10-11: done, report ID `5ca10d0d8bc54905bc3e66339538fb93`; chạy lại skipped.
- Uvicorn: log Application startup complete, bind `127.0.0.1:8000` thành công.
- HTTP smoke qua server Uvicorn thật: run ID `8dae1a281a8a4491a7b63bd04e18fe6f`, status completed, report ID `15c3b328090f439796ee17ab792aa681`, 5 findings, 7 lượt model mô phỏng, 9 trace steps. Không phải browser UI test.
- `pip check`: No broken requirements found.

Kiểm tra PowerShell phát hiện encoding tiếng Việt không tương thích parser Windows PowerShell 5.1. Đã đổi thông báo trong scripts sang ASCII; tài liệu vẫn tiếng Việt. Parser kiểm tra lại `register_task.ps1` và `setup.ps1`: **syntax OK**. `compileall` toàn bộ source: thành công. Script Task Scheduler không được thực thi đăng ký.

Các file runtime bị ignore trong Git, có thể tái tạo bằng các lệnh README.

## Chưa kiểm chứng

- Gọi Gemini thật, quota và model availability của tài khoản người dùng.
- End-to-end RSS thật qua mạng (transport tests dùng httpx.MockTransport).
- Hiển thị/interaction trên trình duyệt: công cụ trả browser không khả dụng và inventory trống. TestClient xác minh HTTP, không xác minh visual layout.
- Scheduled execution: chỉ tạo script, không đăng ký task trên máy.

Không có ảnh hay kết quả live giả. Các test về provider live dùng placeholder key trong mock transport, không phải thông tin xác thực thật.
