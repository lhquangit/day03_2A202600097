from pydantic import ValidationError
import pytest

from src.tools.catalog import get_mock_catalog
from src.tools.models import AllergyGroup, Dish, MenuDay, WeeklyMenu


def _lookup(dish_id: str) -> Dish:
    return next(dish for dish in get_mock_catalog() if dish.id == dish_id)


def test_menu_day_requires_all_slots():
    with pytest.raises(ValidationError):
        MenuDay(
            day_label="Monday",
            staple=_lookup("white_rice"),
            main=_lookup("ginger_chicken"),
            vegetable=_lookup("garlic_mustard_greens"),
            soup=_lookup("pumpkin_minced_pork_soup"),
        )


def test_allergy_group_requires_at_least_one_allergen():
    with pytest.raises(ValidationError):
        AllergyGroup(name="empty_group", forbidden_allergens=[])


def test_weekly_menu_requires_exactly_five_days():
    monday = MenuDay(
        day_label="Monday",
        staple=_lookup("white_rice"),
        main=_lookup("ginger_chicken"),
        vegetable=_lookup("garlic_mustard_greens"),
        soup=_lookup("pumpkin_minced_pork_soup"),
        fruit=_lookup("banana"),
    )
    with pytest.raises(ValidationError):
        WeeklyMenu(days=[monday] * 4)


def test_dish_schema_rejects_negative_cost():
    with pytest.raises(ValidationError):
        Dish.model_validate(
            {
                "id": "invalid_dish",
                "name": "Invalid",
                "category": "main",
                "ingredients": ["ingredient"],
                "allergens": [],
                "cost_per_serving_vnd": -100,
                "nutrition_per_serving": {
                    "calories": 100,
                    "protein_g": 5,
                    "fiber_g": 1,
                },
                "tags": [],
            }
        )
