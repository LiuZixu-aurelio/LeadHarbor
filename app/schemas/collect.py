"""采集请求/结果 DTO。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CollectorMeta(BaseModel):
    name: str
    label: str
    requires_key: str | None = None
    default_region: str | None = None
    supported_regions: list[str] = Field(default_factory=list)


class TemplateMeta(BaseModel):
    key: str
    label: str
    keyword: str
    description: str = ""


class CollectConfig(BaseModel):
    sources: list[CollectorMeta]
    target_countries: list[str]
    default_region: str
    templates: list[TemplateMeta] = Field(default_factory=list)


class CollectRequest(BaseModel):
    """触发一次采集。

    query 由各采集器自行解释，例如 Google Places 使用
    {"text_query": "LED lighting distributor", "region": "DE"}。
    """

    source: str = Field(description="采集器标识，如 google_places 或 2gis")
    query: dict[str, Any] = Field(default_factory=dict)
    max_items: int = Field(default=20, ge=1, le=200)
    rounds: int = Field(default=1, ge=1, le=20, description="重复翻页采集轮次")


class CollectResult(BaseModel):
    source: str
    fetched: int
    ingested: int
    duplicates: int
    failed: int


class BatchCollectRequest(BaseModel):
    """按国家批量采集：对每个 region 跑一次同一关键词。"""

    source: str = Field(description="采集器标识")
    text_query: str = Field(min_length=1, description="搜索关键词/模板")
    regions: list[str] = Field(min_length=1, description="目标国家列表，如 ['KZ','UZ']")
    max_items_per_region: int = Field(default=10, ge=1, le=50)
    rounds: int = Field(default=1, ge=1, le=20, description="采集轮次，每轮翻页抓取不同的结果")
    language: str = Field(default="en", description="结果语言 hl")


class BatchRegionResult(BaseModel):
    region: str
    result: CollectResult | None = None
    error: str | None = None


class BatchCollectResult(BaseModel):
    source: str
    text_query: str
    regions_total: int
    total_fetched: int
    total_ingested: int
    total_duplicates: int
    total_failed: int
    items: list[BatchRegionResult]
