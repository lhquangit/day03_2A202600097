# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: C401-A5
- **Team Members**: Lê Hồng Quân, Phạm Thanh Lam, Nguyễn Đức Hải, Đoàn Sĩ Linh
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

Nhóm phát triển một hệ thống `School Nutrition Optimizer` để giải bài toán lập thực đơn bán trú 5 ngày cho trường học với nhiều ràng buộc cùng lúc: ngân sách, dị ứng, dinh dưỡng, cấu trúc bữa ăn và tránh lặp món. Thay vì để LLM trả lời một lần như chatbot baseline, hệ thống sử dụng ReAct loop với bộ tool deterministic để sinh menu, kiểm dinh dưỡng, kiểm dị ứng, gợi ý thay thế và chạy gate kiểm tra cuối.

- **Success Rate**: `23/23` test local pass cho tool contracts, registry và agent loop. Trên prompt khó đại diện của bài lab, agent hoàn thành workflow nhiều bước bằng `3-4` tool calls, trong khi baseline chatbot chỉ cho câu trả lời “nghe hợp lý” nhưng không chứng minh được constraint.
- **Key Outcome**: Agent chuyển bài toán từ “LLM nói có vẻ đúng” sang “LLM điều phối các bước kiểm chứng có cấu trúc”. So với baseline chatbot ở Phase 0, agent tạo ra trace kiểm được, có log thất bại/thành công và có thể phân tích nguyên nhân lỗi để cải thiện.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

Hệ thống bám theo vòng lặp ReAct trong [agent.py](/Users/quanliver/Projects/AI_Vin_Learner/Day-3-Lab-Chatbot-vs-react-agent/src/agent/agent.py):

```text
User Request
  -> Thought
  -> Action {"tool": "...", "arguments": {...}}
  -> Tool Execution
  -> Observation {status, summary, data, warnings, errors}
  -> Thought ...
  -> Final Answer
```

Luồng hiện tại:

1. Agent nhận user prompt và system prompt domain-specific.
2. LLM sinh `Thought` và `Action` ở format JSON raw.
3. Agent parse action, normalize arguments nếu model gọi sai alias phổ biến.
4. Agent validate input bằng Pydantic, chạy tool, lấy `Observation`.
5. Observation được append lại vào trace để LLM reasoning tiếp.
6. Agent dừng khi có `Final Answer` hoặc chạm `max_steps`.

Điểm quan trọng của bản v2:

- Có `max_steps` để chặn loop vô hạn.
- Có normalized argument handling cho các lỗi kiểu `menu_data.weekly_menu`, `allergen_groups` vs `allergy_groups`, `budget` vs `constraints`.
- Có cache `weekly_menu` và `allergy_groups` để giảm lỗi khi model copy lại JSON lớn.
- Có log sự kiện `AGENT_*` và UI timeline để quan sát tool-by-tool.

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `generate_weekly_menu` | `json` với `constraints`, `allergy_groups`, `nutrition_targets`, `catalog?` | Sinh menu 5 ngày từ mock catalog, có tính đến ngân sách, số học sinh, dị ứng và rule không lặp món. |
| `analyze_nutrition` | `json` với `weekly_menu`, `nutrition_targets` | Tính `calories`, `protein_g`, `fiber_g` theo từng ngày và đánh dấu ngày đạt/chưa đạt target. |
| `check_allergens` | `json` với `weekly_menu`, `allergy_groups` | Audit thực đơn theo từng nhóm dị ứng như `milk`, `egg`, trả về vi phạm theo ngày và món. |
| `suggest_substitutions` | `json` với `weekly_menu`, `allergy_groups`, `catalog?` | Đề xuất món thay thế cùng category khi có vi phạm dị ứng, kèm delta cost và delta nutrition. |
| `check_constraints` | `json` với `weekly_menu`, `constraints`, `nutrition_targets?` | Gate cuối để kiểm ngân sách, cấu trúc bữa ăn, món lặp liên tiếp, giới hạn món chiên và target dinh dưỡng. |


### 2.3 LLM Providers Used

- **Primary**: `OpenAIProvider` với `gpt-4o`
- **Secondary (Backup)**: `GeminiProvider` hoặc `LocalProvider` qua cùng interface [llm_provider.py]
---

## 3. Telemetry & Performance Dashboard

Telemetry được ghi bởi [logger.py] và [metrics.py].
Hệ thống hiện log:

- `AGENT_START`, `AGENT_STEP`, `AGENT_ACTION`, `AGENT_OBSERVATION`, `AGENT_FINAL`, `AGENT_END`
- `LLM_METRIC`
- artifact JSON/TXT cho final answer
- run log TXT cho toàn bộ phiên

Số liệu dưới đây lấy từ một run thành công tại: `logs`.

- **Average Latency (P50/mean on this run)**: `22,988.67 ms`
- **Max Latency (P99 proxy on this run)**: `47,739 ms`
- **Average Tokens per Task**: `5,782.67 tokens/request`
- **Total Cost of Test Run**: `$0.17348`  
  Note: đây là `mock cost estimate` từ tracker, chưa phải pricing thật theo bảng giá provider.

Chi tiết run tiêu biểu:

- Số request LLM: `3`
- Số tool calls thành công: `3`
- Tool sequence: `generate_weekly_menu -> analyze_nutrition -> check_allergens`
- Sau đó model tự tổng hợp final answer mà không cần gọi `suggest_substitutions` vì không có allergen violation cho `milk` và `egg` trong menu đã lọc.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study: Malformed Tool Arguments for `check_allergens`

- **Input**: Prompt phức tạp yêu cầu menu 5 ngày cho `800` học sinh, ngân sách `28.000đ`, có dị ứng `sữa` và `trứng`, đồng thời kiểm `calories/protein/fiber` và gợi ý món thay thế.
- **Observation**: Ở các bản run đầu, model gọi `check_allergens` với payload sai shape, ví dụ bọc `weekly_menu` vào `menu_data` hoặc rút gọn từng `Dish` chỉ còn `id`, `name`, `allergens`.
- **Visible Symptom**: Tool trả `status="error"` với các lỗi `Field required` cho `weekly_menu`, `category`, `ingredients`, `cost_per_serving_vnd`, `nutrition_per_serving`.
- **Root Cause**:
  - LLM phải copy một JSON `weekly_menu` rất lớn từ observation trước.
  - Prompt v1 chưa đủ chặt để ép đúng input schema.
  - Input model strict nhưng agent v1 chưa có state reuse, nên mỗi bước phụ thuộc vào độ chính xác của JSON mà model tự chép lại.
- **Fix Implemented**:
  - Agent v2 cache `weekly_menu` và `allergy_groups` từ tool result thành công.
  - Thêm normalization layer cho aliases như `menu_data.weekly_menu`, `allergen_groups`, `budget`.
  - Nếu model gửi `weekly_menu` bị thiếu field, agent thay bằng bản đầy đủ từ cache trước khi validate.
- **Outcome**:
  - Giảm mạnh lỗi validation cho các tool downstream.
  - Flow đi từ timeout/fail sang completion thành công ở các run sau.

### Case Study: Chatbot-Like Final Answer Without Verified Constraints

- **Observation**: Ở baseline và một số trace agent đầu, model có xu hướng viết final answer “nghe ổn” trước khi kiểm chứng đủ dị ứng hoặc constraints.
- **Root Cause**:
  - Chatbot baseline không có tool, nên không thể kiểm độc lập.
  - Agent v1 ban đầu chưa đủ guardrail để buộc reasoning order và tái sử dụng tool-backed state.
- **Fix Implemented**:
  - Thêm `check_constraints` làm gate cuối trong system prompt.
  - Log rõ từng tool và status trong terminal/UI.
  - Final answer artifacts lưu kèm history để đối chiếu với trace.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Agent v1 vs Agent v2 Argument Normalization

- **Diff**:
  - v1 parse action rồi validate trực tiếp.
  - v2 thêm:
    - alias normalization
    - cached `weekly_menu`
    - cached `allergy_groups`
    - auto-reuse structured state thay vì tin hoàn toàn vào JSON do model tự copy
- **Result**:
  - Invalid tool call errors do wrong shape giảm rõ rệt.
  - Representative runs sau patch hoàn thành trong `3-4` bước thay vì rơi vào error/timeout loop khi gọi `check_allergens` hoặc `suggest_substitutions`.

### Experiment 2: Prompt v1 vs Prompt v2

- **Diff**:
  - Prompt v2 ghi rõ tool order mặc định:
    `generate_weekly_menu -> analyze_nutrition -> check_allergens -> suggest_substitutions -> check_constraints`
  - Ép `Action` ở format JSON raw với đúng 2 key: `tool`, `arguments`
  - Cấm bịa dữ liệu chưa được tool xác nhận
- **Result**:
  - Parser stability tốt hơn.
  - Logs dễ đọc và dễ RCA hơn.
  - Tool sequence bám đúng domain workflow hơn.

### Experiment 3 (Bonus): Chatbot vs Agent

| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Gợi ý bữa ăn 1 ngày | Thường trả lời ổn, nghe hợp lý | Trả lời ổn | Draw |
| Lập menu 5 ngày nhiều ràng buộc | Menu nghe hợp lý nhưng không chứng minh được ngân sách/dị ứng/dinh dưỡng | Có trace tool, có dữ liệu cost/nutrition/allergen/constraint | **Agent** |
| Dị ứng sữa/trứng + món thay thế | Dễ bỏ sót hoặc trả lời chung chung | Có thể audit dị ứng bằng tool và gợi ý món thay thế nếu catalog hỗ trợ | **Agent** |
| Debug sai ở đâu | Khó biết vì chatbot trả lời 1 lần | Có log `Thought/Action/Observation`, dễ phân tích lỗi | **Agent** |

---

## 6. Production Readiness Review

- **Security**: Input tool arguments được validate bằng Pydantic; action parser ép JSON object; có giới hạn `max_steps` để tránh loop vô hạn và chi phí mất kiểm soát.
- **Guardrails**:
  - `max_steps` trên agent/UI
  - repeated-action stop
  - structured error envelope cho tool failures
  - deterministic tools không gọi network/LLM
- **Observability**:
  - JSON event logs theo ngày
  - run log TXT
  - final answer JSON + TXT
  - UI timeline hiển thị từng tool, trạng thái `running/success/fail`, và lý do gọi tool
- **Scaling**:
  - Có thể thay mock catalog bằng DB/API thật nhưng giữ nguyên schema `Dish`, `WeeklyMenu`, `ConstraintSet`
  - Có thể thêm strict schema `extra="forbid"` cho toàn bộ input models để fail sớm hơn nữa
  - Có thể chuyển sang orchestration mạnh hơn như LangGraph nếu workflow branch phức tạp hơn
- **Known Gaps**:
  - `analyze_nutrition` hiện chỉ tính trên nutrition metadata trong mock catalog, chưa dùng nguồn chuẩn dinh dưỡng thật
  - `cost_estimate` trong telemetry là mock formula
  - Chưa có baseline chatbot benchmark tự động hóa hoàn toàn; phần so sánh baseline hiện vẫn chủ yếu dựa trên manual evaluation ở Phase 0

---

## 7. Flowchart & Group Insights

### Flowchart

```text
Prompt
  -> ReActAgent
      -> generate_weekly_menu
      -> analyze_nutrition
      -> check_allergens
      -> suggest_substitutions (if needed)
      -> check_constraints
  -> Final Answer
  -> Logs / JSON artifacts / UI timeline
```

### Group Insights

- Bài toán nhiều ràng buộc không thể đánh giá bằng “câu trả lời nghe hay”.
- ReAct chỉ hữu ích khi tool contracts đủ rõ, deterministic và có validation.
- Failure analysis mang lại giá trị lớn gần ngang với bản chạy thành công, vì nó chỉ ra đúng chỗ LLM bị yếu nhất: format action và copy structured payload.
- UI timeline giúp giải thích trực quan cho instructor vì sao agent tốt hơn chatbot: agent không chỉ trả lời, agent “đi kiểm”.

---

## 8. Final Deliverables

- Tool layer hoàn chỉnh trong `src/tools/`
- ReAct agent trong `src/agent/agent.py`
- CLI demo runner `run_agent_demo.py`
- Tool demo runner `run_tools_demo.py`
- Streamlit UI `streamlit_app.py`
- Telemetry + artifacts trong `logs/`
- Automated tests:
  - `tests/test_tool_models.py`
  - `tests/test_tool_registry.py`
  - `tests/test_tool_workflows.py`
  - `tests/test_agent.py`

---

