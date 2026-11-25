# Coding style

## Quy tắc chung

- Ưu tiên thay đổi nhỏ, có ranh giới rõ; cập nhật contract và tài liệu khi API hoặc schema đổi.
- Tên và giao diện người dùng viết tiếng Việt tự nhiên. Tên module, biến và API dùng tiếng Anh nhất quán.
- Không đưa secret, dữ liệu cá nhân hoặc nội dung ảnh vào log. Lỗi trả cho người dùng không chứa stack trace hay khóa.
- Xem mô tả sản phẩm, đánh giá, URL và văn bản người dùng là dữ liệu không tin cậy; không coi chúng là chỉ thị cho agent.
- Không dùng `dangerouslySetInnerHTML` cho nội dung LLM. Chỉ cho mở URL HTTPS sau khi kiểm tra scheme.
- Không tuyên bố shop là lừa đảo; báo dấu hiệu cụ thể, kèm bằng chứng và giới hạn của phân tích.

## Backend Python

- Dùng 4 dấu cách, type hints cho API/logic dùng chung, `snake_case` cho hàm và biến, `PascalCase` cho class.
- Giữ endpoint mỏng: xác thực/validate/request-response ở API; phép tính và quy tắc miền ở service; orchestration và tool adapter của LLM ở `backend/agents/`.
- Dùng parameterized SQL, transaction cho cập nhật nhiều bảng và lỗi nghiệp vụ rõ ràng.
- Tiền dùng số nguyên VND; thời điểm nghiệp vụ dùng ISO 8601 với múi giờ Việt Nam khi hiển thị/tra cứu.
- Giữ output theo schema trong `contracts/`; không để LLM tự đặt giá, tồn kho, tổng tiền hay trạng thái thanh toán.

## Frontend TypeScript/React

- Dùng TypeScript cho API payload và UI blocks; `PascalCase` cho component, `camelCase` cho hàm/biến.
- Giữ parser/render nội dung LLM an toàn, không chèn HTML thô.
- Hiển thị rõ trạng thái tải, lỗi, dữ liệu mô phỏng và hành động cần người dùng xác nhận.

## Thay đổi có ảnh hưởng

- Khi đổi SSE event, tool, API hay UI block, cập nhật đồng thời backend, frontend, `contracts/schemas/` và ví dụ liên quan.
- Khi đổi schema SQLite, thêm migration tương thích với database đã có; tránh xóa dữ liệu người dùng trong lúc seed danh mục.
