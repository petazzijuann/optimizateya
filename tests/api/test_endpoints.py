"""Endpoints FastAPI: health, readiness y seguridad del webhook."""

import httpx

from api.main import app


async def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_ok():
    async with await _client() as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_with_test_backends(db_engine, redis):
    async with await _client() as client:
        resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"] == {"database": True, "redis": True}


async def test_webhook_rejects_bad_secret():
    async with await _client() as client:
        resp = await client.post("/webhook/telegram/secreto-falso", json={"update_id": 1})
    assert resp.status_code == 403


async def test_metrics_endpoint():
    async with await _client() as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "python_info" in resp.text


async def test_oauth_state_round_trip(user):
    from api.routers.oauth import make_state, parse_state

    state = make_state(user.id)
    assert parse_state(state) == user.id


async def test_oauth_state_tampered():
    import pytest
    from fastapi import HTTPException

    from api.routers.oauth import parse_state

    with pytest.raises(HTTPException):
        parse_state("estado-falsificado")
