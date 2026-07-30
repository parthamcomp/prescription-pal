"""Rough token budgeting so one oversized request can't blow the OpenAI bill.

The estimate (word count * 1.3) is deliberately crude - good enough to
reject runaway requests before they reach a paid API. Think of it as a
bouncer, not an accountant: record() logs the real usage OpenAI reports
back afterwards, which is what actually matters for cost tracking.
"""
from dataclasses import dataclass

from app.config import settings


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


@dataclass
class TokenUsage:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    request_count: int = 0
    rejected_count: int = 0


class TokenBudget:
    """Tracks usage and rejects requests that would exceed the configured
    per-request token ceiling, before any API call is made."""

    def __init__(self, max_tokens_per_request: int | None = None):
        self.max_tokens_per_request = (
            max_tokens_per_request or settings.max_tokens_per_request
        )
        self.usage = TokenUsage()

    def check(self, estimated_tokens: int) -> tuple[bool, str | None]:
        if estimated_tokens > self.max_tokens_per_request:
            self.usage.rejected_count += 1
            return False, (
                f"This request needs roughly {estimated_tokens} tokens, which "
                f"is over the {self.max_tokens_per_request} token limit for a "
                f"single request."
            )
        return True, None

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.usage.total_input_tokens += input_tokens
        self.usage.total_output_tokens += output_tokens
        self.usage.request_count += 1

    def stats(self) -> dict:
        return {
            "total_input_tokens": self.usage.total_input_tokens,
            "total_output_tokens": self.usage.total_output_tokens,
            "total_tokens": self.usage.total_input_tokens + self.usage.total_output_tokens,
            "request_count": self.usage.request_count,
            "rejected_count": self.usage.rejected_count,
        }


# One process-wide tracker - fine for a single API instance. Swap for a
# Redis-backed counter (INCR) if you ever run multiple replicas.
budget = TokenBudget()
