"""Deterministic verification logic. No LLM calls belong in this file.

The LLM only extracts claims (llm.py). Everything here is plain, testable
Python, so a provider's verification status can always be explained by
pointing at the evidence that produced it.
"""
from collections import Counter

from models import DocumentSource, VerificationStatus
from schemas import Claim, ClaimSource, CompetencyCheck, ConfidenceScore

# How much to trust each kind of document. All 1.0 for now: every current
# source gives us the document's exact text. A future OCR source (scanned
# certificates) would get less, because OCR can misread words.
DOCUMENT_QUALITY_WEIGHTS: dict[DocumentSource, float] = {
    DocumentSource.pasted: 1.0,
    DocumentSource.text_file: 1.0,
    DocumentSource.pdf: 1.0,
}

# A provider is shown as "Verified" at or above this confidence.
VERIFIED_THRESHOLD = 0.7

# Statuses where an uploaded document shows the competency.
DOCUMENT_BACKED = {VerificationStatus.corroborated, VerificationStatus.documented_only}


def is_verified(confidence: float) -> bool:
    return confidence >= VERIFIED_THRESHOLD


def document_backed_competencies(checks: list[CompetencyCheck]) -> set[str]:
    """Competency codes that a document backs up, shown as verified on their own."""
    return {check.competency for check in checks if check.status in DOCUMENT_BACKED}


def cross_check(claims: list[Claim]) -> list[CompetencyCheck]:
    """Label each competency by comparing bio claims with document claims.

    - in the bio and a document -> corroborated
    - in the bio only           -> self_reported
    - in a document only        -> documented_only

    Results are sorted by competency code, so the same claims always give the
    same output whatever order they arrive in.
    """
    bio: dict[str, str] = {}
    document: dict[str, str] = {}
    for claim in claims:
        evidence = bio if claim.source is ClaimSource.bio else document
        evidence.setdefault(claim.competency, claim.snippet)

    checks = []
    for code in sorted(bio.keys() | document.keys()):
        if code in bio and code in document:
            status = VerificationStatus.corroborated
        elif code in bio:
            status = VerificationStatus.self_reported
        else:
            status = VerificationStatus.documented_only
        checks.append(CompetencyCheck(
            competency=code,
            status=status,
            bio_snippet=bio.get(code),
            document_snippet=document.get(code),
        ))
    return checks


def document_quality_weight(sources: list[DocumentSource]) -> float:
    """The weight of the most trustworthy document, or 0.0 with no documents."""
    return max((DOCUMENT_QUALITY_WEIGHTS[s] for s in sources), default=0.0)


def score(checks: list[CompetencyCheck], sources: list[DocumentSource]) -> ConfidenceScore:
    """confidence = corroborated / claimed * document_quality_weight

    - claimed = corroborated + self_reported: what the provider says in their
      bio. Documented-only competencies weren't claimed, so they don't count.
    - With nothing claimed there is nothing to verify, so confidence is 0.
    """
    counts = Counter(check.status for check in checks)
    corroborated = counts[VerificationStatus.corroborated]
    self_reported = counts[VerificationStatus.self_reported]
    claimed = corroborated + self_reported
    weight = document_quality_weight(sources)
    confidence = round(corroborated / claimed * weight, 4) if claimed else 0.0
    return ConfidenceScore(
        confidence=confidence,
        corroborated_count=corroborated,
        self_reported_count=self_reported,
        documented_only_count=counts[VerificationStatus.documented_only],
        total_claimed_count=claimed,
        document_quality_weight=weight,
    )
