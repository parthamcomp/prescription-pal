"""Vaccination and growth-measurement context for RAG chat answers.

Unlike prescriptions, this data is small and bounded per child (a few dozen
vaccine slots, a handful of measurements) rather than a free-text corpus that
benefits from embedding/full-text retrieval - so it's always included in full
for the relevant child(ren) rather than scored and top-k'd, mirroring how
services/vaccination_schedule.py and services/growth.py already treat it as a
derived, computed-on-read resource rather than something separately indexed.
"""
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import Child, Measurement
from app.repositories import children as children_repo
from app.repositories import measurements as measurements_repo
from app.repositories import vaccination_doses as vaccination_doses_repo
from app.services.growth import age_in_months, percentile_for_value
from app.services.vaccination_schedule import compute_status


async def _children_in_scope(
    db: AsyncSession, owner_id: uuid.UUID, child_id: uuid.UUID | None
) -> list[Child]:
    if child_id is not None:
        child = await children_repo.get_for_user(db, owner_id, child_id)
        return [child] if child else []
    return await children_repo.list_for_user(db, owner_id)


def _vaccination_block(status: dict) -> str | None:
    # "given" and "due" - "not_due" milestones haven't happened yet and
    # mostly just add noise/tokens to a question about the child's current
    # state; see build_context's docstring on why this isn't retrieval-scored.
    given = [v for m in status["milestones"] for v in m["vaccines"] if v["given"]]
    due = [
        v
        for m in status["milestones"]
        for v in m["vaccines"]
        if not v["given"] and m["status"] == "due"
    ]

    # Exception: when nothing is currently due (every milestone the child
    # has actually reached is fully given), "what's next" is still a fair
    # question to ask ahead of time - surface just the single earliest
    # not-yet-due milestone with anything outstanding, not the whole rest
    # of the schedule out to 18y, which would be mostly irrelevant noise
    # for a parent asking about the next shot.
    upcoming: list[dict] = []
    upcoming_label = None
    if not due:
        for m in status["milestones"]:
            if m["status"] == "not_due":
                pending = [v for v in m["vaccines"] if not v["given"]]
                if pending:
                    upcoming = pending
                    upcoming_label = m["label"]
                    break

    if not given and not due and not upcoming:
        return None

    # `given`/`due` are built by walking status["milestones"] in schedule
    # order (birth -> ... -> 18y), not by administration date - real doses
    # routinely land out of that order (catch-up, a skipped slot filled in
    # later), so without an explicit re-sort + tag the model had no way to
    # tell which given vaccine was actually most recent, and was picking
    # whichever sat last in schedule order instead - then reasoning about
    # "what's next" from that wrong anchor.
    given_sorted = sorted(given, key=lambda v: v["date_administered"], reverse=True)

    lines = ["Vaccination record - given (most recent first):"]
    for i, v in enumerate(given_sorted):
        tag = " [MOST RECENT]" if i == 0 else ""
        lines.append(f"  - {v['name']} ({v['subtitle']}): given on {v['date_administered']}{tag}")

    if due:
        # status["milestones"] is already age-ascending, so `due` (built by
        # walking it in order) is too - the first entry here is the
        # earliest/longest-outstanding gap, i.e. the actual next one to get.
        lines.append("Due, not yet given (earliest/most overdue first):")
        for i, v in enumerate(due):
            tag = " [NEXT DUE]" if i == 0 else ""
            lines.append(f"  - {v['name']} ({v['subtitle']}){tag}")
    elif upcoming:
        lines.append(
            f"Nothing currently due - everything reached so far is given. The next "
            f"milestone on the schedule is {upcoming_label} (not due yet by age):"
        )
        for i, v in enumerate(upcoming):
            tag = " [NEXT UP]" if i == 0 else ""
            lines.append(f"  - {v['name']} ({v['subtitle']}){tag}")

    return "\n".join(lines)


def _growth_block(child: Child, measurements: list[Measurement]) -> str | None:
    if not measurements:
        return None
    # measurements_repo.list_for_user() already orders most-recent-first;
    # keep that order (previously this re-sorted oldest-first and silently
    # threw that away) and label the top entry explicitly rather than
    # leaving the model to infer "latest" from list position - it was
    # picking an older reading and presenting it as current.
    lines = ["Growth measurements (height/weight), most recent first:"]
    for i, m in enumerate(measurements):
        age_months = (
            age_in_months(child.date_of_birth, m.measured_on)
            if child.date_of_birth
            else None
        )
        bits = []
        if m.height_cm is not None:
            pct = (
                percentile_for_value("height_for_age", child.sex, age_months, m.height_cm)
                if child.sex and age_months is not None
                else None
            )
            bits.append(f"height {m.height_cm} cm" + (f" ({pct}th percentile)" if pct is not None else ""))
        if m.weight_kg is not None:
            pct = (
                percentile_for_value("weight_for_age", child.sex, age_months, m.weight_kg)
                if child.sex and age_months is not None
                else None
            )
            bits.append(f"weight {m.weight_kg} kg" + (f" ({pct}th percentile)" if pct is not None else ""))
        if bits:
            tag = " [MOST RECENT]" if i == 0 else ""
            lines.append(f"  - {m.measured_on.isoformat()}: " + ", ".join(bits) + tag)
    return "\n".join(lines) if len(lines) > 1 else None


async def build_context(
    db: AsyncSession, owner_id: uuid.UUID, child_id: uuid.UUID | None
) -> str:
    """One text block per child covering vaccination status and growth
    measurements, for direct inclusion in the chat prompt - empty string if
    there's nothing to say for any child in scope."""
    children = await _children_in_scope(db, owner_id, child_id)
    today = date.today()
    blocks = []
    for child in children:
        sections = []

        doses = await vaccination_doses_repo.list_for_user(db, owner_id, child.id)
        status = compute_status(doses, child.date_of_birth, today)
        vaccination_text = _vaccination_block(status)
        if vaccination_text:
            sections.append(vaccination_text)

        measurements = await measurements_repo.list_for_user(db, owner_id, child.id)
        growth_text = _growth_block(child, measurements)
        if growth_text:
            sections.append(growth_text)

        if sections:
            blocks.append(f"Child: {child.name}\n" + "\n".join(sections))

    return "\n\n---\n\n".join(blocks)
