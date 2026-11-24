"""字段标准化：域名 / 邮箱 / 电话 / 国家。纯函数，便于单测。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.schemas.lead import RawLead

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# 常见国家/地区名 -> ISO2（可后续补全或替换为 pycountry）
_COUNTRY_MAP = {
    "germany": "DE",
    "deutschland": "DE",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "netherlands": "NL",
    "belgium": "BE",
    "poland": "PL",
    "russia": "RU",
    "japan": "JP",
    "china": "CN",
    "india": "IN",
    "brazil": "BR",
    "mexico": "MX",
    "canada": "CA",
    "australia": "AU",
    "turkey": "TR",
    "uae": "AE",
    "united arab emirates": "AE",
}


def normalize_domain(value: str | None) -> str | None:
    """接受域名或完整 URL，返回裸域名（小写、去 www）。"""
    if not value:
        return None
    text = value.strip().lower()
    if "://" in text:
        host = urlparse(text).netloc
    else:
        host = text.split("/")[0]
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    email = value.strip().lower()
    return email if _EMAIL_RE.match(email) else None


def is_valid_email(value: str | None) -> bool:
    return bool(value and _EMAIL_RE.match(value.strip()))


def normalize_phone(value: str | None) -> str | None:
    """粗略 E.164 化：去空格/括号/横线，00 前缀转 +。"""
    if not value:
        return None
    digits = re.sub(r"[^\d+]", "", value)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        rest = re.sub(r"\D", "", digits[1:])
        return f"+{rest}" if rest else None
    rest = re.sub(r"\D", "", digits)
    return rest or None


def normalize_country(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 2 and text.isalpha():
        return text.upper()
    return _COUNTRY_MAP.get(text.lower())


def normalize_lead(lead: RawLead) -> RawLead:
    """返回标准化后的新 RawLead，不改原对象。"""
    return RawLead(
        source=lead.source,
        name=(lead.name or "").strip() or None,
        domain=normalize_domain(lead.domain or lead.website),
        email=normalize_email(lead.email),
        phone=normalize_phone(lead.phone),
        country=normalize_country(lead.country),
        address=(lead.address or "").strip() or None,
        industry=(lead.industry or "").strip() or None,
        website=(lead.website or "").strip() or None,
        title=(lead.title or "").strip() or None,
        raw=lead.raw,
    )
