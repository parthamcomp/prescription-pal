import uuid
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models_db import Prescription
from app.schemas import PrescriptionCreate


def _apply(model: Prescription, data: PrescriptionCreate) -> None:
    model.doctor_name = data.doctor_name
    model.date_of_visit = data.date_of_visit
    model.complaint = data.complaint
    model.diagnosis = data.diagnosis
    model.medications = [m.model_dump() for m in data.medications]
    model.child_age = data.child_age
    model.child_weight = data.child_weight
    model.child_height = data.child_height
    model.child_id = data.child_id
    model.additional_notes = data.additional_notes
    model.source_text = data.source_text


async def list_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    *,
    child_id: uuid.UUID | None = None,
) -> list[Prescription]:
    stmt = select(Prescription).where(Prescription.user_id == user_id)
    if child_id is not None:
        stmt = stmt.where(Prescription.child_id == child_id)
    result = await db.execute(
        stmt.order_by(Prescription.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def get_for_user(
    db: AsyncSession, user_id: uuid.UUID, prescription_id: uuid.UUID
) -> Prescription | None:
    result = await db.execute(
        select(Prescription).where(
            Prescription.id == prescription_id,
            Prescription.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: PrescriptionCreate,
    document: str,
    embedding: list[float] | None,
    image_keys: list[str] | None = None,
) -> Prescription:
    model = Prescription(
        user_id=user_id,
        document=document,
        embedding=embedding,
        image_keys=image_keys or [],
    )
    _apply(model, data)
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def update_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    prescription_id: uuid.UUID,
    data: PrescriptionCreate,
    document: str,
    embedding: list[float] | None,
) -> Prescription | None:
    model = await get_for_user(db, user_id, prescription_id)
    if model is None:
        return None
    _apply(model, data)
    model.document = document
    model.embedding = embedding
    await db.commit()
    await db.refresh(model)
    return model


async def delete_for_user(
    db: AsyncSession, user_id: uuid.UUID, prescription_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(Prescription).where(
            Prescription.id == prescription_id,
            Prescription.user_id == user_id,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def search_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    query_embedding: list[float] | None,
    top_k: int,
    *,
    child_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Prescription]:
    """Hybrid retrieval: pgvector nearest-neighbour + Postgres full-text
    search, merged with reciprocal rank fusion (RRF), narrowed first by any
    structured filters the caller supplies.

    Vector search alone misses exact strings an embedding model treats as
    meaningless tokens - drug names, dosages, doctor names. Full-text search
    alone misses paraphrases ("ear infection" vs "otitis media"). RRF lets
    whichever channel ranks a record highly win, without tuning a blend
    weight between the two scores.

    child_id/date_from/date_to are exact structured filters, not fuzzy
    matches - "which child" and "which time range" are things the caller
    already knows, so there is no reason to make the embedding guess them.
    Applying them as a SQL WHERE clause before ranking is cheaper and more
    reliable than trying to extract that intent from free text.

    query_embedding is optional: when the caller couldn't produce one (e.g.
    the embedding call failed or there's no OpenAI key configured), the
    vector channel is skipped and retrieval falls back to full-text-only.
    """
    fanout = top_k * 4

    filters = [Prescription.user_id == user_id]
    if child_id is not None:
        filters.append(Prescription.child_id == child_id)
    if date_from is not None:
        filters.append(Prescription.date_of_visit >= date_from)
    if date_to is not None:
        filters.append(Prescription.date_of_visit <= date_to)

    if query_embedding is None:
        vector_ids = []
    else:
        vector_ids = (
            await db.execute(
                select(Prescription.id)
                .where(*filters, Prescription.embedding.is_not(None))
                .order_by(Prescription.embedding.cosine_distance(query_embedding))
                .limit(fanout)
            )
        ).scalars().all()

    tsquery = func.plainto_tsquery(settings.fulltext_language, question)
    fulltext_ids = (
        await db.execute(
            select(Prescription.id)
            .where(*filters, Prescription.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank(Prescription.search_vector, tsquery).desc())
            .limit(fanout)
        )
    ).scalars().all()

    if not vector_ids and not fulltext_ids:
        return []

    rrf_k = 60  # standard RRF smoothing constant
    scores: dict[uuid.UUID, float] = {}
    for rank, pid in enumerate(vector_ids):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (rrf_k + rank + 1)
    for rank, pid in enumerate(fulltext_ids):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (rrf_k + rank + 1)

    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]

    rows = (
        await db.execute(select(Prescription).where(Prescription.id.in_(ranked_ids)))
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    return [by_id[pid] for pid in ranked_ids if pid in by_id]
