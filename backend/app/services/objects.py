import boto3
from botocore.client import Config

from app.config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    """Create the bucket if it does not exist (safe for MinIO/local dev)."""
    s3 = _client()
    try:
        s3.head_bucket(Bucket=settings.storage_bucket)
    except Exception:
        try:
            s3.create_bucket(Bucket=settings.storage_bucket)
        except Exception:
            pass


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client().put_object(
        Bucket=settings.storage_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def get_object(key: str) -> bytes:
    resp = _client().get_object(Bucket=settings.storage_bucket, Key=key)
    return resp["Body"].read()


def delete_prefix(prefix: str) -> None:
    """Delete every object under `prefix` (e.g. a user's `uploads/{id}/`
    folder). Used on account deletion so uploaded prescription photos don't
    outlive the account they belonged to - Postgres FK cascades clean up the
    DB rows, but nothing else removes the underlying files from object
    storage."""
    s3 = _client()
    continuation_token = None
    while True:
        kwargs = {"Bucket": settings.storage_bucket, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        resp = s3.list_objects_v2(**kwargs)
        keys = [{"Key": obj["Key"]} for obj in resp.get("Contents", [])]
        if keys:
            s3.delete_objects(Bucket=settings.storage_bucket, Delete={"Objects": keys})
        if not resp.get("IsTruncated"):
            break
        continuation_token = resp.get("NextContinuationToken")
