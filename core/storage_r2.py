"""Backend de storage en Cloudflare R2 (S3-compatible) vía aioboto3."""

import aioboto3

from core.config import get_settings


def _session() -> aioboto3.Session:
    s = get_settings()
    return aioboto3.Session(
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
    )


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    s = get_settings()
    async with _session().client("s3", endpoint_url=s.r2_endpoint_url) as s3:
        await s3.put_object(Bucket=s.r2_bucket, Key=key, Body=data, ContentType=content_type)


async def download_bytes(key: str) -> bytes:
    s = get_settings()
    async with _session().client("s3", endpoint_url=s.r2_endpoint_url) as s3:
        resp = await s3.get_object(Bucket=s.r2_bucket, Key=key)
        return await resp["Body"].read()


async def delete_key(key: str) -> None:
    s = get_settings()
    async with _session().client("s3", endpoint_url=s.r2_endpoint_url) as s3:
        await s3.delete_object(Bucket=s.r2_bucket, Key=key)


async def delete_prefix(prefix: str) -> int:
    """Borra todos los objetos del prefijo. Devuelve cantidad eliminada."""
    s = get_settings()
    deleted = 0
    async with _session().client("s3", endpoint_url=s.r2_endpoint_url) as s3:
        paginator = s3.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=s.r2_bucket, Prefix=prefix):
            keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if keys:
                await s3.delete_objects(Bucket=s.r2_bucket, Delete={"Objects": keys})
                deleted += len(keys)
    return deleted
