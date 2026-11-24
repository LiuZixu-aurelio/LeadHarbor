"""线索相关 DTO。RawLead 是所有采集器的统一输出规范。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawLead(BaseModel):
    """采集器的标准化输出（未清洗）。`raw` 保存原始数据供追溯。"""

    source: str
    name: str | None = None
    domain: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    address: str | None = None
    industry: str | None = None
    website: str | None = None
    title: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class LeadRawOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    status: str
    error: str | None = None
    fetched_at: datetime
