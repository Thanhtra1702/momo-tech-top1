# Hướng dẫn cho coding agent

Đọc `steering/README.md` trước khi thay đổi code. Các quy ước project nằm trong `steering/tech-stack.md`, `steering/coding-style.md` và `steering/folder-structure.md`.

`README.md`, `PLAN.md` và `contracts/` mô tả tính năng, trạng thái và hợp đồng hiện tại. Khi nội dung kế hoạch khác hành vi code, kiểm tra code và contract trước khi kết luận. Không coi số liệu đánh giá đã ghi trong tài liệu là kết quả vừa được chạy lại.

Giữ rõ các giới hạn demo: danh mục vé là dữ liệu mô phỏng; xác nhận đơn không thu tiền; API ngoài chỉ dùng đúng nơi đã khai báo. Không đưa bí mật vào git. SQLite runtime mặc định ở `backend/data/app.db` khi chạy từ `backend/`, đổi bằng `DB_PATH`; `data/` ở root không phải database. Phim giả lập vẫn có trong seed để kiểm thử cũ nhưng agent không được gợi ý hoặc tạo đơn phim từ đó; hướng người dùng tới `#/cinema` và website rạp.
