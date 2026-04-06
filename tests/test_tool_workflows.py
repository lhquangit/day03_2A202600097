from src.tools.analyze_nutrition import analyze_nutrition
from src.tools.catalog import get_mock_catalog
from src.tools.check_allergens import check_allergens
from src.tools.check_constraints import check_constraints
from src.tools.generate_weekly_menu import generate_weekly_menu
from src.tools.models import (
    AllergyGroup,
    AnalyzeNutritionInput,
    CheckAllergensInput,
    CheckConstraintsInput,
    ConstraintSet,
    GenerateWeeklyMenuInput,
    MenuDay,
    NutritionTargets,
    SuggestSubstitutionsInput,
    WeeklyMenu,
)
from src.tools.suggest_substitutions import suggest_substitutions


def _catalog_map():
    return {dish.id: dish for dish in get_mock_catalog()}


def _build_weekly_menu(day_specs: list[dict[str, str]]) -> WeeklyMenu:
    catalog = _catalog_map()
    return WeeklyMenu(
        days=[
            MenuDay(
                day_label=spec["day_label"],
                staple=catalog[spec["staple"]],
                main=catalog[spec["main"]],
                vegetable=catalog[spec["vegetable"]],
                soup=catalog[spec["soup"]],
                fruit=catalog[spec["fruit"]],
            )
            for spec in day_specs
        ]
    )


def test_generate_weekly_menu_returns_complete_five_day_structure():
    result = generate_weekly_menu(GenerateWeeklyMenuInput())

    assert result.status == "ok"
    assert result.data is not None
    assert len(result.data.weekly_menu.days) == 5
    assert len(result.data.daily_costs) == 5
    assert len(result.data.daily_nutrition) == 5
    for day in result.data.weekly_menu.days:
        assert day.staple.category == "staple"
        assert day.main.category == "main"
        assert day.vegetable.category == "vegetable"
        assert day.soup.category == "soup"
        assert day.fruit.category == "fruit"


def test_analyze_nutrition_flags_days_below_targets():
    weekly_menu = _build_weekly_menu(
        [
            {
                "day_label": "Monday",
                "staple": "white_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "stir_fried_chayote",
                "soup": "mustard_green_tofu_soup",
                "fruit": "watermelon",
            },
            {
                "day_label": "Tuesday",
                "staple": "white_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "stir_fried_chayote",
                "soup": "mustard_green_tofu_soup",
                "fruit": "watermelon",
            },
            {
                "day_label": "Wednesday",
                "staple": "white_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "stir_fried_chayote",
                "soup": "mustard_green_tofu_soup",
                "fruit": "watermelon",
            },
            {
                "day_label": "Thursday",
                "staple": "white_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "stir_fried_chayote",
                "soup": "mustard_green_tofu_soup",
                "fruit": "watermelon",
            },
            {
                "day_label": "Friday",
                "staple": "white_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "stir_fried_chayote",
                "soup": "mustard_green_tofu_soup",
                "fruit": "watermelon",
            },
        ]
    )
    result = analyze_nutrition(
        AnalyzeNutritionInput(
            weekly_menu=weekly_menu,
            nutrition_targets=NutritionTargets(
                calories_min=570,
                calories_max=650,
                protein_g_min=18,
                protein_g_max=25,
                fiber_g_min=6,
            ),
        )
    )

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.all_days_within_target is False
    assert result.warnings


def test_check_allergens_detects_milk_and_egg():
    weekly_menu = _build_weekly_menu(
        [
            {
                "day_label": "Monday",
                "staple": "white_rice",
                "main": "braised_pork_with_egg",
                "vegetable": "garlic_mustard_greens",
                "soup": "pumpkin_minced_pork_soup",
                "fruit": "banana",
            },
            {
                "day_label": "Tuesday",
                "staple": "brown_rice",
                "main": "ginger_chicken",
                "vegetable": "buttered_corn",
                "soup": "creamy_corn_soup",
                "fruit": "orange",
            },
            {
                "day_label": "Wednesday",
                "staple": "mixed_grain_rice",
                "main": "grilled_pork",
                "vegetable": "bok_choy_garlic",
                "soup": "cabbage_meat_soup",
                "fruit": "dragon_fruit",
            },
            {
                "day_label": "Thursday",
                "staple": "turmeric_rice",
                "main": "beef_onion",
                "vegetable": "steamed_pumpkin",
                "soup": "spinach_meat_soup",
                "fruit": "apple",
            },
            {
                "day_label": "Friday",
                "staple": "sesame_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "carrot_green_beans",
                "soup": "mustard_green_tofu_soup",
                "fruit": "pear",
            },
        ]
    )
    groups = [
        AllergyGroup(name="milk_allergy", forbidden_allergens=["milk"]),
        AllergyGroup(name="egg_allergy", forbidden_allergens=["egg"]),
    ]
    result = check_allergens(CheckAllergensInput(weekly_menu=weekly_menu, allergy_groups=groups))

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.total_violations == 3
    matched = {tuple(v.matched_allergens) for v in result.data.violations}
    assert ("egg",) in matched
    assert ("milk",) in matched


def test_suggest_substitutions_stays_in_same_category_and_avoids_allergen():
    weekly_menu = _build_weekly_menu(
        [
            {
                "day_label": "Monday",
                "staple": "white_rice",
                "main": "braised_pork_with_egg",
                "vegetable": "garlic_mustard_greens",
                "soup": "pumpkin_minced_pork_soup",
                "fruit": "banana",
            },
            {
                "day_label": "Tuesday",
                "staple": "brown_rice",
                "main": "ginger_chicken",
                "vegetable": "buttered_corn",
                "soup": "creamy_corn_soup",
                "fruit": "orange",
            },
            {
                "day_label": "Wednesday",
                "staple": "mixed_grain_rice",
                "main": "grilled_pork",
                "vegetable": "bok_choy_garlic",
                "soup": "cabbage_meat_soup",
                "fruit": "dragon_fruit",
            },
            {
                "day_label": "Thursday",
                "staple": "turmeric_rice",
                "main": "beef_onion",
                "vegetable": "steamed_pumpkin",
                "soup": "spinach_meat_soup",
                "fruit": "apple",
            },
            {
                "day_label": "Friday",
                "staple": "white_rice",
                "main": "tofu_meat_sauce",
                "vegetable": "carrot_green_beans",
                "soup": "mustard_green_tofu_soup",
                "fruit": "pear",
            },
        ]
    )
    groups = [
        AllergyGroup(name="milk_allergy", forbidden_allergens=["milk"]),
        AllergyGroup(name="egg_allergy", forbidden_allergens=["egg"]),
    ]
    result = suggest_substitutions(
        SuggestSubstitutionsInput(weekly_menu=weekly_menu, allergy_groups=groups)
    )

    assert result.status == "ok"
    assert result.data is not None
    assert len(result.data.suggestions) == 3
    for suggestion in result.data.suggestions:
        assert suggestion.substitute_dish.category == suggestion.component
        assert not set(suggestion.matched_allergens).intersection(
            suggestion.substitute_dish.allergens
        )


def test_check_constraints_catches_budget_and_consecutive_repeats():
    weekly_menu = _build_weekly_menu(
        [
            {
                "day_label": "Monday",
                "staple": "brown_rice",
                "main": "beef_onion",
                "vegetable": "bok_choy_garlic",
                "soup": "spinach_meat_soup",
                "fruit": "apple",
            },
            {
                "day_label": "Tuesday",
                "staple": "brown_rice",
                "main": "beef_onion",
                "vegetable": "bok_choy_garlic",
                "soup": "spinach_meat_soup",
                "fruit": "apple",
            },
            {
                "day_label": "Wednesday",
                "staple": "mixed_grain_rice",
                "main": "crispy_fish_fillet",
                "vegetable": "carrot_green_beans",
                "soup": "cabbage_meat_soup",
                "fruit": "dragon_fruit",
            },
            {
                "day_label": "Thursday",
                "staple": "turmeric_rice",
                "main": "crispy_fish_fillet",
                "vegetable": "steamed_pumpkin",
                "soup": "pumpkin_minced_pork_soup",
                "fruit": "pear",
            },
            {
                "day_label": "Friday",
                "staple": "sesame_rice",
                "main": "ginger_chicken",
                "vegetable": "garlic_mustard_greens",
                "soup": "amaranth_shrimp_soup",
                "fruit": "orange",
            },
        ]
    )
    result = check_constraints(
        CheckConstraintsInput(
            weekly_menu=weekly_menu,
            constraints=ConstraintSet(
                budget_per_student_vnd=25000,
                student_count=800,
                max_fried_per_week=1,
                no_consecutive_repeat_categories=["main"],
            ),
        )
    )

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.budget_ok is False
    assert result.data.no_consecutive_repeat_ok is False
    assert result.data.fry_limit_ok is False
    assert result.data.violations
