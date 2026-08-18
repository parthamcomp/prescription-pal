"""Proves the stub_openai fixture (tests/conftest.py) actually intercepts
calls made through embeddings.py and llm.py, not just openai_client.py
directly. Both of those modules do `from app.services.openai_client import
client`, which binds their own reference at import time - patching only
openai_client.client silently leaves them calling the real API. This test
is what stops that regressing unnoticed (see the fixture's docstring for
the full story of how this was found).
"""
from app.services.embeddings import embed_text
from app.services.llm import chat_completion


class TestStubOpenaiReachesEveryConsumer:
    async def test_embed_text_uses_the_stub_not_a_real_network_call(self, stub_openai):
        result = await embed_text("some prescription text")

        # A real, un-stubbed client would raise (fake API key) rather than
        # return this fixed vector - the value itself is the proof.
        assert result == [0.0] * 1536

    async def test_chat_completion_uses_the_stub_not_a_real_network_call(self, stub_openai):
        result = await chat_completion("system prompt", "user prompt")

        assert "stub answer" in result
