from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models import ProviderType


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


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider_type: ProviderType
    bio: str | None
    location: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime
    competencies: list[CompetencyOut]
