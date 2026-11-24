"""运行时配置服务：把前端填写的密钥持久化到 app_setting 表并即时生效。

优先使用数据库中的覆盖值；未覆盖时回退到 .env 默认值。
密钥以明文存储，请在可信环境中使用；接口返回时只给出打码值。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.app_setting import AppSetting

logger = get_logger(__name__)


@dataclass(frozen=True)
class ConfigField:
    name: str  # 环境变量名，也是 app_setting.key
    attr: str  # settings 上的属性名
    label: str
    group: str
    secret: bool = True
    kind: str = "str"  # str | bool


FIELDS: list[ConfigField] = [
    ConfigField("TWOGIS_API_KEY", "twogis_api_key", "2GIS API Key", "2GIS / 中亚地图"),
    ConfigField(
        "GOOGLE_PLACES_API_KEY",
        "google_places_api_key",
        "Google Places API Key",
        "Google",
    ),
    ConfigField(
        "GOOGLE_SEARCH_API_KEY",
        "google_search_api_key",
        "Google 搜索 API Key",
        "Google",
    ),
    ConfigField(
        "GOOGLE_SEARCH_CX",
        "google_search_cx",
        "Google 搜索引擎 ID (CX)",
        "Google",
        secret=False,
    ),
    ConfigField(
        "YANDEX_GEOSEARCH_API_KEY",
        "yandex_geosearch_api_key",
        "Yandex 地图 API Key",
        "俄语区 / 中亚",
    ),
    ConfigField(
        "OPENCORPORATES_API_TOKEN",
        "opencorporates_api_token",
        "OpenCorporates Token",
        "公司注册数据",
    ),
    ConfigField("OPENAI_API_KEY", "openai_api_key", "OpenAI API Key", "AI"),
    ConfigField(
        "OPENAI_BASE_URL",
        "openai_base_url",
        "OpenAI 兼容 API 基础 URL (DeepSeek 等)",
        "AI",
        secret=False,
    ),
    ConfigField(
        "OPENAI_MODEL",
        "openai_model",
        "AI 提取模型名称",
        "AI",
        secret=False,
    ),
    ConfigField(
        "AI_RESEARCHER_MODEL",
        "ai_researcher_model",
        "AI 研究员模型",
        "AI",
        secret=False,
    ),
    ConfigField(
        "AI_RESEARCHER_ENABLED",
        "ai_researcher_enabled",
        "启用 AI 研究员",
        "AI",
        secret=False,
        kind="bool",
    ),
]
FIELD_MAP: dict[str, ConfigField] = {field.name: field for field in FIELDS}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def _coerce(field: ConfigField, raw: str) -> Any:
    if field.kind == "bool":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return raw


def _current(field: ConfigField) -> Any:
    return getattr(settings, field.attr, "")


def _apply(field: ConfigField, raw: str | None) -> None:
    if raw is None:
        return
    setattr(settings, field.attr, _coerce(field, raw))


def status_list() -> list[dict[str, Any]]:
    """返回所有可配置项及当前状态（密钥打码）。"""
    result: list[dict[str, Any]] = []
    for field in FIELDS:
        value = _current(field)
        string_value = str(value or "")
        if field.kind == "bool":
            configured = bool(value)
            display = "已启用" if value else "未启用"
            public_value: str | None = None
        else:
            configured = bool(string_value.strip())
            display = _mask(string_value) if field.secret else string_value
            public_value = None if field.secret else string_value
        result.append(
            {
                "name": field.name,
                "label": field.label,
                "group": field.group,
                "secret": field.secret,
                "kind": field.kind,
                "configured": configured,
                "value": public_value,
                "masked": _mask(string_value) if (field.secret and string_value) else None,
                "display": display,
            }
        )
    return result


async def apply_overrides(session: AsyncSession) -> int:
    """把数据库中的覆盖值应用到全局 settings（启动/任务开始时调用）。"""
    try:
        rows = (await session.scalars(select(AppSetting))).all()
    except Exception as exc:  # noqa: BLE001 - 表不存在或 DB 未就绪时忽略
        logger.warning("apply_overrides skipped: %s", exc)
        return 0
    count = 0
    for row in rows:
        field = FIELD_MAP.get(row.key)
        if field is None:
            continue
        _apply(field, row.value)
        count += 1
    return count


async def save_updates(
    session: AsyncSession, updates: dict[str, str]
) -> list[dict[str, Any]]:
    """保存前端提交的配置；空值表示清除该覆盖项并回退默认。"""
    unknown = [k for k in updates if k not in FIELD_MAP]
    if unknown:
        raise ValueError(f"未知配置项: {unknown}")

    existing = {row.key: row for row in (await session.scalars(select(AppSetting))).all()}

    for name, value in updates.items():
        field = FIELD_MAP[name]
        if value is None or str(value).strip() == "":
            setattr(settings, field.attr, False if field.kind == "bool" else "")
            if name in existing:
                await session.delete(existing[name])
            continue
        row = existing.get(name)
        if row is None:
            session.add(AppSetting(key=name, value=str(value)))
        else:
            row.value = str(value)
        _apply(field, str(value))

    await session.commit()
    return status_list()
