"""批量采集任务 DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobRegionResult(BaseModel):
    region: str
    fetched: int = 0
    ingested: int = 0
    duplicates: int = 0
    failed: int = 0
    error: str | None = None


class CollectJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    text_query: str
    regions: list[str]
    max_items_per_region: int
    rounds: int = 1
    language: str
    status: str
    total_regions: int
    processed_regions: int
    total_fetched: int
    total_ingested: int
    total_duplicates: int
    total_failed: int
    results: list[JobRegionResult] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime
    updated_at: datetime
