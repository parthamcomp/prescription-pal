"""India UIP vaccination schedule - status computation.

Mirrors services/meds.py::derive_medications - a derived, computed-on-read
resource. Nothing about "given/due/overdue" is stored; only the raw
VaccinationDose rows are persisted (a row's existence means "given", see the
0010_vaccination_doses migration docstring), and this module recomputes the
per-vaccine and per-milestone status against the bundled schedule on every
request.
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "vaccination_schedule_uip.json"

OVERDUE_GRACE_DAYS = 30


@lru_cache(maxsize=1)
def load_schedule() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def compute_status(doses: list, child_dob: date | None, today: date) -> dict:
    """doses: VaccinationDose rows (or anything with .scheduled_slug/.date_administered).
    Returns {"milestones": [...], "given_count": int, "total_count": int}."""
    given_by_slug = {d.scheduled_slug: d.date_administered for d in doses}
    schedule = load_schedule()
    age_days = (today - child_dob).days if child_dob else None

    milestones_out = []
    given_count = 0
    total_count = 0

    for milestone in schedule["milestones"]:
        milestone_age_days = milestone["age_days"]
        is_due = age_days is not None and age_days >= milestone_age_days
        is_overdue_window = (
            age_days is not None
            and age_days >= milestone_age_days + OVERDUE_GRACE_DAYS
        )

        vaccines_out = []
        milestone_given = 0
        for v in milestone["vaccines"]:
            given_date = given_by_slug.get(v["slug"])
            vaccines_out.append(
                {
                    "slug": v["slug"],
                    "name": v["name"],
                    "subtitle": v["subtitle"],
                    "given": given_date is not None,
                    "date_administered": given_date.isoformat() if given_date else None,
                }
            )
            total_count += 1
            if given_date is not None:
                milestone_given += 1
                given_count += 1

        n = len(milestone["vaccines"])
        if milestone_given == n:
            status = "given"
        elif is_due:
            status = "due"
        else:
            status = "not_due"
        overdue = status == "due" and is_overdue_window

        milestones_out.append(
            {
                "key": milestone["key"],
                "label": milestone["label"],
                "summary": milestone["summary"],
                "status": status,  # "given" | "due" | "not_due"
                "overdue": overdue,
                "given_count": milestone_given,
                "total_count": n,
                "vaccines": vaccines_out,
            }
        )

    return {
        "milestones": milestones_out,
        "given_count": given_count,
        "total_count": total_count,
    }
