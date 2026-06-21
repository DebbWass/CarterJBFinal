from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    probe = request.app.state.health_probe
    report = await probe.check()
    status_code = 200 if report.healthy else 503
    return JSONResponse(content=report.as_dict(), status_code=status_code)
