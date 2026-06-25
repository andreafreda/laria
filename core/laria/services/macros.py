"""Macro-nutrient targets derived from a calorie goal.

A small pure function, separated from storage and IO so it is trivial to read
and test. Given a daily calorie target (and optionally a body weight), it splits
the calories into protein, fat, and carbohydrate targets in grams and percent.
"""
from __future__ import annotations


def compute_macro_targets(kcal_target: int | None,
                          weight_kg: float | None) -> dict | None:
    """Split a calorie target into protein, fat, and carb goals.

    Protein is 1.6 g per kg of body weight when weight is known, otherwise 20%
    of calories. Fat is 25% of calories; carbohydrate takes the rest (never
    negative). Returns grams and percent for each macro, or None when there is no
    calorie target to split.
    """
    if not kcal_target:
        return None
    if weight_kg:
        protein_g = round(1.6 * weight_kg, 1)
    else:
        protein_g = round((0.20 * kcal_target) / 4, 1)
    protein_kcal = protein_g * 4
    fat_kcal = 0.25 * kcal_target
    fat_g = round(fat_kcal / 9, 1)
    carbs_kcal = max(0, kcal_target - protein_kcal - fat_kcal)
    carbs_g = round(carbs_kcal / 4, 1)

    def percent(part_kcal: float) -> float:
        return round(100 * part_kcal / kcal_target, 1)

    return {
        "protein_target_g": protein_g,
        "carbs_target_g": carbs_g,
        "fat_target_g": fat_g,
        "protein_pct": percent(protein_kcal),
        "carbs_pct": percent(carbs_kcal),
        "fat_pct": percent(fat_kcal),
    }
