# Tra cứu sự kiện thật qua Ticketbox MCP

Trang `#/live-events` gọi `GET /live/events` có Bearer token, backend gọi trực tiếp [Ticketbox MCP](https://mcp.ticketbox.vn/) mỗi lần người dùng bấm tra cứu. Không dùng cache của ứng dụng. Kết quả có `checked_at`, giá từ (nếu nguồn trả về), thời gian bắt đầu và URL sự kiện trên `ticketbox.vn`. Người dùng tự kiểm tra tình trạng cuối cùng và mua trên Ticketbox. Theo [điều khoản connector](https://mcp.ticketbox.vn/terms), dữ liệu có thể đổi và connector không đặt vé hoặc thanh toán.

Kết quả từ catalog trong chat **vẫn là mô phỏng** và được ghi rõ trên thẻ. Không chuyển dữ liệu giả thành “live” hoặc tạo đơn mô phỏng cho sự kiện thật. Khi nguồn live lỗi, API trả 503 thay vì đưa dữ liệu giả. Tìm kiếm theo tên được kiểm tra lại sau khi nguồn trả về, vì nguồn có thể trả sự kiện không khớp khi không tìm thấy tên.

Nguồn hiện chỉ bao phủ sự kiện Ticketbox. Với phim, công cụ chat không trả kết quả từ phim giả lập nữa; mục `#/cinema` dẫn đến trang phim của [CGV](https://www.cgv.vn/default/movies/now-showing.html), [Galaxy Cinema](https://www.galaxycine.vn/phim-dang-chieu/) và [Lotte Cinema](https://www.lottecinemavn.com/LCHS/Contents/Movie/Movie-List.aspx). Người dùng kiểm tra lịch, giá, ghế và đặt tại rạp. Chuyến bay, phòng và tour cũng cần API được cấp quyền từ nhà cung cấp; ví dụ [Traveloka Partners Network](https://developer.travelokapartnersnetwork.com/) yêu cầu đăng ký đối tác. Không thể tuyên bố giá/tồn kho của các nhóm này là thời gian thực khi chưa có quyền truy cập.

## Chạy thử

Sau khi chạy backend và frontend theo `README.md`, đăng nhập và mở `http://localhost:5173/#/live-events`. Tìm `Lời Thề Biển Xanh`: nếu nguồn không có tên này, kết quả phải rỗng; không hiển thị phim giả trong luồng live. Để kiểm tra sự kiện đang có trên nguồn, để trống tên và bấm **Tra cứu ngay**, hoặc tìm tên từ Ticketbox.

```powershell
cd D:\Antigravity\MOMO\backend
python -m pytest -q tests/test_live_events.py
```
