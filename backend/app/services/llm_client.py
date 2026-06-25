"""共享的 LLM 客户端构造。

把 LLMPipeline 里的 base_url 清洗 + AsyncOpenAI 构造逻辑抽出来，
供需求分析管线和工具君对话等场景复用。
"""

from openai import AsyncOpenAI

from app.config import settings


def build_async_client() -> AsyncOpenAI | None:
    """构造 AsyncOpenAI 客户端；未配置 api_key 时返回 None。"""
    if not settings.llm_api_key:
        return None

    # 清理 base_url：确保不以 /chat/completions 结尾（SDK 会自动追加）
    clean_url = settings.llm_api_base.rstrip("/")
    if clean_url.endswith("/chat/completions"):
        clean_url = clean_url[: -len("/chat/completions")]

    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=clean_url,
    )
