"""Unit normalization shared by the measurements API and OCR-derived growth
data - one conversion path so a manually-typed inch/pound value and an
OCR-extracted one land on the same canonical cm/kg number.
"""

CM_PER_INCH = 2.54
KG_PER_LB = 0.45359237


def height_to_cm(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if unit == "in":
        return round(value * CM_PER_INCH, 2)
    return round(value, 2)  # "cm" or unspecified - assume already canonical


def weight_to_kg(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if unit == "lb":
        return round(value * KG_PER_LB, 3)
    return round(value, 3)  # "kg" or unspecified
