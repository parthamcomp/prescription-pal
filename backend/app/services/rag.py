import json
import re
import uuid
from datetime import date, timedelta

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models_db import Prescription
from app.repositories import prescriptions as repo
from app.schemas import (
    ChatResponse,
    FactOut,
    FollowUpOut,
    MedTagOut,
    PrescriptionBase,
    SourceOut,
)
from app.services.embeddings import embed_text
from app.services.llm import chat_completion
from app.services.meds import color_key_for, parse_duration_days, shorten_duration

SAFETY_NOTE_TEXT = (
    "This is what your prescription says — not medical advice. Check with your "
    "prescriber or pharmacist before changing anything."
)

CHAT_SYSTEM = """You are a helpful assistant for a parent reviewing their child's past medical prescriptions.
Answer using only the information contained in the prescription records provided below.

Judge each question by whether the records contain relevant information, not by how the question
is phrased. "What medication should I give for a cough?" and "What should I do if my child has a
cough?" are asking the same thing - if a cough visit is on record, answer with what was recorded
(medication, dosage, frequency, duration, doctor's notes) either way. Don't refuse just because a
question is worded as "what should I do" or "how do I treat X" when the records already answer it.

Only decline when the records genuinely don't contain relevant information, or when the question
asks for a new medical judgment the records never made - e.g. diagnosing a new or worsening
symptom, assessing safety/interactions, or deciding whether something is an emergency. In those
cases, say you don't have that information and suggest contacting a doctor. Never guess or invent
advice beyond what's recorded.

Be concise and cite which visit(s) your answer comes from when possible.

Respond with ONLY a JSON object of this exact shape, no markdown fence, no explanation:
{
  "text": "your prose answer. Wrap key values you state (dose, frequency, duration, dates) in **double asterisks**.",
  "medication_name": "the single medication name this answer centres on, spelled exactly as it appears in the records, or null if the answer isn't about one specific medication (e.g. it compares several, or isn't about medication at all)",
  "follow_ups": [
    {"label": "2-4 word chip label", "question": "the full natural-language question that label stands for"}
  ]
}
follow_ups must have 3-4 items - plain-language, grounded only in what's actually in the retrieved
records, never inventing a medication or visit that isn't there, and never repeating the question
just asked. "question" is the complete question a parent would type; "label" is that same question
shortened to its 2-4 word core, e.g. question "What antibiotics has my child taken?" pairs with
label "Antibiotics taken" - not a generic word count, an actually short label.
Never put numeric facts (dose, frequency, duration, dates) anywhere except inside "text" - a
separate part of the system derives those directly from the records, not from you."""


class _RawFollowUp(BaseModel):
    label: str = Field(min_length=1)
    question: str = Field(min_length=1)


class _RawAnswer(BaseModel):
    text: str = Field(min_length=1)
    medication_name: str | None = None
    follow_ups: list[_RawFollowUp] = Field(default_factory=list)


def build_document(p: PrescriptionBase) -> str:
    meds = "\n".join(
        f"  - {m.name}: {m.dosage}, {m.frequency}, for {m.duration}"
        for m in p.medications
    )
    return f"""Doctor: {p.doctor_name}
Date: {p.date_of_visit or 'unknown'}
Child age: {p.child_age}
Child weight: {p.child_weight}
Complaint: {p.complaint}
Diagnosis: {p.diagnosis}
Medications:
{meds or '  (none recorded)'}
Notes: {p.additional_notes}
"""


def _clamp_label(label: str, max_words: int = 5) -> str:
    """Defensive ceiling only - the model is asked for a 2-4 word label
    directly (see prompt), this just guards against a pathological reply
    blowing out the chip layout."""
    words = label.strip().split()
    return " ".join(words[:max_words])


def _short_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}" if d.year == date.today().year else f"{d.day} {d.strftime('%b %Y')}"


def _build_source(hit: Prescription) -> SourceOut:
    meds = hit.medications or []
    if meds and (meds[0].get("name") or "").strip():
        title = f"{meds[0]['name']} {meds[0].get('dosage', '')}".strip()
    elif hit.date_of_visit:
        title = f"Prescription · {_short_date(hit.date_of_visit)}"
    else:
        title = "Prescription"

    return SourceOut(
        id=str(hit.id),
        kind="prescription",
        title=title,
        prescriber=hit.doctor_name or None,
        date=hit.date_of_visit.isoformat() if hit.date_of_visit else None,
        page=None,
    )


def _find_medication(
    hits: list[Prescription], name: str
) -> tuple[Prescription, dict] | None:
    target = name.strip().lower()
    if not target:
        return None
    for h in hits:
        for m in h.medications or []:
            if (m.get("name") or "").strip().lower() == target:
                return h, m
    for h in hits:
        for m in h.medications or []:
            mname = (m.get("name") or "").strip().lower()
            if mname and (target in mname or mname in target):
                return h, m
    return None


def _build_facts(
    med: dict, visit_date: date | None, question: str
) -> list[FactOut]:
    facts: list[FactOut] = []
    if med.get("dosage"):
        facts.append(FactOut(label="DOSE", value=med["dosage"]))
    if med.get("frequency"):
        facts.append(FactOut(label="HOW OFTEN", value=med["frequency"]))

    duration = med.get("duration") or ""
    if duration:
        facts.append(FactOut(label="COURSE", value=shorten_duration(duration)))

    if visit_date:
        days = parse_duration_days(duration)
        if days is not None:
            ends_date = visit_date + timedelta(days=days)
            asked_about_end = bool(
                re.search(
                    r"how long|until when|finish|last dose|when.*(stop|done|end)",
                    question,
                    re.IGNORECASE,
                )
            )
            facts.append(
                FactOut(
                    label="ENDS",
                    value=_short_date(ends_date),
                    emphasis=asked_about_end,
                )
            )

    # A single fact isn't a strip - fold it back into the prose instead.
    return facts[:4] if len(facts) >= 2 else []


async def answer(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    *,
    child_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ChatResponse:
    try:
        query_embedding = await embed_text(question)
    except Exception:  # noqa: BLE001
        # No OpenAI key, or the embedding call failed - fall back to
        # full-text-only retrieval instead of failing the whole request.
        query_embedding = None

    hits: list[Prescription] = await repo.search_for_user(
        db,
        user_id,
        question,
        query_embedding,
        settings.rag_top_k,
        child_id=child_id,
        date_from=date_from,
        date_to=date_to,
    )

    if not hits:
        return ChatResponse(
            text="No prescription records found. Upload prescriptions first, then ask questions."
        )

    sources = [_build_source(h) for h in hits]
    context_block = "\n\n---\n\n".join(
        f"Visit {h.id} ({h.date_of_visit or 'unknown date'}):\n{h.document}"
        for h in hits
    )
    user_prompt = f"""PRESCRIPTION RECORDS:
{context_block}

QUESTION: {question}

Respond with only the JSON object described in your instructions."""

    try:
        content = await chat_completion(
            CHAT_SYSTEM, user_prompt, temperature=0.2, json_mode=True
        )
    except ValueError as budget_error:
        return ChatResponse(
            text=f"{budget_error} Try asking a shorter or more specific question.",
            sources=sources,
        )
    except Exception:  # noqa: BLE001
        return ChatResponse(
            text=f"Found relevant records but the LLM is unavailable. Raw context:\n\n{context_block[:2000]}",
            sources=sources,
        )

    try:
        parsed = _RawAnswer.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError):
        # The model didn't return the shape we asked for - degrade to plain
        # prose + sources rather than crash or fake structured data.
        return ChatResponse(text=content or "No answer.", sources=sources)

    med_tag = None
    facts = None
    safety_note = None
    if parsed.medication_name:
        found = _find_medication(hits, parsed.medication_name)
        if found:
            hit, med = found
            med_tag = MedTagOut(name=med["name"], color_key=color_key_for(med["name"]))
            built_facts = _build_facts(med, hit.date_of_visit, question)
            if built_facts:
                facts = built_facts
                safety_note = SAFETY_NOTE_TEXT

    follow_ups = [
        FollowUpOut(label=_clamp_label(f.label), question=f.question)
        for f in parsed.follow_ups
        if f.label.strip() and f.question.strip()
    ][:4]

    return ChatResponse(
        text=parsed.text,
        med=med_tag,
        facts=facts,
        safety_note=safety_note,
        sources=sources,
        follow_ups=follow_ups,
    )
