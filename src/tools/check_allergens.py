from __future__ import annotations

from src.tools.models import (
    AllergenCheckData,
    AllergenViolation,
    CheckAllergensInput,
    CheckAllergensOutput,
)
from src.tools.utils import flatten_menu_day


def check_allergens(payload: CheckAllergensInput) -> CheckAllergensOutput:
    violations: list[AllergenViolation] = []

    for group in payload.allergy_groups:
        forbidden = set(group.forbidden_allergens)
        for day in payload.weekly_menu.days:
            for component, dish in flatten_menu_day(day).items():
                matched = sorted(forbidden.intersection(dish.allergens))
                if matched:
                    violations.append(
                        AllergenViolation(
                            day_label=day.day_label,
                            group_name=group.name,
                            component=component,
                            dish_id=dish.id,
                            dish_name=dish.name,
                            matched_allergens=matched,
                        )
                    )

    summary = (
        f"Found {len(violations)} allergen violations."
        if violations
        else "No allergen violations found for the supplied groups."
    )

    return CheckAllergensOutput(
        tool="check_allergens",
        summary=summary,
        data=AllergenCheckData(
            violations=violations,
            total_violations=len(violations),
            groups_checked=[group.name for group in payload.allergy_groups],
        ),
    )
