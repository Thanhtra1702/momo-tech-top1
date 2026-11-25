# Steering

Thư mục này lưu quy ước dùng chung của project, tách khỏi mã chạy trong `backend/` và `frontend/`.

## Tài liệu

- [Tech stack](tech-stack.md): công nghệ đang dùng và các giới hạn triển khai.
- [Coding style](coding-style.md): quy tắc khi sửa backend, agent runtime và frontend.
- [Folder structure](folder-structure.md): trách nhiệm của từng thư mục và ranh giới import.

## Cách áp dụng

Coding agent nên đọc `AGENTS.md` ở root rồi đọc các tài liệu steering liên quan trước khi sửa. Đây là quy ước theo source hiện tại, không phải cam kết rằng mọi tính năng đã deploy hay đã được kiểm tra lại.

Khi đổi stack, cấu trúc hoặc contract, cập nhật tài liệu tương ứng cùng thay đổi code. Nếu tài liệu mâu thuẫn với `contracts/` hoặc hành vi đang chạy, ghi nhận điểm lệch và thống nhất contract trước khi sửa diện rộng.
