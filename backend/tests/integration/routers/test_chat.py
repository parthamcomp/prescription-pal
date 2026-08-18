"""Tier 2 integration tests for routers/chat.py + services/rag.py's
answer() - the core value proposition of the app, and the least-tested
code before this (29% on rag.py). The chat completion itself is stubbed
(stub_openai) with per-test response content, since what's actually being
verified is the CODE's decision logic around whatever the model returns:
whether an answer counts as "grounded" (must have an explicit [[record]]
marker - "retrieval found something" is not the same thing, see rag.py's
own comment on this), whether facts/med tag/safety note get attached, and
every degrade-gracefully path (malformed JSON, budget rejection, the LLM
call itself failing).

Retrieval goes through the real hybrid vector+full-text search
(repositories/prescriptions.py::search_for_user) against a real Postgres,
not a mock - test prescriptions set `document` to contain the exact terms
being asked about so full-text matching finds them deterministically,
without depending on the embedding column (make_prescription's default
leaves it NULL, which the vector channel simply skips).
"""
from tests.builders import make_child, make_prescription, make_user
from tests.integration.conftest import auth_cookies


def _chat_response(text: str, medication_name: str | None = None, follow_ups=None):
    """A fake OpenAI chat-completion response matching the JSON shape
    rag.py's CHAT_SYSTEM prompt asks for."""
    import json

    async def _create(*args, **kwargs):
        from unittest.mock import AsyncMock

        resp = AsyncMock()
        resp.choices = [AsyncMock()]
        resp.choices[0].message.content = json.dumps(
            {
                "text": text,
                "medication_name": medication_name,
                "follow_ups": follow_ups or [],
            }
        )
        resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=5)
        return resp

    return _create


class TestChatWithNoRecords:
    async def test_no_records_at_all_gets_a_deterministic_message(
        self, client, db_session, stub_openai
    ):
        user = await make_user(db_session)
        resp = await client.post(
            "/api/chat", json={"question": "what was prescribed?"}, cookies=auth_cookies(user.id)
        )
        assert resp.status_code == 200
        assert "No prescription records found" in resp.json()["text"]
        assert resp.json()["grounded"] is False


class TestChatValidation:
    async def test_empty_question_is_rejected(self, client, db_session):
        user = await make_user(db_session)
        resp = await client.post(
            "/api/chat", json={"question": "   "}, cookies=auth_cookies(user.id)
        )
        assert resp.status_code == 400

    async def test_unauthenticated_request_is_rejected(self, client):
        resp = await client.post("/api/chat", json={"question": "anything"})
        assert resp.status_code == 401


class TestGroundedAnswers:
    async def test_a_record_marker_makes_the_answer_grounded_with_sources(
        self, client, db_session, stub_openai
    ):
        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session,
            user.id,
            child_id=child.id,
            # plainto_tsquery ANDs every non-stopword term in the question
            # together - "what was the amoxicillin dose" needs both
            # "amoxicillin" and "dose" present here, or full-text retrieval
            # finds nothing and the test silently exercises the no-hits path
            # instead of the one it's meant to.
            document="amoxicillin dose prescription for ear infection",
            medications=[
                {
                    "name": "Amoxicillin",
                    "form": "Syrup",
                    "dosage": "250mg/5ml",
                    "frequency": "twice daily",
                    "duration": "7 days",
                }
            ],
        )
        stub_openai.chat.completions.create = _chat_response(
            "[[record]]Your child was prescribed Amoxicillin 250mg/5ml.",
            medication_name="Amoxicillin",
        )

        resp = await client.post(
            "/api/chat",
            json={"question": "what was the amoxicillin dose"},
            cookies=auth_cookies(user.id),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["grounded"] is True
        assert len(body["sources"]) == 1
        assert body["med"]["name"] == "Amoxicillin"
        # dosage + frequency is >= 2 facts, so the strip is built
        assert body["facts"] is not None
        assert any(f["label"] == "DOSE" for f in body["facts"])
        assert body["safety_note"] is not None

    async def test_a_single_fact_does_not_produce_a_facts_strip(
        self, client, db_session, stub_openai
    ):
        # _build_facts folds a lone fact back into prose rather than
        # rendering a one-item strip.
        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session,
            user.id,
            child_id=child.id,
            document="ibuprofen dose prescription",
            medications=[
                {
                    "name": "Ibuprofen",
                    "form": "",
                    "dosage": "100mg",
                    "frequency": "",
                    "duration": "",
                }
            ],
        )
        stub_openai.chat.completions.create = _chat_response(
            "[[record]]Your child was prescribed Ibuprofen 100mg.",
            medication_name="Ibuprofen",
        )

        resp = await client.post(
            "/api/chat",
            json={"question": "ibuprofen dose"},
            cookies=auth_cookies(user.id),
        )

        body = resp.json()
        assert body["grounded"] is True
        assert body["facts"] is None
        assert body["safety_note"] is None

    async def test_medication_name_not_found_in_hits_skips_the_med_tag(
        self, client, db_session, stub_openai
    ):
        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session,
            user.id,
            child_id=child.id,
            document="amoxicillin prescription",
            medications=[{"name": "Amoxicillin", "form": "", "dosage": "250mg", "frequency": "", "duration": ""}],
        )
        # Model names a medication that isn't actually in the retrieved hits
        stub_openai.chat.completions.create = _chat_response(
            "[[record]]Your child takes Amoxicillin.",
            medication_name="SomethingElseEntirely",
        )

        resp = await client.post(
            "/api/chat",
            json={"question": "amoxicillin"},
            cookies=auth_cookies(user.id),
        )

        body = resp.json()
        assert body["grounded"] is True
        assert body["med"] is None


class TestUngroundedAnswers:
    async def test_no_record_marker_means_not_grounded_and_no_sources(
        self, client, db_session, stub_openai
    ):
        # Retrieval can return a top-k hit even when nothing is actually
        # relevant - grounded must come from the model's own marker, not
        # from "a hit came back."
        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session,
            user.id,
            child_id=child.id,
            document="amoxicillin prescription",
            medications=[{"name": "Amoxicillin", "form": "", "dosage": "250mg", "frequency": "", "duration": ""}],
        )
        stub_openai.chat.completions.create = _chat_response(
            "[[general]]Amoxicillin is a penicillin-type antibiotic used for bacterial infections."
        )

        resp = await client.post(
            "/api/chat",
            json={"question": "what is amoxicillin used for"},
            cookies=auth_cookies(user.id),
        )

        body = resp.json()
        assert body["grounded"] is False
        assert body["sources"] == []
        assert body["med"] is None
        assert body["facts"] is None


class TestDegradedPaths:
    async def test_malformed_model_json_degrades_to_plain_text_with_sources(
        self, client, db_session, stub_openai
    ):
        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session, user.id, child_id=child.id, document="amoxicillin prescription"
        )

        async def _garbage(*args, **kwargs):
            from unittest.mock import AsyncMock

            resp = AsyncMock()
            resp.choices = [AsyncMock()]
            resp.choices[0].message.content = "not valid json at all"
            resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=5)
            return resp

        stub_openai.chat.completions.create = _garbage

        resp = await client.post(
            "/api/chat", json={"question": "amoxicillin"}, cookies=auth_cookies(user.id)
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "not valid json at all"
        assert len(body["sources"]) == 1
        assert body["grounded"] is False

    async def test_chat_completion_failure_degrades_to_raw_context_message(
        self, client, db_session, stub_openai
    ):
        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session, user.id, child_id=child.id, document="amoxicillin prescription"
        )

        async def _blow_up(*args, **kwargs):
            raise ConnectionError("openai is down")

        stub_openai.chat.completions.create = _blow_up

        resp = await client.post(
            "/api/chat", json={"question": "amoxicillin"}, cookies=auth_cookies(user.id)
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "LLM is unavailable" in body["text"]
        assert len(body["sources"]) == 1

    async def test_embedding_failure_still_returns_an_answer_via_fulltext(
        self, client, db_session, stub_openai
    ):
        # answer() tolerates embed_text() failing and falls back to
        # full-text-only retrieval instead of failing the whole request.
        async def _embed_blows_up(*args, **kwargs):
            raise ConnectionError("embeddings endpoint down")

        stub_openai.embeddings.create = _embed_blows_up
        stub_openai.chat.completions.create = _chat_response(
            "[[record]]Found it via full-text."
        )

        user = await make_user(db_session)
        child = await make_child(db_session, user.id)
        await make_prescription(
            db_session, user.id, child_id=child.id, document="amoxicillin prescription"
        )

        resp = await client.post(
            "/api/chat", json={"question": "amoxicillin"}, cookies=auth_cookies(user.id)
        )

        assert resp.status_code == 200
        assert resp.json()["grounded"] is True
