from app.config import settings
from app.services.openai_client import client


async def embed_text(text: str) -> list[float]:
    """Return an embedding vector for a single piece of text."""
    resp = await client.embeddings.create(
        model=settings.openai_embed_model,
        input=text[:8000] or " ",
    )
    return resp.data[0].embedding
