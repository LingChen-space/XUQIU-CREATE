"""应用配置，支持 .env 覆盖。"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "需求发生工具"
    debug: bool = True

    # 数据库 - 开发环境默认 SQLite，生产改为 PostgreSQL
    _data_dir = Path(__file__).resolve().parent.parent / "data"
    _data_dir.mkdir(parents=True, exist_ok=True)
    database_url: str = f"sqlite+aiosqlite:///{_data_dir / 'demand_tool.db'}"

    # 现有爬虫体系 API
    crawler_api_base: str = "http://localhost:8001/api/v1"
    crawler_api_key: str = ""

    # LLM API（用户提供）
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # 每日调度时间（24小时制）
    schedule_hour: int = 6
    schedule_minute: int = 0

    # 信号引擎阈值
    signal_repeat_question_threshold: float = 0.75
    signal_info_scatter_threshold: int = 5
    signal_scarcity_keywords: list[str] = ["限量", "资格", "抢码", "体验服", "测试资格", "内测", "先到先得"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
