"""Deterministic search personalisation. No LLM calls belong in this file.

Turns a user's saved accessibility profile into extra search requirements and
merges them into the filter the LLM extracted from their query.
"""
from typing import Protocol

from models import CommunicationNeed, MobilityDevice, ProviderType
from schemas import SearchFilter

# Communication needs that map to a provider competency. The others
# (lip reading, written, easy read, extra time) have no competency yet.
COMMUNICATION_COMPETENCIES: dict[CommunicationNeed, str] = {
    CommunicationNeed.bsl: "bsl_fluent",
}

# What a driver needs for each mobility device. Only applied to driver
# searches: a wheelchair doesn't say which skills a carer needs.
DRIVER_MOBILITY_COMPETENCIES: dict[MobilityDevice, str] = {
    MobilityDevice.powered_wheelchair: "wav_driving",  # too heavy to fold; travel in it
    MobilityDevice.mobility_scooter: "wav_driving",
    MobilityDevice.manual_wheelchair: "wheelchair_assistance",  # transfer and fold it
}


# Competencies that only make sense for one provider type. A profile
# requirement for the other type is left out of the search instead of
# excluding everyone (e.g. "hoist transfer" on a search for a driver).
TYPE_SPECIFIC_COMPETENCIES: dict[ProviderType, set[str]] = {
    ProviderType.carer: {"hoist_transfer", "peg_feeding", "medication_administration", "personal_care"},
    ProviderType.driver: {"wav_driving"},
}


def applies_to(code: str, provider_type: ProviderType | None) -> bool:
    """Whether a competency is relevant to a search for this provider type.

    With no type known, only competencies that apply to both types count.
    """
    for owner, codes in TYPE_SPECIFIC_COMPETENCIES.items():
        if code in codes:
            return owner is provider_type
    return True


class ProfileLike(Protocol):
    mobility_device: MobilityDevice | None
    communication_needs: list[str]
    required_competencies: list[str]


def profile_competencies(profile: ProfileLike, provider_type: ProviderType | None) -> list[str]:
    """Competency codes a profile requires for a search, in a stable order."""
    codes = list(profile.required_competencies)
    for need in profile.communication_needs:
        code = COMMUNICATION_COMPETENCIES.get(CommunicationNeed(need))
        if code:
            codes.append(code)
    if provider_type is ProviderType.driver and profile.mobility_device:
        code = DRIVER_MOBILITY_COMPETENCIES.get(profile.mobility_device)
        if code:
            codes.append(code)
    return [code for code in dict.fromkeys(codes) if applies_to(code, provider_type)]


def apply_profile(
    query_filter: SearchFilter, profile: ProfileLike, skip: set[str] = frozenset()
) -> tuple[SearchFilter, list[str]]:
    """Merge a profile into a search filter.

    Returns (merged filter, codes the profile added). The query's own provider
    type and location are kept as they are; the profile only adds required
    competencies, minus any the user chose to skip for this search.
    """
    added = [
        code
        for code in profile_competencies(profile, query_filter.provider_type)
        if code not in query_filter.required_competencies and code not in skip
    ]
    merged = query_filter.model_copy(
        update={"required_competencies": query_filter.required_competencies + added}
    )
    return merged, added
