"""Unit normalization shared by the measurements API and prescription-
derived growth data - one conversion path so a manually-typed inch/pound
value and a free-text-parsed one land on the same canonical cm/kg number.
"""
import re

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


# Prescription.child_height/child_weight are free text, same as they've
# always been (e.g. "80 cm", "14kg") - these pull a number+unit out of that
# text for the growth chart. Deliberately conservative: no unit in the text
# means no derived measurement, rather than guessing kg vs lb or cm vs in
# for a health-adjacent number.
_HEIGHT_RE = re.compile(r"(\d+\.?\d*)\s*(cm|centimet(?:er|re)s?|in(?:ch(?:es)?)?)\b", re.IGNORECASE)
_WEIGHT_RE = re.compile(r"(\d+\.?\d*)\s*(kgs?|kilograms?|lbs?|pounds?)\b", re.IGNORECASE)


def parse_height_text(text: str) -> float | None:
    if not text:
        return None
    m = _HEIGHT_RE.search(text)
    if not m:
        return None
    unit = "in" if m.group(2).lower().startswith("in") else "cm"
    return height_to_cm(float(m.group(1)), unit)


def parse_weight_text(text: str) -> float | None:
    if not text:
        return None
    m = _WEIGHT_RE.search(text)
    if not m:
        return None
    unit = "lb" if m.group(2).lower().startswith(("lb", "pound")) else "kg"
    return weight_to_kg(float(m.group(1)), unit)
