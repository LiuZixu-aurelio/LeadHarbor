"""采集器注册表：按 source_name 查找采集器工厂。新增渠道在此登记。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.collectors.base import BaseCollector
from app.collectors.sources.ai_extractor import AIExtractorCollector
from app.collectors.sources.ai_researcher import AIResearcherCollector
from app.collectors.sources.google_places import GooglePlacesCollector
from app.collectors.sources.google_search import GoogleSearchCollector
from app.collectors.sources.opencorporates import OpenCorporatesCollector
from app.collectors.sources.openstreetmap import OpenStreetMapCollector
from app.collectors.sources.twogis import TwoGisCollector
from app.collectors.sources.website import WebsiteCollector
from app.collectors.sources.wikidata import WikidataCollector
from app.collectors.sources.yandex_maps import YandexMapsCollector

CollectorFactory = Callable[[], BaseCollector]

_REGISTRY: dict[str, CollectorFactory] = {
    TwoGisCollector.source_name: TwoGisCollector,
    GooglePlacesCollector.source_name: GooglePlacesCollector,
    GoogleSearchCollector.source_name: GoogleSearchCollector,
    OpenStreetMapCollector.source_name: OpenStreetMapCollector,
    OpenCorporatesCollector.source_name: OpenCorporatesCollector,
    AIResearcherCollector.source_name: AIResearcherCollector,
    AIExtractorCollector.source_name: AIExtractorCollector,
    WebsiteCollector.source_name: WebsiteCollector,
    WikidataCollector.source_name: WikidataCollector,
    YandexMapsCollector.source_name: YandexMapsCollector,
}


def register(source_name: str, factory: CollectorFactory) -> None:
    _REGISTRY[source_name] = factory


def get_collector(source_name: str) -> BaseCollector:
    try:
        factory = _REGISTRY[source_name]
    except KeyError as exc:
        raise KeyError(
            f"未知采集器: {source_name!r}，可用: {sorted(_REGISTRY)}"
        ) from exc
    return factory()


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


def describe_sources() -> list[dict[str, Any]]:
    """返回各采集器的元数据，供前端渲染数据源下拉框与区域选择。"""
    described: list[dict[str, Any]] = []
    for name in available_sources():
        cls = _REGISTRY[name]
        described.append(
            {
                "name": name,
                "label": getattr(cls, "label", name) or name,
                "requires_key": getattr(cls, "requires_key", "") or None,
                "default_region": getattr(cls, "default_region", None),
                "supported_regions": list(getattr(cls, "supported_regions", []) or []),
            }
        )
    return described
