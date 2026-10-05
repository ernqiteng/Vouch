from types import SimpleNamespace

from matching import apply_profile, profile_competencies
from models import MobilityDevice, ProviderType
from schemas import SearchFilter

CARER, DRIVER = ProviderType.carer, ProviderType.driver


def profile(mobility=None, comms=(), required=()):
    return SimpleNamespace(
        mobility_device=mobility,
        communication_needs=list(comms),
        required_competencies=list(required),
    )


def test_required_competencies_are_added():
    merged, added = apply_profile(SearchFilter(provider_type=CARER), profile(required=["hoist_transfer"]))
    assert merged.required_competencies == ["hoist_transfer"]
    assert added == ["hoist_transfer"]


def test_query_requirements_come_first_and_arent_duplicated():
    query = SearchFilter(provider_type=CARER, required_competencies=["first_aid", "hoist_transfer"])
    merged, added = apply_profile(query, profile(required=["hoist_transfer", "dementia_care"]))
    assert merged.required_competencies == ["first_aid", "hoist_transfer", "dementia_care"]
    assert added == ["dementia_care"]


def test_bsl_communication_need_requires_bsl_fluency():
    assert profile_competencies(profile(comms=["bsl"]), CARER) == ["bsl_fluent"]


def test_communication_needs_without_a_competency_add_nothing():
    assert profile_competencies(profile(comms=["written", "easy_read", "extra_time"]), CARER) == []


def test_mobility_device_only_applies_to_driver_searches():
    powered = profile(mobility=MobilityDevice.powered_wheelchair)
    assert profile_competencies(powered, DRIVER) == ["wav_driving"]
    assert profile_competencies(powered, CARER) == []
    assert profile_competencies(powered, None) == []


def test_each_mobility_device_maps_to_the_right_driver_skill():
    expected = {
        MobilityDevice.powered_wheelchair: ["wav_driving"],
        MobilityDevice.mobility_scooter: ["wav_driving"],
        MobilityDevice.manual_wheelchair: ["wheelchair_assistance"],
        MobilityDevice.walking_aid: [],
        MobilityDevice.none: [],
    }
    for device, codes in expected.items():
        assert profile_competencies(profile(mobility=device), DRIVER) == codes, device


def test_skipped_competencies_are_left_out_for_this_search():
    p = profile(comms=["bsl"], required=["hoist_transfer"])
    merged, added = apply_profile(SearchFilter(provider_type=CARER), p, skip={"hoist_transfer"})
    assert merged.required_competencies == ["bsl_fluent"]
    assert added == ["bsl_fluent"]


def test_query_type_and_location_are_kept():
    query = SearchFilter(provider_type=DRIVER, location="Leeds")
    merged, _ = apply_profile(query, profile(mobility=MobilityDevice.manual_wheelchair))
    assert merged.provider_type is DRIVER
    assert merged.location == "Leeds"
    assert merged.required_competencies == ["wheelchair_assistance"]


def test_original_filter_is_not_modified():
    query = SearchFilter(provider_type=CARER, required_competencies=["first_aid"])
    apply_profile(query, profile(required=["hoist_transfer"]))
    assert query.required_competencies == ["first_aid"]


def test_carer_only_skills_are_left_out_of_driver_searches():
    p = profile(required=["hoist_transfer", "personal_care", "bsl_fluent"])
    assert profile_competencies(p, DRIVER) == ["bsl_fluent"]
    assert profile_competencies(p, CARER) == ["hoist_transfer", "personal_care", "bsl_fluent"]


def test_driver_only_skills_are_left_out_of_carer_searches():
    p = profile(required=["wav_driving", "first_aid"])
    assert profile_competencies(p, CARER) == ["first_aid"]
    assert profile_competencies(p, DRIVER) == ["wav_driving", "first_aid"]


def test_unknown_provider_type_only_applies_shared_skills():
    p = profile(required=["hoist_transfer", "wav_driving", "dementia_care"], comms=["bsl"])
    assert profile_competencies(p, None) == ["dementia_care", "bsl_fluent"]


def test_empty_profile_changes_nothing():
    query = SearchFilter(provider_type=CARER, required_competencies=["first_aid"])
    merged, added = apply_profile(query, profile())
    assert merged == query
    assert added == []
