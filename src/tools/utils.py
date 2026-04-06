from __future__ import annotations

from collections import defaultdict

from src.tools.catalog import get_mock_catalog
from src.tools.models import (
    AllergyGroup,
    DayCostReport,
    DayNutritionReport,
    Dish,
    MenuDay,
    NutritionTargets,
    WeeklyMenu,
)

WEEKDAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def get_catalog(catalog: list[Dish] | None = None) -> list[Dish]:
    return catalog if catalog is not None else get_mock_catalog()


def group_catalog_by_category(catalog: list[Dish]) -> dict[str, list[Dish]]:
    grouped: dict[str, list[Dish]] = defaultdict(list)
    for dish in catalog:
        grouped[dish.category].append(dish)
    return {key: sorted(value, key=lambda dish: dish.id) for key, value in grouped.items()}


def flatten_menu_day(day: MenuDay) -> dict[str, Dish]:
    return {
        "staple": day.staple,
        "main": day.main,
        "vegetable": day.vegetable,
        "soup": day.soup,
        "fruit": day.fruit,
    }


def calculate_day_cost(day: MenuDay, student_count: int) -> DayCostReport:
    per_serving_cost = sum(dish.cost_per_serving_vnd for dish in flatten_menu_day(day).values())
    return DayCostReport(
        day_label=day.day_label,
        per_serving_vnd=per_serving_cost,
        total_for_student_count_vnd=per_serving_cost * student_count,
    )


def calculate_day_nutrition(
    day: MenuDay, nutrition_targets: NutritionTargets | None = None
) -> DayNutritionReport:
    calories = sum(dish.nutrition_per_serving.calories for dish in flatten_menu_day(day).values())
    protein_g = sum(dish.nutrition_per_serving.protein_g for dish in flatten_menu_day(day).values())
    fiber_g = sum(dish.nutrition_per_serving.fiber_g for dish in flatten_menu_day(day).values())

    issues: list[str] = []
    within_target = True
    if nutrition_targets is not None:
        if calories < nutrition_targets.calories_min or calories > nutrition_targets.calories_max:
            issues.append(
                f"Calories {calories:.1f} outside target {nutrition_targets.calories_min:.0f}-{nutrition_targets.calories_max:.0f}."
            )
        if protein_g < nutrition_targets.protein_g_min or protein_g > nutrition_targets.protein_g_max:
            issues.append(
                f"Protein {protein_g:.1f}g outside target {nutrition_targets.protein_g_min:.0f}-{nutrition_targets.protein_g_max:.0f}g."
            )
        if fiber_g < nutrition_targets.fiber_g_min:
            issues.append(
                f"Fiber {fiber_g:.1f}g below minimum {nutrition_targets.fiber_g_min:.0f}g."
            )
        within_target = not issues

    return DayNutritionReport(
        day_label=day.day_label,
        calories=round(calories, 1),
        protein_g=round(protein_g, 1),
        fiber_g=round(fiber_g, 1),
        within_target=within_target,
        issues=issues,
    )


def union_forbidden_allergens(allergy_groups: list[AllergyGroup]) -> set[str]:
    allergens: set[str] = set()
    for group in allergy_groups:
        allergens.update(group.forbidden_allergens)
    return allergens


def count_tagged_dishes(menu: WeeklyMenu, tag: str) -> int:
    count = 0
    for day in menu.days:
        for dish in flatten_menu_day(day).values():
            if tag in dish.tags:
                count += 1
    return count


def find_safe_substitute(
    *,
    category: str,
    catalog: list[Dish],
    forbidden_allergens: set[str],
    exclude_dish_id: str,
) -> Dish | None:
    candidates = [
        dish
        for dish in catalog
        if dish.category == category
        and dish.id != exclude_dish_id
        and not forbidden_allergens.intersection(dish.allergens)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda dish: (dish.cost_per_serving_vnd, dish.id))[0]
