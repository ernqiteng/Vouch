"""Deterministic ranking of search results. No LLM calls belong in this file.

    score = competency_match                 * 0.40
          + verification_confidence          * 0.25
          + availability_at_requested_time   * 0.20
          + eta_or_distance                  * 0.15

Each term is its own function returning 0-1, so each can be tested and
explained on its own. Weights match the README.
"""
from math import asin, cos, radians, sin, sqrt

from schemas import ProviderOut, RankedProvider, RankingBreakdown

WEIGHTS = {
    "competency_match": 0.40,
    "verification_confidence": 0.25,
    "availability": 0.20,
    "distance": 0.15,
}

# Providers this far away or further get a distance score of 0.
MAX_SEARCH_RADIUS_KM = 100.0
# Distance score for everyone when we don't know where the user is, so
# distance doesn't change the order.
NEUTRAL_DISTANCE_SCORE = 0.5

Coords = tuple[float, float]


def competency_match(provider_codes: set[str], required: list[str]) -> float:
    """Fraction of the required competencies the provider has. 1.0 if none required."""
    wanted = set(required)
    if not wanted:
        return 1.0
    return len(wanted & provider_codes) / len(wanted)


def verification_confidence(confidence: float | None) -> float:
    """The provider's latest verification confidence (Phase 2). 0 if never verified."""
    if confidence is None:
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def availability_at_requested_time(provider: ProviderOut) -> float:
    """1 if the provider is free at the requested time, 0 if not.

    Stub until Phase 4 adds availability: everyone counts as available.
    """
    return 1.0


def distance_km(a: Coords, b: Coords) -> float:
    """Straight-line (great-circle) distance between two points."""
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def eta_or_distance(provider_coords: Coords | None, user_coords: Coords | None) -> float:
    """1 - distance / MAX_SEARCH_RADIUS_KM, clamped to 0-1.

    Neutral (0.5 for everyone) when the user's location is unknown; 0 for a
    provider with no location when the user's is known.
    """
    if user_coords is None:
        return NEUTRAL_DISTANCE_SCORE
    if provider_coords is None:
        return 0.0
    return max(0.0, 1.0 - distance_km(provider_coords, user_coords) / MAX_SEARCH_RADIUS_KM)


def score(competency: float, verification: float, availability: float, distance: float) -> float:
    return (
        competency * WEIGHTS["competency_match"]
        + verification * WEIGHTS["verification_confidence"]
        + availability * WEIGHTS["availability"]
        + distance * WEIGHTS["distance"]
    )


def breakdown(
    provider: ProviderOut, required: list[str], user_coords: Coords | None
) -> RankingBreakdown:
    provider_coords = (
        (provider.latitude, provider.longitude)
        if provider.latitude is not None and provider.longitude is not None
        else None
    )
    parts = {
        "competency_match": competency_match({c.code for c in provider.competencies}, required),
        "verification_confidence": verification_confidence(
            provider.verification.confidence if provider.verification else None
        ),
        "availability": availability_at_requested_time(provider),
        "distance": eta_or_distance(provider_coords, user_coords),
    }
    return RankingBreakdown(
        **{k: round(v, 4) for k, v in parts.items()},
        distance_km=round(distance_km(provider_coords, user_coords), 1)
        if provider_coords and user_coords
        else None,
        score=round(score(*parts.values()), 4),
    )


def rank(
    providers: list[ProviderOut], required: list[str], user_coords: Coords | None
) -> list[RankedProvider]:
    """Score every provider and sort by score, highest first.

    Ties keep the database order (by id), so results are stable.
    """
    ranked = [
        RankedProvider(**p.model_dump(), ranking=breakdown(p, required, user_coords))
        for p in providers
    ]
    return sorted(ranked, key=lambda p: p.ranking.score, reverse=True)
