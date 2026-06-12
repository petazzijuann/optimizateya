"""Liveness y readiness."""

from fastapi import APIRouter, Response
from sqlalchemy import text

from core.database import get_engine
from core.redis import get_redis

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict:
    checks = {"database": False, "redis": False}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(await get_redis().ping())
    except Exception:
        pass
    if not all(checks.values()):
        response.status_code = 503
    return {"status": "ready" if all(checks.values()) else "degraded", "checks": checks}
