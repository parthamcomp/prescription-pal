from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.logging_conf import logger
from app.metrics import timed_request
from app.models_db import User
from app.schemas import ChatRequest, ChatResponse
from app.services import rag
from app.services.rate_limit import user_rate_limit

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    dependencies=[Depends(user_rate_limit(60, 3600, "chat"))],
)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    with timed_request() as ctx:
        try:
            result = await rag.answer(
                db,
                user.id,
                question,
                child_id=body.child_id,
                date_from=body.date_from,
                date_to=body.date_to,
            )
        except Exception:
            ctx["error"] = True
            raise

    logger.info(
        "chat_completed",
        extra={
            "extra_fields": {
                "user_id": str(user.id),
                "source_count": len(result.sources),
            }
        },
    )
    return result
