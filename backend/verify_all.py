"""Run verification for providers, e.g. after seeding sample documents.

Run from backend/:
    python verify_all.py         # providers that have documents
    python verify_all.py --all   # every provider (uses one LLM call each)
"""
import sys

from sqlalchemy import select

from database import SessionLocal
from models import Document, Provider
from pipeline import run_verification
from verification import is_verified


def verify_all(everyone: bool = False) -> None:
    with SessionLocal() as db:
        query = select(Provider).order_by(Provider.id)
        if not everyone:
            query = query.where(Provider.documents.any(Document.id.isnot(None)))
        providers = list(db.scalars(query))
        print(f"Verifying {len(providers)} providers...")

        failed = 0
        for provider in providers:
            verification = run_verification(db, provider)
            if verification is None:
                failed += 1
                print(f"  {provider.name}: extraction failed, nothing stored")
                continue
            badge = "Verified" if is_verified(verification.confidence) else "Self-reported"
            print(
                f"  {provider.name}: {verification.confidence:.2f} ({badge}) - "
                f"{verification.corroborated_count}/{verification.total_claimed_count} corroborated"
            )
    if failed:
        print(f"{failed} failed (usually a busy or rate-limited model); run again later.")


if __name__ == "__main__":
    verify_all(everyone="--all" in sys.argv)
