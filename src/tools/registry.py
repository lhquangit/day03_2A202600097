from __future__ import annotations

from src.tools.analyze_nutrition import analyze_nutrition
from src.tools.base import ToolSpec
from src.tools.check_allergens import check_allergens
from src.tools.check_constraints import check_constraints
from src.tools.generate_weekly_menu import generate_weekly_menu
from src.tools.models import (
    AnalyzeNutritionInput,
    AnalyzeNutritionOutput,
    CheckAllergensInput,
    CheckAllergensOutput,
    CheckConstraintsInput,
    CheckConstraintsOutput,
    GenerateWeeklyMenuInput,
    GenerateWeeklyMenuOutput,
    SuggestSubstitutionsInput,
    SuggestSubstitutionsOutput,
)
from src.tools.suggest_substitutions import suggest_substitutions

TOOL_REGISTRY: list[ToolSpec] = [
    ToolSpec(
        name="generate_weekly_menu",
        description=(
            "Generate a deterministic 5-day school lunch menu from the local dish catalog using "
            "budget, student count, required meal structure, allergen groups, and simple repeat/frying constraints. "
            "Returns the weekly menu plus daily cost and nutrition estimates."
        ),
        input_model=GenerateWeeklyMenuInput,
        output_model=GenerateWeeklyMenuOutput,
        handler=generate_weekly_menu,
    ),
    ToolSpec(
        name="analyze_nutrition",
        description=(
            "Calculate calories, protein, and fiber for each day in a 5-day menu. "
            "Use this after a menu is drafted to verify which days pass or fail the nutrition targets."
        ),
        input_model=AnalyzeNutritionInput,
        output_model=AnalyzeNutritionOutput,
        handler=analyze_nutrition,
    ),
    ToolSpec(
        name="check_allergens",
        description=(
            "Audit a weekly menu against named allergy groups such as milk or egg allergies. "
            "Returns exact day, dish, component, and matched allergens for every violation."
        ),
        input_model=CheckAllergensInput,
        output_model=CheckAllergensOutput,
        handler=check_allergens,
    ),
    ToolSpec(
        name="suggest_substitutions",
        description=(
            "Suggest safe replacement dishes for allergen violations while keeping the same meal component "
            "category. Returns delta cost, delta nutrition, and unresolved violations if the catalog has no safe substitute."
        ),
        input_model=SuggestSubstitutionsInput,
        output_model=SuggestSubstitutionsOutput,
        handler=suggest_substitutions,
    ),
    ToolSpec(
        name="check_constraints",
        description=(
            "Run the final gate on a weekly menu. Checks budget per serving, required meal structure, "
            "consecutive-repeat rules, optional frying limits, and optional nutrition targets."
        ),
        input_model=CheckConstraintsInput,
        output_model=CheckConstraintsOutput,
        handler=check_constraints,
    ),
]


def get_tool_registry() -> list[ToolSpec]:
    return TOOL_REGISTRY.copy()


def get_agent_tools() -> list[dict[str, object]]:
    return [tool.to_agent_dict() for tool in TOOL_REGISTRY]
