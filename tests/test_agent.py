from __future__ import annotations

import json

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.tools import get_agent_tools
from src.tools.generate_weekly_menu import generate_weekly_menu
from src.tools.models import (
    AllergyGroup,
    GenerateWeeklyMenuInput,
    MenuDay,
    WeeklyMenu,
)
from run_agent_demo import run_agent_session


class MockLLMProvider(LLMProvider):
    def __init__(self, responses: list[str]):
        super().__init__(model_name="mock-llm")
        self.responses = list(responses)
        self.calls: list[dict[str, str | None]] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> dict[str, object]:
        if not self.responses:
            raise RuntimeError("No mock responses remaining.")
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        content = self.responses.pop(0)
        return {
            "content": content,
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "latency_ms": 1,
            "provider": "mock",
        }

    def stream(self, prompt: str, system_prompt: str | None = None):
        yield from []


def _build_violation_menu() -> WeeklyMenu:
    generated = generate_weekly_menu(GenerateWeeklyMenuInput()).data.weekly_menu
    monday = MenuDay(
        day_label=generated.days[0].day_label,
        staple=generated.days[0].staple,
        main=next(
            dish
            for dish in [
                generated.days[0].main,
                generated.days[1].main,
                generated.days[2].main,
                generated.days[3].main,
                generated.days[4].main,
            ]
            if dish.id == "crispy_fish_fillet"
        )
        if any(day.main.id == "crispy_fish_fillet" for day in generated.days)
        else generated.days[0].main,
        vegetable=generated.days[0].vegetable,
        soup=generated.days[0].soup,
        fruit=generated.days[0].fruit,
    )
    catalog_days = generated.days[1:]
    return WeeklyMenu(days=[monday, *catalog_days])


def _build_egg_milk_violation_menu() -> WeeklyMenu:
    from src.tools.catalog import get_mock_catalog

    catalog = {dish.id: dish for dish in get_mock_catalog()}
    return WeeklyMenu(
        days=[
            MenuDay(
                day_label="Monday",
                staple=catalog["white_rice"],
                main=catalog["braised_pork_with_egg"],
                vegetable=catalog["buttered_corn"],
                soup=catalog["creamy_corn_soup"],
                fruit=catalog["banana"],
            ),
            MenuDay(
                day_label="Tuesday",
                staple=catalog["brown_rice"],
                main=catalog["ginger_chicken"],
                vegetable=catalog["garlic_mustard_greens"],
                soup=catalog["pumpkin_minced_pork_soup"],
                fruit=catalog["orange"],
            ),
            MenuDay(
                day_label="Wednesday",
                staple=catalog["mixed_grain_rice"],
                main=catalog["grilled_pork"],
                vegetable=catalog["carrot_green_beans"],
                soup=catalog["cabbage_meat_soup"],
                fruit=catalog["dragon_fruit"],
            ),
            MenuDay(
                day_label="Thursday",
                staple=catalog["turmeric_rice"],
                main=catalog["beef_onion"],
                vegetable=catalog["steamed_pumpkin"],
                soup=catalog["spinach_meat_soup"],
                fruit=catalog["apple"],
            ),
            MenuDay(
                day_label="Friday",
                staple=catalog["white_rice"],
                main=catalog["tofu_meat_sauce"],
                vegetable=catalog["stir_fried_chayote"],
                soup=catalog["mustard_green_tofu_soup"],
                fruit=catalog["pear"],
            ),
        ]
    )


def test_extract_action_payload_parses_raw_json():
    agent = ReActAgent(llm=MockLLMProvider([]), tools=get_agent_tools())

    payload = agent._extract_action_payload(
        'Thought: Need a draft menu.\nAction: {"tool":"generate_weekly_menu","arguments":{}}'
    )

    assert payload == {"tool": "generate_weekly_menu", "arguments": {}}


def test_extract_final_answer_returns_content_without_action():
    agent = ReActAgent(llm=MockLLMProvider([]), tools=get_agent_tools())

    final_answer = agent._extract_final_answer(
        "Thought: I have enough information.\nFinal Answer: Here is the finished menu."
    )

    assert final_answer == "Here is the finished menu."


def test_safe_parse_action_json_supports_code_fences():
    agent = ReActAgent(llm=MockLLMProvider([]), tools=get_agent_tools())

    payload = agent._safe_parse_action_json(
        '```json\n{"tool":"check_constraints","arguments":{"weekly_menu":{"days":[]}}}\n```'
    )

    assert payload["tool"] == "check_constraints"


def test_react_agent_runs_generate_menu_then_final_answer():
    llm = MockLLMProvider(
        [
            'Thought: I should draft the menu first.\nAction: {"tool":"generate_weekly_menu","arguments":{}}',
            "Thought: I now have the weekly menu.\nFinal Answer: Menu draft completed.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=3)

    result = agent.run("Create a weekly menu for 800 students.")

    assert result == "Menu draft completed."
    assert len(llm.calls) == 2
    assert "Observation:" in llm.calls[1]["prompt"]
    assert '"tool":"generate_weekly_menu"' in llm.calls[1]["prompt"]


def test_react_agent_supports_multi_tool_flow():
    weekly_menu = generate_weekly_menu(GenerateWeeklyMenuInput()).data.weekly_menu.model_dump(mode="json")
    allergy_groups = [
        {"name": "milk_allergy", "forbidden_allergens": ["milk"]},
        {"name": "egg_allergy", "forbidden_allergens": ["egg"]},
    ]
    llm = MockLLMProvider(
        [
            'Thought: Start with a draft.\nAction: {"tool":"generate_weekly_menu","arguments":{}}',
            (
                "Thought: Verify nutrition next.\nAction: "
                + json.dumps({"tool": "analyze_nutrition", "arguments": {"weekly_menu": weekly_menu}})
            ),
            (
                "Thought: Audit allergies now.\nAction: "
                + json.dumps(
                    {
                        "tool": "check_allergens",
                        "arguments": {"weekly_menu": weekly_menu, "allergy_groups": allergy_groups},
                    }
                )
            ),
            (
                "Thought: Run the final constraint gate.\nAction: "
                + json.dumps(
                    {
                        "tool": "check_constraints",
                        "arguments": {
                            "weekly_menu": weekly_menu,
                            "constraints": {
                                "budget_per_student_vnd": 28000,
                                "student_count": 800,
                                "max_fried_per_week": 2,
                                "no_consecutive_repeat_categories": ["main"],
                            },
                            "nutrition_targets": {
                                "calories_min": 550,
                                "calories_max": 650,
                                "protein_g_min": 18,
                                "protein_g_max": 25,
                                "fiber_g_min": 6,
                            },
                        },
                    }
                )
            ),
            "Thought: I have enough evidence.\nFinal Answer: Full tool flow completed.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=6)

    result = agent.run("Build and verify a compliant weekly menu.")

    assert result == "Full tool flow completed."
    assert len(llm.calls) == 5
    assert '"tool":"check_constraints"' in llm.calls[-1]["prompt"]


def test_react_agent_calls_suggest_substitutions_for_allergen_violations():
    weekly_menu = _build_egg_milk_violation_menu().model_dump(mode="json")
    allergy_groups = [
        {"name": "milk_allergy", "forbidden_allergens": ["milk"]},
        {"name": "egg_allergy", "forbidden_allergens": ["egg"]},
    ]
    llm = MockLLMProvider(
        [
            (
                "Thought: Check allergies first.\nAction: "
                + json.dumps(
                    {
                        "tool": "check_allergens",
                        "arguments": {"weekly_menu": weekly_menu, "allergy_groups": allergy_groups},
                    }
                )
            ),
            (
                "Thought: I found violations, so I need suggestions.\nAction: "
                + json.dumps(
                    {
                        "tool": "suggest_substitutions",
                        "arguments": {"weekly_menu": weekly_menu, "allergy_groups": allergy_groups},
                    }
                )
            ),
            "Thought: I can summarize now.\nFinal Answer: Suggested substitutions are ready.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=4)

    result = agent.run("Check allergen safety and propose substitutions.")

    assert result == "Suggested substitutions are ready."
    assert '"tool":"suggest_substitutions"' in llm.calls[-1]["prompt"]


def test_react_agent_reuses_cached_weekly_menu_for_check_allergens():
    llm = MockLLMProvider(
        [
            (
                "Thought: Draft the menu first.\nAction: "
                '{"tool":"generate_weekly_menu","arguments":{"budget_per_serving":28000,"student_count":800,"allergen_groups":["milk","egg"]}}'
            ),
            (
                "Thought: Check allergies now.\nAction: "
                + json.dumps(
                    {
                        "tool": "check_allergens",
                        "arguments": {
                            "weekly_menu": {
                                "days": [
                                    {
                                        "day_label": "Monday",
                                        "staple": {"id": "brown_rice", "name": "Com gao lut", "allergens": []},
                                        "main": {"id": "beef_onion", "name": "Bo xao hanh tay", "allergens": []},
                                        "vegetable": {"id": "bok_choy_garlic", "name": "Cai thia xao toi", "allergens": []},
                                        "soup": {"id": "amaranth_shrimp_soup", "name": "Canh mong toi nau tom", "allergens": ["shellfish"]},
                                        "fruit": {"id": "apple", "name": "Tao", "allergens": []},
                                    }
                                ]
                            }
                        },
                    }
                )
            ),
            "Thought: I can summarize now.\nFinal Answer: Cached weekly menu was reused safely.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=4)

    result = agent.run("Build a weekly menu for students with milk and egg allergies.")

    assert result == "Cached weekly menu was reused safely."
    assert '"tool":"check_allergens"' in llm.calls[2]["prompt"]
    assert '"status":"ok"' in llm.calls[2]["prompt"]
    assert '"groups_checked":["milk_allergy","egg_allergy"]' in llm.calls[2]["prompt"]


def test_react_agent_handles_unknown_tool_gracefully():
    llm = MockLLMProvider(
        [
            'Thought: I will call a missing tool.\nAction: {"tool":"imaginary_tool","arguments":{}}',
            "Thought: The tool failed, so I will finish.\nFinal Answer: Unknown tool was handled safely.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=3)

    result = agent.run("Try a missing tool.")

    assert result == "Unknown tool was handled safely."
    assert '"status":"error"' in llm.calls[1]["prompt"]
    assert "imaginary_tool" in llm.calls[1]["prompt"]


def test_react_agent_handles_malformed_action_and_recovers():
    llm = MockLLMProvider(
        [
            'Thought: I should act.\nAction: {"tool":"generate_weekly_menu","arguments":',
            "Thought: I will stop after the parser error.\nFinal Answer: Parser error handled.",
        ]
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=3)

    result = agent.run("Trigger a parser error.")

    assert result == "Parser error handled."
    assert "Could not parse Action" in llm.calls[1]["prompt"]


def test_react_agent_returns_timeout_fallback_when_no_final_answer():
    llm = MockLLMProvider(
        ['Thought: Draft first.\nAction: {"tool":"generate_weekly_menu","arguments":{}}']
    )
    agent = ReActAgent(llm=llm, tools=get_agent_tools(), max_steps=1)

    result = agent.run("Create a menu but never finish.")

    assert "Agent could not complete the full ReAct workflow." in result
    assert "max_steps=1" in result


def test_run_agent_session_creates_log_file(tmp_path):
    llm = MockLLMProvider(
        ["Thought: I already know the answer.\nFinal Answer: Demo runner completed."]
    )
    log_path = tmp_path / "agent_run.log"

    final_answer, saved_log_path, json_log_path = run_agent_session(
        "Summarize the menu status.",
        llm=llm,
        max_steps=2,
        log_path=str(log_path),
    )

    assert final_answer == "Demo runner completed."
    assert saved_log_path == str(log_path)
    assert log_path.exists()
    log_contents = log_path.read_text(encoding="utf-8")
    assert "Demo runner completed." in log_contents
    assert "Run log file:" in log_contents
    assert "Agent answer JSON:" in log_contents
    assert "Agent answer TXT:" in log_contents

    with open(json_log_path, "r", encoding="utf-8") as file_stream:
        payload = json.load(file_stream)
    assert payload["status"] == "success"
    assert payload["final_answer"] == "Demo runner completed."
    assert payload["final_answer_text_path"]

    txt_path = payload["final_answer_text_path"]
    with open(txt_path, "r", encoding="utf-8") as file_stream:
        txt_payload = file_stream.read()
    assert "Demo runner completed." in txt_payload
