from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from documents import MAX_UPLOAD_BYTES, DocumentError, clean_text, extract_text
from llm import extract_claims, parse_search_query
from models import (
    Competency,
    Document,
    DocumentSource,
    Provider,
    ProviderCompetency,
    ProviderType,
    Verification,
)
from schemas import (
    Claim,
    ClaimsResponse,
    CompetencyOut,
    DocumentOut,
    ProviderCreate,
    ProviderOut,
    SearchRequest,
    SearchResponse,
    VerificationOut,
)
from verification import cross_check, score

app = FastAPI()

# Load each provider's competencies in one extra query instead of one per provider.
WITH_COMPETENCIES = selectinload(Provider.competency_links).selectinload(
    ProviderCompetency.competency
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/competencies", response_model=list[CompetencyOut])
def list_competencies(db: Session = Depends(get_db)):
    return db.scalars(select(Competency).order_by(Competency.code)).all()


@app.post("/providers", response_model=ProviderOut, status_code=201)
def create_provider(body: ProviderCreate, db: Session = Depends(get_db)):
    codes = set(body.competencies)
    competencies = db.scalars(
        select(Competency).where(Competency.code.in_(codes))
    ).all()
    unknown = codes - {c.code for c in competencies}
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown competency codes: {sorted(unknown)}",
        )

    provider = Provider(**body.model_dump(exclude={"competencies"}))
    provider.competency_links = [
        ProviderCompetency(competency=c) for c in competencies
    ]
    db.add(provider)
    db.commit()
    return get_provider(provider.id, db)


def find_providers(
    db: Session,
    provider_type: ProviderType | None = None,
    competencies: list[str] = (),
    location: str | None = None,
) -> list[Provider]:
    """Providers matching every filter given. Used by both listing and search."""
    query = select(Provider).options(WITH_COMPETENCIES).order_by(Provider.id)
    if provider_type:
        query = query.where(Provider.provider_type == provider_type)
    for code in competencies:
        query = query.where(
            Provider.competency_links.any(
                ProviderCompetency.competency.has(Competency.code == code)
            )
        )
    if location:
        query = query.where(Provider.location.icontains(location.strip()))
    return list(db.scalars(query).all())


@app.get("/providers", response_model=list[ProviderOut])
def list_providers(
    competency: list[str] = Query(
        default=[], description="Only providers with ALL of these codes"
    ),
    provider_type: ProviderType | None = None,
    location: str | None = Query(default=None, description="City or postcode"),
    db: Session = Depends(get_db),
):
    return find_providers(db, provider_type, competency, location)


@app.post("/search", response_model=SearchResponse)
def search(body: SearchRequest, db: Session = Depends(get_db)):
    competencies = {c.code: c.label for c in db.scalars(select(Competency))}
    search_filter, parsed = parse_search_query(body.query, competencies)
    results = find_providers(
        db,
        search_filter.provider_type,
        search_filter.required_competencies,
        search_filter.location,
    )
    return SearchResponse(
        query=body.query, filter=search_filter, filter_parsed=parsed, results=results
    )


@app.get("/providers/{provider_id}", response_model=ProviderOut)
def get_provider(provider_id: int, db: Session = Depends(get_db)):
    provider = db.scalar(
        select(Provider)
        .options(WITH_COMPETENCIES)
        .where(Provider.id == provider_id)
    )
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@app.post(
    "/providers/{provider_id}/documents", response_model=DocumentOut, status_code=201
)
def upload_document(
    provider_id: int,
    file: UploadFile | None = File(default=None, description=".txt or text-based .pdf"),
    text: str | None = Form(default=None, description="Pasted document text"),
    title: str | None = Form(default=None, max_length=255),
    db: Session = Depends(get_db),
):
    """Attach a document (e.g. a certificate) to a provider. Send a file OR text."""
    if db.get(Provider, provider_id) is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if (file is None) == (not text):
        raise HTTPException(status_code=400, detail="Send exactly one of: a file, or pasted text.")

    try:
        if file is not None:
            data = file.file.read(MAX_UPLOAD_BYTES + 1)
            raw_text, source = extract_text(data, file.filename or "")
        else:
            raw_text, source = clean_text(text), DocumentSource.pasted
    except DocumentError as e:
        raise HTTPException(status_code=422, detail=str(e))

    filename = file.filename if file is not None else None
    document = Document(
        provider_id=provider_id,
        title=title or filename,
        source_type=source,
        filename=filename,
        raw_text=raw_text,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@app.post("/providers/{provider_id}/extract-claims", response_model=ClaimsResponse)
def extract_provider_claims(provider_id: int, db: Session = Depends(get_db)):
    """Extract claims from a provider's bio and documents, then cross-check them.

    Stores nothing. Useful for seeing what verification would conclude.
    """
    provider = _provider_or_404(provider_id, db)
    claims, ok = _extract(provider, db)
    return ClaimsResponse(
        provider_id=provider_id,
        claims=claims,
        checks=cross_check(claims),
        extraction_ok=ok,
        documents_used=len(provider.documents),
    )


@app.post(
    "/providers/{provider_id}/verify", response_model=VerificationOut, status_code=201
)
def verify_provider(provider_id: int, db: Session = Depends(get_db)):
    """Run the full pipeline and store the result as a new verification.

    LLM extracts claims -> plain code cross-checks them -> plain code scores them.
    If extraction fails nothing is stored, so a good score is never replaced by
    an empty one.
    """
    provider = _provider_or_404(provider_id, db)
    claims, ok = _extract(provider, db)
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="Claim extraction is unavailable right now. Please try again shortly.",
        )

    checks = cross_check(claims)
    result = score(checks, [d.source_type for d in provider.documents])
    verification = Verification(
        provider_id=provider_id,
        **result.model_dump(),
        document_ids=[d.id for d in provider.documents],
        claims=[c.model_dump(mode="json") for c in claims],
        checks=[c.model_dump(mode="json") for c in checks],
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    return verification


@app.get("/providers/{provider_id}/verifications", response_model=list[VerificationOut])
def list_verifications(provider_id: int, db: Session = Depends(get_db)):
    """A provider's verification history, oldest first. The last one is current."""
    return _provider_or_404(provider_id, db).verifications


def _provider_or_404(provider_id: int, db: Session) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


def _extract(provider: Provider, db: Session) -> tuple[list[Claim], bool]:
    competencies = {c.code: c.label for c in db.scalars(select(Competency))}
    document_text = "\n\n".join(d.raw_text for d in provider.documents)
    return extract_claims(provider.bio or "", document_text, competencies)


@app.get("/providers/{provider_id}/documents", response_model=list[DocumentOut])
def list_documents(provider_id: int, db: Session = Depends(get_db)):
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider.documents
