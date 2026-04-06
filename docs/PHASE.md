# Hướng Dẫn Công Việc Theo Từng Phase

Tài liệu này chuyển phần `Timeline & Flow` trong `INSTRUCTOR_GUIDE.md` thành các công việc cụ thể cho chủ đề:

**School Nutrition Optimizer** - Agent hỗ trợ lên thực đơn bán trú cho trường học.

---

## 1. Tổng mục tiêu của dự án

Agent cần nhận đầu vào như:
- ngân sách mỗi ngày,
- số lượng học sinh,
- danh sách dị ứng hoặc chế độ ăn đặc biệt,
- tiêu chuẩn dinh dưỡng theo độ tuổi,

và tạo ra:
- menu tuần 5 ngày,
- món thay thế cho học sinh bị dị ứng,
- phân tích dinh dưỡng,
- phân tích ràng buộc ngân sách, dị ứng, trùng món,
- hỗ trợ chỉnh tay rồi cập nhật lại phân tích.

Phần này bám sát yêu cầu MVP trong `docs/PROBLEM.md`.

---

## 2. Phase 0: The Hook

Tài liệu triển khai chi tiết:
- Xem `docs/PHASE0_HOOK.md`
- Prompt copy-paste nhanh: `docs/PHASE0_PROMPTS.md`

### Mục tiêu
Cho thấy vì sao chatbot thường không đủ cho bài toán nhiều ràng buộc.

### Công việc
- Chuẩn bị 2 câu hỏi demo.
- 1 câu đơn giản: "Gợi ý một bữa trưa đủ dinh dưỡng cho học sinh tiểu học."
- 1 câu nhiều bước: "Lập thực đơn 5 ngày cho 800 học sinh, ngân sách 28.000đ/ngày/em, có nhóm dị ứng sữa và trứng, không lặp món 2 ngày liên tiếp, rồi kiểm tra calories/protein/fiber và gợi ý món thay thế."
- Chạy thử bằng chatbot baseline hoặc mô phỏng phản hồi để thấy các điểm yếu.

### Điều cần quan sát
- Chatbot có thể trả lời nghe hợp lý.
- Nhưng chatbot không thực sự kiểm chứng được ngân sách, dinh dưỡng, dị ứng.
- Chatbot dễ bỏ sót món thay thế hoặc vi phạm ràng buộc mà không tự phát hiện.

### Kết quả mong đợi
- Có ví dụ rõ ràng để chứng minh: chatbot nói hay nhưng chưa chắc xử lý đúng bài toán nhiều bước.

---

## 3. Phase 1: Tool Design

### Mục tiêu
Thiết kế bộ tool đủ rõ để agent có thể hành động thay vì chỉ trả lời cảm tính.

### Công việc
- Tạo thư mục `src/tools/` vì repo hiện chưa có sẵn.
- Thiết kế các tool theo domain thực đơn trường học.
- Viết description cho từng tool thật rõ: input gì, output gì, dùng khi nào, giới hạn ra sao.

### Bộ tool đề xuất

#### `generate_weekly_menu`
- Mục đích: sinh menu 5 ngày từ ngân sách, số học sinh, nhóm tuổi, dữ liệu món ăn.

#### `analyze_nutrition`
- Mục đích: tính calories, protein, fiber, vitamin của từng ngày hoặc cả tuần.

#### `check_allergens`
- Mục đích: kiểm tra món nào vi phạm dị ứng của nhóm học sinh.

#### `suggest_substitutions`
- Mục đích: tìm món thay thế an toàn khi có dị ứng.

#### `check_constraints`
- Mục đích: xác nhận menu có vi phạm ngân sách, trùng món, hoặc ràng buộc đặc biệt không.

### Bản MVP tối thiểu
Nếu muốn làm gọn cho bản đầu, có thể bắt đầu với 3 tool:
- `analyze_nutrition`
- `check_allergens`
- `suggest_substitutions`

### Cách viết description tốt
Ví dụ nên viết:

`analyze_nutrition(menu_items, age_group, serving_size)`:
"Tính calories, protein, fiber và các chỉ số dinh dưỡng chính cho danh sách món ăn theo khẩu phần học sinh. Trả về số liệu theo từng ngày và cảnh báo thiếu hoặc thừa."

Không nên viết quá mơ hồ như:
- "Kiểm tra dinh dưỡng"

### Kết quả mong đợi
- Có danh sách tools rõ ràng.
- Có schema input/output.
- Có description đủ tốt để đưa vào system prompt của agent.

---

## 4. Phase 2: Chatbot Baseline

### Mục tiêu
Tạo một bản chatbot đơn giản để dùng làm mốc so sánh với agent.

### Công việc
- Tạo `chatbot.py` hoặc file tương tự để gọi trực tiếp một provider trong `src/core/`.
- Cho chatbot nhận prompt và trả lời một lần.
- Không dùng tool.
- Không có loop ReAct.
- Chuẩn bị bộ test case theo đúng domain thực đơn trường học.

### Bộ test case nên có
- Câu đơn giản: gợi ý bữa ăn 1 ngày.
- Câu trung bình: lập thực đơn 3 ngày với ngân sách.
- Câu khó: thực đơn 5 ngày cho 800 học sinh, có dị ứng, không trùng món, có phân tích dinh dưỡng và món thay thế.

### Điều cần quan sát
- Chatbot có thể sinh menu trông hợp lý.
- Nhưng thường không kiểm chứng từng ràng buộc.
- Dễ bỏ sót món thay thế cho dị ứng.
- Dễ mô tả dinh dưỡng chung chung mà không có số liệu đáng tin cậy.

### Kết quả mong đợi
- Có baseline để so sánh.
- Có danh sách các lỗi phổ biến của chatbot trong bài toán này.

---

## 5. Phase 3: Building Agent v1

### Mục tiêu
Hoàn thiện agent ReAct để xử lý bài toán nhiều bước bằng tool.

### File trọng tâm
- `src/agent/agent.py`

### Công việc
- Hoàn thiện `get_system_prompt()` để agent biết:
  - vai trò của nó là tối ưu thực đơn bán trú,
  - danh sách tool hiện có,
  - format bắt buộc: `Thought`, `Action`, `Observation`, `Final Answer`.
- Hoàn thiện `run()`:
  - gọi `self.llm.generate(...)`,
  - parse `Action`,
  - gọi `_execute_tool(...)`,
  - append `Observation` vào prompt,
  - lặp cho tới khi có `Final Answer` hoặc `max_steps`.
- Hoàn thiện `_execute_tool()` để gọi đúng function của từng tool.

### Luồng reasoning nên có
1. Hiểu yêu cầu đầu vào.
2. Sinh menu sơ bộ.
3. Kiểm tra dinh dưỡng.
4. Kiểm tra dị ứng.
5. Nếu vi phạm thì gọi tool gợi ý món thay thế.
6. Kiểm tra lại ngân sách và trùng món.
7. Trả `Final Answer`.

### Output cuối nên có
- Menu theo Thứ 2 đến Thứ 6.
- Món thay thế cho từng nhóm dị ứng.
- Phân tích dinh dưỡng.
- Kiểm tra ràng buộc.
- Cảnh báo hoặc ghi chú nếu còn trade-off.

### Kết quả mong đợi
- Agent v1 chạy được với ít nhất 2 tool.
- Agent xử lý tốt hơn chatbot ở các câu hỏi nhiều ràng buộc.

---

## 6. Phase 4: Failure Analysis

### Mục tiêu
Đọc log để hiểu agent sai ở đâu và cải thiện từ v1 sang v2.

### Công việc
- Bật logging bằng `src/telemetry/logger.py`.
- Ghi metric bằng `src/telemetry/metrics.py`.
- Chạy nhiều test case khó rồi mở thư mục `logs/` để xem trace.

### Các lỗi đặc trưng của domain này
- Agent gọi sai tool, ví dụ chưa kiểm tra dị ứng mà đã chốt menu.
- Agent chọn món thay thế nhưng lại vượt ngân sách.
- Agent phân tích dinh dưỡng không nhất quán giữa các ngày.
- Agent lặp mãi giữa đổi món và kiểm tra lại.
- Agent hallucinate dữ liệu dinh dưỡng nếu tool description quá mơ hồ.

### Hướng cải thiện từ v1 sang v2
- Viết lại description tool chặt hơn.
- Buộc thứ tự reasoning trong system prompt.
- Thêm điều kiện dừng rõ hơn.
- Thêm bước `check_constraints` cuối cùng trước khi trả `Final Answer`.
- Nếu tool trả kết quả rỗng thì yêu cầu agent fallback an toàn.

### Kết quả mong đợi
- Có ít nhất 1 case fail được phân tích rõ nguyên nhân.
- Có cải tiến cụ thể từ Agent v1 sang Agent v2.

---

## 7. Phase 5: Group Evaluation

### Mục tiêu
Đo hiệu quả thực tế của agent thay vì chỉ cảm giác là tốt hơn.

### Công việc
- Chuẩn bị bộ test chuẩn cho chủ đề thực đơn bán trú.
- So sánh Chatbot vs Agent ở các nhóm bài:
  - câu hỏi dinh dưỡng đơn giản,
  - lập menu 1 ngày,
  - lập menu 5 ngày nhiều ràng buộc,
  - case có dị ứng,
  - case chỉnh tay thực đơn rồi phân tích lại.

### Metric cần theo dõi
Theo `EVALUATION.md`, nên đo:
- token,
- latency,
- số loop,
- lỗi parser,
- hallucination,
- timeout.

### Metric gắn với bài toán
- Thời gian tạo một thực đơn tuần.
- Tỷ lệ menu đạt chuẩn dinh dưỡng.
- Tỷ lệ xử lý đúng dị ứng.
- Mức giảm lặp món.
- Mức độ hài lòng của người dùng.

### Kết quả mong đợi
- Có bảng so sánh rõ ràng để đưa vào group report.

---

## 8. Deliverable cuối cho chủ đề này

Nên chốt thành 6 đầu ra cụ thể:
- `src/tools/` với các tool về menu, dị ứng, dinh dưỡng, ràng buộc.
- Chatbot baseline.
- Agent v1 chạy được.
- Agent v2 cải thiện sau khi đọc log.
- Bộ test case theo domain trường bán trú.
- Báo cáo nhóm và báo cáo cá nhân.

---

## 9. Gợi ý thứ tự triển khai thực tế

1. Chốt dữ liệu mẫu: món ăn, dinh dưỡng, dị ứng phổ biến, ngân sách.
2. Viết 3 tool tối thiểu.
3. Làm chatbot baseline.
4. Hoàn thiện ReAct agent.
5. Thêm logging và metrics.
6. Chạy test, phân tích lỗi, cải tiến v2.
7. Viết report.

---

## 10. Ghi chú quan trọng

Repo hiện tại là starter repo, chưa hoàn chỉnh end-to-end. Một số phần được tài liệu nhắc tới nhưng chưa có sẵn trong source hiện tại, ví dụ:
- `src/tools/`
- `chatbot.py`

Vì vậy, khi triển khai theo các phase ở trên, cần hiểu rằng đây là các phần nhóm phải tự bổ sung.
