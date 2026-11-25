# Demo cảnh báo tài khoản tự xưng là đối tác đặt vé/đặt phòng

## Phạm vi

`POST /risk/account-check` nhận tên tài khoản, link hồ sơ và tin nhắn. API bắt buộc Bearer token của ứng dụng; không gọi LLM, không tải trang hồ sơ, không lưu nội dung kiểm tra. Kết quả luôn là `identity_status: unverified`: chưa có tích hợp xác minh chủ tài khoản từ Agoda/Traveloka/MoMo. Điểm rủi ro là luật demo, không phải xác suất hay danh sách đen tài khoản thật. Trang `#/account-check` có ba tình huống **giả định** để thử.

## Mẫu tình huống dựa trên cảnh báo công khai

1. Người tự xưng hỗ trợ Agoda dọa hủy đặt phòng, chuyển sang Zalo và xin OTP: cảnh báo cao, nêu bằng chứng trong tin nhắn. [Agoda Help Center](https://www.agoda.com/info/contact.html) khuyên trao đổi trong kênh Agoda và không cung cấp OTP; [Agoda Partner Hub](https://www.partnerhub.agoda.com/cyber-attacks-how-can-you-keep-your-hotel-and-your-customers-safe/) mô tả tin nhắn dọa hủy booking kèm link thanh toán giả.
2. Tài khoản tự xưng Traveloka dùng domain chứa tên thương hiệu nhưng khác `traveloka.com`, đòi chuyển khoản cá nhân: cảnh báo domain không khớp và thanh toán ngoài kênh. Đây là **tình huống tổng hợp**, không gắn với tài khoản hay sự cố cụ thể.
3. Khách sạn gửi thông tin giá và chính sách hủy bình thường: không tự kết luận an toàn, vẫn ghi chưa xác minh danh tính. Cách này giảm báo động nhầm khi chỉ có tên tài khoản.

MoMo cũng [cảnh báo](https://www.momo.vn/hoi-dap/nhan-biet-dau-hieu-lua-dao-nhu-the-nao) các tài khoản/nhân viên giả mạo yêu cầu OTP, mật khẩu và thông tin tài khoản. Các nguồn trên cung cấp **mẫu hành vi**, không cung cấp API xác thực tài khoản hay tập dữ liệu gán nhãn cho các ví dụ trong demo.

## Thử qua API local

Từ thư mục gốc repo:

```powershell
cd frontend
npm ci
npm run build
cd ../backend
python -m pip install -r requirements-dev.txt
python scripts/dev_server.py 8000
```

Mở `http://localhost:8000/#/account-check`, đăng nhập `demo1` / `momo2026`, chọn một tình huống và bấm **Kiểm tra dấu hiệu**. Endpoint không cần khóa DeepSeek.

Để thử nội dung nghi vấn thực tế của chính bạn, nhập tên tài khoản và dán nguyên văn link/tin nhắn vào biểu mẫu. Không cần gửi mật khẩu, OTP, số thẻ hay giấy tờ vào công cụ.

Kiểm thử tự động:

```powershell
cd backend
python -m pytest -q tests/test_accountcheck.py
python -m pytest -q tests/test_e2e_ui.py -k account_check_demo
python ../eval/run_scam_eval.py --heldout
```

Test giao diện cần `python -m playwright install chromium` một lần; các ca này dùng Chromium local và không gọi LLM hay đối tác thật.
