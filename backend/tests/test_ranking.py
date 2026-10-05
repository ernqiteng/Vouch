import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

import ranking
from models import ProviderType
from places import TOWNS, locate
from ranking import (
    WEIGHTS,
    availability_at_requested_time,
    competency_match,
    distance_km,
    eta_or_distance,
    rank,
    verification_confidence,
)
from schemas import ProviderCompetencyOut, ProviderOut, VerificationSummary

NOW = datetime(2026, 10, 1, tzinfo=UTC)
LEEDS, LONDON = TOWNS["Leeds"], TOWNS["London"]


def provider(id, name, codes=(), confidence=None, at=LEEDS):
    return ProviderOut(
        id=id, name=name, provider_type=ProviderType.carer, bio=None,
        location=None, latitude=at[0] if at else None, longitude=at[1] if at else None,
        created_at=NOW, updated_at=NOW,
        competencies=[ProviderCompetencyOut(code=c, label=c, verified=False) for c in codes],
        verification=None if confidence is None else VerificationSummary(
            verification_id=1, confidence=confidence, verified=confidence >= 0.7, verified_at=NOW),
    )


# --- The formula itself ----------------------------------------------------

def test_weights_match_the_readme():
    assert WEIGHTS == {
        "competency_match": 0.40,
        "verification_confidence": 0.25,
        "availability": 0.20,
        "distance": 0.15,
    }
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_score_is_the_weighted_sum():
    assert ranking.score(1, 1, 1, 1) == pytest.approx(1.0)
    assert ranking.score(0.5, 0.8, 1, 0.2) == pytest.approx(0.5 * 0.4 + 0.8 * 0.25 + 1 * 0.2 + 0.2 * 0.15)


# --- Each term on its own --------------------------------------------------

def test_competency_match_is_the_fraction_of_required_skills_held():
    assert competency_match({"a", "b"}, ["a", "b"]) == 1.0
    assert competency_match({"a"}, ["a", "b"]) == 0.5
    assert competency_match({"x"}, ["a", "b", "c", "d"]) == 0.0


def test_competency_match_is_full_when_nothing_is_required():
    assert competency_match(set(), []) == 1.0


def test_verification_confidence_uses_the_score_or_zero():
    assert verification_confidence(0.75) == 0.75
    assert verification_confidence(None) == 0.0
    assert verification_confidence(1.4) == 1.0


def test_availability_is_stubbed_as_available_until_phase_4():
    assert availability_at_requested_time(provider(1, "A")) == 1.0


def test_distance_km_is_roughly_right():
    assert distance_km(LEEDS, LEEDS) == 0
    assert distance_km(LEEDS, LONDON) == pytest.approx(272, abs=5)


def test_eta_or_distance_scales_down_to_zero_at_the_radius():
    assert eta_or_distance(LEEDS, LEEDS) == 1.0
    assert eta_or_distance(LONDON, LEEDS) == 0.0  # ~270 km is beyond 100 km
    near = TOWNS["Bradford"]  # ~14 km from Leeds
    assert 0.8 < eta_or_distance(near, LEEDS) < 0.9


def test_eta_or_distance_is_neutral_without_a_user_location():
    assert eta_or_distance(LEEDS, None) == eta_or_distance(LONDON, None) == 0.5


def test_eta_or_distance_is_zero_for_a_provider_without_a_location():
    assert eta_or_distance(None, LEEDS) == 0.0


# --- Ranking hand-made providers -------------------------------------------

def test_known_providers_rank_in_the_expected_order():
    """Required: hoist + bsl. User in Leeds. Expected scores:
    perfect: 0.40 + 0.25 + 0.20 + 0.15 = 1.00
    far:     0.40 + 0.25 + 0.20 + 0    = 0.85  (London, beyond radius)
    partial: 0.20 + 0.25 + 0.20 + 0.15 = 0.80  (has 1 of 2 skills)
    unverified: 0.40 + 0 + 0.20 + 0.15 = 0.75
    """
    required = ["hoist_transfer", "bsl_fluent"]
    providers = [
        provider(1, "unverified", required, confidence=None),
        provider(2, "partial", ["hoist_transfer"], confidence=1.0),
        provider(3, "far", required, confidence=1.0, at=LONDON),
        provider(4, "perfect", required, confidence=1.0),
    ]
    results = rank(providers, required, LEEDS)
    assert [r.name for r in results] == ["perfect", "far", "partial", "unverified"]
    assert [r.ranking.score for r in results] == pytest.approx([1.0, 0.85, 0.80, 0.75])


def test_profile_and_location_change_the_ranking():
    """The same candidates, ranked for an anonymous user and for a logged-in user
    who needs BSL and lives in Leeds."""
    providers = [
        provider(1, "London, BSL, verified", ["bsl_fluent"], confidence=1.0, at=LONDON),
        provider(2, "Leeds, no BSL, verified", [], confidence=1.0),
        provider(3, "Leeds, BSL, unverified", ["bsl_fluent"]),
    ]
    anonymous = [r.name for r in rank(providers, [], None)]
    personalised = [r.name for r in rank(providers, ["bsl_fluent"], LEEDS)]
    assert anonymous == ["London, BSL, verified", "Leeds, no BSL, verified", "Leeds, BSL, unverified"]
    assert personalised == ["London, BSL, verified", "Leeds, BSL, unverified", "Leeds, no BSL, verified"]
    assert anonymous != personalised


def test_ties_keep_the_original_order():
    providers = [provider(i, f"p{i}", confidence=0.5) for i in range(5)]
    assert [r.name for r in rank(providers, [], None)] == ["p0", "p1", "p2", "p3", "p4"]


def test_breakdown_reports_each_part_and_the_distance():
    [r] = rank([provider(1, "A", ["a"], confidence=0.5, at=TOWNS["Bradford"])], ["a", "b"], LEEDS)
    assert r.ranking.competency_match == 0.5
    assert r.ranking.verification_confidence == 0.5
    assert r.ranking.availability == 1.0
    assert r.ranking.distance_km == pytest.approx(13.7, abs=1)


# --- Supporting pieces ------------------------------------------------------

def test_locate_finds_towns_in_free_text():
    assert locate("Leeds") == LEEDS
    assert locate("  leeds ") == LEEDS
    assert locate("central Leeds, LS1") == LEEDS
    assert locate("LS1 4AP") is None
    assert locate(None) is None


def test_ranking_module_never_imports_the_llm():
    source = Path(__file__).parent.parent / "ranking.py"
    imported = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any(n == "llm" or n.startswith("google") for n in imported), imported
