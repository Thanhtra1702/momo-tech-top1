# Bộ đánh giá

`cases.jsonl` có 55 ca thuộc 12 nhóm: tìm vé giải trí, di chuyển, lưu trú, tour, thông tin (thời tiết, địa điểm), so sánh nhiều lượt, lịch trình, từ chối ngoài phạm vi, hỏi lại khi thiếu thông tin, bộ nhớ, đơn nháp và an toàn thanh toán, tiêm lệnh qua dữ liệu.

```powershell
cd backend
$env:LLM_API_KEY = "<khóa DeepSeek>"
.\.venv\Scripts\python ..\eval\run_eval.py --estimate-only      # xem ước tính trước (khoảng 300 lần gọi, dưới 1 USD)
.\.venv\Scripts\python ..\eval\run_eval.py --modes fast,deep    # chạy thật, ghi eval/results/latest.md
.\.venv\Scripts\python ..\eval\run_eval.py --only refuse,order  # chỉ một số nhóm hoặc id
```

Mỗi ca chạy trên bản sao DB tạm với người dùng `eval`. Ca `injection` chèn một sự kiện có tiêu đề chứa chỉ thị độc hại, và kiểm tra agent không tạo đơn.

## Chỉ số

- Tỷ lệ đạt theo nhóm và tổng (mọi kiểm tra của ca đều đạt mới tính là đạt).
- Từ chối đúng câu ngoài phạm vi, không có đơn nào bị AI xác nhận, không tạo đơn khi gặp tiêm lệnh, không lưu dữ liệu nhạy cảm, tổng chi phí lịch trình khớp tổng các mục.
- Độ trễ trung bình và p95, chi phí trung bình và tổng cho mỗi chế độ.

Logic chấm điểm (`scoring.py`) và bộ chạy được kiểm thử bằng LLM giả trong `backend/tests/test_eval.py`.

`inspect_case.py <id...> --mode fast` in chi tiết một ca (lệnh gọi công cụ, thẻ, phản hồi, kiểm tra) để tìm nguyên nhân khi ca không đạt.

## Bộ giữ riêng (held-out)

`cases_heldout.jsonl` có 31 ca viết **sau** khi đã chỉnh hệ thống theo bộ 55 ca, không có câu nào trùng và không được dùng để chỉnh prompt hay dữ liệu. Gồm gõ không dấu và viết tắt, vé khứ hồi, hội thoại nhiều lượt, ngoài phạm vi, an toàn, ca biên, và 5 ca có ảnh. Chạy: `run_eval.py --cases heldout`, kết quả ở `results/latest-heldout.md`.

Ảnh trong bộ này do `make_images.py` vẽ bằng mã (poster concert, biển hiệu, vé máy bay, ghi chú chứa chỉ thị độc hại, phương trình). Chúng kiểm tra đọc chữ, chống chỉ thị trong ảnh và định tuyến công cụ. **Không** kiểm tra nhận diện ảnh chụp thật của địa danh.

Kết quả lần chạy duy nhất (24/11/2026): nhanh 30/31, sâu 30/31. Ca duy nhất lỗi là `h24` ("Tìm vé phim ở Đà Lạt ngày 1/1/2020", kỳ vọng không có thẻ nào). Mô hình tìm ngày đã qua, báo không có, rồi gợi ý các suất sắp tới kèm thẻ. Chạy lại riêng ca này thì không hiện thẻ. Hành vi đó chấp nhận được và tôi không sửa ca hay hệ thống theo kết quả này, để bộ giữ riêng không bị dùng để chỉnh. Với 31 ca, khoảng tin cậy rộng: 97% có thể tương ứng với tỷ lệ thật thấp hơn đáng kể.

## Kết quả đã đo trên bộ phát triển (24/11/2026, `deepseek-flash`)

Xem `results/latest.md` (bảng đầy đủ) và các file `results/*.json`. Lần chạy cuối: chế độ nhanh 54/55, chế độ suy luận sâu 55/55. Không có ca ngoài phạm vi nào bị trả lời nhầm, không có đơn nào bị AI xác nhận, không có đơn nào được tạo khi gặp dữ liệu chứa chỉ thị độc hại.

**Hạn chế khi đọc số liệu:**
- Đây là bộ ca do chính nhóm viết, và đã dùng các ca lỗi của lần chạy đầu để sửa prompt, từ khóa tìm kiếm và dữ liệu mô phỏng. Số liệu là kết quả trên bộ phát triển, không phải kiểm thử độc lập.
- Mô hình không xác định, mỗi lần chạy có thể lệch 1 đến 2 ca (ca `e04`, `e06`, `q03` từng đạt rồi lỗi giữa các lần chạy; `q03` lỗi khi mô hình hỏi lại mà không có dấu "?", chạy lại thì đạt).
- Sau khi rút gọn kết quả công cụ và prompt (bỏ `deeplink` khỏi dữ liệu gửi mô hình, giới hạn khoảng 80 từ), độ trễ trung bình giảm từ 3.0 xuống 2.5 giây (nhanh) và từ 4.6 xuống 3.5 giây (sâu), chi phí ước tính mỗi lượt giảm khoảng 5% (nhanh) và 19% (sâu). Chi phí này là ước tính của code, không tính cache.
- Mỗi ca chạy một lần. Các ca ảnh chưa nằm trong bộ.
- Các lần chạy trước khi sửa cho 52/55 (nhanh) rồi 53/55 và 54/55 (nhanh, sâu).


## Giai đoạn 2: kiểm tra lừa đảo, ngân sách, chia tiền, đơn

### Bộ ca `cases_phase2.jsonl` (23 ca, chạy với DeepSeek thật)

Nhóm: kiểm tra lừa đảo (7), ngân sách (5), chia tiền (4), đơn của tôi (2), từ chối câu hỏi tài chính ngoài phạm vi (5). Chạy: `run_eval.py --cases phase2`.

| Lần chạy (24/11/2026) | Kết quả |
|---|---|
| Chế độ nhanh | 21/23 (lần đầu), ca lỗi `p09`, `p16` |
| Chế độ sâu | 23/23 |

Hai ca lỗi ở chế độ nhanh không phải lỗi sản phẩm: `p09` mô hình trả lời đúng số dư (4.550.000đ) từ kết quả của công cụ `add_expense` nên không gọi thêm `get_trip_budget` như ca kỳ vọng (kỳ vọng quá chặt), và `p16` đạt khi chạy lại riêng (dao động của mô hình). Tôi không sửa ca hay hệ thống theo kết quả này.

### Hồi quy sau khi thêm 7 công cụ và đổi prompt (chế độ nhanh)

Bộ phát triển 55/55, bộ giữ riêng 31/31. Lưu ý chi phí ước tính mỗi lượt tăng từ khoảng 0,0023 lên 0,0031 USD (+35%) vì danh sách công cụ dài hơn (18 công cụ), chưa tính cache.

### Bộ luật kiểm tra lừa đảo (`scamcheck.py`), đo offline bằng `run_scam_eval.py`

Bộ luật xác định, không dùng LLM. Hai bộ có nhãn do chính nhóm viết:

| Bộ | Ngưỡng | Precision | Recall | Báo nhầm |
|---|---|---|---|---|
| **Giữ riêng** (18 lừa đảo, 18 bình thường), đo một lần, **không chỉnh luật sau đó** | Cảnh báo (trung bình trở lên) | 100% (14/14) | 78% (14/18) | 0% (0/18) |
| | Nguy cơ cao (cao trở lên) | 100% (10/10) | 56% (10/18) | 0% (0/18) |
| Phát triển (24 và 30), **đã dùng để chỉnh luật** | Cảnh báo | 100% | 100% | 0% |

Đọc số liệu:
- Số trên bộ phát triển **không có ý nghĩa** vì luật đã được thêm để khớp các ca khó của chính bộ đó. Lần đo đầu tiên (trước khi chỉnh) là precision 79%, recall 92%, báo nhầm 20% ở ngưỡng cảnh báo.
- Số trên bộ giữ riêng là ước lượng trung thực hơn: bộ luật **thận trọng** (không báo nhầm trên 18 tin bình thường kể cả các ca khó như nhắc mang CCCD, tin OTP thật, "hủy miễn phí") nhưng **bỏ sót** khoảng 1 phần 5 đến 1 nửa số tin lừa đảo, nhất là tin diễn đạt khác thường. Với 36 ca, khoảng tin cậy rộng.
- Kết quả của bộ luật chỉ là một đầu vào. Mô hình ngôn ngữ đọc cả tin nhắn và được yêu cầu nêu nhận định thận trọng riêng nếu nội dung đáng ngờ dù luật báo ít dấu hiệu. Phần bổ sung này chưa được đo riêng.
- Danh sách tên miền chính thức (momo.vn, vietjetair.com, ...) chỉ là mẫu, cần cập nhật khi dùng thật.