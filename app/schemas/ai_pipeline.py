"""AI 串联采集 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIPipelineRequest(BaseModel):
    keyword: str = Field(min_length=2, max_length=512)
    region: str = Field(default="KZ", min_length=2, max_length=2)
    max_pages: int = Field(default=5, ge=1, le=20)
    max_items_per_page: int = Field(default=10, ge=1, le=50)
    language: str = Field(default="en", max_length=16)


class AIPipelineResult(BaseModel):
    keyword: str
    region: str
    pages_found: int
    pages_processed: int
    fetched: int
    ingested: int
    duplicates: int
    failed: int
    urls: list[str] = Field(default_factory=list)
