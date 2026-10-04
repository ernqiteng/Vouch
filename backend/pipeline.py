"""The verification pipeline, shared by the API and scripts.

LLM extracts claims (llm.py) -> plain code cross-checks and scores them
(verification.py) -> the result is stored as a new Verification row.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm import CallStats, extract_claims
from models import Competency, Provider, Verification
from schemas import Claim
from verification import cross_check, score


def extract(db: Session, provider: Provider) -> tuple[list[Claim], bool, CallStats]:
    competencies = {c.code: c.label for c in db.scalars(select(Competency))}
    document_text = "\n\n".join(d.raw_text for d in provider.documents)
    return extract_claims(provider.bio or "", document_text, competencies)


def run_verification(db: Session, provider: Provider) -> Verification | None:
    """Verify a provider and store the result. Returns None if extraction failed,
    in which case nothing is stored, so a good score is never replaced by an
    empty one."""
    claims, ok, stats = extract(db, provider)
    if not ok:
        return None

    checks = cross_check(claims)
    result = score(checks, [d.source_type for d in provider.documents])
    verification = Verification(
        provider_id=provider.id,
        **result.model_dump(),
        document_ids=[d.id for d in provider.documents],
        claims=[c.model_dump(mode="json") for c in claims],
        checks=[c.model_dump(mode="json") for c in checks],
        llm_model=stats.model,
        llm_latency_ms=stats.latency_ms,
        llm_prompt_tokens=stats.prompt_tokens,
        llm_output_tokens=stats.output_tokens,
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    return verification
