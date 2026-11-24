"""去重：domain 为硬键，公司名做 fuzzy 软合并。"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.schemas.lead import RawLead

DEFAULT_NAME_THRESHOLD = 90


class DedupeSet:
    """批内去重索引。可用于一次采集的流式去重。

    用法：
        seen = DedupeSet()
        if seen.add(lead):   # True 表示新线索
            ...
    """

    def __init__(self, name_threshold: int = DEFAULT_NAME_THRESHOLD) -> None:
        self._domains: set[str] = set()
        self._names: list[str] = []
        self._threshold = name_threshold

    def add(self, lead: RawLead) -> bool:
        """返回 True 表示未重复（新线索），False 表示重复。"""
        domain = normalize_key_domain(lead.domain)
        if domain:
            if domain in self._domains:
                return False
            self._domains.add(domain)
            # 域名命中直接视为新，但仍登记名字供后续软匹配
            if lead.name:
                self._names.append(lead.name)
            return True

        # 无域名则退化为公司名 fuzzy 判重
        name = (lead.name or "").strip().lower()
        if not name:
            # 既无域名又无名字，无法判重，视为新
            return True
        if self._is_duplicate_name(name):
            return False
        self._names.append(name)
        return True

    def _is_duplicate_name(self, name: str) -> bool:
        return any(
            fuzz.token_sort_ratio(name, existing) >= self._threshold
            for existing in self._names
        )


def normalize_key_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    d = domain.strip().lower()
    if d.startswith("www."):
        d = d[4:]
    return d or None
