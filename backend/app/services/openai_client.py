from openai import AsyncOpenAI

from app.config import settings

# Single shared async client. The API key is read from settings (env), never
# hardcoded. If unset, calls will fail loudly at request time.
client = AsyncOpenAI(api_key=settings.openai_api_key or "missing-key")
