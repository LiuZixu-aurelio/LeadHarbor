"""AI 网页提取采集器：用大模型把网页纯文本抽成结构化线索。

适合「目录页/黄页/公司列表/关于我们」等含多家公司或联系方式的页面：
给定 URL，抓取 HTML → 转纯文本 → LLM 抽取 {name, website, email, phone,
address, industry} → 入库。需要 OPENAI_API_KEY，按 token 计费。

注意：AI 结果需人工核实；它只抽取文本中真实出现的信息。
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from openai import AsyncOpenAI
from parsel import Selector

from app.collectors.base import BaseCollector
from app.collectors.http import RateLimiter, acquire_client, can_fetch, fetch_with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_MAX_TEXT_CHARS = 12000

_SYSTEM_PROMPT = (
    "你是信息抽取助手。用户会给一个网页的纯文本，请抽取其中出现的所有公司/商家线索。"
    "只输出 JSON 数组，不要额外说明。每个对象字段："
    "name（公司名）、website（官网，没有留空）、email（邮箱）、phone（电话）、"
    "address（地址）、industry（行业）。"
    "只抽取文本中真实存在的信息，不要编造；缺失字段用空字符串。"
)


def html_to_text(html: str, limit: int = _MAX_TEXT_CHARS) -> str:
    """用 parsel 提取 body 文本并压缩空白，截断到 limit 字符。"""
    try:
        sel = Selector(text=html)
        chunks = sel.xpath("//body//text()").getall()
    except Exception:  # noqa: BLE001
        chunks = re.sub(r"<[^>]+>", " ", html).split("\n")
    text = " ".join(part.strip() for part in chunks if part and part.strip())
    return text[:limit]


def _is_probable_url(value: str) -> bool:
    """判断是否为可抓取的网址/域名，过滤 'wholesaler' 之类关键词。"""
    text = value.strip()
    if "://" in text:
        return True
    # 裸域名需含点且无空格，如 acme.kz / example.com
    return "." in text and " " not in text and not text.startswith((".", "-"))


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    except ValueError:
        return None
    return host.removeprefix("www.").split(":", 1)[0] or None


def parse_ai_extractor_response(text: str, source: str = "ai_extractor") -> list[RawLead]:
    """纯函数：把 LLM 返回的 JSON 文本解析为 RawLead（便于单测）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            return []
        try:
            data = json.loads(text[start : end + 1])
        except Exception:  # noqa: BLE001
            return []
    if not isinstance(data, list):
        return []
    leads: list[RawLead] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or None
        if not name:
            continue
        website = str(item.get("website") or "").strip() or None
        leads.append(
            RawLead(
                source=source,
                name=name,
                domain=_domain(website),
                website=website,
                email=str(item.get("email") or "").strip() or None,
                phone=str(item.get("phone") or "").strip() or None,
                address=str(item.get("address") or "").strip() or None,
                industry=str(item.get("industry") or "").strip() or None,
                raw={"ai_extracted": True},
            )
        )
    return leads


class AIExtractorCollector(BaseCollector):
    source_name = "ai_extractor"
    label = "AI 网页提取（OpenAI）"
    requires_key = "OPENAI_API_KEY"
    default_region = None
    supported_regions: list[str] = []

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.openai_api_key
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法使用 ai_extractor 采集器")
        self._base_url = settings.openai_base_url or None
        self._model = model or settings.openai_model
        self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def _extract(self, text: str, url: str, max_items: int) -> list[RawLead]:
        user_prompt = (
            f"来源网址：{url}\n最多抽取 {max_items} 条公司线索。\n\n网页文本：\n{text}"
        )
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = completion.choices[0].message.content or ""
        return parse_ai_extractor_response(content)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        raw_urls = query.get("urls")
        if not raw_urls:
            single = query.get("url") or query.get("text_query")
            # 关键词模式先通过搜索提供方发现网页，再抓取页面提取线索。
            if single and not _is_probable_url(str(single)):
                from app.collectors.registry import get_collector

                search_provider = str(query.get("search_provider") or "google_search")
                if search_provider not in {"google_search", "bing", "tavily"}:
                    raise ValueError("不支持的网页搜索提供方")
                search = get_collector("google_search")
                discovered: list[str] = []
                async for item in search.collect(
                    {
                        "text_query": str(single),
                        "region": query.get("region") or settings.default_region,
                        "language": query.get("language", "en"),
                        "max_items": min(10, int(query.get("max_pages", 5))),
                    }
                ):
                    if item.website:
                        discovered.append(item.website)
                raw_urls = discovered
                if not raw_urls:
                    raise RuntimeError(
                        "关键词没有搜索到网页；请配置 GOOGLE_SEARCH_API_KEY + GOOGLE_SEARCH_CX，"
                        "或直接输入 https:// 开头的网址"
                    )
            else:
                raw_urls = re.split(r"[\s,]+", str(single)) if single else []
        candidates = [str(u).strip() for u in raw_urls if str(u).strip()]
        if not candidates:
            raise ValueError("ai_extractor 采集需要 query['urls']（网页地址列表）")
        urls = [u for u in candidates if _is_probable_url(u)]
        invalid = [u for u in candidates if not _is_probable_url(u)]
        if invalid:
            logger.warning("ai_extractor 忽略非网址输入: %s", invalid)
        if not urls:
            raise ValueError(
                f"输入不是有效网址（需含域名的链接，如 https://example.com），收到: {invalid[:3]}"
            )

        max_items = min(100, int(query.get("max_items", 20)))
        per_page = max(1, max_items)
        errors: list[str] = []
        valid_fetched = 0

        for url in urls:
            full_url = url if "://" in url else f"https://{url}"
            if not can_fetch(full_url):
                logger.info("robots disallow, skip %s", full_url)
                continue
            try:
                await self._limiter.wait()
                async with acquire_client() as client:
                    resp = await fetch_with_retry(
                        client, "GET", full_url, retries=1, timeout=20.0
                    )
            except Exception as exc:  # noqa: BLE001 - 单站网络异常不影响其它网址
                reason = f"{full_url}: {type(exc).__name__} {exc}"[:200]
                logger.warning("ai_extractor fetch failed %s", reason)
                errors.append(reason)
                continue
            valid_fetched += 1
            if resp.status_code != 200:
                logger.warning("ai_extractor fetch %s -> HTTP %s", full_url, resp.status_code)
                errors.append(f"{full_url}: HTTP {resp.status_code}")
                continue
            text = html_to_text(resp.text)
            if len(text) < 50:
                continue
            try:
                leads = await self._extract(text, full_url, per_page)
            except Exception as exc:  # noqa: BLE001
                logger.error("ai_extractor LLM failed for %s: %s", full_url, exc)
                raise RuntimeError(
                    f"AI 提取失败（模型调用出错，请检查模型/密钥/base_url）: {exc}"
                ) from exc
            for lead in leads[:per_page]:
                yield lead

        if valid_fetched == 0 and errors:
            raise RuntimeError(
                "所有网址都无法访问（可能是网址错误或网络不通）: " + "；".join(errors)
            )
