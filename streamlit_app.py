from __future__ import annotations

import json
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from run_agent_demo import build_provider_from_env
from src.agent.agent import ReActAgent
from src.telemetry.logger import logger
from src.tools import get_agent_tools


TOOL_REASON_MAP = {
    "generate_weekly_menu": "Sinh bản nháp thực đơn 5 ngày từ catalog và các ràng buộc đầu bài.",
    "analyze_nutrition": "Tính calories, protein và fiber để kiểm tra menu có đạt mục tiêu dinh dưỡng không.",
    "check_allergens": "Rà soát thực đơn theo nhóm dị ứng như sữa và trứng để tìm món vi phạm.",
    "suggest_substitutions": "Tìm món thay thế an toàn hơn khi menu đang có vi phạm dị ứng.",
    "check_constraints": "Chạy cổng kiểm tra cuối cho ngân sách, cấu trúc bữa ăn, lặp món và dinh dưỡng.",
}


@dataclass
class ToolTimelineItem:
    tool: str
    reason: str
    step: int
    thought: str | None = None
    argument_keys: list[str] = field(default_factory=list)
    status: str = "RUNNING"
    summary: str = "Đang gọi tool..."


def _render_header() -> None:
    st.set_page_config(
        page_title="School Lunch Agent UI",
        page_icon="🍱",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
          .hero {
            padding: 1.2rem 1.4rem;
            border-radius: 20px;
            background: linear-gradient(135deg, #fff7ed 0%, #ecfccb 55%, #dcfce7 100%);
            border: 1px solid rgba(22, 101, 52, 0.08);
            margin-bottom: 1rem;
          }
          .tool-card {
            padding: 0.9rem 1rem;
            border-radius: 16px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: #ffffff;
            margin-bottom: 0.75rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
          }
          .tool-title {
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 0.2rem;
          }
          .tool-meta {
            color: #475569;
            font-size: 0.92rem;
            margin-bottom: 0.25rem;
          }
          .tool-summary {
            color: #1e293b;
            font-size: 0.96rem;
          }
          .status-pill {
            display: inline-block;
            font-size: 0.78rem;
            font-weight: 700;
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            margin-bottom: 0.45rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="hero">
          <h1 style="margin:0; color:#14532d;">School Nutrition ReAct Agent</h1>
          <p style="margin:0.45rem 0 0; color:#334155;">
            Giao diện demo cho agent lập thực đơn. Bạn sẽ thấy agent đang nghĩ gì, đang gọi tool nào,
            tool đó chạy thành công hay thất bại, và vì sao tool đó được gọi.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_pill(status: str) -> str:
    normalized = status.upper()
    if normalized == "SUCCESS":
        return '<span class="status-pill" style="background:#dcfce7;color:#166534;">SUCCESS</span>'
    if normalized == "FAIL":
        return '<span class="status-pill" style="background:#fee2e2;color:#991b1b;">FAIL</span>'
    return '<span class="status-pill" style="background:#fef3c7;color:#92400e;">RUNNING</span>'


def _render_timeline(items: list[ToolTimelineItem]) -> None:
    if not items:
        st.info("Timeline tool sẽ xuất hiện ở đây sau khi agent bắt đầu chạy.")
        return

    for item in items:
        thought_block = f"<div class='tool-meta'><strong>Thought:</strong> {item.thought}</div>" if item.thought else ""
        arg_keys = ", ".join(item.argument_keys) if item.argument_keys else "không có"
        st.markdown(
            f"""
            <div class="tool-card">
              {_status_pill(item.status)}
              <div class="tool-title">Bước {item.step}: <code>{item.tool}</code></div>
              <div class="tool-meta"><strong>Vì sao gọi tool này:</strong> {item.reason}</div>
              {thought_block}
              <div class="tool-meta"><strong>Argument keys:</strong> {arg_keys}</div>
              <div class="tool-summary">{item.summary}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _extract_thought(llm_response: str) -> str | None:
    match = re.search(r"Thought:\s*(.+?)(?:\nAction:|\nFinal Answer:|$)", llm_response, re.DOTALL)
    if not match:
        return None
    return " ".join(match.group(1).strip().split()) or None


def _parse_observation(observation: str) -> dict[str, Any]:
    try:
        return json.loads(observation)
    except json.JSONDecodeError:
        return {"status": "error", "summary": observation}


def _history_to_timeline(history: list[dict[str, Any]]) -> list[ToolTimelineItem]:
    items: list[ToolTimelineItem] = []
    for step_entry in history:
        action = step_entry.get("action")
        if not isinstance(action, dict):
            continue

        tool_name = str(action.get("tool", "unknown_tool"))
        observation_payload = _parse_observation(str(step_entry.get("observation", "")))
        raw_status = str(observation_payload.get("status", "error")).lower()
        status = "SUCCESS" if raw_status == "ok" else "FAIL"
        summary = str(observation_payload.get("summary", "No summary provided."))
        errors = observation_payload.get("errors") or []
        if status == "FAIL" and errors:
            summary = f"{summary} | first_error={str(errors[0])[:180]}"

        items.append(
            ToolTimelineItem(
                tool=tool_name,
                reason=TOOL_REASON_MAP.get(tool_name, "Agent cần tool này để xác minh bước tiếp theo."),
                step=int(step_entry.get("step", len(items) + 1)),
                thought=_extract_thought(str(step_entry.get("llm_response", ""))),
                argument_keys=sorted(list((action.get("arguments") or {}).keys())),
                status=status,
                summary=summary,
            )
        )
    return items


def _render_tool_summary(history: list[dict[str, Any]]) -> None:
    tool_names = [
        str(step["action"]["tool"])
        for step in history
        if isinstance(step.get("action"), dict) and step["action"].get("tool")
    ]
    if not tool_names:
        st.info("Phiên chạy này chưa ghi nhận lời gọi tool nào.")
        return

    unique_tools = list(dict.fromkeys(tool_names))
    st.markdown(
        f"**Đã chạy {len(tool_names)} lời gọi tool** qua **{len(unique_tools)} tool**: "
        + ", ".join(f"`{tool}`" for tool in unique_tools)
    )


def _write_agent_artifacts(prompt: str, provider_name: str, model_name: str, max_steps: int, final_answer: str, history: list[dict[str, Any]], text_log_path: str) -> tuple[str, str]:
    txt_log_path = logger.write_text_artifact(
        final_answer,
        prefix="agent_answer",
    )
    json_log_path = logger.write_json_artifact(
        {
            "status": "success",
            "prompt": prompt,
            "provider": provider_name,
            "model": model_name,
            "max_steps": max_steps,
            "final_answer": final_answer,
            "history": history,
            "text_log_path": text_log_path,
            "final_answer_text_path": txt_log_path,
        },
        prefix="agent_answer",
    )
    return txt_log_path, json_log_path


def _run_agent_worker(prompt: str, max_steps: int, event_queue: queue.Queue[dict[str, Any]]) -> None:
    provider = build_provider_from_env()
    agent = ReActAgent(llm=provider, tools=get_agent_tools(), max_steps=max_steps)
    agent.set_event_callback(event_queue.put)

    target_log_path = logger.create_run_log_path(prefix="agent_run")
    final_answer = ""

    with logger.capture_console(target_log_path):
        try:
            final_answer = agent.run(prompt)
            txt_path, json_path = _write_agent_artifacts(
                prompt,
                provider.__class__.__name__,
                provider.model_name,
                max_steps,
                final_answer,
                agent.history,
                target_log_path,
            )
            event_queue.put(
                {
                    "type": "run_complete",
                    "status": "success",
                    "final_answer": final_answer,
                    "history": agent.history,
                    "run_log_path": target_log_path,
                    "answer_txt_path": txt_path,
                    "answer_json_path": json_path,
                }
            )
        except Exception as exc:
            error_answer = (
                "Agent run failed.\n"
                f"Error Type: {exc.__class__.__name__}\n"
                f"Message: {str(exc)}"
            )
            txt_path = logger.write_text_artifact(error_answer, prefix="agent_answer")
            json_path = logger.write_json_artifact(
                {
                    "status": "error",
                    "prompt": prompt,
                    "provider": provider.__class__.__name__,
                    "model": provider.model_name,
                    "max_steps": max_steps,
                    "final_answer": "",
                    "history": agent.history,
                    "text_log_path": target_log_path,
                    "final_answer_text_path": txt_path,
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                },
                prefix="agent_answer",
            )
            event_queue.put(
                {
                    "type": "run_complete",
                    "status": "error",
                    "error": f"{exc.__class__.__name__}: {str(exc)}",
                    "history": agent.history,
                    "run_log_path": target_log_path,
                    "answer_txt_path": txt_path,
                    "answer_json_path": json_path,
                }
            )


def _consume_events(event_queue: queue.Queue[dict[str, Any]], timeline: list[ToolTimelineItem], latest_thought: dict[str, str | None]) -> dict[str, Any] | None:
    run_complete_event = None
    while True:
        try:
            event = event_queue.get_nowait()
        except queue.Empty:
            break

        event_type = event.get("type")
        if event_type == "thought":
            latest_thought["value"] = str(event.get("thought") or "")
        elif event_type == "tool_start":
            tool_name = str(event.get("tool"))
            timeline.append(
                ToolTimelineItem(
                    tool=tool_name,
                    reason=TOOL_REASON_MAP.get(tool_name, "Agent cần tool này để xác minh bước tiếp theo."),
                    step=int(event.get("step", len(timeline) + 1)),
                    thought=latest_thought.get("value"),
                    argument_keys=list(event.get("argument_keys") or []),
                )
            )
        elif event_type == "tool_result":
            tool_name = str(event.get("tool"))
            for item in reversed(timeline):
                if item.tool == tool_name and item.status == "RUNNING":
                    item.status = str(event.get("status") or "FAIL")
                    item.summary = str(event.get("summary") or "Tool finished.")
                    break
        elif event_type == "parser_error":
            timeline.append(
                ToolTimelineItem(
                    tool="parser",
                    reason="Agent không parse được action từ model nên phải tự phục hồi.",
                    step=int(event.get("step", len(timeline) + 1)),
                    thought=latest_thought.get("value"),
                    status="FAIL",
                    summary=str(event.get("error") or "Parser error."),
                )
            )
        elif event_type == "run_complete":
            run_complete_event = event
    return run_complete_event


def main() -> None:
    _render_header()

    with st.sidebar:
        st.subheader("Cấu hình")
        max_steps = st.slider("Max Steps", min_value=3, max_value=10, value=5)
        st.caption("UI sẽ hiển thị trạng thái từng tool theo thời gian thực.")

    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        prompt = st.text_area(
            "Prompt",
            height=180,
            value="Lập thực đơn 5 ngày cho 800 học sinh, ngân sách 28.000đ/ngày/em, có nhóm dị ứng sữa và trứng, không lặp món 2 ngày liên tiếp, rồi kiểm tra calories, protein, fiber và gợi ý món thay thế.",
        )
        run_clicked = st.button("Chạy Agent", type="primary", use_container_width=True)
        final_placeholder = st.empty()
        log_placeholder = st.empty()

    with right:
        st.subheader("Timeline Tools")
        timeline_placeholder = st.empty()
        progress_placeholder = st.empty()

    if not run_clicked:
        return

    if not prompt.strip():
        st.error("Prompt không được để trống.")
        return

    event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    worker = threading.Thread(
        target=_run_agent_worker,
        args=(prompt.strip(), max_steps, event_queue),
        daemon=True,
    )
    worker.start()

    timeline: list[ToolTimelineItem] = []
    latest_thought: dict[str, str | None] = {"value": None}
    result_event: dict[str, Any] | None = None

    with progress_placeholder.container():
        st.info("Agent đang chạy. Timeline sẽ cập nhật mỗi khi agent qua một tool.")

    while worker.is_alive() or not event_queue.empty():
        result_event = _consume_events(event_queue, timeline, latest_thought) or result_event
        with timeline_placeholder.container():
            _render_timeline(timeline)
        time.sleep(0.15)

    result_event = _consume_events(event_queue, timeline, latest_thought) or result_event
    with timeline_placeholder.container():
        _render_timeline(timeline)

    if result_event is None:
        progress_placeholder.error("Không nhận được kết quả cuối cùng từ agent.")
        return

    if result_event["status"] == "success":
        history = list(result_event.get("history") or [])
        timeline = _history_to_timeline(history) or timeline
        with timeline_placeholder.container():
            _render_timeline(timeline)
        progress_placeholder.success("Agent đã chạy xong.")
        final_placeholder.subheader("Final Answer")
        final_placeholder.markdown(result_event["final_answer"])
        with log_placeholder.container():
            st.caption("Tool Summary")
            _render_tool_summary(history)
            st.caption("Artifacts")
            st.code(
                json.dumps(
                    {
                        "run_log_path": result_event["run_log_path"],
                        "answer_txt_path": result_event["answer_txt_path"],
                        "answer_json_path": result_event["answer_json_path"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                language="json",
            )
    else:
        history = list(result_event.get("history") or [])
        timeline = _history_to_timeline(history) or timeline
        with timeline_placeholder.container():
            _render_timeline(timeline)
        progress_placeholder.error("Agent chạy lỗi.")
        final_placeholder.subheader("Lỗi")
        final_placeholder.code(result_event["error"])
        with log_placeholder.container():
            st.caption("Tool Summary")
            _render_tool_summary(history)
            st.caption("Artifacts")
            st.code(
                json.dumps(
                    {
                        "run_log_path": result_event["run_log_path"],
                        "answer_txt_path": result_event["answer_txt_path"],
                        "answer_json_path": result_event["answer_json_path"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                language="json",
            )


if __name__ == "__main__":
    main()
