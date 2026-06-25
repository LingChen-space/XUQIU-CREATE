"""工具君对话 API —— SSE 流式输出。"""

import json
from datetime import date
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.chat import build_context, stream_chat

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _sse(event: dict) -> str:
    """编码一帧 SSE 数据。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _event_stream(messages: list[ChatMessage], context: str) -> AsyncGenerator[str, None]:
    """生成器：只与 LLM 交互，不再访问 DB（context 已提前取好）。"""
    try:
        raw_messages = [{"role": m.role, "content": m.content} for m in messages]
        async for delta in stream_chat(raw_messages, context):
            yield _sse({"type": "delta", "content": delta})
        yield _sse({"type": "done"})
    except Exception as e:  # noqa: BLE001 - 透传给前端
        yield _sse({"type": "error", "message": str(e)})


async def _error_stream(message: str) -> AsyncGenerator[str, None]:
    yield _sse({"type": "error", "message": message})


@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """工具君对话：基于当日需求数据上下文，流式返回 AI 分析。"""
    # LLM 未配置：直接返回错误流，前端展示提示
    if not settings.llm_api_key:
        return StreamingResponse(
            _error_stream("LLM 未配置，请在 backend/.env 设置 LLM_API_KEY / LLM_API_BASE / LLM_MODEL 后重启后端。"),
            media_type="text/event-stream",
            headers=_sse_headers(),
        )

    # 关键：在返回响应前（依赖作用域内）取完上下文，生成器不再碰 DB
    context = await build_context(db, date.today())

    return StreamingResponse(
        _event_stream(req.messages, context),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


def _sse_headers() -> dict:
    return {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # 禁用反向代理缓冲，保证逐字下发
        "Connection": "keep-alive",
    }
