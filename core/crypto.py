"""Cifrado Fernet para tokens OAuth. Regla: NUNCA persistir tokens en claro."""

from cryptography.fernet import Fernet

from core.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_settings().fernet_key.encode())
    return _fernet


def encrypt_token(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt_token(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
