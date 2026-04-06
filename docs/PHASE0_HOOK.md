# Phase 0: The Hook

Tài liệu này là bản triển khai thực tế cho Phase 0 của chủ đề **School Nutrition Optimizer**.

Mục tiêu của Phase 0 là tạo một màn demo ngắn để chứng minh rằng chatbot có thể trả lời trông hợp lý, nhưng không đáng tin cậy khi phải xử lý bài toán nhiều ràng buộc như thực đơn bán trú.

---

## 1. Mục tiêu buổi demo

Người nghe cần hiểu ngay 3 ý:
- Chatbot làm tốt các câu hỏi đơn giản.
- Chatbot yếu khi phải xử lý nhiều ràng buộc cùng lúc.
- Vì vậy nhóm cần chuyển từ chatbot sang agent có tool và cơ chế kiểm tra từng bước.

---

## 2. Kịch bản demo 15 phút

### 2.1 Mở bài (2 phút)

Nội dung nói:

> Bài toán của chúng ta không phải chỉ là gợi ý món ăn.  
> Hệ thống cần lên thực đơn cho khoảng 800 học sinh, có ngân sách theo ngày, có dị ứng sữa và trứng, cần đủ dinh dưỡng, và tránh lặp món quá sát nhau.  
> Đây là bài toán ra quyết định dưới nhiều ràng buộc, không chỉ là bài toán viết câu trả lời nghe hợp lý.

Thông điệp cần chốt:
- Đây không phải bài "model nói hay".
- Đây là bài "hệ thống có kiểm tra và hành động đúng hay không".

### 2.2 Demo câu hỏi đơn giản (3 phút)

Prompt dùng để demo:

```text
Gợi ý một bữa trưa đủ dinh dưỡng cho học sinh tiểu học.
```

Điều cần quan sát:
- Chatbot thường trả lời khá ổn.
- Câu trả lời có thể gồm cơm, món mặn, rau, canh, trái cây.
- Người nghe sẽ thấy chatbot có vẻ hữu ích ở bài toán đơn giản.

Điểm cần nói sau khi chatbot trả lời:

> Với yêu cầu đơn giản như thế này, chatbot có thể đủ dùng vì chưa phải kiểm tra nhiều ràng buộc hay gọi hành động nào đặc biệt.

### 2.3 Demo câu hỏi nhiều ràng buộc (6 phút)

Prompt chính:

```text
Lập thực đơn 5 ngày cho 800 học sinh, ngân sách 28.000đ/ngày/em, có nhóm dị ứng sữa và trứng, không lặp món 2 ngày liên tiếp, rồi kiểm tra calories, protein, fiber và gợi ý món thay thế cho các trường hợp dị ứng.
```

Khi chatbot trả lời, người demo cần đọc kết quả và chỉ ra 4 dấu hiệu fail:
- Không chứng minh được menu có thật sự nằm trong ngân sách.
- Phân tích dinh dưỡng mang tính ước lượng, thiếu kiểm chứng hoặc không nhất quán.
- Món thay thế cho dị ứng bị bỏ sót hoặc không tách rõ theo dị ứng sữa và dị ứng trứng.
- Có khả năng lặp món hoặc chồng nguyên liệu mà chatbot không tự phát hiện.

Nếu chatbot trả lời quá đẹp, dùng ngay 2 prompt follow-up:

```text
Hãy chỉ rõ bảng calories/protein/fiber theo từng ngày và giải thích món thay thế nào dành cho dị ứng sữa, món nào dành cho dị ứng trứng.
```

```text
Kiểm tra lại xem có món nào lặp trong 2 ngày liên tiếp không.
```

Mục tiêu của phần này:
- Làm lộ ra việc chatbot không có cơ chế kiểm tra độc lập.
- Chatbot chỉ tiếp tục sinh văn bản, chứ không thật sự kiểm toán menu.

### 2.4 Chốt insight (4 phút)

Nội dung nói:

> Chatbot mạnh ở việc tạo ra câu trả lời tự nhiên.  
> Nhưng bài toán này cần một chuỗi hành động rõ ràng: sinh menu, kiểm tra dinh dưỡng, kiểm tra dị ứng, thay thế món, rồi kiểm tra lại ràng buộc.  
> Chúng ta không cần model nói hay hơn. Chúng ta cần hệ thống biết kiểm tra và hành động từng bước.

Câu chuyển sang Phase 1:

> Vì chatbot không tự kiểm tra được các ràng buộc, chúng ta cần thiết kế tools để agent xử lý từng bước.

---

## 3. Checklist chuẩn bị trước buổi demo

### 3.1 Nguồn chạy demo
- Có thể dùng một chat UI LLM bất kỳ.
- Hoặc dùng provider từ repo sau này khi có giao diện one-shot đơn giản.
- Phase 0 không bắt buộc phải có `chatbot.py`.

### 3.2 Prompt cần khóa sẵn
- 1 prompt đơn giản.
- 1 prompt nhiều ràng buộc.
- 2 prompt follow-up.

Khuyến nghị:
- Lưu sẵn trong một file riêng để copy-paste nhanh.
- Không đổi prompt trong lúc demo để tránh làm loãng thông điệp.

### 3.3 Checklist quan sát
- Có ngân sách cụ thể theo ngày không.
- Có bảng dinh dưỡng theo từng ngày không.
- Có tách rõ dị ứng sữa và dị ứng trứng không.
- Có kiểm tra trùng món 2 ngày liên tiếp không.

### 3.4 Phương án dự phòng

Nếu chatbot trả lời có vẻ khá tốt ở lần đầu, thêm ràng buộc phụ:

```text
Mỗi ngày phải có món mặn, món rau, canh và trái cây; không dùng món chiên quá 2 lần/tuần.
```

Mục tiêu:
- Tăng độ phức tạp để chatbot dễ lộ việc không kiểm chứng được toàn bộ ràng buộc.

---

## 4. Bảng quan sát lỗi chatbot

| Dấu hiệu | Cách nhận biết | Vì sao đây là fail |
| :--- | :--- | :--- |
| Không kiểm chứng ngân sách | Chatbot nêu menu nhưng không có cách tính chi phí theo ngày hoặc theo suất | Không chứng minh được menu phù hợp ngân sách 28.000đ/ngày/em |
| Dinh dưỡng thiếu tin cậy | Chatbot nêu calories/protein/fiber nhưng không rõ nguồn hoặc số liệu thiếu nhất quán | Bài toán yêu cầu kiểm tra, không chỉ ước lượng |
| Dị ứng xử lý chưa đủ | Không tách riêng thay thế cho dị ứng sữa và dị ứng trứng, hoặc bỏ sót một số món | Có rủi ro an toàn thực tế cho học sinh |
| Không tự phát hiện trùng món | Chatbot không phát hiện món lặp hoặc nguyên liệu lặp sát nhau | Không đảm bảo yêu cầu vận hành thực đơn |

---

## 5. Test plan cho Phase 0

### Scenario 1
- Input: `Gợi ý một bữa trưa đủ dinh dưỡng cho học sinh tiểu học.`
- Pass: chatbot trả lời hợp lý, ngắn gọn, dễ hiểu.

### Scenario 2
- Input: prompt lập thực đơn 5 ngày với ngân sách, dị ứng, không lặp món, phân tích dinh dưỡng.
- Pass: người demo chỉ ra được ít nhất 3 trong 4 dấu hiệu fail trong bảng quan sát.

### Scenario 3
- Input: 2 prompt follow-up yêu cầu chứng minh bảng dinh dưỡng và kiểm tra trùng món.
- Pass: chatbot bộc lộ sự thiếu nhất quán, thiếu kiểm chứng, hoặc tiếp tục trả lời chung chung.

---

## 6. Tiêu chí thành công

Phase 0 được xem là thành công khi:
- Người nghe hiểu ngay sự khác biệt giữa chatbot và agent.
- Có ít nhất 1 ví dụ cụ thể chatbot bỏ sót hoặc không chứng minh được ràng buộc.
- Demo tạo được động lực rõ ràng để bước sang Phase 1: Tool Design.

---

## 7. Ghi chú triển khai

- Phase 0 không yêu cầu chỉnh sửa public API hay code lõi trong `src/`.
- Nếu cần lưu dấu vết, chỉ cần lưu prompt và checklist trong thư mục `docs/`.
- Thành công của Phase 0 được đo bằng độ rõ của insight, không phải số dòng code.
