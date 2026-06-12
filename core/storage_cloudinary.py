"""Backend de storage en Cloudinary vía REST (httpx, async).

Los archivos se suben como resource_type "raw" con public_id = key, así el
prefijo users/{user_id}/ funciona igual que en R2 (carpetas + borrado masivo).
La entrega es por URL pública pero no adivinable (uuid hex en la clave); para
privacidad estricta de archivos usar R2.
"""

import hashlib
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from core.config import get_settings

_API = "https://api.cloudinary.com/v1_1"


def _creds() -> tuple[str, str, str]:
    """(cloud_name, api_key, api_secret) desde CLOUDINARY_URL."""
    parsed = urlparse(get_settings().cloudinary_url)
    return parsed.hostname or "", parsed.username or "", parsed.password or ""


def sign(params: dict[str, str], api_secret: str) -> str:
    """Firma de la Upload API: sha1(params ordenados como query + secret)."""
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha1((to_sign + api_secret).encode()).hexdigest()


def _signed_form(params: dict[str, str], api_key: str, api_secret: str) -> dict[str, str]:
    return {**params, "api_key": api_key, "signature": sign(params, api_secret)}


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    cloud, api_key, secret = _creds()
    params = {"public_id": key, "timestamp": str(int(time.time()))}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{_API}/{cloud}/raw/upload",
            data=_signed_form(params, api_key, secret),
            files={"file": (key.rsplit("/", 1)[-1], data, content_type)},
        )
        resp.raise_for_status()


async def download_bytes(key: str) -> bytes:
    cloud, _, _ = _creds()
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(f"https://res.cloudinary.com/{cloud}/raw/upload/{key}")
        resp.raise_for_status()
        return resp.content


async def delete_key(key: str) -> None:
    cloud, api_key, secret = _creds()
    params = {"public_id": key, "timestamp": str(int(time.time()))}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_API}/{cloud}/raw/destroy", data=_signed_form(params, api_key, secret)
        )
        resp.raise_for_status()


async def delete_prefix(prefix: str) -> int:
    """Borra todos los recursos del prefijo (Admin API). Devuelve cantidad."""
    cloud, api_key, secret = _creds()
    deleted = 0
    async with httpx.AsyncClient(timeout=60, auth=(api_key, secret)) as client:
        while True:
            resp = await client.delete(
                f"{_API}/{cloud}/resources/raw/upload", params={"prefix": prefix}
            )
            resp.raise_for_status()
            body: dict[str, Any] = resp.json()
            deleted += len(body.get("deleted") or {})
            if not body.get("partial"):
                return deleted
