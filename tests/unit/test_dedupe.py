"""dedupe 测试。"""

from app.pipeline.dedupe import DedupeSet
from app.schemas.lead import RawLead


def _lead(domain: str | None = None, name: str | None = None) -> RawLead:
    return RawLead(source="test", domain=domain, name=name)


def test_dedupe_by_domain():
    seen = DedupeSet()
    assert seen.add(_lead(domain="acme.com")) is True
    assert seen.add(_lead(domain="acme.com")) is False


def test_dedupe_domain_case_insensitive_and_www():
    seen = DedupeSet()
    assert seen.add(_lead(domain="ACME.com")) is True
    assert seen.add(_lead(domain="www.acme.com")) is False


def test_dedupe_by_fuzzy_name_when_no_domain():
    seen = DedupeSet(name_threshold=90)
    assert seen.add(_lead(name="Acme Lighting GmbH")) is True
    assert seen.add(_lead(name="Acme Lighting GMBH")) is False


def test_dedupe_no_domain_no_name_considered_new():
    seen = DedupeSet()
    assert seen.add(_lead()) is True
    assert seen.add(_lead()) is True
