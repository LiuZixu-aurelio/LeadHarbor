"""客户匹配打分：默认启发式（离线可用），AI/向量打分为预留扩展点。

返回 0-100 分。维度：行业关键词命中、国家匹配、信息完整度。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.lead import RawLead


@dataclass
class ScoreProfile:
    """目标客户画像。"""

    keywords: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)


def score_lead(lead: RawLead, profile: ScoreProfile) -> int:
    """启发式打分（纯函数，便于单测）。

    - 行业/名称命中关键词：每个 +15，上限 45
    - 国家命中：+25
    - 有邮箱：+20；有域名/网站：+10
    """
    score = 0
    blob = " ".join(
        filter(None, [lead.name, lead.industry, lead.title])
    ).lower()

    if profile.keywords:
        hits = sum(1 for kw in profile.keywords if kw.lower() in blob)
        score += min(hits * 15, 45)

    if profile.countries and lead.country:
        if lead.country.upper() in {c.upper() for c in profile.countries}:
            score += 25

    if lead.email:
        score += 20
    if lead.domain or lead.website:
        score += 10

    return max(0, min(100, score))


class HeuristicScorer:
    def __init__(self, profile: ScoreProfile) -> None:
        self._profile = profile

    def score(self, lead: RawLead) -> int:
        return score_lead(lead, self._profile)
