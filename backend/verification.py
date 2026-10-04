"""Deterministic verification logic. No LLM calls belong in this file.

The LLM only extracts claims (llm.py). Everything here is plain, testable
Python, so a provider's verification status can always be explained by
pointing at the evidence that produced it.
"""
from models import VerificationStatus
from schemas import Claim, ClaimSource, CompetencyCheck


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
