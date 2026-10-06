import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProviderType(str, enum.Enum):
    carer = "carer"
    driver = "driver"


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type"), index=True
    )
    bio: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    competency_links: Mapped[list["ProviderCompetency"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Document.created_at",
    )
    verifications: Mapped[list["Verification"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Verification.id",
    )
    availability_slots: Mapped[list["AvailabilitySlot"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AvailabilitySlot.starts_at",
    )

    @property
    def competencies(self) -> list["Competency"]:
        return [link.competency for link in self.competency_links]


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(255))

    provider_links: Mapped[list["ProviderCompetency"]] = relationship(
        back_populates="competency"
    )


# A full class rather than a plain link table, so Phase 2 can add
# per-competency columns (status, confidence) here.
class ProviderCompetency(Base):
    __tablename__ = "provider_competencies"

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True
    )
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("competencies.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )

    provider: Mapped[Provider] = relationship(back_populates="competency_links")
    competency: Mapped[Competency] = relationship(back_populates="provider_links")


class VerificationStatus(str, enum.Enum):
    """Result of cross-checking a competency's bio claim against documents."""

    corroborated = "corroborated"  # claimed in the bio AND shown in a document
    self_reported = "self_reported"  # claimed in the bio only
    documented_only = "documented_only"  # in a document, but not claimed in the bio


class DocumentSource(str, enum.Enum):
    """How the document's text was obtained. Phase 2.4 can weight these differently."""

    pasted = "pasted"
    text_file = "text_file"
    pdf = "pdf"


class Document(Base):
    """Evidence a provider uploads, e.g. a certificate. Only the text is stored."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[DocumentSource] = mapped_column(
        Enum(DocumentSource, name="document_source")
    )
    filename: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    provider: Mapped[Provider] = relationship(back_populates="documents")


class Verification(Base):
    """One verification run: the confidence score and every input behind it.

    Rows are never updated, so a provider's history is kept; the newest row is
    their current status.
    """

    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float)
    corroborated_count: Mapped[int]
    self_reported_count: Mapped[int]
    documented_only_count: Mapped[int]
    total_claimed_count: Mapped[int]
    document_quality_weight: Mapped[float] = mapped_column(Float)
    document_ids: Mapped[list[int]] = mapped_column(JSONB)
    claims: Mapped[list[dict]] = mapped_column(JSONB)
    checks: Mapped[list[dict]] = mapped_column(JSONB)
    # LLM cost of the extraction step, for latency and cost-per-verification
    # numbers. Null on rows created before these were recorded.
    llm_model: Mapped[str | None] = mapped_column(String(64))
    llm_latency_ms: Mapped[int | None]
    llm_prompt_tokens: Mapped[int | None]
    llm_output_tokens: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    provider: Mapped[Provider] = relationship(back_populates="verifications")


class User(Base):
    """Someone searching for a carer or driver. Passwords are stored hashed only."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)  # stored lowercased
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class MobilityDevice(str, enum.Enum):
    none = "none"
    manual_wheelchair = "manual_wheelchair"
    powered_wheelchair = "powered_wheelchair"
    mobility_scooter = "mobility_scooter"
    walking_aid = "walking_aid"
    other = "other"


class CommunicationNeed(str, enum.Enum):
    bsl = "bsl"  # British Sign Language
    lip_reading = "lip_reading"
    written = "written"  # prefers written messages to calls
    easy_read = "easy_read"
    extra_time = "extra_time"  # needs time to process or respond


class UserProfile(Base):
    """A user's saved accessibility needs, applied to their searches (Phase 3.2)."""

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    mobility_device: Mapped[MobilityDevice | None] = mapped_column(
        Enum(MobilityDevice, name="mobility_device")
    )
    communication_needs: Mapped[list[str]] = mapped_column(JSONB, default=list)
    required_competencies: Mapped[list[str]] = mapped_column(JSONB, default=list)
    location: Mapped[str | None] = mapped_column(String(255))  # home city or postcode
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class AvailabilitySlot(Base):
    """A specific time window a provider can be booked for, e.g. Tue 09:00-12:00.

    Specific slots rather than recurring weekly hours: simpler to book against
    and enough for the demo. A slot is booked as a whole (Phase 4.2).
    """

    __tablename__ = "availability_slots"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_availability_slots_ends_after_start"),
        UniqueConstraint("provider_id", "starts_at", name="uq_availability_slots_provider_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    provider: Mapped[Provider] = relationship(back_populates="availability_slots")
    booking: Mapped["Booking | None"] = relationship(back_populates="slot")


class BookingStatus(str, enum.Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"


class Booking(Base):
    """A user's booking of one whole availability slot.

    verification_snapshot is a copy of the provider's verification at booking
    time, not a reference to it, so the booking keeps proof of what was
    confirmed even if the provider's verification changes later. For the same
    reason the booking survives the provider or slot being deleted.
    """

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), index=True
    )
    # Unique: at most one booking per slot. The database's last line of
    # defence against double-booking.
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("availability_slots.id", ondelete="SET NULL"), unique=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pickup: Mapped[str] = mapped_column(String(255))
    dropoff: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    verification_snapshot: Mapped[dict] = mapped_column(JSONB)
    # Cancelling keeps the booking (and its snapshot) on record, but clears
    # slot_id so the slot can be booked again.
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.confirmed,
        server_default=BookingStatus.confirmed.value,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    slot: Mapped[AvailabilitySlot | None] = relationship(back_populates="booking")
