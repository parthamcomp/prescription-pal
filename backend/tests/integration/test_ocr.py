"""Tier 2 integration tests for routers/ocr.py, run against the real MinIO
and Redis instances in the Docker Compose stack (same rationale as
test_objects.py - a thin upload/enqueue endpoint's real risk is in the
actual S3 put and Arq enqueue calls, not something worth mocking away).
Nothing consumes the enqueued job during these tests (no worker running),
so `enqueue_job` is a safe, inert side effect - process_ocr_job itself is
covered separately in tests/integration/test_worker.py.

app.queue's Arq pool is a module-level singleton like app.db.engine (see
test_worker.py's docstring for the full story) - same fix, dispose/reset
it between tests so a stale connection from a prior test's event loop
doesn't leak into the next one.
"""
import io

import pytest

import app.queue as queue_module
from app.config import settings
from app.services.objects import delete_prefix, get_object
from tests.builders import make_user
from tests.integration.conftest import auth_cookies


@pytest.fixture(autouse=True)
async def _reset_arq_pool_between_tests():
    yield
    await queue_module.close_pool()


def _image_file(name="photo.jpg", content=b"fake-jpeg-bytes", content_type="image/jpeg"):
    return (name, io.BytesIO(content), content_type)


class TestSubmitOcrValidation:
    async def test_no_files_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        resp = await client.post("/api/ocr", files=[], cookies=auth_cookies(user.id))
        assert resp.status_code in (400, 422)  # empty list may fail FastAPI's own File(...) parsing

    async def test_more_than_max_pages_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        files = [("files", _image_file(f"p{i}.jpg")) for i in range(7)]
        resp = await client.post("/api/ocr", files=files, cookies=auth_cookies(user.id))
        assert resp.status_code == 400

    async def test_a_non_image_file_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        files = [("files", ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))]
        resp = await client.post("/api/ocr", files=files, cookies=auth_cookies(user.id))
        assert resp.status_code == 400

    async def test_an_oversized_file_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        too_big = b"x" * (settings.max_upload_mb * 1024 * 1024 + 1)
        files = [("files", _image_file(content=too_big))]
        resp = await client.post("/api/ocr", files=files, cookies=auth_cookies(user.id))
        assert resp.status_code == 400


class TestSubmitOcrSuccess:
    async def test_a_single_image_creates_a_job_and_uploads_the_bytes(
        self, client, db_session, fake_redis
    ):
        user = await make_user(db_session)
        try:
            files = [("files", _image_file(content=b"page-one-bytes"))]
            resp = await client.post("/api/ocr", files=files, cookies=auth_cookies(user.id))

            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "queued"
            assert body["job_id"]
        finally:
            delete_prefix(f"uploads/{user.id}/")

    async def test_multiple_images_become_one_job_with_multiple_keys(
        self, client, db_session, fake_redis
    ):
        from sqlalchemy import select

        from app.models_db import ProcessingJob

        user = await make_user(db_session)
        try:
            files = [
                ("files", _image_file("p1.jpg", b"page-1")),
                ("files", _image_file("p2.jpg", b"page-2")),
            ]
            resp = await client.post("/api/ocr", files=files, cookies=auth_cookies(user.id))
            assert resp.status_code == 200

            job = (
                await db_session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == resp.json()["job_id"])
                )
            ).scalar_one()
            assert len(job.image_keys) == 2
            assert get_object(job.image_keys[0]) == b"page-1"
            assert get_object(job.image_keys[1]) == b"page-2"
        finally:
            delete_prefix(f"uploads/{user.id}/")

    async def test_uploaded_object_lands_under_the_owners_prefix(
        self, client, db_session, fake_redis
    ):
        # Account-deletion cleanup (services/objects.py::delete_prefix) only
        # works if every upload actually lands under uploads/{owner_id}/ -
        # this is what makes that guarantee true.
        from sqlalchemy import select

        from app.models_db import ProcessingJob

        user = await make_user(db_session)
        try:
            files = [("files", _image_file())]
            resp = await client.post("/api/ocr", files=files, cookies=auth_cookies(user.id))

            job = (
                await db_session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == resp.json()["job_id"])
                )
            ).scalar_one()
            assert job.image_keys[0].startswith(f"uploads/{user.id}/")
        finally:
            delete_prefix(f"uploads/{user.id}/")
