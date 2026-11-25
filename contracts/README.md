# Hợp đồng giữa backend, agent và frontend

Chỉ sửa khi cập nhật đồng thời backend, frontend và `contracts/examples/`. Test `backend/tests/test_contracts.py` kiểm tra mọi file mẫu hợp lệ với schema, và các test khác kiểm tra dữ liệu thật do backend sinh ra cũng hợp lệ.

## Schema dữ liệu (`schemas/`)
`event`, `transport`, `lodging`, `tour`, `order_draft`, `ui_block`, `sse_event`. Tiền tệ là số nguyên VND. Thời gian theo ISO 8601 có múi giờ +07:00. `deeplink` là link tìm kiếm công khai của bên thứ ba với truy vấn điền sẵn (không phải API đặt vé).

## Công cụ của agent (đã cài ở `backend/app/tools.py`)

| Công cụ | Tham số chính | Kết quả |
|---|---|---|
| `search_events` | `query?`, `kind?` (movie/concert/event), `city?`, `date_from?`, `date_to?`, `max_price_vnd?`, `limit`, `sort_by` | `ticket_cards` |
| `search_transport` | `origin`, `destination`, `date?`, `return_date?` (khứ hồi), `mode?` (flight/train/bus), `max_price_vnd?`, `limit`, `sort_by` | `ticket_cards`; khứ hồi có thêm nhãn "Chiều đi"/"Chiều về" và tổng rẻ nhất mỗi người |
| `search_lodging` | `city`, `check_in?`, `check_out?`, `max_price_per_night_vnd?`, `amenities?`, `kind?`, `limit`, `sort_by` | `ticket_cards` + tổng ước tính theo số đêm |
| `search_tours` | `city?`, `max_price_per_person_vnd?`, `max_days?`, `query?`, `limit`, `sort_by` | `ticket_cards` |
| `get_weather` | `city`, `date?` | `{temp_c, sky, rain_chance_pct, source}`; `source` là `open-meteo` hoặc `estimate` |
| `get_places` | `city`, `category?` | danh sách địa điểm tuyển chọn |
| `compare_options` | `ref_ids[2..5]` cùng loại | `comparison_table` + mục nên chọn |
| `build_itinerary` | `city`, `days`, `budget_vnd`, `guests`, `start_date`, `origin?`, `preferences?` | `itinerary`, tổng = tổng các mục |
| `save_preference` | `key` (danh sách cho phép), `value` | `{saved}` |
| `recall_memory` | không | `{memory}` |
| `create_order_draft` | `items[{ref_id, quantity}]`, `trip?` (tên hoặc mã chuyến để tính vào ngân sách) | `order_draft` (chỉ trạng thái `draft`) |
| `get_my_orders` | không | đơn gần đây và các mục sắp diễn ra |
| `check_scam` | `text` (nguyên văn tin nhắn hoặc link) | `risk_report`: mức, điểm, dấu hiệu kèm trích dẫn, đánh giá từng link, lời khuyên. Luật xác định, không gọi LLM |
| `create_trip` | `name`, `budget_vnd` | `budget_status` |
| `set_trip_budget` | `trip?`, `budget_vnd` | `budget_status` |
| `add_expense` | `trip?`, `label`, `amount_vnd`, `category?`, `paid_by?` | `budget_status` |
| `get_trip_budget` | `trip?` | `budget_status`. Chi tiêu = đơn ĐÃ XÁC NHẬN gắn chuyến + khoản ghi tay, đơn nháp không tính |
| `split_bill` | `total_vnd` hoặc `trip`, `people[2..20]`, `payer?`, `weights?`, `label?` | `split_result`. Tổng các phần luôn khớp tổng tiền. Chỉ soạn tin nhắn nhắc, không gửi thật |

Ảnh không phải công cụ. Người dùng gửi ảnh kèm tin nhắn, `deepseek-flash` đọc trực tiếp (đa phương thức gốc). Ảnh không lưu đĩa và không giữ trong lịch sử.

Quy tắc an toàn:
- Không có công cụ nào đặt đơn sang `confirmed`. Chỉ `POST /orders/{id}/confirm` do người dùng bấm mới làm việc đó.
- `create_order_draft` chỉ nhận `ref_id` đã hiển thị cho người dùng trong phiên, hoặc do chính người dùng nêu và có trong danh mục.
- Kết quả công cụ được gói trong `{"data": ..., "_note": "..."}` để mô hình coi là dữ liệu, không phải chỉ thị.

## API HTTP

| Phương thức, đường dẫn | Xác thực | Mô tả |
|---|---|---|
| `GET /health` | không | `{"status":"ok"}` |
| `GET /samples` | không | `{prompts: string[]}` câu mẫu |
| `POST /auth/login` | không | Body `{username, password}`, trả `{token, username}`. Giới hạn 10 lần/5 phút |
| `GET /auth/me`, `GET /usage` | Bearer | Người dùng hiện tại, chi phí trong ngày |
| `POST /chat` | Bearer | Body `{message, mode: "fast"\|"deep", session_id, image?: {mime, data(base64)}}`. Trả `text/event-stream`, mỗi dòng `data:` là một `sse_event`. 409 nếu phiên đang xử lý, 429 khi vượt tần suất hoặc trần chi phí, 503 khi thiếu khóa LLM |
| `GET /orders` | Bearer | `{orders, upcoming}`: mọi đơn của người dùng (mới nhất trước) và các mục đã xác nhận sắp diễn ra |
| `GET /conversations/latest` | Bearer | Cuộc trò chuyện gần nhất để khôi phục sau khi tải lại trang |
| `GET /orders/{id}` | Bearer | `order_draft` của chính người dùng, 404 nếu không phải của họ |
| `POST /orders/{id}/confirm` | Bearer | Xác nhận mô phỏng. 409 nếu giá đổi, hết chỗ hoặc đơn hết hạn (30 phút) |
| `GET/PUT/DELETE /memory`, `DELETE /memory/{key}` | Bearer | Xem, thêm, xóa bộ nhớ cá nhân |
| `GET /admin/costs` | Header `X-Admin-Token` | Chi phí theo người dùng trong ngày. 404 nếu chưa đặt `ADMIN_TOKEN` |
| `POST /risk/account-check` | Bearer | Body `{account_name, profile_url?, message?}`; trả `{account_name, identity_status: "unverified", report: risk_report}`. Kiểm tra dấu hiệu trong dữ liệu người dùng cung cấp, không xác minh danh tính với nền tảng ngoài |

Lỗi trả JSON `{"detail": "..."}` bằng tiếng Việt, không chứa chi tiết nội bộ hay khóa API.
