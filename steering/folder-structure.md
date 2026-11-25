# Folder structure

```text
backend/
  app/                 FastAPI, cấu hình, SQLite, domain services
  agents/              Prompt, session, agent orchestration và tool adapters
  data/                SQLite runtime mặc định (bị loại khỏi git)
  tests/               pytest: API, domain, contracts, eval và browser flow
  scripts/             tiện ích local/load/cache
  spike/               thử nghiệm riêng với API LLM
frontend/
  src/                 React UI, API client, SSE và UI blocks
contracts/
  schemas/             JSON Schema cho payload/event/UI block
  examples/            payload ví dụ được kiểm tra với schema
eval/                  bộ ca, scorer, runner, kết quả đã ghi
docs/                  ghi chú kỹ thuật và bản nháp nội dung nộp
data/                  hiện chỉ là placeholder; không lưu database runtime ở đây
scripts/               đóng gói source submission
steering/              quy ước project cho người và coding agent
```

## Ranh giới module

- `backend/app/main.py`: HTTP, auth, validation, rate/cost guard, SSE transport, mount frontend.
- `backend/app/`: catalog, orders, trips, memory, scam rules, persistence và domain logic. Domain không phụ thuộc React.
- `backend/agents/`: prompts, session/orchestrator và tool schemas/adapters. Agent gọi domain services; API không tự thực hiện quyết định nghiệp vụ của LLM.
- `backend/app/agent.py` và `backend/app/tools.py`: compatibility shims cho scripts/tests cũ. Code mới nên import từ package `agents`.
- `frontend/src/`: render contract; không tự tính giá, đánh giá rủi ro hay xác nhận thanh toán.
- `contracts/`: điểm đồng bộ giữa backend, agent và frontend. Đổi contract cần cập nhật cả schema, ví dụ và consumer.
- `eval/`: số liệu lưu sẵn là artifact của lần chạy trước; chỉ runner mới tạo kết quả mới.

Giữ agent runtime độc lập với HTTP framework để có thể thay API/UI mà không phải viết lại orchestration. Giữ domain services độc lập với agent để có thể kiểm tra nghiệp vụ mà không gọi LLM.
