from datetime import UTC, datetime
from types import SimpleNamespace

from models import ProviderType, VerificationStatus
from schemas import SnapshotProvider
from snapshots import build_snapshot

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
VERIFIED_AT = datetime(2026, 10, 1, tzinfo=UTC)
PROVIDER = SnapshotProvider(id=7, name="Grace Mensah", provider_type=ProviderType.carer, location="London")
LABELS = {"hoist_transfer": "Hoist transfer", "bsl_fluent": "Fluent in BSL",
          "first_aid": "First aid", "dementia_care": "Dementia care"}
HELD = [("hoist_transfer", "Hoist transfer"), ("bsl_fluent", "Fluent in BSL"), ("first_aid", "First aid")]


def verification(confidence=0.6667):
    return SimpleNamespace(id=42, confidence=confidence, created_at=VERIFIED_AT, checks=[
        {"competency": "hoist_transfer", "status": "corroborated",
         "bio_snippet": "trained in hoist transfers", "document_snippet": "including hoist transfers"},
        {"competency": "bsl_fluent", "status": "corroborated",
         "bio_snippet": "Fluent BSL signer", "document_snippet": "Level 6 BSL"},
        {"competency": "first_aid", "status": "self_reported",
         "bio_snippet": "first aid trained", "document_snippet": None},
    ])


def by_code(snapshot):
    return {c.code: c for c in snapshot.competencies}


def test_snapshot_copies_provider_and_overall_verification():
    s = build_snapshot(PROVIDER, HELD, verification(), set(), LABELS, NOW)
    assert s.captured_at == NOW
    assert s.provider.name == "Grace Mensah"
    assert s.verification.verification_id == 42
    assert s.verification.confidence == 0.6667
    assert s.verification.verified is False  # below 0.7
    assert s.verification.threshold == 0.7
    assert s.verification.verified_at == VERIFIED_AT


def test_each_competency_has_status_verified_flag_confidence_and_evidence():
    rows = by_code(build_snapshot(PROVIDER, HELD, verification(), set(), LABELS, NOW))
    hoist = rows["hoist_transfer"]
    assert (hoist.status, hoist.verified, hoist.confidence) == (VerificationStatus.corroborated, True, 0.6667)
    assert hoist.bio_evidence == "trained in hoist transfers"
    assert hoist.document_evidence == "including hoist transfers"
    assert hoist.verified_at == VERIFIED_AT
    first_aid = rows["first_aid"]
    assert (first_aid.status, first_aid.verified) == (VerificationStatus.self_reported, False)


def test_relevant_competencies_are_flagged_and_listed_first():
    s = build_snapshot(PROVIDER, HELD, verification(), {"first_aid"}, LABELS, NOW)
    assert s.competencies[0].code == "first_aid"
    assert s.competencies[0].relevant is True
    assert all(not c.relevant for c in s.competencies[1:])


def test_needed_but_missing_competency_is_recorded_as_not_held():
    rows = by_code(build_snapshot(PROVIDER, HELD, verification(), {"dementia_care"}, LABELS, NOW))
    missing = rows["dementia_care"]
    assert (missing.held, missing.relevant, missing.verified, missing.status) == (False, True, False, None)
    assert missing.label == "Dementia care"


def test_never_verified_provider_has_no_verification_and_nothing_verified():
    s = build_snapshot(PROVIDER, HELD, None, set(), LABELS, NOW)
    assert s.verification is None
    assert all(not c.verified and c.status is None and c.confidence is None for c in s.competencies)


def test_snapshot_is_plain_data_that_survives_json():
    s = build_snapshot(PROVIDER, HELD, verification(), {"hoist_transfer"}, LABELS, NOW)
    stored = s.model_dump(mode="json")
    assert stored["competencies"][0]["status"] == "corroborated"
    assert type(s).model_validate(stored) == s
