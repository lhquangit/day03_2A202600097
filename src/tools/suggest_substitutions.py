from __future__ import annotations

from src.tools.check_allergens import check_allergens
from src.tools.models import (
    CheckAllergensInput,
    Dish,
    SubstitutionData,
    SubstitutionSuggestion,
    SuggestSubstitutionsInput,
    SuggestSubstitutionsOutput,
)
from src.tools.utils import find_safe_substitute, flatten_menu_day, get_catalog


def _nutrition_delta(original: Dish, substitute: Dish) -> tuple[float, float, float]:
    return (
        round(substitute.nutrition_per_serving.calories - original.nutrition_per_serving.calories, 1),
        round(substitute.nutrition_per_serving.protein_g - original.nutrition_per_serving.protein_g, 1),
        round(substitute.nutrition_per_serving.fiber_g - original.nutrition_per_serving.fiber_g, 1),
    )


def suggest_substitutions(payload: SuggestSubstitutionsInput) -> SuggestSubstitutionsOutput:
    catalog = get_catalog(payload.catalog)
    allergen_result = check_allergens(
        CheckAllergensInput(weekly_menu=payload.weekly_menu, allergy_groups=payload.allergy_groups)
    )
    violations = allergen_result.data.violations if allergen_result.data else []

    suggestions: list[SubstitutionSuggestion] = []
    unresolved = []

    for violation in violations:
        day = next(day for day in payload.weekly_menu.days if day.day_label == violation.day_label)
        original_dish = flatten_menu_day(day)[violation.component]
        substitute = find_safe_substitute(
            category=violation.component,
            catalog=catalog,
            forbidden_allergens=set(violation.matched_allergens),
            exclude_dish_id=original_dish.id,
        )
        if substitute is None:
            unresolved.append(violation)
            continue

        delta_calories, delta_protein_g, delta_fiber_g = _nutrition_delta(original_dish, substitute)
        suggestions.append(
            SubstitutionSuggestion(
                day_label=violation.day_label,
                group_name=violation.group_name,
                component=violation.component,
                original_dish_id=original_dish.id,
                original_dish_name=original_dish.name,
                substitute_dish=substitute,
                matched_allergens=violation.matched_allergens,
                delta_cost_per_serving_vnd=substitute.cost_per_serving_vnd - original_dish.cost_per_serving_vnd,
                delta_calories=delta_calories,
                delta_protein_g=delta_protein_g,
                delta_fiber_g=delta_fiber_g,
                rationale=(
                    f"Selected {substitute.name} because it stays in the {violation.component} category "
                    f"and excludes {', '.join(violation.matched_allergens)}."
                ),
            )
        )

    warnings = []
    if unresolved:
        warnings.append(f"Could not resolve {len(unresolved)} allergen violations with the current catalog.")

    return SuggestSubstitutionsOutput(
        tool="suggest_substitutions",
        summary=f"Prepared {len(suggestions)} substitution suggestions.",
        warnings=warnings,
        data=SubstitutionData(suggestions=suggestions, unresolved_violations=unresolved),
    )
