"""模型导出：确保 Alembic autogenerate 能发现所有表。"""

from app.models.app_setting import AppSetting
from app.models.base import Base
from app.models.collect_job import CollectJob
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import (
    CollectJobStatus,
    CompanyStatus,
    LeadStatus,
    OutreachChannel,
    OutreachStatus,
)
from app.models.lead_raw import LeadRaw
from app.models.outreach import Outreach

__all__ = [
    "AppSetting",
    "Base",
    "CollectJob",
    "CollectJobStatus",
    "Company",
    "Contact",
    "CompanyStatus",
    "LeadRaw",
    "LeadStatus",
    "Outreach",
    "OutreachChannel",
    "OutreachStatus",
]
