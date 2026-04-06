# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Lê Hồng Quân
- **Student ID**: [Your ID Here]
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

Trong lab này, phần đóng góp kỹ thuật chính của tôi tập trung vào việc biến skeleton ban đầu thành một agent có thể kiểm chứng bằng tool thay vì chỉ trả lời theo cảm tính. Tôi tham gia vào cả ba lớp quan trọng: domain tools, ReAct loop, và observability/UI để việc debug và demo trở nên rõ ràng.

- **Modules Implemented**:
  - [registry.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/src/tools/registry.py): khai báo inventory 5 tools cho agent prompt và runtime.
  - [analyze_nutrition.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/src/tools/analyze_nutrition.py):  tool phân tích thực đơn.
  - [agent.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/src/agent/agent.py): hoàn thiện ReAct loop, action parser, tool execution, argument normalization, state reuse và terminal/UI events.
  - [logger.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/src/telemetry/logger.py): thêm `capture_console`, text/json artifacts cho run logs và final answer.
  - [run_agent_demo.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/run_agent_demo.py): CLI runner end-to-end với provider từ `.env`.
  - [streamlit_app.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/streamlit_app.py): UI demo hiển thị timeline từng tool, loading, trạng thái `success/fail`, và final answer.
  - [test_agent.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/tests/test_agent.py), [test_tool_models.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/tests/test_tool_models.py), [test_tool_registry.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/tests/test_tool_registry.py), [test_tool_workflows.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/tests/test_tool_workflows.py): unit và integration tests cho tools và agent.
- **Code Highlights**:
  - Tool contracts dùng cùng một output shape `status / tool / summary / data / warnings / errors`, giúp agent parse observation ổn định hơn.
  - ReAct agent dùng format `Action: {"tool":"...", "arguments": {...}}` để giảm ambiguity trong parsing.
  - Agent có cơ chế normalize arguments và cache `weekly_menu` để tránh lỗi do model phải copy lại JSON rất lớn.
  - Logger tạo cả `run log txt`, `final answer json`, `final answer txt`, giúp việc trace và viết RCA dễ hơn.
- **Documentation**:
  - Tôi tham gia chốt mô tả tool và contract trong [PHASE1_TOOL_DESIGN.md](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/docs/PHASE1_TOOL_DESIGN.md).
  - Cách các module tương tác với ReAct loop:
    1. Agent dùng registry để đưa tool descriptions vào system prompt.
    2. LLM sinh action JSON.
    3. Agent validate input qua Pydantic model tương ứng.
    4. Tool trả về output envelope.
    5. Observation quay lại prompt và đồng thời được log/hiển thị trên UI.

---

## II. Debugging Case Study (10 Points)

### Problem Description

Một lỗi điển hình tôi gặp là agent gọi `check_allergens` với payload sai shape. Thay vì truyền top-level `weekly_menu`, model lại bọc payload thành `menu_data.weekly_menu`, hoặc rút gọn mỗi `Dish` chỉ còn `id`, `name`, `allergens`. Kết quả là tool fail validation và agent không thể tiếp tục workflow một cách ổn định.

### Log Source

Failure trace thể hiện rất rõ trong các run đầu. Ví dụ symptom xuất hiện ở log:

- [2026-04-06.log](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/logs/2026-04-06.log)
- và artifact history trong [agent_answer_2026-04-06_16-28-27.json](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/logs/agent_answer_2026-04-06_16-28-27.json)

Dạng lỗi quan sát được:

- `Tool 'check_allergens' rejected the input arguments`
- nhiều `Field required`
- thiếu các field như `category`, `ingredients`, `cost_per_serving_vnd`, `nutrition_per_serving`

### Diagnosis

Sau khi đọc trace, tôi kết luận đây không phải lỗi logic của `check_allergens`, mà là lỗi phối hợp giữa model và structured tool schema:

1. `weekly_menu` là object lớn, nhiều tầng.
2. LLM phải copy lại JSON này từ observation trước.
3. Khi copy thủ công, model dễ làm mất field hoặc bọc sai một tầng.
4. Prompt ban đầu chưa đủ chặt để ép model luôn đúng input schema.
5. Agent v1 cũng chưa có state reuse, nên mỗi bước vẫn phụ thuộc vào JSON do model tự chép lại.

### Solution

Tôi sửa theo hướng agent-centric thay vì chỉ tiếp tục “nhắc model cẩn thận hơn”:

- cache `weekly_menu` và `allergy_groups` từ các observation `status="ok"`
- thêm argument normalization trong [agent.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/src/agent/agent.py):
  - unwrap `menu_data.weekly_menu`
  - map alias `allergen_groups` -> `allergy_groups`
  - map `budget` / `budget_per_serving` -> `constraints.budget_per_student_vnd`
- nếu model gửi `weekly_menu` không đầy đủ, agent tự thay bằng bản cached đầy đủ trước khi validate

### Outcome

Sau khi sửa:

- invalid tool-call errors giảm rõ rệt
- các run đại diện hoàn thành bằng `3-4` steps
- bộ test agent và tool hiện pass `23/23`

Điều quan trọng nhất tôi rút ra ở case này là: trong hệ thống agent thực tế, không nên kỳ vọng LLM luôn copy structured payload hoàn hảo. Hệ thống cần một lớp bảo vệ ở runtime.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning

`Thought` block không làm agent “thông minh hơn” theo nghĩa có thêm tri thức, nhưng nó giúp chia bài toán thành các bước có mục tiêu. Với chatbot thường, prompt khó sẽ bị trả lời một lần theo kiểu tổng hợp cảm tính. Với ReAct, `Thought` buộc agent xác định bước tiếp theo là gì: sinh menu, kiểm dinh dưỡng, kiểm dị ứng hay chạy gate cuối. Điều này đặc biệt hữu ích với bài toán nhiều ràng buộc như school lunch planning.

### 2. Reliability

Agent không phải lúc nào cũng tốt hơn chatbot. Trong các case đơn giản, chatbot có thể nhanh hơn và ít tốn token hơn. Agent cũng có thể tệ hơn chatbot khi:

- parser `Action` fail
- model gọi sai schema tool
- payload quá lớn làm model copy sai
- workflow chưa có enough guardrails và dừng sớm trước khi gọi đủ tool

Tức là agent mạnh hơn ở khả năng kiểm chứng, nhưng cũng mong manh hơn về orchestration nếu implementation chưa tốt.

### 3. Observation

Observation là phần quan trọng nhất làm nên khác biệt. Chatbot không có “môi trường phản hồi” ngoài chính câu trả lời của nó. Agent thì có:

- observation từ tool
- validation errors
- warnings
- constraint reports

Những observation này buộc bước reasoning tiếp theo dựa trên dữ liệu có cấu trúc, không chỉ dựa vào “trí nhớ” của model. Khi tool trả `error`, observation cũng giúp tôi debug rõ nguyên nhân hơn rất nhiều so với chatbot baseline.

---

## IV. Future Improvements (5 Points)

- **Scalability**:
  - thay mock catalog bằng DB/API thật nhưng giữ nguyên domain schema
  - thêm menu state handle hoặc `menu_id` để tránh phải truyền full `weekly_menu` qua nhiều step
  - nếu workflow lớn hơn, chuyển sang graph-based orchestration như LangGraph
- **Safety**:
  - bật strict schema `extra="forbid"` cho toàn bộ input models
  - không cho `Final Answer` nếu các tool bắt buộc như `check_allergens` hoặc `check_constraints` chưa chạy thành công
  - thêm supervisor logic để kiểm final answer có khớp với tool outputs hay không
- **Performance**:
  - rút gọn payload giữa các step bằng state handle thay vì copy full menu
  - cache tool outputs theo menu state
  - tách UI event stream khỏi logging pipeline để tránh mất sync giữa log file và live timeline

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.

