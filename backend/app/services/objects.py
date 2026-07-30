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
