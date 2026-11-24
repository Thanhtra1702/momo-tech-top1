# Dàn ý slide (tối đa 10 trang, xuất PDF)

> Slide không sửa được sau khi nộp. Chỉ đưa số liệu đã đo từ `eval/results/` và `eval/README.md`. Không đưa số liệu chưa đo. Nói rõ các hạn chế, vì ban giám khảo sẽ tự thử.

1. **Tiêu đề.** Trợ lý chuyến đi trên ví MoMo: một hành trình từ lúc muốn đi đến lúc về. Chủ đề: Trợ lý AI và Chống lừa đảo. Tên nhóm, link sản phẩm.
2. **Vấn đề.** Đặt chuyến đi hay buổi giải trí phải mở nhiều app, so giá thủ công, dễ chốt nhầm, dễ gặp người bán lừa đảo, rồi lại tự theo dõi chi tiêu và chia tiền với bạn bè. Mỗi bước một công cụ riêng.
3. **Giải pháp.** Một trợ lý hội thoại đi cùng cả hành trình: tìm và so sánh (mua sắm), lập lịch và nhớ sở thích (cá nhân), kiểm tra người bán (chống lừa đảo), xác nhận và chia tiền (thanh toán), theo dõi ngân sách (tài chính). Người dùng luôn giữ quyền bấm xác nhận.
4. **Demo luồng chính.** Ảnh chụp: câu nhu cầu → thẻ vé → dán tin nhắn người bán → báo cáo rủi ro → đơn nháp → xác nhận → ngân sách và chia tiền.
5. **Kiến trúc theo Muse Spark.** Bảng ánh xạ: đa phương thức, tool-use (18 công cụ), suy luận nhanh và sâu, giao diện tương tác, cá nhân hoá, guardrails. Nói rõ: Muse Spark là mô hình đóng, nhóm dựng lại các lớp hệ thống, không sao chép kiến trúc mạng.
6. **AI là cốt lõi, nhưng không bịa số.** DeepSeek `deepseek-flash` hiểu nhu cầu, chọn công cụ, đọc ảnh, diễn giải. Mọi con số (giá, chỗ, tổng chi phí, ngân sách, chia tiền) do code và SQL tính, kiểm thử bằng thuộc tính (tổng các phần luôn khớp).
7. **Chống lừa đảo.** Bộ luật tiếng Việt và phân tích link (tên miền nhái thương hiệu, link rút gọn, thủ thuật `@`, đuôi lạ). Báo cáo kèm bằng chứng trích từ chính tin nhắn, chỉ nói "dấu hiệu rủi ro". Số liệu trên bộ giữ riêng: precision 100%, báo nhầm 0%, recall 78% (cảnh báo) và 56% (nguy cơ cao). Nói thẳng: bỏ sót tin diễn đạt khác thường.
8. **An toàn theo thiết kế.** Agent chỉ tạo đơn nháp, không có công cụ thanh toán. Kiểm tra lại giá và chỗ khi xác nhận. Chống chỉ thị độc hại trong dữ liệu và ảnh. Bộ nhớ từ chối dữ liệu nhạy cảm. Từ chối tư vấn đầu tư, vay, thuế. Giới hạn tần suất và trần chi phí.
9. **Kết quả đánh giá.** Bảng từ `eval/results/` và `eval/README.md`: ba bộ ca (phát triển 55, giữ riêng 31, giai đoạn 2 gồm 23), từ chối đúng, không đơn nào bị AI xác nhận, độ trễ và chi phí mỗi lượt, thử tải 9 phiên song song. Ghi chú: bộ ca do nhóm tự viết, mẫu nhỏ, mô hình có dao động giữa các lần chạy.
10. **Hạn chế và hướng phát triển.** Dữ liệu vé và thanh toán là mô phỏng. Hướng phát triển: nối API đối tác và ví MoMo thật (xác thực hai lớp), bổ sung bộ nhận diện lừa đảo bằng mô hình, dữ liệu thật cho danh sách tên miền chính thức, điều phối nhiều agent. Thông tin thành viên.
