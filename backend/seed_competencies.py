"""Fill the competencies table. Safe to run more than once.

Run from backend/:  python seed_competencies.py
"""
from sqlalchemy.dialects.postgresql import insert

from database import SessionLocal
from models import Competency

COMPETENCIES = [
    ("hoist_transfer", "Hoist transfer"),
    ("manual_handling", "Manual handling"),
    ("wheelchair_assistance", "Wheelchair assistance"),
    ("wav_driving", "Wheelchair-accessible vehicle driving"),
    ("personal_care", "Personal care"),
    ("medication_administration", "Medication administration"),
    ("peg_feeding", "PEG feeding"),
    ("dementia_care", "Dementia care"),
    ("autism_awareness", "Autism awareness"),
    ("bsl_fluent", "Fluent in BSL"),
    ("first_aid", "First aid"),
]


def seed_competencies() -> None:
    with SessionLocal() as db:
        db.execute(
            insert(Competency)
            .values([{"code": code, "label": label} for code, label in COMPETENCIES])
            .on_conflict_do_nothing(index_elements=["code"])
        )
        db.commit()


if __name__ == "__main__":
    seed_competencies()
    print(f"Competencies table has the {len(COMPETENCIES)} standard codes.")
