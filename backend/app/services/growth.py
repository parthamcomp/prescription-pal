"""WHO Child Growth Standards percentile engine.

Reference data: backend/app/data/who_growth_lms.json (see its "source" field
for provenance). WHO only, ages 0-5 - a deliberate scope decision, not a
placeholder; do not extend to CDC data or hand-approximate values outside
that range. Callers should treat an out-of-range age or missing sex as "no
percentile available", never a guessed number.
"""
import json
import math
import statistics
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "who_growth_lms.json"

Measure = str  # "height_for_age" | "weight_for_age"
Sex = str  # "male" | "female"

_SEX_KEY = {"male": "boys", "female": "girls"}

# The percentile bands the growth chart draws (3rd-97th and 15th-85th tinted
# ranges, plus the dashed median).
CHART_PERCENTILES = [3, 15, 50, 85, 97]

MIN_AGE_MONTHS = 0
MAX_AGE_MONTHS = 60


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def age_in_months(dob, on) -> float:
    """Fractional age in months between two date objects."""
    days = (on - dob).days
    return days / 30.4375


def in_supported_range(age_months: float) -> bool:
    return MIN_AGE_MONTHS <= age_months <= MAX_AGE_MONTHS


@lru_cache(maxsize=8)
def _series(measure: Measure, sex: Sex) -> tuple[dict, ...]:
    sex_key = _SEX_KEY[sex]
    return tuple(_load()[measure][sex_key])


def lms_lookup(measure: Measure, sex: Sex, age_months: float) -> tuple[float, float, float] | None:
    """Linearly interpolate (L, M, S) between the two nearest whole-month
    rows for a fractional age. Returns None outside the supported range."""
    if not in_supported_range(age_months):
        return None
    series = _series(measure, sex)
    lo_month = min(int(age_months), MAX_AGE_MONTHS - 1)
    lo, hi = series[lo_month], series[lo_month + 1]
    frac = age_months - lo_month
    return (
        lo["L"] + (hi["L"] - lo["L"]) * frac,
        lo["M"] + (hi["M"] - lo["M"]) * frac,
        lo["S"] + (hi["S"] - lo["S"]) * frac,
    )


def z_score(value: float, L: float, M: float, S: float) -> float:
    # L≈0 special case: WHO's weight-for-age tables do carry L values at/near
    # zero at some ages (see who_growth_lms.json), and the general formula
    # divides by zero there - this is a correctness requirement, not an edge
    # case to skip.
    if abs(L) < 1e-8:
        return math.log(value / M) / S
    return ((value / M) ** L - 1) / (L * S)


def value_at_z(z: float, L: float, M: float, S: float) -> float:
    """Inverse of z_score() - the measurement value at a given z."""
    if abs(L) < 1e-8:
        return M * math.exp(S * z)
    return M * (1 + L * S * z) ** (1 / L)


def z_to_percentile(z: float) -> float:
    return statistics.NormalDist().cdf(z) * 100


def percentile_to_z(p: float) -> float:
    return statistics.NormalDist().inv_cdf(p / 100)


def percentile_for_value(
    measure: Measure, sex: Sex, age_months: float, value: float
) -> float | None:
    lms = lms_lookup(measure, sex, age_months)
    if lms is None:
        return None
    return round(z_to_percentile(z_score(value, *lms)), 1)


def percentile_curves(measure: Measure, sex: Sex) -> list[dict]:
    """One row per whole month (0-60) with the value at each of
    CHART_PERCENTILES - what the chart's percentile bands are drawn from."""
    out = []
    for row in _series(measure, sex):
        lms = (row["L"], row["M"], row["S"])
        out.append(
            {
                "month": row["month"],
                **{
                    f"p{p}": round(value_at_z(percentile_to_z(p), *lms), 2)
                    for p in CHART_PERCENTILES
                },
            }
        )
    return out
