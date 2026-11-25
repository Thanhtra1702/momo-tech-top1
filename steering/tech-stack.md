# Tech stack

## Runtime hiện tại

- Backend: Python 3.12, FastAPI, Uvicorn.
- Database: SQLite; WAL được bật cho database file.
- LLM: SDK `openai` gọi API tương thích OpenAI, mặc định DeepSeek `deepseek-flash`; cấu hình bằng biến môi trường.
- Streaming: Server-Sent Events (SSE) cho phản hồi chat.
- Frontend: React 18, Vite, TypeScript.
- Frontend tests/build: Vitest và TypeScript compiler.
- Backend tests: pytest; JSON contracts được kiểm tra bằng `jsonschema`.
- Packaging: Docker đa giai đoạn, frontend build được FastAPI phục vụ.
- Hosting: có `render.yaml`; tài liệu hiện ghi deployment công khai chưa hoàn tất/chưa xác nhận.

## Dịch vụ ngoài

- Open-Meteo cho dự báo thời tiết; khi lỗi hoặc ngày ngoài cửa sổ dự báo, backend trả ước tính khí hậu và ghi rõ nguồn là `estimate`.
- Ticketbox MCP cho tra cứu sự kiện live chỉ đọc. Khi nguồn lỗi, API live trả lỗi rõ ràng, không thay bằng dữ liệu catalog mô phỏng.
- Deep link đối tác hiện là trang tìm kiếm công khai; backend không đặt vé qua đối tác.

## Cấu hình và giới hạn

- Secrets chỉ qua environment (ví dụ `LLM_API_KEY`, `ADMIN_TOKEN`); `.env` dùng local và không commit.
- Mọi giá, ngân sách, tồn kho và chia tiền được tính bằng code/SQL, không giao cho LLM.
- Danh mục và đơn hàng là dữ liệu demo. Xác nhận đơn chỉ đổi trạng thái mô phỏng, không trừ tiền.
- App hiện thiết kế cho một tiến trình và SQLite. Rate limiter giữ trong bộ nhớ; không xem đó là giới hạn dùng chung cho nhiều instance.
