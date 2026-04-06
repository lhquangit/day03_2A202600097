from __future__ import annotations

from src.tools.models import (
    CheckConstraintsInput,
    CheckConstraintsOutput,
    ConstraintCheckData,
    ConstraintViolation,
)
from src.tools.utils import calculate_day_cost, calculate_day_nutrition, count_tagged_dishes, flatten_menu_day


def check_constraints(payload: CheckConstraintsInput) -> CheckConstraintsOutput:
    violations: list[ConstraintViolation] = []
    daily_costs = [
        calculate_day_cost(day, payload.constraints.student_count) for day in payload.weekly_menu.days
    ]

    budget_ok = True
    for cost_report in daily_costs:
        if cost_report.per_serving_vnd > payload.constraints.budget_per_student_vnd:
            budget_ok = False
            violations.append(
                ConstraintViolation(
                    rule="budget_per_student_vnd",
                    day_label=cost_report.day_label,
                    message=(
                        f"{cost_report.day_label} costs {cost_report.per_serving_vnd} VND per serving, "
                        f"above the {payload.constraints.budget_per_student_vnd} VND budget."
                    ),
                )
            )

    meal_structure_ok = True
    for day in payload.weekly_menu.days:
        components = flatten_menu_day(day)
        for category in payload.constraints.required_categories:
            if category not in components:
                meal_structure_ok = False
                violations.append(
                    ConstraintViolation(
                        rule="required_categories",
                        day_label=day.day_label,
                        message=f"{day.day_label} is missing required category '{category}'.",
                    )
                )

    no_consecutive_repeat_ok = True
    previous_day = None
    for day in payload.weekly_menu.days:
        if previous_day is not None:
            for category in payload.constraints.no_consecutive_repeat_categories:
                current_dish = getattr(day, category)
                previous_dish = getattr(previous_day, category)
                if current_dish.id == previous_dish.id:
                    no_consecutive_repeat_ok = False
                    violations.append(
                        ConstraintViolation(
                            rule="no_consecutive_repeat_categories",
                            day_label=day.day_label,
                            message=(
                                f"{category} repeats on consecutive days: "
                                f"{previous_day.day_label} and {day.day_label} both use {current_dish.name}."
                            ),
                        )
                    )
        previous_day = day

    fry_limit_ok = True
    if payload.constraints.max_fried_per_week is not None:
        fried_count = count_tagged_dishes(payload.weekly_menu, "fried")
        if fried_count > payload.constraints.max_fried_per_week:
            fry_limit_ok = False
            violations.append(
                ConstraintViolation(
                    rule="max_fried_per_week",
                    message=(
                        f"Weekly menu contains {fried_count} fried dishes, above the limit of "
                        f"{payload.constraints.max_fried_per_week}."
                    ),
                )
            )

    nutrition_reports = []
    nutrition_ok: bool | None = None
    if payload.nutrition_targets is not None:
        nutrition_reports = [
            calculate_day_nutrition(day, payload.nutrition_targets) for day in payload.weekly_menu.days
        ]
        nutrition_ok = all(report.within_target for report in nutrition_reports)
        for report in nutrition_reports:
            for issue in report.issues:
                violations.append(
                    ConstraintViolation(
                        rule="nutrition_targets",
                        day_label=report.day_label,
                        message=issue,
                    )
                )

    summary_parts = []
    summary_parts.append("budget ok" if budget_ok else "budget failed")
    summary_parts.append("structure ok" if meal_structure_ok else "structure failed")
    summary_parts.append("repeat ok" if no_consecutive_repeat_ok else "repeat failed")
    summary_parts.append("fry ok" if fry_limit_ok else "fry failed")
    if nutrition_ok is not None:
        summary_parts.append("nutrition ok" if nutrition_ok else "nutrition failed")

    return CheckConstraintsOutput(
        tool="check_constraints",
        summary=", ".join(summary_parts).capitalize() + ".",
        warnings=[violation.message for violation in violations],
        data=ConstraintCheckData(
            budget_ok=budget_ok,
            meal_structure_ok=meal_structure_ok,
            no_consecutive_repeat_ok=no_consecutive_repeat_ok,
            fry_limit_ok=fry_limit_ok,
            nutrition_ok=nutrition_ok,
            daily_costs=daily_costs,
            nutrition_reports=nutrition_reports,
            violations=violations,
        ),
    )