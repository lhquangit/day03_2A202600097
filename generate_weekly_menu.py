from __future__ import annotations

from src.tools.models import (
    Dish,
    GenerateWeeklyMenuData,
    GenerateWeeklyMenuInput,
    GenerateWeeklyMenuOutput,
    MenuDay,
    WeeklyMenu,
)
from src.tools.utils import (
    WEEKDAY_LABELS,
    calculate_day_cost,
    calculate_day_nutrition,
    get_catalog,
    group_catalog_by_category,
    union_forbidden_allergens,
)


def _select_candidate(
    *,
    candidates: list[Dish],
    day_index: int,
    previous_dish_id: str | None = None,
    allow_fried: bool = True,
) -> Dish | None:
    if not candidates:
        return None

    total_candidates = len(candidates)
    for offset in range(total_candidates):
        candidate = candidates[(day_index + offset) % total_candidates]
        if previous_dish_id and candidate.id == previous_dish_id:
            continue
        if not allow_fried and "fried" in candidate.tags:
            continue
        return candidate
    return None


def _replace_main_to_fit_budget(
    *,
    selected_dishes: dict[str, Dish],
    grouped_catalog: dict[str, list[Dish]],
    budget_per_student_vnd: int,
    previous_main_id: str | None,
) -> dict[str, Dish]:
    current_cost = sum(dish.cost_per_serving_vnd for dish in selected_dishes.values())
    if current_cost <= budget_per_student_vnd:
        return selected_dishes

    main_candidates = sorted(grouped_catalog.get("main", []), key=lambda dish: (dish.cost_per_serving_vnd, dish.id))
    for candidate in main_candidates:
        if previous_main_id and candidate.id == previous_main_id:
            continue
        if candidate.id == selected_dishes["main"].id:
            continue
        adjusted_cost = current_cost - selected_dishes["main"].cost_per_serving_vnd + candidate.cost_per_serving_vnd
        if adjusted_cost <= budget_per_student_vnd:
            updated = dict(selected_dishes)
            updated["main"] = candidate
            return updated
    return selected_dishes


def generate_weekly_menu(payload: GenerateWeeklyMenuInput) -> GenerateWeeklyMenuOutput:
    catalog = get_catalog(payload.catalog)
    forbidden_allergens = union_forbidden_allergens(payload.allergy_groups)
    filtered_catalog = [
        dish for dish in catalog if not forbidden_allergens.intersection(dish.allergens)
    ]
    grouped_catalog = group_catalog_by_category(filtered_catalog)

    warnings: list[str] = []
    selection_notes: list[str] = []
    previous_main_id: str | None = None
    fried_count = 0
    days: list[MenuDay] = []

    for category in payload.constraints.required_categories:
        if not grouped_catalog.get(category):
            return GenerateWeeklyMenuOutput(
                status="error",
                tool="generate_weekly_menu",
                summary=f"Missing candidate dishes for category '{category}'.",
                errors=[f"No dishes available for required category '{category}' after allergy filtering."],
            )

    for index, day_label in enumerate(WEEKDAY_LABELS):
        selected_dishes: dict[str, Dish] = {}
        for category in payload.constraints.required_categories:
            allow_fried = True
            if payload.constraints.max_fried_per_week is not None and category == "main":
                allow_fried = fried_count < payload.constraints.max_fried_per_week

            previous_dish_id = previous_main_id if category == "main" else None
            dish = _select_candidate(
                candidates=grouped_catalog.get(category, []),
                day_index=index,
                previous_dish_id=previous_dish_id,
                allow_fried=allow_fried,
            )
            if dish is None:
                return GenerateWeeklyMenuOutput(
                    status="error",
                    tool="generate_weekly_menu",
                    summary=f"Unable to select a {category} dish for {day_label}.",
                    errors=[f"Catalog could not satisfy category '{category}' on {day_label}."],
                )
            selected_dishes[category] = dish

        selected_dishes = _replace_main_to_fit_budget(
            selected_dishes=selected_dishes,
            grouped_catalog=grouped_catalog,
            budget_per_student_vnd=payload.constraints.budget_per_student_vnd,
            previous_main_id=previous_main_id,
        )

        day = MenuDay(day_label=day_label, **selected_dishes)
        days.append(day)

        if "fried" in day.main.tags:
            fried_count += 1

        previous_main_id = day.main.id
        selection_notes.append(
            f"{day_label}: selected {day.main.name} with total cost {calculate_day_cost(day, payload.constraints.student_count).per_serving_vnd} VND per serving."
        )

    weekly_menu = WeeklyMenu(days=days)
    daily_costs = [calculate_day_cost(day, payload.constraints.student_count) for day in weekly_menu.days]
    daily_nutrition = [
        calculate_day_nutrition(day, payload.nutrition_targets) for day in weekly_menu.days
    ]

    for cost_report in daily_costs:
        if cost_report.per_serving_vnd > payload.constraints.budget_per_student_vnd:
            warnings.append(
                f"{cost_report.day_label} exceeds budget at {cost_report.per_serving_vnd} VND per serving."
            )

    if forbidden_allergens:
        selection_notes.insert(
            0,
            "Filtered dishes containing allergens: "
            + ", ".join(sorted(forbidden_allergens))
            + ".",
        )

    return GenerateWeeklyMenuOutput(
        tool="generate_weekly_menu",
        summary=f"Generated a 5-day menu for {payload.constraints.student_count} students.",
        warnings=warnings,
        data=GenerateWeeklyMenuData(
            weekly_menu=weekly_menu,
            daily_costs=daily_costs,
            daily_nutrition=daily_nutrition,
            selection_notes=selection_notes,
        ),
    )