import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
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
