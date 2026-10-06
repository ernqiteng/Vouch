import enum
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, model_validator

from models import (
    BookingStatus,
    CommunicationNeed,
    DocumentSource,
    MobilityDevice,
    ProviderType,
    VerificationStatus,
)


class CompetencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: ProviderType
    bio: str | None = None
    location: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    competencies: list[str] = Field(
        default_factory=list,
        description="Competency codes, e.g. ['hoist_transfer', 'first_aid']",
    )


class ProviderCompetencyOut(CompetencyOut):
    verified: bool = Field(
        description="An uploaded document backs this competency (latest verification)"
    )


class VerificationSummary(BaseModel):
    """The provider's latest verification, as shown on their profile."""

    verification_id: int
    confidence: float
    verified: bool = Field(description="confidence >= the Verified threshold")
    verified_at: datetime


class ProviderOut(BaseModel):
    id: int
    name: str
    provider_type: ProviderType
    bio: str | None
    location: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime
    competencies: list[ProviderCompetencyOut]
    verification: VerificationSummary | None = Field(
        description="Latest verification, or null if never verified"
    )


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    title: str | None
    source_type: DocumentSource
    filename: str | None
    raw_text: str
    created_at: datetime


class ClaimSource(str, enum.Enum):
    bio = "bio"
    document = "document"


class Claim(BaseModel):
    """One competency the LLM found evidence for, with the text it relied on."""

    competency: str = Field(description="A competency code from the fixed list")
    source: ClaimSource
    snippet: str = Field(description="The supporting text, copied exactly from the source")


class ClaimList(BaseModel):
    """Wrapper so the LLM returns a JSON object rather than a bare list."""

    claims: list[Claim] = Field(default_factory=list)


class CompetencyCheck(BaseModel):
    """Cross-check result for one competency, with the evidence behind it."""

    competency: str
    status: VerificationStatus
    bio_snippet: str | None = None
    document_snippet: str | None = None


class ConfidenceScore(BaseModel):
    """A confidence score together with every input used to calculate it."""

    confidence: float = Field(ge=0, le=1)
    corroborated_count: int
    self_reported_count: int
    documented_only_count: int
    total_claimed_count: int = Field(description="corroborated + self_reported")
    document_quality_weight: float


class VerificationOut(ConfidenceScore):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    document_ids: list[int]
    claims: list[Claim]
    checks: list[CompetencyCheck]
    llm_model: str | None
    llm_latency_ms: int | None
    llm_prompt_tokens: int | None
    llm_output_tokens: int | None
    created_at: datetime


class ClaimsResponse(BaseModel):
    provider_id: int
    claims: list[Claim]
    checks: list[CompetencyCheck]
    extraction_ok: bool = Field(
        description="False if the LLM call failed and no claims could be extracted"
    )
    documents_used: int


MAX_SLOT_HOURS = 12


class SlotIn(BaseModel):
    """A new availability slot. Times must include a time zone, e.g. 2026-10-06T09:00:00+01:00."""

    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def check_times(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if (self.ends_at - self.starts_at).total_seconds() > MAX_SLOT_HOURS * 3600:
            raise ValueError(f"A slot can be at most {MAX_SLOT_HOURS} hours long")
        return self


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    starts_at: datetime
    ends_at: datetime
    booked: bool = False


class BookingIn(BaseModel):
    provider_id: int
    requested_time: AwareDatetime = Field(
        description="Any time inside one of the provider's slots; the whole slot is booked"
    )
    pickup: str = Field(min_length=1, max_length=255, description="Pickup or visit address")
    dropoff: str | None = Field(
        default=None, max_length=255, description="Destination. Required for drivers."
    )
    notes: str | None = Field(default=None, max_length=1000)


class SnapshotProvider(BaseModel):
    id: int
    name: str
    provider_type: ProviderType
    location: str | None


class SnapshotVerification(BaseModel):
    verification_id: int
    confidence: float
    verified: bool
    threshold: float
    verified_at: datetime


class SnapshotCompetency(BaseModel):
    code: str
    label: str
    held: bool = Field(description="The provider lists this competency")
    relevant: bool = Field(description="The booking user needs it (from their profile)")
    verified: bool = Field(description="An uploaded document backed it at booking time")
    status: VerificationStatus | None = Field(description="Cross-check result; null if never checked")
    confidence: float | None = Field(description="The provider's verification confidence then")
    verified_at: datetime | None
    bio_evidence: str | None
    document_evidence: str | None


class VerificationSnapshot(BaseModel):
    """A frozen copy of the provider's verification at the moment of booking."""

    captured_at: datetime
    provider: SnapshotProvider
    verification: SnapshotVerification | None
    competencies: list[SnapshotCompetency]


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int | None
    slot_id: int | None
    starts_at: datetime
    ends_at: datetime
    pickup: str
    dropoff: str | None
    notes: str | None
    verification_snapshot: VerificationSnapshot
    status: BookingStatus
    cancelled_at: datetime | None
    created_at: datetime


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Public view of a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class ProfileIn(BaseModel):
    mobility_device: MobilityDevice | None = None
    communication_needs: list[CommunicationNeed] = Field(default_factory=list)
    required_competencies: list[str] = Field(
        default_factory=list, description="Competency codes, e.g. ['hoist_transfer']"
    )
    location: str | None = Field(
        default=None, max_length=255, description="Home city or postcode"
    )


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime


class MeOut(BaseModel):
    user: UserOut
    profile: ProfileOut | None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    use_profile: bool = Field(
        default=True, description="Apply the logged-in user's saved profile"
    )
    skip_profile_competencies: list[str] = Field(
        default_factory=list,
        description="Profile requirements to leave out of this search only",
    )


class SearchFilter(BaseModel):
    """What the LLM extracts from a search query."""

    provider_type: ProviderType | None = None
    required_competencies: list[str] = Field(default_factory=list)
    location: str | None = None


class RankingBreakdown(BaseModel):
    """Why a result is ranked where it is. Each part is 0-1; see ranking.py."""

    competency_match: float
    verification_confidence: float
    availability: float
    distance: float
    distance_km: float | None = Field(description="Null when either location is unknown")
    score: float = Field(description="0.40, 0.25, 0.20 and 0.15 times the parts above")


class RankedProvider(ProviderOut):
    ranking: RankingBreakdown


class SearchResponse(BaseModel):
    query: str
    query_filter: SearchFilter = Field(
        description="What the LLM extracted from the query. Its competencies filter results."
    )
    filter: SearchFilter = Field(
        description="All requirements considered: the query's plus the profile's"
    )
    filter_parsed: bool = Field(
        description="False if the LLM call failed and an empty filter was used"
    )
    profile_applied: bool = Field(description="A saved profile was used for this search")
    added_from_profile: list[str] = Field(
        description="Competencies from the profile. They rank results; they don't filter them."
    )
    ranked_from: str | None = Field(
        description="Location used for the distance score, or null if unknown"
    )
    results: list[RankedProvider] = Field(description="Sorted by ranking.score, highest first")
