"""AI 研究员采集器：用 OpenAI Token 研究/推断公司信息（按 token 计费）。

适合「已有关键词、缺乏结构化公司名单」的场景：给定行业关键词 + 国家，
让模型列出可能的公司名称、官网、行业、简介，作为采集种子。

结果由 LLM 生成，存在幻觉，标注 source=ai_researcher 并建议人工核实后再
触达。建议配合 `website` 采集器对返回的官网做一次抓取验证。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.collectors.base import BaseCollector
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "你是一位 B2B 线索研究助手。用户给出一个行业关键词和目标国家，"
    "请列出该国可能存在的真实公司/经销商，作为线索采集的种子。"
    "要求：1) 只返回 JSON 数组，不要额外说明。"
    "2) 每个对象包含 name、website（官网域名，如有可留空）、industry、"
    "description（一句中文简介）、confidence（0-100 置信度）。"
    "3) 名称尽量真实可验证，不要编造不存在的网址，不确定的留空。"
    "4) 每次最多返回 10 条。5) description 用中文。"
)


def parse_ai_researcher_response(text: str, source: str = "ai_researcher") -> list[RawLead]:
    """纯函数：把 LLM 返回的 JSON 文本解析为 RawLead（便于单测）。"""
    import json as _json

    leads: list[RawLead] = []
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # 去掉可能的 json 标记
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = _json.loads(text)
    except Exception:
        logger.warning("ai_researcher 返回非 JSON，尝试提取首个数组: %s", text[:200])
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return leads
        try:
            data = _json.loads(text[start : end + 1])
        except Exception:
            return leads
    if not isinstance(data, list):
        return leads
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        website = item.get("website") or None
        from urllib.parse import urlparse

        domain = None
        if website:
            try:
                host = urlparse(website if "://" in website else f"https://{website}").netloc.lower()
                domain = host.removeprefix("www.").split(":", 1)[0] or None
            except ValueError:
                domain = None
        leads.append(
            RawLead(
                source=source,
                name=str(name).strip(),
                domain=domain,
                website=website,
                industry=item.get("industry"),
                country=None,
                raw={
                    "description": item.get("description"),
                    "confidence": item.get("confidence"),
                    "ai_generated": True,
                },
            )
        )
    return leads


class AIResearcherCollector(BaseCollector):
    source_name = "ai_researcher"
    label = "AI 研究员（按 token 计费）"
    requires_key = "OPENAI_API_KEY"
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU", "US", "GB", "DE", "CN"]

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        if not settings.ai_researcher_enabled:
            raise RuntimeError(
                "AI 研究员未启用，请在 .env 中设置 AI_RESEARCHER_ENABLED=true"
            )
        self._api_key = api_key or settings.openai_api_key
        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY 未配置，无法使用 ai_researcher 采集器"
            )
        self._base_url = settings.openai_base_url or None
        self._model = model or (
            settings.openai_model
            if settings.openai_base_url
            else settings.ai_researcher_model
        )
        self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        text_query = str(query.get("text_query") or query.get("q") or "").strip()
        if not text_query:
            raise ValueError("ai_researcher 采集需要 query['text_query']")
        region = str(query.get("region") or settings.default_region).upper()
        max_items = min(20, int(query.get("max_items", 10)))

        user_prompt = (
            f"目标国家：{region}\n"
            f"行业关键词：{text_query}\n"
            f"请列出该国可能存在的真实公司/经销商，最多 {max_items} 条，返回 JSON 数组。"
        )

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ai_researcher OpenAI 请求失败: %s", exc)
            raise RuntimeError(f"AI 研究员请求失败: {exc}") from exc

        text = completion.choices[0].message.content or ""
        for lead in parse_ai_researcher_response(text):
            yield lead
