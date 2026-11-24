"""官网/主页抓取器：给一批种子 URL，抓公司名、邮箱、电话。

适用：公司官网、社媒主页（Facebook/Instagram/Telegram 公开页等），
只要提供一个 URL 列表即可。抓取严格遵守 robots.txt（can_fetch），
并复用全局限速与超时。

query 结构：
  {"urls": ["example.com", "https://foo.kz/contact"], "max_pages_per_site": 3}
或 {"url": "example.com"}
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urljoin, urlparse

from parsel import Selector

from app.collectors.base import BaseCollector
from app.collectors.http import RateLimiter, acquire_client, can_fetch, fetch_with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s()\-]{7,}\d")
_CONTACT_HINTS = ("contact", "контакт", "aloqa", "bog'lanish", "about", "о нас", "liw", "support")
_BAD_EMAIL_HINTS = ("example.com", "sentry", "wixpress", "@2x", ".png", ".jpg", ".webp")
_SKIP_LINK_EXTS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".css",
    ".js",
    ".zip",
    ".rar",
    ".gz",
    ".mp4",
    ".mp3",
    ".woff",
    ".woff2",
    ".ttf",
    ".xls",
    ".xlsx",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
)


def _normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def _extract_domain(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0] or None


def _dedupe_pick(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        low = item.lower()
        if any(bad in low for bad in _BAD_EMAIL_HINTS):
            continue
        if item not in seen:
            seen.append(item)
    return seen


def parse_website_html(html: str, base_url: str) -> dict[str, Any]:
    """纯函数：从 HTML 中提取公司名、邮箱、电话、联系页候选。"""
    sel = Selector(text=html)

    name = sel.css('meta[property="og:site_name"]::attr(content)').get()
    if not name:
        name = sel.css("title::text").get()
    name = (name or "").strip() or None

    emails = _EMAIL_RE.findall(html)
    for href in sel.css('a[href^="mailto:"]::attr(href)').getall():
        emails.append(href.split("mailto:", 1)[1].split("?", 1)[0])
    emails = _dedupe_pick([e.strip() for e in emails if "@" in e])

    phones: list[str] = []
    for href in sel.css('a[href^="tel:"]::attr(href)').getall():
        phones.append(href.split("tel:", 1)[1].strip())
    # 不管有没有 tel: 链接，都再从整页文本里找电话格式，尽量多收。
    body_text = " ".join(sel.css("body ::text").getall())
    phones.extend(p.strip() for p in _PHONE_RE.findall(body_text))
    deduped_phones: list[str] = []
    for phone in phones:
        normalized = re.sub(r"\s+", " ", phone).strip()
        if normalized and normalized not in deduped_phones:
            deduped_phones.append(normalized)

    contact_links: list[str] = []
    all_links: list[str] = []
    for href in sel.css("a::attr(href)").getall():
        if not href:
            continue
        low = href.lower()
        if low.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(base_url, href)
        all_links.append(absolute)
        if any(h in low for h in _CONTACT_HINTS):
            contact_links.append(absolute)

    return {
        "name": name,
        "emails": emails,
        "phones": deduped_phones,
        "contact_links": contact_links,
        "all_links": all_links,
    }


class WebsiteCollector(BaseCollector):
    source_name = "website"
    label = "官网/主页抓取"
    requires_key = ""  # 无需密钥
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU", "DE", "US", "GB", "AE", "TR"]

    def __init__(self) -> None:
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    def _seed_urls(self, query: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        if single := query.get("url"):
            urls.append(str(single))
        if isinstance(query.get("urls"), list):
            urls.extend(str(u) for u in query["urls"])
        normalized = [_normalize_url(u) for u in urls]
        return [u for u in normalized if u]

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        seeds = self._seed_urls(query)
        if not seeds:
            raise ValueError("website 采集需要 query['urls']（URL 列表）或 query['url']")

        max_pages = int(query.get("max_pages_per_site", 2))
        async with acquire_client() as client:
            for seed in seeds:
                leads = await self._collect_site(client, seed, max_pages)
                for lead in leads:
                    yield lead

    async def _collect_site(self, client, seed: str, max_pages: int) -> list[RawLead]:
        domain = _extract_domain(seed)
        if not domain:
            return []

        pages_to_visit = [seed]
        visited: set[str] = set()
        name: str | None = None
        emails: list[str] = []
        phones: list[str] = []
        first_url = seed

        while pages_to_visit and len(visited) < max_pages:
            url = pages_to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if not can_fetch(url):
                logger.info("robots.txt 禁止抓取: %s", url)
                continue

            await self._limiter.wait()
            try:
                resp = await fetch_with_retry(client, "GET", url)
            except Exception as exc:  # noqa: BLE001 - 单页失败不影响整站
                logger.warning("website fetch failed %s: %s", url, exc)
                continue
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                continue

            parsed = parse_website_html(resp.text, url)
            name = name or parsed["name"]
            emails.extend(parsed["emails"])
            phones.extend(parsed["phones"])
            first_url = first_url or url

            # 关键页面(contact/about/support)优先，其余同域页面在配额内继续抓，
            # 这样藏在普通页面里的邮箱/电话也能被发现。
            remaining = max_pages - len(visited)
            if remaining > 0:
                prioritized = list(parsed.get("contact_links", []))
                others = [link for link in parsed.get("all_links", []) if link not in prioritized]
                for link in prioritized + others:
                    if remaining <= 0:
                        break
                    low = link.lower()
                    if low.split("?")[0].endswith(_SKIP_LINK_EXTS):
                        continue
                    if (
                        _extract_domain(link) == domain
                        and link not in visited
                        and link not in pages_to_visit
                    ):
                        pages_to_visit.append(link)
                        remaining -= 1

        emails = _dedupe_pick(emails)
        primary_email = emails[0] if emails else None
        primary_phone = phones[0] if phones else None

        if not (emails or phones or name):
            return []

        return [
            RawLead(
                source=self.source_name,
                name=name,
                domain=domain,
                website=seed,
                email=primary_email,
                phone=primary_phone,
                raw={
                    "seed": seed,
                    "url": first_url,
                    "emails": emails,
                    "phones": phones,
                },
            )
        ]
