import ast
import random
from pathlib import Path

import pytest

from models import DocumentSource, VerificationStatus
from schemas import Claim, ClaimSource
from verification import cross_check, score

BIO, DOC = ClaimSource.bio, ClaimSource.document
PASTED, PDF = DocumentSource.pasted, DocumentSource.pdf


def claim(code, source, snippet="evidence"):
    return Claim(competency=code, source=source, snippet=snippet)


def statuses(checks):
    return {c.competency: c.status for c in checks}


def test_in_bio_and_document_is_corroborated():
    checks = cross_check([
        claim("hoist_transfer", BIO, "trained in hoist transfers"),
        claim("hoist_transfer", DOC, "Moving and Handling, including hoist transfers"),
    ])
    assert len(checks) == 1
    check = checks[0]
    assert check.status is VerificationStatus.corroborated
    assert check.bio_snippet == "trained in hoist transfers"
    assert check.document_snippet == "Moving and Handling, including hoist transfers"


def test_in_bio_only_is_self_reported():
    [check] = cross_check([claim("bsl_fluent", BIO, "Fluent BSL signer")])
    assert check.status is VerificationStatus.self_reported
    assert check.bio_snippet == "Fluent BSL signer"
    assert check.document_snippet is None


def test_in_document_only_is_documented_only():
    [check] = cross_check([claim("first_aid", DOC, "Emergency First Aid at Work")])
    assert check.status is VerificationStatus.documented_only
    assert check.bio_snippet is None
    assert check.document_snippet == "Emergency First Aid at Work"


def test_mixed_profile_labels_each_competency_separately():
    checks = cross_check([
        claim("hoist_transfer", BIO),
        claim("hoist_transfer", DOC),
        claim("personal_care", BIO),
        claim("first_aid", DOC),
    ])
    assert statuses(checks) == {
        "first_aid": VerificationStatus.documented_only,
        "hoist_transfer": VerificationStatus.corroborated,
        "personal_care": VerificationStatus.self_reported,
    }


def test_no_claims_gives_no_checks():
    assert cross_check([]) == []


def test_duplicate_claims_keep_the_first_snippet():
    [check] = cross_check([
        claim("first_aid", BIO, "first aid trained"),
        claim("first_aid", BIO, "holds a first aid certificate"),
    ])
    assert check.status is VerificationStatus.self_reported
    assert check.bio_snippet == "first aid trained"


def test_output_is_sorted_and_independent_of_input_order():
    claims = [
        claim("wav_driving", DOC),
        claim("bsl_fluent", BIO),
        claim("hoist_transfer", BIO),
        claim("hoist_transfer", DOC),
        claim("autism_awareness", BIO),
    ]
    expected = cross_check(claims)
    assert [c.competency for c in expected] == sorted(c.competency for c in expected)
    for seed in range(20):
        shuffled = claims[:]
        random.Random(seed).shuffle(shuffled)
        assert statuses(cross_check(shuffled)) == statuses(expected)


def checks_for(corroborated=0, self_reported=0, documented_only=0):
    claims = []
    for i in range(corroborated):
        claims += [claim(f"c{i}", BIO), claim(f"c{i}", DOC)]
    claims += [claim(f"s{i}", BIO) for i in range(self_reported)]
    claims += [claim(f"d{i}", DOC) for i in range(documented_only)]
    return cross_check(claims)


def test_score_is_corroborated_over_claimed():
    result = score(checks_for(corroborated=2, self_reported=1), [PDF])
    assert result.confidence == pytest.approx(0.6667)
    assert result.corroborated_count == 2
    assert result.self_reported_count == 1
    assert result.total_claimed_count == 3
    assert result.document_quality_weight == 1.0


def test_everything_corroborated_scores_one():
    assert score(checks_for(corroborated=3), [PASTED]).confidence == 1.0


def test_documented_only_competencies_dont_change_the_score():
    without = score(checks_for(corroborated=1, self_reported=1), [PDF])
    with_extra = score(checks_for(corroborated=1, self_reported=1, documented_only=4), [PDF])
    assert with_extra.confidence == without.confidence == 0.5
    assert with_extra.documented_only_count == 4


def test_no_documents_scores_zero():
    result = score(checks_for(self_reported=3), [])
    assert result.confidence == 0.0
    assert result.document_quality_weight == 0.0


def test_nothing_claimed_scores_zero_without_dividing_by_zero():
    result = score(checks_for(documented_only=2), [PDF])
    assert result.confidence == 0.0
    assert result.total_claimed_count == 0


def test_document_quality_weight_scales_the_score(monkeypatch):
    import verification

    monkeypatch.setitem(verification.DOCUMENT_QUALITY_WEIGHTS, PASTED, 0.8)
    result = score(checks_for(corroborated=1, self_reported=1), [PASTED])
    assert result.document_quality_weight == 0.8
    assert result.confidence == pytest.approx(0.4)
    # With several documents, the most trustworthy one sets the weight.
    assert score(checks_for(corroborated=1), [PASTED, PDF]).document_quality_weight == 1.0


def test_verification_module_never_imports_the_llm():
    """The cross-check must stay deterministic: no LLM code in verification.py."""
    source = Path(__file__).parent.parent / "verification.py"
    imported = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any(name == "llm" or name.startswith("google") for name in imported), imported
