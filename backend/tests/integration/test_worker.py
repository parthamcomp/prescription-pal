"""Tier 2 integration tests for app/worker.py::process_ocr_job - previously
0% covered despite being the only place OCR/extraction actually runs (see
CLAUDE.md: "never called inline in a request").

worker.py opens its own DB session via app.db.SessionLocal rather than
FastAPI's Depends(get_db), so unlike the router tests in this suite it does
NOT go through the client fixture's per-request session override - it uses
whatever database app.db.engine was built against at import time. Running
these with DATABASE_URL set to the same value as TEST_DATABASE_URL (see
tests/README.md) points that module-level engine at the same Postgres the
db_session fixture uses, so a job row created via db_session is visible to
the worker's own session and vice versa, exactly like two real concurrent
processes talking to the same database.

get_object/extract_text_from_image/extract_prescription_from_text are
mocked directly on the app.worker module (worker.py does `from X import Y`,
so patching the origin module wouldn't reach worker's own reference - the
same gotcha the stub_openai fixture had, see test_stub_openai_fixture.py).
"""
import pytest

import app.db as db_module
import app.worker as worker_module
from tests.builders import make_job, make_user


@pytest.fixture(autouse=True)
async def _dispose_worker_engine_between_tests():
    """process_ocr_job uses app.db.SessionLocal directly (it has no
    Depends(get_db) to override, unlike the router tests in this suite),
    so it's the one thing in Tier 2 touching that module-level engine. Its
    connection pool gets bound to whichever event loop was active the first
    time a connection was actually opened - but pytest-asyncio hands each
    test function a fresh loop, so reusing a pooled connection from a prior
    test's loop blows up with "attached to a different loop". Disposing the
    pool after each test forces fresh connections on the next test's loop,
    same fix SQLAlchemy's own docs give for an async engine reused across
    event loops."""
    yield
    await db_module.engine.dispose()


@pytest.fixture
def mock_pipeline(monkeypatch):
    """Configurable get_object/OCR/extraction stand-ins. Each starts with a
    single-page happy-path default; tests override what they need."""
    state = {
        "images": {"key-1": b"fake-image-bytes"},
        "ocr_text": {"key-1": "Amoxicillin 250mg twice daily"},
        "extracted": {
            "doctor_name": "Dr. Test",
            "date_of_visit": None,
            "complaint": "",
            "diagnosis": "",
            "medications": [],
            "child_age": "",
            "child_weight": "",
            "additional_notes": "",
            "low_confidence": [],
        },
    }

    def fake_get_object(key: str) -> bytes:
        return state["images"][key]

    def fake_ocr(image_bytes: bytes) -> str:
        # Map back through the bytes->key relationship set up in "images"
        for key, val in state["images"].items():
            if val == image_bytes:
                return state["ocr_text"].get(key, "")
        return ""

    async def fake_extract(raw_text: str) -> dict:
        return state["extracted"]

    monkeypatch.setattr(worker_module, "get_object", fake_get_object)
    monkeypatch.setattr(worker_module, "extract_text_from_image", fake_ocr)
    monkeypatch.setattr(worker_module, "extract_prescription_from_text", fake_extract)
    return state


class TestProcessOcrJobHappyPath:
    async def test_single_page_job_completes_with_extracted_fields(
        self, db_session, mock_pipeline
    ):
        user = await make_user(db_session)
        job = await make_job(db_session, user.id, image_keys=["key-1"])

        result = await worker_module.process_ocr_job({}, str(job.id))

        assert result == {"status": "done"}
        await db_session.refresh(job)
        assert job.status == "done"
        assert job.raw_text == "Amoxicillin 250mg twice daily"
        assert job.extracted["doctor_name"] == "Dr. Test"

    async def test_multi_page_job_joins_text_with_page_markers(
        self, db_session, mock_pipeline
    ):
        mock_pipeline["images"] = {"key-1": b"page-one", "key-2": b"page-two"}
        mock_pipeline["ocr_text"] = {"key-1": "first page text", "key-2": "second page text"}

        user = await make_user(db_session)
        job = await make_job(db_session, user.id, image_keys=["key-1", "key-2"])

        await worker_module.process_ocr_job({}, str(job.id))

        await db_session.refresh(job)
        assert job.status == "done"
        assert "--- page 1 ---" in job.raw_text
        assert "--- page 2 ---" in job.raw_text
        assert "first page text" in job.raw_text
        assert "second page text" in job.raw_text

    async def test_single_page_job_has_no_page_marker(self, db_session, mock_pipeline):
        # The "--- page N ---" prefix only makes sense once there's more
        # than one page to distinguish - a single-page upload should read
        # like plain OCR output, not "page 1" of a set of one.
        user = await make_user(db_session)
        job = await make_job(db_session, user.id, image_keys=["key-1"])

        await worker_module.process_ocr_job({}, str(job.id))

        await db_session.refresh(job)
        assert "page 1" not in job.raw_text.lower()


class TestProcessOcrJobFailureModes:
    async def test_job_id_that_does_not_exist_is_a_no_op(self, db_session, mock_pipeline):
        import uuid

        result = await worker_module.process_ocr_job({}, str(uuid.uuid4()))
        assert result == {"error": "job not found"}

    async def test_no_text_detected_marks_the_job_as_error(self, db_session, mock_pipeline):
        mock_pipeline["ocr_text"] = {"key-1": ""}  # blank photo, blurry, etc.

        user = await make_user(db_session)
        job = await make_job(db_session, user.id, image_keys=["key-1"])

        result = await worker_module.process_ocr_job({}, str(job.id))

        assert result == {"status": "error"}
        await db_session.refresh(job)
        assert job.status == "error"
        assert "clearer photo" in job.error

    async def test_an_exception_during_ocr_marks_the_job_as_error_not_crash(
        self, db_session, monkeypatch, mock_pipeline
    ):
        def blow_up(image_bytes: bytes) -> str:
            raise RuntimeError("tesseract exploded")

        monkeypatch.setattr(worker_module, "extract_text_from_image", blow_up)

        user = await make_user(db_session)
        job = await make_job(db_session, user.id, image_keys=["key-1"])

        result = await worker_module.process_ocr_job({}, str(job.id))

        assert result == {"status": "error", "detail": "tesseract exploded"}
        await db_session.refresh(job)
        assert job.status == "error"
        assert job.error == "tesseract exploded"
