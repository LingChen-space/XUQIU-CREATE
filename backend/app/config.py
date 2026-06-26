"""应用配置，支持 .env 覆盖。"""

from pydantic import model_validator
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

    # 监控采集微服务（本机）
    monitor_api_base: str = "http://127.0.0.1:8001/api/monitor"

    # Tap + 快爆论坛监控后台标准导出
    tap_kb_api_url: str = "https://news.4399.com/app/comm/tap_version2/api.php"
    tap_kb_api_secret: str = "a7f3c2e1b9d4f8e0a2c6b1d5e9f3a7c4"
    tap_kb_content_export_url: str = ""
    tap_kb_config_export_url: str = ""
    tap_kb_api_key: str = ""

    # TapTap 代理 API（自建代理 1.117.17.251，HMAC-SHA256 签名 GET）
    # 区别于 Tap+快爆后台同步(tap_kb_*)：本接口直连 TapTap 代理拉分组 Feed，
    # 由代理服务器代抓，本地 IP 不直接采集 TapTap。group_id→游戏 在采集配置里维护。
    tap_proxy_api_url: str = "http://1.117.17.251:10890/api/v1"
    tap_proxy_api_secret: str = "a38f0c1fa52641908dfb90a735cd161e"
    tap_proxy_max_pages: int = 2

    # LLM API（用户提供）
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # 每日调度时间（24小时制）
    schedule_hour: int = 6
    schedule_minute: int = 0

    # 信号引擎阈值
    signal_repeat_question_threshold: float = 0.75
    signal_info_scatter_threshold: int = 5
    signal_scarcity_keywords: list[str] = ["限量", "资格", "抢码", "体验服", "测试资格", "内测", "先到先得"]

    @model_validator(mode="after")
    def validate_llm_config(self):
        missing = [
            env_name
            for env_name, value in (
                ("LLM_API_KEY", self.llm_api_key),
                ("LLM_API_BASE", self.llm_api_base),
                ("LLM_MODEL", self.llm_model),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError(f"缺少必需的 LLM 配置: {', '.join(missing)}")
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
