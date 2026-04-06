import json

from src.telemetry.logger import logger
from src.tools.check_allergens import check_allergens
from src.tools.check_constraints import check_constraints
from src.tools.generate_weekly_menu import generate_weekly_menu
from src.tools.models import (
    AllergyGroup,
    CheckAllergensInput,
    CheckConstraintsInput,
    ConstraintSet,
    GenerateWeeklyMenuInput,
    SuggestSubstitutionsInput,
)
from src.tools.suggest_substitutions import suggest_substitutions
from src.tools.analyze_nutrition import analyze_nutrition
from src.tools.models import AnalyzeNutritionInput


def _print_output(title: str, payload: object) -> None:
    print(f"\n=== {title} ===")
    if hasattr(payload, "model_dump"):
        print(json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(payload)


def main() -> None:
    with logger.capture_console() as log_path:
        print(f"Run log file: {log_path}")

        allergy_groups = [
            AllergyGroup(name="milk_allergy", forbidden_allergens=["milk"]),
            AllergyGroup(name="egg_allergy", forbidden_allergens=["egg"]),
        ]
        constraints = ConstraintSet(
            budget_per_student_vnd=28000,
            student_count=800,
            max_fried_per_week=2,
            no_consecutive_repeat_categories=["main"],
        )

        menu_result = generate_weekly_menu(
            GenerateWeeklyMenuInput(
                constraints=constraints,
                allergy_groups=allergy_groups,
            )
        )
        logger.log_event("TOOL_OUTPUT", {"tool": "generate_weekly_menu", "status": menu_result.status})
        _print_output("generate_weekly_menu", menu_result)

        if not menu_result.data:
            print("Menu generation failed. Stopping demo run.")
            return

        weekly_menu = menu_result.data.weekly_menu

        nutrition_result = analyze_nutrition(
            AnalyzeNutritionInput(weekly_menu=weekly_menu)
        )
        logger.log_event("TOOL_OUTPUT", {"tool": "analyze_nutrition", "status": nutrition_result.status})
        _print_output("analyze_nutrition", nutrition_result)

        allergen_result = check_allergens(
            CheckAllergensInput(weekly_menu=weekly_menu, allergy_groups=allergy_groups)
        )
        logger.log_event("TOOL_OUTPUT", {"tool": "check_allergens", "status": allergen_result.status})
        _print_output("check_allergens", allergen_result)

        substitution_result = suggest_substitutions(
            SuggestSubstitutionsInput(weekly_menu=weekly_menu, allergy_groups=allergy_groups)
        )
        logger.log_event("TOOL_OUTPUT", {"tool": "suggest_substitutions", "status": substitution_result.status})
        _print_output("suggest_substitutions", substitution_result)

        constraint_result = check_constraints(
            CheckConstraintsInput(
                weekly_menu=weekly_menu,
                constraints=constraints,
                nutrition_targets=GenerateWeeklyMenuInput().nutrition_targets,
            )
        )
        logger.log_event("TOOL_OUTPUT", {"tool": "check_constraints", "status": constraint_result.status})
        _print_output("check_constraints", constraint_result)


if __name__ == "__main__":
    main()
