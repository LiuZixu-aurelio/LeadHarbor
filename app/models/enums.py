"""业务枚举。3.11+ StrEnum，天然可序列化为字符串值。"""

from __future__ import annotations

from enum import StrEnum


class LeadStatus(StrEnum):
    """原始线索处理状态。"""

    PENDING = "pending"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class CompanyStatus(StrEnum):
    """客户生命周期状态。"""

    LEAD = "lead"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    REPLIED = "replied"
    MEETING = "meeting"
    WON = "won"
    LOST = "lost"


class OutreachChannel(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"


class OutreachStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"


class CollectJobStatus(StrEnum):
    """批量采集任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
