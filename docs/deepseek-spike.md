# Kết quả thử DeepSeek (Task 1)

Chạy ngày 24/11/2026 với `deepseek-flash`, base URL `https://api.deepseek.com`, bằng `backend/spike/deepseek_spike.py`.

| Kiểm tra | Kết quả | Ghi chú |
|---|---|---|
| 1. Chat thường, thinking tắt | PASS | |
| 2. Tool-calls kèm thinking, gửi lại `reasoning_content` | PASS | API chấp nhận message assistant có `reasoning_content` ở lượt kế |
| 3. Gửi ảnh (`image_url` với data URL) vào `deepseek-flash` | PASS | Ảnh PNG đơn sắc đỏ 64x64, mô hình trả lời đúng màu đỏ |

Cũng đã kiểm tra chạy thật qua server (`uvicorn`): streaming, tool-calling nhiều bước, chế độ suy luận sâu, tạo đơn nháp rồi xác nhận, từ chối câu ngoài phạm vi, ghi nhận chi phí. Một lượt tìm vé tốn khoảng 6 giây ở chế độ nhanh.

Chưa kiểm tra: giới hạn kích thước ảnh của API (mã đang giới hạn 4 MB phía máy chủ), ảnh thật (poster, ảnh địa điểm) thay vì ảnh đơn sắc, `usage` trong chế độ stream với ảnh.

## Ảnh

Nếu sau này ảnh thất bại: đặt `IMAGES_ENABLED=false`. Nút gửi ảnh sẽ ẩn, máy chủ trả 422 cho yêu cầu có ảnh, phần còn lại không ảnh hưởng.
