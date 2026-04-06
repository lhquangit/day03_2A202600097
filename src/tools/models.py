from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DishCategory = Literal["staple", "main", "vegetable", "soup", "fruit"]
ToolStatus = Literal["ok", "error"]

DEFAULT_REQUIRED_CATEGORIES: list[DishCategory] = [
    "staple",
    "main",
    "vegetable",
    "soup",
    "fruit",
]


def _normalize_string_list(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


class NutritionInfo(BaseModel):
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)
    micronutrients: dict[str, float] = Field(default_factory=dict)


class DayCostReport(BaseModel):
    day_label: str
    per_serving_vnd: int = Field(ge=0)
    total_for_student_count_vnd: int = Field(ge=0)


class DayNutritionReport(BaseModel):
    day_label: str
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)
    within_target: bool
    issues: list[str] = Field(default_factory=list)


class Dish(BaseModel):
    id: str
    name: str
    category: DishCategory
    ingredients: list[str] = Field(min_length=1)
    allergens: list[str] = Field(default_factory=list)
    cost_per_serving_vnd: int = Field(gt=0)
    nutrition_per_serving: NutritionInfo
    tags: list[str] = Field(default_factory=list)

    @field_validator("allergens", "tags", mode="before")
    @classmethod
    def normalize_labels(cls, value: list[str] | None) -> list[str]:
        return _normalize_string_list(value or [])


class MenuDay(BaseModel):
    day_label: str
    staple: Dish
    main: Dish
    vegetable: Dish
    soup: Dish
    fruit: Dish

    @model_validator(mode="after")
    def validate_categories(self) -> "MenuDay":
        expected_categories = {
            "staple": "staple",
            "main": "main",
            "vegetable": "vegetable",
            "soup": "soup",
            "fruit": "fruit",
        }
        for field_name, expected in expected_categories.items():
            dish = getattr(self, field_name)
            if dish.category != expected:
                raise ValueError(
                    f"{field_name} must use a '{expected}' dish, got '{dish.category}'."
                )
        return self


class WeeklyMenu(BaseModel):
    days: list[MenuDay] = Field(min_length=5, max_length=5)

    @field_validator("days")
    @classmethod
    def validate_unique_day_labels(cls, value: list[MenuDay]) -> list[MenuDay]:
        labels = [day.day_label for day in value]
        if len(labels) != len(set(labels)):
            raise ValueError("Weekly menu day labels must be unique.")
        return value


class AllergyGroup(BaseModel):
    name: str
    forbidden_allergens: list[str] = Field(min_length=1)

    @field_validator("forbidden_allergens", mode="before")
    @classmethod
    def normalize_allergens(cls, value: list[str] | None) -> list[str]:
        normalized = _normalize_string_list(value or [])
        if not normalized:
            raise ValueError("At least one forbidden allergen is required.")
        return normalized


class NutritionTargets(BaseModel):
    calories_min: float = Field(default=550, ge=0)
    calories_max: float = Field(default=650, ge=0)
    protein_g_min: float = Field(default=18, ge=0)
    protein_g_max: float = Field(default=25, ge=0)
    fiber_g_min: float = Field(default=6, ge=0)


class ConstraintSet(BaseModel):
    budget_per_student_vnd: int = Field(default=28000, gt=0)
    student_count: int = Field(default=800, gt=0)
    required_categories: list[DishCategory] = Field(
        default_factory=lambda: DEFAULT_REQUIRED_CATEGORIES.copy()
    )
    max_fried_per_week: int | None = Field(default=2, ge=0)
    no_consecutive_repeat_categories: list[DishCategory] = Field(
        default_factory=lambda: ["main"]
    )

    @field_validator("required_categories", "no_consecutive_repeat_categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: list[str] | None) -> list[str]:
        normalized = _normalize_string_list(value or [])
        return normalized


class AllergenViolation(BaseModel):
    day_label: str
    group_name: str
    component: DishCategory
    dish_id: str
    dish_name: str
    matched_allergens: list[str]


class SubstitutionSuggestion(BaseModel):
    day_label: str
    group_name: str
    component: DishCategory
    original_dish_id: str
    original_dish_name: str
    substitute_dish: Dish
    matched_allergens: list[str]
    delta_cost_per_serving_vnd: int
    delta_calories: float
    delta_protein_g: float
    delta_fiber_g: float
    rationale: str


class ConstraintViolation(BaseModel):
    rule: str
    day_label: str | None = None
    message: str


class ToolOutputBase(BaseModel):
    status: ToolStatus = "ok"
    tool: str
    summary: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class GenerateWeeklyMenuData(BaseModel):
    weekly_menu: WeeklyMenu
    daily_costs: list[DayCostReport]
    daily_nutrition: list[DayNutritionReport]
    selection_notes: list[str] = Field(default_factory=list)


class NutritionAnalysisData(BaseModel):
    daily_reports: list[DayNutritionReport]
    weekly_average_calories: float = Field(ge=0)
    weekly_average_protein_g: float = Field(ge=0)
    weekly_average_fiber_g: float = Field(ge=0)
    all_days_within_target: bool


class AllergenCheckData(BaseModel):
    violations: list[AllergenViolation]
    total_violations: int = Field(ge=0)
    groups_checked: list[str] = Field(default_factory=list)


class SubstitutionData(BaseModel):
    suggestions: list[SubstitutionSuggestion]
    unresolved_violations: list[AllergenViolation] = Field(default_factory=list)


class ConstraintCheckData(BaseModel):
    budget_ok: bool
    meal_structure_ok: bool
    no_consecutive_repeat_ok: bool
    fry_limit_ok: bool
    nutrition_ok: bool | None = None
    daily_costs: list[DayCostReport]
    nutrition_reports: list[DayNutritionReport] = Field(default_factory=list)
    violations: list[ConstraintViolation] = Field(default_factory=list)


class GenerateWeeklyMenuOutput(ToolOutputBase):
    data: GenerateWeeklyMenuData | None = None


class AnalyzeNutritionOutput(ToolOutputBase):
    data: NutritionAnalysisData | None = None


class CheckAllergensOutput(ToolOutputBase):
    data: AllergenCheckData | None = None


class SuggestSubstitutionsOutput(ToolOutputBase):
    data: SubstitutionData | None = None


class CheckConstraintsOutput(ToolOutputBase):
    data: ConstraintCheckData | None = None


class GenerateWeeklyMenuInput(BaseModel):
    constraints: ConstraintSet = Field(default_factory=ConstraintSet)
    age_group: str = "primary"
    allergy_groups: list[AllergyGroup] = Field(default_factory=list)
    nutrition_targets: NutritionTargets = Field(default_factory=NutritionTargets)
    catalog: list[Dish] | None = None


class AnalyzeNutritionInput(BaseModel):
    weekly_menu: WeeklyMenu
    age_group: str = "primary"
    nutrition_targets: NutritionTargets = Field(default_factory=NutritionTargets)


class CheckAllergensInput(BaseModel):
    weekly_menu: WeeklyMenu
    allergy_groups: list[AllergyGroup] = Field(default_factory=list)


class SuggestSubstitutionsInput(BaseModel):
    weekly_menu: WeeklyMenu
    allergy_groups: list[AllergyGroup] = Field(default_factory=list)
    catalog: list[Dish] | None = None


class CheckConstraintsInput(BaseModel):
    weekly_menu: WeeklyMenu
    constraints: ConstraintSet = Field(default_factory=ConstraintSet)
    nutrition_targets: NutritionTargets | None = None
