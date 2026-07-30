from app.config import settings
from app.services.budget import budget, estimate_tokens
from app.services.openai_client import client


async def chat_completion(
    system: str, user: str, *, temperature: float = 0.2, json_mode: bool = False
) -> str:
    estimated = estimate_tokens(system) + estimate_tokens(user)
    allowed, reason = budget.check(estimated)
    if not allowed:
        raise ValueError(reason)

    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    if resp.usage:
        budget.record(resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return (resp.choices[0].message.content or "").strip()
