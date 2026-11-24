"""应用配置：统一从环境变量加载，禁止在代码里硬编码密钥。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。字段名与 .env 中的变量名大小写不敏感对应。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    app_name: str = "LeadHarbor"
    app_env: str = "dev"
    debug: bool = False

    # 目标市场：中亚优先（ISO 3166-1 alpha-2，逗号分隔）
    target_countries: str = "KZ,UZ,KG,TJ,TM"
    default_region: str = "KZ"

    # 数据库
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/leadharbor"
    database_url_sync: str = "postgresql+psycopg://user:pass@localhost:5432/leadharbor"
    db_echo: bool = False

    # 队列
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # 采集
    google_places_api_key: str = ""
    twogis_api_key: str = ""
    # Google 可编程搜索（Custom Search JSON API）：直接按关键词找公司官网
    google_search_api_key: str = ""
    google_search_cx: str = ""
    # OpenCorporates 公司注册数据（免费额度 + api_token，中亚公司注册信息）
    opencorporates_api_token: str = ""
    # Yandex Geosearch（俄语区/中亚商家搜索，免费额度 + apikey）
    yandex_geosearch_api_key: str = ""
    yandex_geosearch_url: str = "https://search-maps.yandex.ru/v1/"
    # AI 研究员：用 OpenAI Token 研究/推断公司信息（按 token 计费，结果需人工核实）
    ai_researcher_enabled: bool = False
    ai_researcher_model: str = "gpt-4o-mini"
    # OpenStreetMap Overpass（免费开放数据，受公共实例限流）
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    crawler_user_agent: str = "LeadHarborBot/0.1 (+contact@example.com)"
    crawler_max_concurrency: int = Field(default=5, ge=1, le=50)
    crawler_requests_per_second: float = Field(default=2.0, gt=0)
    crawler_timeout_seconds: float = 20.0

    # AI
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_dim: int = 1536

    @property
    def target_country_list(self) -> list[str]:
        """把逗号分隔的 TARGET_COUNTRIES 解析为去重、大写的国家码列表。"""
        seen: list[str] = []
        for code in self.target_countries.split(","):
            code = code.strip().upper()
            if code and code not in seen:
                seen.append(code)
        return seen


@lru_cache
def get_settings() -> Settings:
    """返回缓存的配置单例。测试中可调用 get_settings.cache_clear()。"""
    return Settings()


settings = get_settings()
