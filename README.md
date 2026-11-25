# Trợ lý AI đặt vé, du lịch và giải trí

Trợ lý hội thoại theo kiến trúc hệ thống của Muse Spark (tool-use, suy luận nhanh và sâu, đa phương thức, giao diện tương tác, cá nhân hoá, guardrails), giới hạn ở vé giải trí, vé di chuyển, lưu trú và tour. Dự thi MoMo TechDay 2026, chủ đề Trợ lý AI. Kế hoạch chi tiết: [PLAN.md](PLAN.md).

**Lưu ý:** danh mục vé, chuyến đi và khách sạn là **dữ liệu mô phỏng**. Thanh toán là mô phỏng. Trợ lý chỉ tạo đơn nháp, người dùng tự xác nhận.

## Tính năng

- Chat streaming (SSE), hai chế độ: nhanh (thinking tắt) và suy luận sâu (thinking bật).
- 18 công cụ: tìm vé giải trí, di chuyển (kể cả khứ hồi), lưu trú, tour; thời tiết (Open-Meteo); địa điểm; so sánh; lập lịch trình; bộ nhớ; tạo đơn nháp; xem đơn; kiểm tra lừa đảo; ngân sách chuyến đi (tạo, ghi chi, xem); chia tiền nhóm.
- **Kiểm tra lừa đảo:** dán tin nhắn hoặc link người bán, bộ luật tiếng Việt chỉ ra dấu hiệu (ép chuyển khoản ngoài kênh, đòi OTP, tên miền nhái thương hiệu, link rút gọn, đuôi tên miền đáng ngờ, thủ thuật `@`...) kèm bằng chứng trích từ chính nội dung. Chỉ nêu "dấu hiệu rủi ro", không kết luận ai lừa đảo.
- **Kiểm tra tài khoản liên hệ:** trang `#/account-check` nhận tên tài khoản, link hồ sơ và tin nhắn; cần đăng nhập, nêu bằng chứng rủi ro và luôn ghi rõ chưa xác minh danh tính tài khoản. Ba tình huống demo là giả định dựa trên [cảnh báo công khai](docs/account-impersonation-demo.md), không phải danh sách tài khoản lừa đảo thật.
- **Sự kiện thật:** trang `#/live-events` truy vấn trực tiếp [Ticketbox MCP](https://mcp.ticketbox.vn/) theo tên/thành phố, ghi thời điểm truy vấn và dẫn đến URL Ticketbox. Không có kết quả khớp thì báo không tìm thấy; không dùng danh mục mô phỏng để bù. Giá và chỗ trống phải kiểm tra lại trên Ticketbox. [Chi tiết](docs/live-ticketbox.md).
- **Ngân sách chuyến đi:** đơn đã xác nhận gắn với chuyến tự tính vào chi tiêu, thêm khoản chi tay, thanh tiến độ và cảnh báo từ 80%.
- **Chia tiền nhóm:** chia đều hoặc theo tỷ trọng, tổng các phần luôn khớp, soạn tin nhắn nhắc (không gửi thật).
- **Đơn của tôi:** danh sách đơn và mục "Sắp tới". Gợi ý trả lời nhanh sau mỗi kết quả. Nhập bằng giọng nói (Chrome, Edge; cần HTTPS hoặc localhost).
- Thẻ vé, bảng so sánh, dòng thời gian lịch trình, thẻ đơn nháp. Câu trả lời hiển thị markdown (đậm, danh sách).
- Vé khứ hồi (chiều đi và chiều về trong một lần tìm).
- Lưu hội thoại theo người dùng: tải lại trang hoặc khởi động lại máy chủ không mất cuộc trò chuyện. Nút Dừng khi đang trả lời.
- Đơn nháp có đồng hồ đếm ngược 30 phút.
- Gửi ảnh (đa phương thức), ảnh không lưu.
- Bộ nhớ cá nhân hoá, xem và xóa được, từ chối dữ liệu nhạy cảm.
- Trang xác nhận đơn mô phỏng, kiểm tra lại giá và chỗ khi xác nhận, deep link tới trang tìm kiếm công khai.
- Đăng nhập tài khoản dùng thử, giới hạn tần suất, trần chi phí theo ngày.

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `backend/` | FastAPI API, dịch vụ nghiệp vụ, danh mục mô phỏng, đơn hàng, xác thực và kiểm thử |
| `backend/agents/` | Prompt, session và vòng lặp điều phối agent; tách khỏi API và nghiệp vụ trong `backend/app/` |
| `frontend/` | React, Vite, TypeScript |
| `contracts/` | Schema dữ liệu, chữ ký công cụ, API, file mẫu |
| `eval/` | 55 ca đánh giá và bộ chạy (xem `eval/README.md`) |
| `docs/` | Bản nháp tài liệu nộp: hướng dẫn 1 trang, dàn ý slide, kịch bản video, kết quả thử DeepSeek |
| `scripts/` | `make_submission_zip.ps1`: tạo zip nộp và quét khóa API |

## Chạy local

Cần Python 3.11 trở lên, Node 20 trở lên.

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:LLM_API_KEY = "<khóa DeepSeek>"
.\.venv\Scripts\python -m uvicorn app.main:create_app --factory --reload --port 8000

# Frontend (cửa sổ khác)
cd frontend
npm install
npm run dev        # http://localhost:5173, proxy sang backend 8000
npm run build      # tạo frontend/dist   (backend tự tìm và phục vụ frontend/dist, không cần biến môi trường)
```

Đăng nhập bằng tài khoản dùng thử (mặc định `demo1`, `demo2`, `demo3`, mật khẩu `momo2026`, đổi bằng `DEMO_USERS`).

**Thử giao diện khi chưa có khóa DeepSeek:** `python scripts/dev_server.py 8000` (trong `backend/`, sau khi `npm run build`) chạy với LLM giả theo luật, chỉ hiểu vài mẫu câu. Không dùng cho sản phẩm thật.

Biến môi trường: xem `.env.example`. Cách dễ nhất: sao chép thành `.env` ở thư mục gốc dự án và điền `LLM_API_KEY`. Backend, script thử và bộ đánh giá tự đọc file này (biến đặt sẵn trong shell được ưu tiên). `.env` đã bị `.gitignore` và `.dockerignore` chặn.

## Kiểm thử

```powershell
cd backend;  .\.venv\Scripts\python -m pytest -q     # test backend (LLM giả, không gọi mạng)
cd frontend; npm test; npm run build                  # test logic và build, gồm kiểm tra kiểu TypeScript
```

Test giao diện thật bằng Chromium (LLM giả, không tốn chi phí) nằm trong `backend/tests/test_e2e_ui.py`. Cần `npm run build` trước và `python -m playwright install chromium` một lần, nếu thiếu thì test tự bỏ qua. Đặt `SCREENSHOT_DIR` để lưu ảnh chụp màn hình bản máy tính và điện thoại.

## Thử DeepSeek thật (cần khóa)

```powershell
cd backend
.\.venv\Scripts\python spike\deepseek_spike.py                       # chat, tool-calls kèm thinking, gửi ảnh
.\.venv\Scripts\python ..\eval\run_eval.py --estimate-only           # ước tính chi phí
.\.venv\Scripts\python ..\eval\run_eval.py --modes fast,deep         # đánh giá, ghi eval/results/latest.md
```

Ghi kết quả thử vào `docs/deepseek-spike.md`. Nếu gửi ảnh thất bại, xem mục "Ảnh" trong `docs/deepseek-spike.md`.

## Deploy

Một container: `docker build -t momo-travel .`. Image đã được build và chạy thử cục bộ (đăng nhập, chat thật, phục vụ giao diện, chạy bằng người dùng không phải root).

```powershell
docker run -d -p 8000:8000 `
  -e LLM_API_KEY="<khóa DeepSeek>" `
  -e DEMO_USERS="giamkhao:<mật khẩu từ 8 ký tự trở lên>" `
  -e ADMIN_TOKEN="<chuỗi ngẫu nhiên từ 16 ký tự>" `
  -v momo-data:/srv/backend/data `
  momo-travel
```

- Image đặt `APP_ENV=production`: **máy chủ từ chối khởi động** nếu thiếu `LLM_API_KEY`, còn dùng mật khẩu demo mặc định hoặc mật khẩu dưới 8 ký tự. Chạy local (`APP_ENV=development`) thì không bị chặn.
- Gắn volume vào `/srv/backend/data` để giữ đơn hàng, bộ nhớ và hội thoại khi deploy lại. Không gắn thì dữ liệu mất mỗi lần deploy (danh mục mô phỏng vẫn tự sinh lại).
- Cổng lấy từ `PORT`. Có `render.yaml` cho Render (chưa thử trên tài khoản thật).
- Một tiến trình, SQLite chế độ WAL: phù hợp vài chục người dùng đồng thời. Quy mô lớn hơn cần đổi sang PostgreSQL và chạy nhiều bản sao.

Thử tải với DeepSeek thật (tốn tiền, khoảng 0,003 USD mỗi lượt): `python scripts/load_test.py --sessions 9`. Kết quả đo ngày 24/11/2026: 9 phiên song song, mỗi phiên 3 lượt chat và 1 lần xác nhận đơn, 9/9 chạy hết luồng, lượt chat trung bình 4,2 giây, p95 5,8 giây.
## Đóng gói nộp bài

```powershell
pwsh scripts/make_submission_zip.ps1      # tạo momo-travel-assistant-source.zip, từ chối nếu thấy dấu hiệu lộ khóa
```

## Công nghệ và tài sản (khai báo cho bài nộp)

- Python, FastAPI, Uvicorn, SDK `openai` (trỏ về DeepSeek), httpx, SQLite
- React, Vite, TypeScript, Vitest
- LLM: DeepSeek API (`deepseek-flash`). Thời tiết: Open-Meteo (không cần khóa)
- Công cụ AI dùng khi phát triển: Kiro
- Dữ liệu: mô phỏng, sinh bằng mã (`backend/app/seed.py`). Địa điểm tham quan là danh sách tuyển chọn, tọa độ gần đúng

## Đo cache hit của DeepSeek

```powershell
cd backend
.\.venv\Scripts\python scripts\cache_probe.py     # vài cent, in prompt_cache_hit_tokens của từng yêu cầu
```
