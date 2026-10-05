"""Build the verification snapshot stored on a booking. No LLM calls here.

The snapshot copies everything a user might later need to see about what was
confirmed when they booked, so it stays true even after the provider's
verification changes.
"""
from datetime import datetime
from typing import Protocol

from schemas import (
    CompetencyCheck,
    SnapshotCompetency,
    SnapshotProvider,
    SnapshotVerification,
    VerificationSnapshot,
)
from verification import VERIFIED_THRESHOLD, document_backed_competencies, is_verified


class VerificationLike(Protocol):
    id: int
    confidence: float
    created_at: datetime
    checks: list[dict]


def build_snapshot(
    provider: SnapshotProvider,
    competencies: list[tuple[str, str]],
    latest: VerificationLike | None,
    relevant: set[str],
    labels: dict[str, str],
    captured_at: datetime,
) -> VerificationSnapshot:
    """
    - provider: who was booked.
    - competencies: (code, label) pairs the provider lists.
    - latest: their latest verification, or None if never verified.
    - relevant: codes the booking user needs. Ones the provider doesn't hold
      are included too (held=False), so the gap is on record.
    - labels: code -> label for every competency, for the relevant-but-not-held ones.
    """
    checks = {c["competency"]: CompetencyCheck(**c) for c in latest.checks} if latest else {}
    backed = document_backed_competencies(list(checks.values()))
    held = dict(competencies)

    codes = list(held) + sorted(code for code in relevant if code not in held)
    rows = []
    for code in codes:
        check = checks.get(code)
        rows.append(SnapshotCompetency(
            code=code,
            label=held.get(code) or labels.get(code, code),
            held=code in held,
            relevant=code in relevant,
            verified=code in backed,
            status=check.status if check else None,
            confidence=latest.confidence if latest else None,
            verified_at=latest.created_at if latest else None,
            bio_evidence=check.bio_snippet if check else None,
            document_evidence=check.document_snippet if check else None,
        ))
    # Relevant competencies first, so the snapshot leads with what matters for this trip.
    rows.sort(key=lambda r: not r.relevant)

    return VerificationSnapshot(
        captured_at=captured_at,
        provider=provider,
        verification=SnapshotVerification(
            verification_id=latest.id,
            confidence=latest.confidence,
            verified=is_verified(latest.confidence),
            threshold=VERIFIED_THRESHOLD,
            verified_at=latest.created_at,
        )
        if latest
        else None,
        competencies=rows,
    )
