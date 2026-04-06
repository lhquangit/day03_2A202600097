from pydantic import BaseModel

from src.tools.registry import get_agent_tools, get_tool_registry


def test_registry_loads_all_five_tools():
    registry = get_tool_registry()
    names = [tool.name for tool in registry]
    assert names == [
        "generate_weekly_menu",
        "analyze_nutrition",
        "check_allergens",
        "suggest_substitutions",
        "check_constraints",
    ]


def test_registry_exposes_complete_tool_metadata():
    registry = get_tool_registry()
    for tool in registry:
        assert tool.description
        assert callable(tool.handler)
        assert issubclass(tool.input_model, BaseModel)
        assert issubclass(tool.output_model, BaseModel)


def test_agent_tool_inventory_keeps_legacy_shape():
    agent_tools = get_agent_tools()
    assert len(agent_tools) == 5
    for tool in agent_tools:
        assert set(["name", "description", "input_model", "output_model", "handler"]).issubset(
            tool.keys()
        )
