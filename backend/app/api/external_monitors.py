# -*- coding: utf-8 -*-
"""外部监控后台同步接口。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import async_session
from app.services.external_monitor_sync import TapKbForumSyncService, get_tap_kb_sync_status

router = APIRouter(prefix="/api/external-monitors", tags=["external-monitors"])


class TapKbSyncRequest(BaseModel):
    days: int = 30
    force: bool = False


@router.post("/tap-kb/sync")
async def sync_tap_kb(payload: TapKbSyncRequest | None = None):
    req = payload or TapKbSyncRequest()
    async with async_session() as session:
        service = TapKbForumSyncService(session)
        return await service.sync(days=req.days, force=req.force)


@router.get("/tap-kb/status")
async def get_tap_kb_status():
    return get_tap_kb_sync_status()
