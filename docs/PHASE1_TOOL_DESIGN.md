# Phase 1: Tool Design Evolution

Tài liệu này chốt contract cho bộ tool của `School Nutrition Optimizer` ở Phase 1.

## 1. Mục tiêu thiết kế

- Tool phải deterministic, không gọi network hay LLM.
- Input/output phải có schema rõ ràng để Phase 3 parse `Action` an toàn hơn.
- Output của mọi tool dùng cùng một envelope:
  - `status`
  - `tool`
  - `summary`
  - `data`
  - `warnings`
  - `errors`

## 2. Tool Inventory

| Tool | Dùng khi nào | Input chính | Output chính |
| :--- | :--- | :--- | :--- |
| `generate_weekly_menu` | Cần sinh menu tuần ban đầu | `constraints`, `allergy_groups`, `nutrition_targets`, `catalog?` | `weekly_menu`, `daily_costs`, `daily_nutrition`, `selection_notes` |
| `analyze_nutrition` | Cần kiểm toán calories/protein/fiber | `weekly_menu`, `nutrition_targets` | `daily_reports`, weekly averages, pass/fail |
| `check_allergens` | Cần audit dị ứng | `weekly_menu`, `allergy_groups` | danh sách `violations` |
| `suggest_substitutions` | Có violation dị ứng cần thay món | `weekly_menu`, `allergy_groups`, `catalog?` | `suggestions`, `unresolved_violations` |
| `check_constraints` | Gate cuối trước khi chốt menu | `weekly_menu`, `constraints`, `nutrition_targets?` | budget/structure/repeat/fry/nutrition checks |

## 3. Domain Schema

### Dish
- `id`
- `name`
- `category`: `staple | main | vegetable | soup | fruit`
- `ingredients`
- `allergens`
- `cost_per_serving_vnd`
- `nutrition_per_serving`
- `tags`

### Weekly Menu
- `WeeklyMenu.days` luôn có đúng 5 `MenuDay`
- Mỗi `MenuDay` phải có:
  - `staple`
  - `main`
  - `vegetable`
  - `soup`
  - `fruit`

### Constraints
- `budget_per_student_vnd`
- `student_count`
- `required_categories`
- `max_fried_per_week`
- `no_consecutive_repeat_categories`

### NutritionTargets
- `calories_min`
- `calories_max`
- `protein_g_min`
- `protein_g_max`
- `fiber_g_min`

## 4. Final Descriptions For Agent Prompt

### `generate_weekly_menu`
Generate a deterministic 5-day school lunch menu from the local dish catalog using budget, student count, required meal structure, allergen groups, and simple repeat/frying constraints. Returns the weekly menu plus daily cost and nutrition estimates.

### `analyze_nutrition`
Calculate calories, protein, and fiber for each day in a 5-day menu. Use this after a menu is drafted to verify which days pass or fail the nutrition targets.

### `check_allergens`
Audit a weekly menu against named allergy groups such as milk or egg allergies. Returns exact day, dish, component, and matched allergens for every violation.

### `suggest_substitutions`
Suggest safe replacement dishes for allergen violations while keeping the same meal component category. Returns delta cost, delta nutrition, and unresolved violations if the catalog has no safe substitute.

### `check_constraints`
Run the final gate on a weekly menu. Checks budget per serving, required meal structure, consecutive-repeat rules, optional frying limits, and optional nutrition targets.

## 5. Example Action Inputs

```json
{
  "tool": "generate_weekly_menu",
  "arguments": {
    "constraints": {
      "budget_per_student_vnd": 28000,
      "student_count": 800
    },
    "allergy_groups": [
      { "name": "milk_allergy", "forbidden_allergens": ["milk"] },
      { "name": "egg_allergy", "forbidden_allergens": ["egg"] }
    ]
  }
}
```

```json
{
  "tool": "check_constraints",
  "arguments": {
    "weekly_menu": { "days": "..." },
    "constraints": {
      "budget_per_student_vnd": 28000,
      "student_count": 800,
      "max_fried_per_week": 2,
      "no_consecutive_repeat_categories": ["main"]
    }
  }
}
```

## 6. Example Observation Shape

```json
{
  "status": "ok",
  "tool": "check_allergens",
  "summary": "Found 2 allergen violations.",
  "data": {
    "violations": [
      {
        "day_label": "Tuesday",
        "group_name": "egg_allergy",
        "component": "main",
        "dish_id": "braised_pork_with_egg",
        "dish_name": "Thit kho trung",
        "matched_allergens": ["egg"]
      }
    ],
    "total_violations": 2,
    "groups_checked": ["milk_allergy", "egg_allergy"]
  },
  "warnings": [],
  "errors": []
}
```

## 7. Guardrails và Giới Hạn

- Catalog hiện là mock data trong repo, chưa phải dữ liệu chuẩn y khoa.
- Nutrition MVP chỉ enforce `calories`, `protein_g`, `fiber_g`.
- Tool không tự chỉnh menu trực tiếp; `suggest_substitutions` chỉ đề xuất.
- `check_constraints` là gate cuối, không thay thế cho phân tích thủ công khi đưa vào vận hành thực tế.
