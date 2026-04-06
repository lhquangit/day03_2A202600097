import json
import re
from typing import List, Dict, Any, Optional, Callable

from pydantic import ValidationError

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []
        self.max_repeated_actions = 3
        self.cached_weekly_menu: Optional[Dict[str, Any]] = None
        self.cached_allergy_groups: list[Dict[str, Any]] = []
        self.event_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_event_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        self.event_callback = callback

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            [
                f"- {self._tool_attr(t, 'name')}: {self._tool_attr(t, 'description')}"
                for t in self.tools
            ]
        )
        return f"""
You are a School Nutrition Optimizer agent for school lunch planning.
Your job is to solve multi-step menu planning tasks by using tools, not by guessing.

Available tools:
{tool_descriptions}

Default reasoning order:
1. Understand the school lunch request and identify constraints.
2. Call `generate_weekly_menu` to draft the 5-day menu.
3. Call `analyze_nutrition` to verify calories, protein, and fiber.
4. Call `check_allergens` to audit milk/egg or other allergy groups.
5. Call `suggest_substitutions` only when allergen violations exist.
6. Call `check_constraints` before producing the final answer.

Rules:
- Never invent nutrition, allergen, or budget facts that were not confirmed by a tool.
- Use raw JSON in `Action:` exactly once when you need a tool.
- The JSON must have exactly 2 keys: `tool` and `arguments`.
- Do not include markdown code fences around `Action`.
- If the latest Observation contains an error, fix the next Action instead of repeating the same invalid call.
- When enough information is available, respond with `Final Answer:` and no new `Action`.

Required output format:
Thought: brief reasoning about the next step.
Action: {{"tool":"tool_name","arguments":{{...}}}}

When you are done:
Thought: brief reasoning about completion.
Final Answer: provide a user-friendly response that includes:
- Weekly menu for Monday to Friday
- Nutrition summary
- Allergen findings
- Substitution suggestions if any
- Constraint check summary and remaining trade-offs
        """

    def run(self, user_input: str) -> str:
        logger.log_event(
            "AGENT_START",
            {"input": user_input, "model": self.llm.model_name, "max_steps": self.max_steps},
        )
        self._emit_event(
            {
                "type": "agent_start",
                "input": user_input,
                "model": self.llm.model_name,
                "max_steps": self.max_steps,
            }
        )
        logger.info(
            f"[Agent] Start | model={self.llm.model_name} | max_steps={self.max_steps}"
        )

        self.history = []
        self.cached_weekly_menu = None
        self.cached_allergy_groups = self._infer_allergy_groups_from_text(user_input)
        conversation_trace = [f"User Request:\n{user_input}"]
        repeated_action_count = 0
        last_action_signature: Optional[str] = None
        final_answer: Optional[str] = None
        final_status = "timeout"
        steps = 0

        while steps < self.max_steps:
            steps += 1
            trace_text = "\n\n".join(conversation_trace)
            logger.log_event("AGENT_STEP", {"step": steps, "trace_length": len(trace_text)})
            self._emit_event({"type": "step", "step": steps, "max_steps": self.max_steps})
            logger.info(f"[Agent] Step {steps}/{self.max_steps}")

            result = self.llm.generate(trace_text, system_prompt=self.get_system_prompt())
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )

            content = (result.get("content") or "").strip()
            self.history.append({"step": steps, "llm_response": content})
            logger.log_event(
                "AGENT_LLM_RESPONSE",
                {
                    "step": steps,
                    "latency_ms": result.get("latency_ms", 0),
                    "usage": result.get("usage", {}),
                    "content": content,
                },
            )
            thought = self._extract_thought(content)
            if thought:
                self._emit_event({"type": "thought", "step": steps, "thought": thought})
                logger.info(f"[Agent] Thought | {thought}")

            final_answer = self._extract_final_answer(content)
            if final_answer:
                final_status = "completed"
                logger.log_event("AGENT_FINAL", {"step": steps, "final_answer": final_answer})
                self._emit_event(
                    {
                        "type": "final_answer",
                        "step": steps,
                        "final_answer": final_answer,
                    }
                )
                logger.info("[Agent] Final Answer ready.")
                break

            try:
                action_payload = self._extract_action_payload(content)
            except ValueError as exc:
                parser_observation = self._build_observation(
                    self._error_payload(
                        tool_name="parser",
                        summary="Could not parse Action from model response.",
                        errors=[str(exc)],
                    )
                )
                logger.log_event(
                    "AGENT_ACTION",
                    {"step": steps, "parser_status": "error", "error": str(exc)},
                )
                self._emit_event(
                    {
                        "type": "parser_error",
                        "step": steps,
                        "error": str(exc),
                    }
                )
                logger.info(f"[Agent] Parser Error | {exc}")
                conversation_trace.append(content)
                conversation_trace.append(f"Observation: {parser_observation}")
                self.history[-1]["observation"] = parser_observation
                continue

            prepared_arguments = self._prepare_tool_arguments(
                action_payload["tool"],
                action_payload["arguments"],
            )
            if prepared_arguments != action_payload["arguments"]:
                self._emit_event(
                    {
                        "type": "action_normalized",
                        "step": steps,
                        "tool": action_payload["tool"],
                        "argument_keys": sorted(prepared_arguments.keys()),
                    }
                )
                logger.info(
                    f"[Agent] Action Normalized | tool={action_payload['tool']} | arguments={self._summarize_arguments(prepared_arguments)}"
                )
            action_payload["arguments"] = prepared_arguments

            action_signature = json.dumps(action_payload, sort_keys=True, ensure_ascii=False)
            repeated_action_count = (
                repeated_action_count + 1
                if action_signature == last_action_signature
                else 1
            )
            last_action_signature = action_signature

            logger.log_event(
                "AGENT_ACTION",
                {
                    "step": steps,
                    "parser_status": "ok",
                    "tool_name": action_payload["tool"],
                    "arguments": action_payload["arguments"],
                    "repeat_count": repeated_action_count,
                },
            )
            logger.info(
                f"[Agent] Action | tool={action_payload['tool']} | arguments={self._summarize_arguments(action_payload['arguments'])}"
            )
            logger.info(f"[Tool] Start | name={action_payload['tool']}")
            self._emit_event(
                {
                    "type": "tool_start",
                    "step": steps,
                    "tool": action_payload["tool"],
                    "argument_keys": sorted(action_payload["arguments"].keys()),
                }
            )

            if repeated_action_count >= self.max_repeated_actions:
                final_status = "repeated_action_stop"
                final_answer = self._build_fallback_answer(
                    reason=(
                        f"Agent stopped after repeating the same action "
                        f"`{action_payload['tool']}` {repeated_action_count} times."
                    )
                )
                logger.log_event(
                    "AGENT_FINAL",
                    {
                        "step": steps,
                        "final_answer": final_answer,
                        "reason": "repeated_action_stop",
                    },
                )
                self._emit_event(
                    {
                        "type": "agent_stop",
                        "step": steps,
                        "reason": "repeated_action_stop",
                        "tool": action_payload["tool"],
                    }
                )
                logger.info(
                    f"[Agent] Stop | repeated action `{action_payload['tool']}` {repeated_action_count} times."
                )
                break

            tool_result = self._execute_tool(
                action_payload["tool"],
                action_payload["arguments"],
            )
            self._remember_tool_state(action_payload["tool"], tool_result, action_payload["arguments"])
            observation = self._build_observation(tool_result)
            logger.log_event(
                "AGENT_OBSERVATION",
                {
                    "step": steps,
                    "tool_name": action_payload["tool"],
                    "observation": observation,
                },
            )
            observation_status, observation_summary = self._summarize_observation_for_console(
                observation
            )
            self._emit_event(
                {
                    "type": "tool_result",
                    "step": steps,
                    "tool": action_payload["tool"],
                    "status": observation_status,
                    "summary": observation_summary,
                    "observation": observation,
                }
            )
            logger.info(
                f"[Agent] Observation | tool={action_payload['tool']} | status={observation_status} | {observation_summary}"
            )
            logger.info(
                f"[Tool] {'Success' if observation_status == 'SUCCESS' else 'Fail'} | name={action_payload['tool']} | {observation_summary}"
            )

            conversation_trace.append(content)
            conversation_trace.append(f"Observation: {observation}")
            self.history[-1]["action"] = action_payload
            self.history[-1]["observation"] = observation

        if final_answer is None:
            final_answer = self._build_fallback_answer(
                reason=(
                    f"Agent reached max_steps={self.max_steps} without producing a Final Answer."
                )
            )
            self._emit_event(
                {
                    "type": "final_answer",
                    "step": len(self.history),
                    "final_answer": final_answer,
                }
            )

        logger.log_event(
            "AGENT_END",
            {"steps": len(self.history), "final_status": final_status, "history": self.history},
        )
        self._emit_event(
            {
                "type": "agent_end",
                "steps": len(self.history),
                "final_status": final_status,
            }
        )
        logger.info(f"[Agent] End | status={final_status} | steps={len(self.history)}")
        return final_answer

    def _tool_attr(self, tool: Any, name: str, default: Any = None) -> Any:
        if isinstance(tool, dict):
            return tool.get(name, default)
        return getattr(tool, name, default)

    def _emit_event(self, payload: Dict[str, Any]) -> None:
        if self.event_callback is None:
            return
        try:
            self.event_callback(payload)
        except Exception:
            pass

    def _extract_thought(self, text: str) -> Optional[str]:
        match = re.search(r"Thought:\s*(.+?)(?:\nAction:|\nFinal Answer:|$)", text, re.DOTALL)
        if not match:
            return None
        thought = " ".join(match.group(1).strip().split())
        return thought or None

    def _extract_final_answer(self, text: str) -> Optional[str]:
        match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
        if not match:
            return None
        answer = match.group(1).strip()
        return answer or None

    def _extract_action_payload(self, text: str) -> Dict[str, Any]:
        marker = "Action:"
        marker_index = text.find(marker)
        if marker_index == -1:
            raise ValueError("Response is missing an `Action:` block.")

        raw_action = text[marker_index + len(marker):].strip()
        raw_json = self._extract_first_json_object(raw_action)
        return self._safe_parse_action_json(raw_json)

    def _safe_parse_action_json(self, raw: str) -> Dict[str, Any]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Action JSON is invalid: {exc.msg}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Action payload must be a JSON object.")
        if set(payload.keys()) != {"tool", "arguments"}:
            raise ValueError("Action JSON must contain exactly `tool` and `arguments` keys.")
        if not isinstance(payload["tool"], str) or not payload["tool"].strip():
            raise ValueError("`tool` must be a non-empty string.")
        if not isinstance(payload["arguments"], dict):
            raise ValueError("`arguments` must be a JSON object.")
        return payload

    def _extract_first_json_object(self, text: str) -> str:
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found after `Action:`.")

        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        raise ValueError("Could not find a complete JSON object for `Action:`.")

    def _build_observation(self, tool_result: Any) -> str:
        payload = tool_result
        if isinstance(tool_result, str):
            try:
                payload = json.loads(tool_result)
            except json.JSONDecodeError:
                payload = {"status": "error", "summary": tool_result}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _summarize_arguments(self, arguments: Dict[str, Any]) -> str:
        if not arguments:
            return "{}"
        keys = sorted(arguments.keys())
        summary = ", ".join(keys[:6])
        if len(keys) > 6:
            summary += ", ..."
        return "{" + summary + "}"

    def _summarize_observation_for_console(self, observation: str) -> tuple[str, str]:
        try:
            payload = json.loads(observation)
        except json.JSONDecodeError:
            return ("FAIL", observation[:200])

        raw_status = str(payload.get("status", "unknown")).lower()
        status = "SUCCESS" if raw_status == "ok" else "FAIL"
        summary = str(payload.get("summary", "No summary provided."))
        errors = payload.get("errors") or []
        if status == "FAIL" and errors:
            first_error = errors[0]
            summary = f"{summary} | first_error={str(first_error)[:180]}"
        return (status, summary)

    def _error_payload(
        self,
        *,
        tool_name: str,
        summary: str,
        errors: list[str],
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "tool": tool_name,
            "summary": summary,
            "data": data or {},
            "warnings": [],
            "errors": errors,
        }

    def _build_fallback_answer(self, reason: str) -> str:
        return (
            "Agent could not complete the full ReAct workflow.\n"
            f"Reason: {reason}\n"
            "Please review the latest observations in the logs and retry with a clearer prompt or a higher max_steps value."
        )

    def _infer_allergy_groups_from_text(self, text: str) -> list[Dict[str, Any]]:
        lowered = text.lower()
        allergen_aliases = {
            "milk": ["milk", "dairy", "sua", "sữa"],
            "egg": ["egg", "eggs", "trung", "trứng"],
            "soy": ["soy", "soya", "dau hu", "đậu hũ", "dau nanh", "đậu nành"],
            "shellfish": ["shellfish", "shrimp", "tom", "tôm"],
        }

        groups: list[Dict[str, Any]] = []
        for allergen, aliases in allergen_aliases.items():
            if any(alias in lowered for alias in aliases):
                groups.append(
                    {
                        "name": f"{allergen}_allergy",
                        "forbidden_allergens": [allergen],
                    }
                )
        return groups

    def _normalize_allergy_groups(self, value: Any) -> list[Dict[str, Any]]:
        if not value:
            return []
        if isinstance(value, list):
            normalized: list[Dict[str, Any]] = []
            for entry in value:
                if isinstance(entry, str):
                    allergen = entry.strip().lower()
                    if allergen.endswith("s") and allergen[:-1] in {"egg"}:
                        allergen = allergen[:-1]
                    if allergen:
                        normalized.append(
                            {
                                "name": f"{allergen}_allergy",
                                "forbidden_allergens": [allergen],
                            }
                        )
                elif isinstance(entry, dict) and "forbidden_allergens" in entry:
                    normalized.append(entry)
            return normalized
        return []

    def _weekly_menu_looks_complete(self, weekly_menu: Any) -> bool:
        if not isinstance(weekly_menu, dict):
            return False
        days = weekly_menu.get("days")
        if not isinstance(days, list) or not days:
            return False
        required_day_keys = ["staple", "main", "vegetable", "soup", "fruit"]
        sample_day = days[0]
        if not isinstance(sample_day, dict):
            return False
        for key in required_day_keys:
            dish = sample_day.get(key)
            if not isinstance(dish, dict):
                return False
            required_dish_keys = ["id", "name", "category", "ingredients", "cost_per_serving_vnd", "nutrition_per_serving"]
            if any(field not in dish for field in required_dish_keys):
                return False
        return True

    def _coerce_generate_weekly_menu_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(arguments)
        constraints = dict(normalized.get("constraints", {}))

        budget = (
            normalized.pop("budget_per_student_vnd", None)
            or normalized.pop("budget_per_serving", None)
            or normalized.pop("budget_per_student", None)
            or normalized.pop("budget", None)
        )
        if budget is not None:
            constraints["budget_per_student_vnd"] = budget

        student_count = normalized.pop("student_count", None)
        if student_count is not None:
            constraints["student_count"] = student_count

        fried_limit = normalized.pop("max_fried_per_week", None)
        if fried_limit is not None:
            constraints["max_fried_per_week"] = fried_limit

        repeat_constraint = normalized.pop("repeat_constraints", None)
        simple_repeat = normalized.pop("simple_repeat", None)
        if repeat_constraint == "no_consecutive" or simple_repeat is True:
            constraints["no_consecutive_repeat_categories"] = ["main"]

        if constraints:
            normalized["constraints"] = constraints

        allergy_groups = (
            normalized.pop("allergy_groups", None)
            or normalized.pop("allergen_groups", None)
            or normalized.pop("avoid_allergens", None)
        )
        normalized_allergies = self._normalize_allergy_groups(allergy_groups)
        if normalized_allergies:
            normalized["allergy_groups"] = normalized_allergies

        return normalized

    def _prepare_tool_arguments(self, tool_name: str, arguments: Any) -> Dict[str, Any]:
        if not isinstance(arguments, dict):
            return {}

        prepared = dict(arguments)
        if tool_name == "generate_weekly_menu":
            prepared = self._coerce_generate_weekly_menu_arguments(prepared)

        menu_data = prepared.pop("menu_data", None)
        if isinstance(menu_data, dict) and "weekly_menu" in menu_data and "weekly_menu" not in prepared:
            prepared["weekly_menu"] = menu_data["weekly_menu"]

        alias_allergies = (
            prepared.pop("allergen_groups", None)
            or prepared.pop("avoid_allergens", None)
        )
        if alias_allergies and "allergy_groups" not in prepared:
            prepared["allergy_groups"] = self._normalize_allergy_groups(alias_allergies)

        if tool_name in {
            "analyze_nutrition",
            "check_allergens",
            "suggest_substitutions",
            "check_constraints",
        }:
            if self.cached_weekly_menu and not self._weekly_menu_looks_complete(prepared.get("weekly_menu")):
                prepared["weekly_menu"] = self.cached_weekly_menu

        if tool_name in {"generate_weekly_menu", "check_allergens", "suggest_substitutions"}:
            normalized_allergies = self._normalize_allergy_groups(prepared.get("allergy_groups"))
            if normalized_allergies:
                prepared["allergy_groups"] = normalized_allergies
            elif self.cached_allergy_groups:
                prepared["allergy_groups"] = self.cached_allergy_groups

        return prepared

    def _remember_tool_state(self, tool_name: str, tool_result: Any, arguments: Dict[str, Any]) -> None:
        normalized_allergies = self._normalize_allergy_groups(arguments.get("allergy_groups"))
        if normalized_allergies:
            self.cached_allergy_groups = normalized_allergies

        payload = tool_result
        if isinstance(tool_result, str):
            try:
                payload = json.loads(tool_result)
            except json.JSONDecodeError:
                return

        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return

        data = payload.get("data") or {}
        weekly_menu = data.get("weekly_menu")
        if self._weekly_menu_looks_complete(weekly_menu):
            self.cached_weekly_menu = weekly_menu

    def _execute_tool(self, tool_name: str, args: Any) -> str:
        for tool in self.tools:
            if self._tool_attr(tool, "name") == tool_name:
                handler = self._tool_attr(tool, "handler")
                input_model = self._tool_attr(tool, "input_model")
                if not callable(handler):
                    return json.dumps(
                        self._error_payload(
                            tool_name=tool_name,
                            summary=f"Tool `{tool_name}` is not callable.",
                            errors=[f"Handler for tool `{tool_name}` is missing or invalid."],
                        ),
                        ensure_ascii=False,
                    )
                try:
                    parsed_args: Any = args
                    if isinstance(args, str):
                        parsed_args = json.loads(args)
                    if input_model is not None and isinstance(parsed_args, dict):
                        parsed_args = input_model.model_validate(parsed_args)
                    result = handler(parsed_args)
                    if hasattr(result, "model_dump_json"):
                        return result.model_dump_json()
                    return str(result)
                except ValidationError as exc:
                    return json.dumps(
                        self._error_payload(
                            tool_name=tool_name,
                            summary=f"Tool `{tool_name}` rejected the input arguments.",
                            errors=[json.dumps(exc.errors(), ensure_ascii=False)],
                        ),
                        ensure_ascii=False,
                    )
                except Exception as exc:
                    return json.dumps(
                        self._error_payload(
                            tool_name=tool_name,
                            summary=f"Tool `{tool_name}` execution failed.",
                            errors=[str(exc)],
                        ),
                        ensure_ascii=False,
                    )
        return json.dumps(
            self._error_payload(
                tool_name=tool_name,
                summary=f"Tool `{tool_name}` not found.",
                errors=[f"Tool `{tool_name}` is not registered in this agent."],
            ),
            ensure_ascii=False,
        )
