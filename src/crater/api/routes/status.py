from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/status")
async def status(request: Request) -> dict:
    metrics = request.app.state.metrics
    return {"status": "running", "metrics": metrics.get_all()}
