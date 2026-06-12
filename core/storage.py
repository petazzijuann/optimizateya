"""Object storage con backend intercambiable: Cloudinary o Cloudflare R2.

Se elige por config: si CLOUDINARY_URL está seteada se usa Cloudinary;
si no, R2 (R2_*). Claves con prefijo por usuario: users/{user_id}/... — el
borrado total de un usuario (privacidad) elimina el prefijo completo.
"""

from types import ModuleType

from core.config import get_settings


def _backend() -> ModuleType:
    if get_settings().cloudinary_url:
        from core import storage_cloudinary

        return storage_cloudinary
    from core import storage_r2

    return storage_r2


def user_prefix(user_id: str) -> str:
    return f"users/{user_id}/"


async def upload_bytes(
    key: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    await _backend().upload_bytes(key, data, content_type)


async def download_bytes(key: str) -> bytes:
    return await _backend().download_bytes(key)


async def delete_key(key: str) -> None:
    await _backend().delete_key(key)


async def delete_user_prefix(user_id: str) -> int:
    """Borra todos los objetos del usuario. Devuelve cantidad eliminada."""
    return await _backend().delete_prefix(user_prefix(user_id))
