import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models_db import Prescription
from app.repositories import prescriptions as repo
from app.schemas import PrescriptionBase
from app.services.embeddings import embed_text
from app.services.llm import chat_completion

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

Be concise and cite which visit(s) your answer comes from when possible."""


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


async def answer(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    *,
    child_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[str, list[str]]:
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
        return (
            "No prescription records found. Upload prescriptions first, then ask questions.",
            [],
        )

    context_block = "\n\n---\n\n".join(
        f"Visit {h.id}:\n{h.document}" for h in hits
    )
    sources = [f"Visit {h.id}" for h in hits]

    user_prompt = f"""PRESCRIPTION RECORDS:
{context_block}

QUESTION: {question}

ANSWER:"""

    try:
        text = await chat_completion(CHAT_SYSTEM, user_prompt, temperature=0.2)
        if text:
            return text, sources
    except ValueError as budget_error:
        return (
            f"{budget_error} Try asking a shorter or more specific question.",
            sources,
        )
    except Exception:  # noqa: BLE001
        pass

    return (
        f"Found relevant records but the LLM is unavailable. Raw context:\n\n{context_block[:2000]}",
        sources,
    )
