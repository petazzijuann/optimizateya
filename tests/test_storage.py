"""Storage: selección de backend (Cloudinary/R2) y firma de la Upload API."""

import hashlib

import pytest

from core import storage, storage_cloudinary, storage_r2
from core.config import Settings, get_settings


def test_backend_dispatch_cloudinary(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "cloudinary_url", "cloudinary://key:secret@democloud", raising=True
    )
    assert storage._backend() is storage_cloudinary


def test_backend_dispatch_r2_por_defecto(monkeypatch):
    monkeypatch.setattr(get_settings(), "cloudinary_url", "", raising=True)
    assert storage._backend() is storage_r2


def test_user_prefix():
    assert storage.user_prefix("abc-123") == "users/abc-123/"


def test_cloudinary_creds_parse(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "cloudinary_url", "cloudinary://mykey:mysecret@democloud", raising=True
    )
    cloud, api_key, secret = storage_cloudinary._creds()
    assert (cloud, api_key, secret) == ("democloud", "mykey", "mysecret")


def test_cloudinary_sign_ordena_params():
    params = {"timestamp": "1700000000", "public_id": "users/u1/x.ogg"}
    expected = hashlib.sha1(
        b"public_id=users/u1/x.ogg&timestamp=1700000000" + b"s3cr3t"
    ).hexdigest()
    assert storage_cloudinary.sign(params, "s3cr3t") == expected


def test_config_cloudinary_url_valida(monkeypatch):
    monkeypatch.setenv("CLOUDINARY_URL", "cloudinary://k:s@cloud")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.cloudinary_url == "cloudinary://k:s@cloud"


def test_config_cloudinary_url_invalida(monkeypatch):
    from pydantic import ValidationError as PydanticValidationError

    monkeypatch.setenv("CLOUDINARY_URL", "https://no-es-cloudinary.com")
    with pytest.raises(PydanticValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
