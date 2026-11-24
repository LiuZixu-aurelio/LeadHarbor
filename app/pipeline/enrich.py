"""线索增强：当前实现「官网抓邮箱」；AI 决策人推断为预留扩展点。

注意：网络调用必须传入/复用 httpx 客户端，便于测试 mock，且遵守 robots.txt。
"""

from __future__ import annotations

import re
from typing import Protocol

import httpx

from app.collectors.http import can_fetch, fetch_with_retry
from app.core.logging import get_logger
from app.pipeline.normalize import (
    is_valid_email,
    normalize_domain,
    normalize_email,
    normalize_phone,
)
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_MAILTO = re.compile(r"mailto:([^\"'>\s]+)", re.IGNORECASE)
_TEL = re.compile(r"tel:([+\d][\d\s\-()]{5,})", re.IGNORECASE)


def extract_phone(html: str) -> str | None:
    """从 HTML 的 tel: 链接里提取第一个有效电话。"""
    for match in _TEL.findall(html):
        phone = normalize_phone(match)
        if phone and len(phone) >= 7:
            return phone
    return None


class Enricher(Protocol):
    async def enrich(self, lead: RawLead) -> RawLead: ...


def extract_emails(html: str) -> list[str]:
    """从 HTML 文本中提取邮箱，去重保序，过滤无效值。"""
    found: list[str] = []
    for match in _MAILTO.findall(html) + _EMAIL_IN_TEXT.findall(html):
        email = normalize_email(match.split("?")[0])
        if email and is_valid_email(email) and email not in found:
            found.append(email)
    return found


class WebsiteEmailEnricher:
    """访问公司官网，从页面里提取邮箱补全到 lead.email。"""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def enrich(self, lead: RawLead) -> RawLead:
        if lead.email:
            return lead
        website = lead.website
        if not website:
            domain = normalize_domain(lead.domain)
            if not domain:
                return lead
            website = f"https://{domain}"

        if not can_fetch(website):
            logger.info("robots disallow, skip enrich: %s", website)
            return lead

        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=15.0, follow_redirects=True
        )
        try:
            resp = await fetch_with_retry(client, "GET", website)
            if resp.status_code == 200:
                html = resp.text
                if not lead.email:
                    emails = extract_emails(html)
                    if emails:
                        lead.email = emails[0]
                if not lead.phone:
                    lead.phone = extract_phone(html)
        except Exception as exc:  # noqa: BLE001 - 增强失败不阻断主流程
            logger.warning("enrich failed for %s: %s", website, exc)
        finally:
            if own_client:
                await client.aclose()
        return lead
