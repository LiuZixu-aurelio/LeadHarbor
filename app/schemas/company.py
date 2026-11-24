"""公司相关 DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CompanyStatus


class CompanyBase(BaseModel):
    name: str
    domain: str | None = None
    website: str | None = None
    country: str | None = None
    industry: str | None = None
    phone: str | None = None
    address: str | None = None
    source: str | None = None


class CompanyCreate(CompanyBase):
    ai_score: int | None = None


class CompanyOut(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ai_score: int | None = None
    status: str
    contact_count: int = 0
    has_email: bool = False
    has_phone: bool = False
    created_at: datetime


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    linkedin_url: str | None = None
    email_verified: bool = False
    do_not_contact: bool = False
    source: str | None = None


class CompanyDetail(CompanyOut):
    contacts: list[ContactOut] = []


class CompanyUpdate(BaseModel):
    """可编辑字段：目前开放生命周期状态。"""

    status: CompanyStatus | None = None
