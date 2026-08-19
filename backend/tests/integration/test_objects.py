"""Tier 2 integration tests for services/objects.py, run against the real
MinIO instance already in the Docker Compose stack (the same one the app
itself uses locally) rather than mocking boto3 - a thin S3 wrapper's real
risk is signature/pagination/request-shape mistakes that a mock would just
agree to accept, not decision logic worth testing in isolation. Every
object created here lives under a unique per-test prefix and is cleaned
up via delete_prefix() at teardown, so tests don't collide with each other
or leave anything behind in the shared bucket.
"""
import uuid

import httpx
import pytest

from app.services.objects import delete_prefix, get_object, presigned_url, put_object


@pytest.fixture
def test_prefix():
    prefix = f"test-objects-{uuid.uuid4().hex}/"
    yield prefix
    delete_prefix(prefix)


class TestPutAndGetObject:
    async def test_round_trips_bytes_exactly(self, test_prefix):
        key = f"{test_prefix}file.bin"
        data = b"\x00\x01hello world\xff\xfe"

        put_object(key, data, content_type="application/octet-stream")
        result = get_object(key)

        assert result == data

    async def test_getting_a_key_that_was_never_written_raises(self, test_prefix):
        with pytest.raises(Exception):
            get_object(f"{test_prefix}never-written.bin")


class TestDeletePrefix:
    async def test_removes_every_object_under_the_prefix(self, test_prefix):
        put_object(f"{test_prefix}a.txt", b"a")
        put_object(f"{test_prefix}b.txt", b"b")
        put_object(f"{test_prefix}nested/c.txt", b"c")

        delete_prefix(test_prefix)

        for key in ["a.txt", "b.txt", "nested/c.txt"]:
            with pytest.raises(Exception):
                get_object(f"{test_prefix}{key}")

    async def test_does_not_touch_objects_outside_the_prefix(self, test_prefix):
        sibling_prefix = f"test-objects-{uuid.uuid4().hex}/"
        put_object(f"{test_prefix}mine.txt", b"mine")
        put_object(f"{sibling_prefix}not-mine.txt", b"not mine")

        delete_prefix(test_prefix)

        # Still there - proves delete_prefix scoped to the Prefix param and
        # didn't, say, wipe the whole bucket or match on a loose substring.
        assert get_object(f"{sibling_prefix}not-mine.txt") == b"not mine"
        delete_prefix(sibling_prefix)

    async def test_an_empty_prefix_with_nothing_under_it_does_not_raise(self):
        delete_prefix(f"test-objects-{uuid.uuid4().hex}/never-existed/")


class TestPresignedUrl:
    async def test_the_url_actually_serves_the_object(self, test_prefix):
        key = f"{test_prefix}photo.jpg"
        put_object(key, b"fake-jpeg-bytes", content_type="image/jpeg")

        url = presigned_url(key, expires_in=60)

        async with httpx.AsyncClient() as http:
            resp = await http.get(url)
        assert resp.status_code == 200
        assert resp.content == b"fake-jpeg-bytes"

    async def test_the_url_embeds_the_bucket_and_key(self, test_prefix):
        key = f"{test_prefix}photo.jpg"
        put_object(key, b"data")

        url = presigned_url(key)

        assert "prescriptions" in url  # storage_bucket
        assert key in url
