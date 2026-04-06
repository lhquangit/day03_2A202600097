from __future__ import annotations

from src.tools.models import AnalyzeNutritionInput, AnalyzeNutritionOutput, NutritionAnalysisData
from src.tools.utils import calculate_day_nutrition


def analyze_nutrition(payload: AnalyzeNutritionInput) -> AnalyzeNutritionOutput:
    daily_reports = [
        calculate_day_nutrition(day, payload.nutrition_targets) for day in payload.weekly_menu.days
    ]
    warnings = [issue for report in daily_reports for issue in report.issues]

    total_days = len(daily_reports)
    weekly_average_calories = sum(report.calories for report in daily_reports) / total_days
    weekly_average_protein_g = sum(report.protein_g for report in daily_reports) / total_days
    weekly_average_fiber_g = sum(report.fiber_g for report in daily_reports) / total_days
    all_days_within_target = all(report.within_target for report in daily_reports)

    return AnalyzeNutritionOutput(
        tool="analyze_nutrition",
        summary=(
            "Computed calories, protein, and fiber for all 5 days; "
            f"{sum(1 for report in daily_reports if report.within_target)}/{total_days} days met the target."
        ),
        warnings=warnings,
        data=NutritionAnalysisData(
            daily_reports=daily_reports,
            weekly_average_calories=round(weekly_average_calories, 1),
            weekly_average_protein_g=round(weekly_average_protein_g, 1),
            weekly_average_fiber_g=round(weekly_average_fiber_g, 1),
            all_days_within_target=all_days_within_target,
        ),
    )
