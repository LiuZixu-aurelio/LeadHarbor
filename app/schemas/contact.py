"""联系人相关 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    do_not_contact: bool
    email_verified: bool
