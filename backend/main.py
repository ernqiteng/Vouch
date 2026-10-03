from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Competency, Provider, ProviderCompetency, ProviderType
from schemas import CompetencyOut, ProviderCreate, ProviderOut

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


@app.get("/providers", response_model=list[ProviderOut])
def list_providers(
    competency: list[str] = Query(
        default=[], description="Only providers with ALL of these codes"
    ),
    provider_type: ProviderType | None = None,
    db: Session = Depends(get_db),
):
    query = select(Provider).options(WITH_COMPETENCIES).order_by(Provider.id)
    if provider_type:
        query = query.where(Provider.provider_type == provider_type)
    for code in competency:
        query = query.where(
            Provider.competency_links.any(
                ProviderCompetency.competency.has(Competency.code == code)
            )
        )
    return db.scalars(query).all()


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
