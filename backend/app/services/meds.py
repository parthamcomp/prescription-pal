import hashlib
import re
import uuid
from datetime import date, timedelta

from app.models_db import Prescription
from app.schemas import MedOut

COLOR_KEYS = ["violet", "mint", "amber", "sky"]

_DURATION_RE = re.compile(
    r"(\d+)\s*(days|day|d\b|weeks|week|wk|months|month|mo\b)", re.IGNORECASE
)
_DURATION_UNIT_DAYS = {
    "day": 1,
    "days": 1,
    "d": 1,
    "week": 7,
    "weeks": 7,
    "wk": 7,
    "month": 30,
    "months": 30,
    "mo": 30,
}

_CADENCE_PATTERNS = [
    (re.compile(r"\b(once|1)\s*(x|time)?\b.*\bdaily\b|\bonce\s+a?\s*day\b|\bonce\s+daily\b", re.I), "1×"),
    (re.compile(r"\btwice\b|\b2\s*(x|times?)\b", re.I), "2×"),
    (re.compile(r"\bthrice\b|\bthree\s+times\b|\b3\s*(x|times?)\b", re.I), "3×"),
    (re.compile(r"\bfour\s+times\b|\b4\s*(x|times?)\b", re.I), "4×"),
    (re.compile(r"\bweekly\b|\bonce\s+a\s+week\b", re.I), "weekly"),
    (re.compile(r"\bas\s+needed\b|\bprn\b", re.I), "as needed"),
    (re.compile(r"\bdaily\b|\bonce\s+a?\s*day\b", re.I), "1×"),
]
_GENERIC_TIMES_RE = re.compile(r"(\d+)\s*(?:x|×|times?)\b", re.I)


def parse_duration_days(duration: str) -> int | None:
    """Best-effort "3 weeks after dinner" -> 21. None when unparseable."""
    if not duration:
        return None
    m = _DURATION_RE.search(duration)
    if not m:
        return None
    count = int(m.group(1))
    unit = m.group(2).lower().rstrip(".")
    return count * _DURATION_UNIT_DAYS.get(unit, 0) or None


def shorten_duration(duration: str) -> str:
    """"3 weeks after dinner" -> "3 weeks" - the smallest true phrase, so
    the fact-strip cell never wraps. Falls back to the raw text if it
    doesn't match the expected "<n> <unit>" shape."""
    if not duration:
        return duration
    m = _DURATION_RE.search(duration)
    if not m:
        return duration
    return m.group(0).strip()


def cadence_for(frequency: str) -> str:
    """Normalise a free-text frequency into a short sidebar-safe label."""
    if not frequency:
        return "as needed"
    for pattern, label in _CADENCE_PATTERNS:
        if pattern.search(frequency):
            return label
    generic = _GENERIC_TIMES_RE.search(frequency)
    if generic:
        return f"{generic.group(1)}×"
    trimmed = frequency.strip()
    return trimmed if len(trimmed) <= 14 else trimmed[:13].rstrip() + "…"


def color_key_for(name: str) -> str:
    """Stable per-medication colour: hash the normalised name into the
    4-colour palette so the same medication keeps its colour across
    sessions and views without needing a dedicated table/column."""
    normalized = name.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return COLOR_KEYS[int(digest, 16) % len(COLOR_KEYS)]


def stable_med_id(name: str) -> str:
    normalized = name.strip().lower()
    return uuid.uuid5(uuid.NAMESPACE_URL, f"med:{normalized}").hex


def derive_medications(prescriptions: list[Prescription]) -> list[MedOut]:
    """Group medications out of a user's parsed records by normalised name,
    keeping the most recently seen occurrence's details, newest first.
    Not a separate user-managed list - purely derived from what's already
    on file."""
    today = date.today()
    by_name: dict[str, dict] = {}

    for p in prescriptions:
        visit_date = p.date_of_visit
        last_seen = visit_date or (p.created_at.date() if p.created_at else None)
        for m in p.medications or []:
            name = (m.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()

            duration_days = parse_duration_days(m.get("duration") or "")
            active = True
            if visit_date and duration_days is not None:
                active = (visit_date + timedelta(days=duration_days)) >= today

            existing = by_name.get(key)
            if existing is not None and existing["last_seen"] and last_seen:
                if last_seen <= existing["last_seen"]:
                    continue
            elif existing is not None and existing["last_seen"] and not last_seen:
                continue

            by_name[key] = {
                "name": name,
                "form": m.get("form") or "",
                "cadence": cadence_for(m.get("frequency") or ""),
                "last_seen": last_seen,
                "active": active,
            }

    meds = [
        MedOut(
            id=stable_med_id(v["name"]),
            name=v["name"],
            form=v["form"],
            cadence=v["cadence"],
            color_key=color_key_for(v["name"]),
            last_seen_at=v["last_seen"].isoformat() if v["last_seen"] else "",
            active=v["active"],
        )
        for v in by_name.values()
    ]
    meds.sort(key=lambda m: m.last_seen_at, reverse=True)
    return meds
