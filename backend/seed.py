"""Fill the database with fake providers and sample certificates for development.

Run from backend/:
    python seed.py           # adds providers if the table is empty, plus any
                             # missing sample certificates
    python seed.py --reset   # deletes ALL providers first, then adds them
"""
import sys

from sqlalchemy import delete, func, select

from database import SessionLocal
from documents import clean_text
from models import (
    Competency,
    Document,
    DocumentSource,
    Provider,
    ProviderCompetency,
    ProviderType,
)
from seed_competencies import seed_competencies

CITIES = {
    "Leeds": (53.8008, -1.5491),
    "Manchester": (53.4808, -2.2426),
    "London": (51.5072, -0.1276),
    "Birmingham": (52.4862, -1.8904),
    "Bristol": (51.4545, -2.5879),
    "Sheffield": (53.3811, -1.4701),
    "Liverpool": (53.4084, -2.9916),
    "Newcastle": (54.9783, -1.6178),
    "Nottingham": (52.9548, -1.1581),
    "Edinburgh": (55.9533, -3.1883),
    "Glasgow": (55.8642, -4.2518),
    "Cardiff": (51.4816, -3.1791),
}

CARER, DRIVER = ProviderType.carer, ProviderType.driver

# (name, type, city, competency codes, bio)
PROVIDERS = [
    ("Amara Okafor", CARER, "Leeds",
     ["hoist_transfer", "manual_handling", "personal_care", "first_aid"],
     "Home carer for six years, mostly supporting wheelchair users. Trained in hoist transfers and safe manual handling, with an up-to-date first aid certificate."),
    ("Daniel Hughes", CARER, "Leeds",
     ["dementia_care", "personal_care", "medication_administration"],
     "Specialise in supporting older adults living with dementia. Comfortable managing medication schedules and helping with washing and dressing."),
    ("Priya Sharma", CARER, "Manchester",
     ["bsl_fluent", "autism_awareness", "personal_care"],
     "Fluent in British Sign Language, with a Deaf parent. Experienced supporting autistic adults and young people with daily routines."),
    ("Tom Fletcher", CARER, "Manchester",
     ["hoist_transfer", "peg_feeding", "medication_administration", "manual_handling"],
     "Former healthcare assistant on a neuro rehab ward. Confident with hoists, PEG feeding and administering medication."),
    ("Grace Mensah", CARER, "London",
     ["hoist_transfer", "bsl_fluent", "first_aid", "personal_care"],
     "Carer for eight years. Fluent BSL signer and trained in hoist transfers. Happy to support with personal care and outings."),
    ("Liam O'Connor", CARER, "London",
     ["dementia_care", "first_aid"],
     "Companion carer for people with early-stage dementia. Patient, calm, and first aid trained."),
    ("Sofia Rossi", CARER, "Birmingham",
     ["personal_care", "medication_administration", "manual_handling"],
     "Live-in and visiting carer. Help with personal care, medication prompts and moving around the home safely."),
    ("Hannah Clarke", CARER, "Birmingham",
     ["autism_awareness", "first_aid"],
     "Support worker with a background in special educational needs. Autism awareness trained and first aid certified."),
    ("Kwame Asante", CARER, "Bristol",
     ["hoist_transfer", "manual_handling", "wheelchair_assistance"],
     "Physically strong and well trained in transfers, including ceiling and mobile hoists. Experienced pushing and transferring from wheelchairs."),
    ("Emily Watson", CARER, "Sheffield",
     ["bsl_fluent", "dementia_care", "personal_care"],
     "BSL Level 6 qualified. Support Deaf older adults, including those living with dementia."),
    ("Mohammed Iqbal", CARER, "Sheffield",
     ["peg_feeding", "medication_administration", "first_aid"],
     "Complex care carer. Trained in PEG feeding and medication administration, and hold a first aid at work certificate."),
    ("Chloe Bennett", CARER, "Liverpool",
     ["personal_care", "autism_awareness", "manual_handling", "hoist_transfer"],
     "Support autistic adults and people with physical disabilities. Trained in manual handling and hoist use."),
    ("Fiona MacLeod", CARER, "Edinburgh",
     ["dementia_care", "medication_administration", "personal_care"],
     "Twelve years in dementia care, both in care homes and in people's own homes."),
    ("Rhys Evans", CARER, "Cardiff",
     ["hoist_transfer", "personal_care", "first_aid"],
     "Welsh and English speaker. Hoist trained and experienced with personal care for wheelchair users."),
    ("Aisha Bello", CARER, "Newcastle",
     [],
     "Newly registered carer, just starting out and keen to help."),
    ("James Carter", DRIVER, "Leeds",
     ["wav_driving", "wheelchair_assistance", "first_aid"],
     "Drive a wheelchair-accessible van with a rear ramp. Help passengers in and out and secure wheelchairs properly."),
    ("Oliver Grant", DRIVER, "Manchester",
     ["wav_driving", "manual_handling"],
     "Accessible transport driver for a local community scheme for five years."),
    ("Nadia Hussain", DRIVER, "London",
     ["wav_driving", "wheelchair_assistance", "bsl_fluent"],
     "Wheelchair-accessible taxi driver and fluent BSL signer, so Deaf passengers can talk to me directly."),
    ("Ben Turner", DRIVER, "London",
     ["first_aid"],
     "Standard saloon car, so not suitable for passengers who need to stay in their wheelchair. First aid trained."),
    ("Ewan Stewart", DRIVER, "Glasgow",
     ["wav_driving", "wheelchair_assistance", "autism_awareness"],
     "Drive an adapted minibus. Used to supporting autistic passengers who prefer a calm, predictable journey."),
    ("Laura Price", DRIVER, "Bristol",
     ["wav_driving", "first_aid", "manual_handling"],
     "Accessible vehicle with a side lift. Trained in manual handling and first aid."),
    ("Samuel Adeyemi", DRIVER, "Birmingham",
     ["wheelchair_assistance", "dementia_care"],
     "Hospital appointment driver. Help passengers with folding wheelchairs and am experienced with passengers living with dementia."),
    ("Megan Lloyd", DRIVER, "Cardiff",
     ["wav_driving", "wheelchair_assistance"],
     "Wheelchair-accessible vehicle with a ramp. Regular school and day-centre runs."),
    ("Ravi Patel", DRIVER, "Nottingham",
     ["wav_driving", "first_aid", "bsl_fluent"],
     "Accessible taxi driver. Fluent BSL signer and first aid trained."),
]


# Sample certificates for some providers: (provider name, title, text).
# Some cover everything the bio claims and some only part of it, so the demo
# shows both fully verified and partly verified providers once verify_all.py
# has been run.
DOCUMENTS = [
    ("Amara Okafor", "Moving and handling + first aid",
     "CERTIFICATE OF COMPLETION\nSafe Moving and Handling of People, including hoist transfers\n"
     "Awarded to Amara Okafor, February 2025\n\n"
     "FIRST AID AT WORK\nThis certifies that Amara Okafor has completed First Aid at Work training. "
     "Valid until 2027."),
    ("Grace Mensah", "Hoist and BSL certificates",
     "Certificate: Moving and Handling of People, including hoist transfers. Grace Mensah, 2024.\n"
     "Signature Level 6 NVQ Certificate in British Sign Language. Awarded to Grace Mensah."),
    ("Tom Fletcher", "Clinical skills record",
     "Clinical skills sign-off for Tom Fletcher, Healthcare Assistant.\n"
     "Competent: hoist transfers (mobile and ceiling hoists).\n"
     "Competent: enteral feeding via PEG tube.\n"
     "Competent: safe administration of medication."),
    ("Priya Sharma", "BSL qualification",
     "Signature Level 3 Certificate in British Sign Language Studies. Awarded to Priya Sharma, 2023."),
    ("Kwame Asante", "Hoist training",
     "Training record: Kwame Asante completed hoist transfer training (ceiling and mobile hoists), 2025."),
    ("Fiona MacLeod", "Dementia and medication training",
     "Certificate in Dementia Care (SCQF Level 7), awarded to Fiona MacLeod.\n"
     "Safe Administration of Medication course completed, 2024."),
    ("James Carter", "Accessible driver training",
     "MiDAS Accessible Driver Training: wheelchair-accessible vehicle driving, ramp operation and "
     "wheelchair securing. Awarded to James Carter.\nEmergency First Aid at Work, valid until 2026."),
    ("Nadia Hussain", "Driver and BSL certificates",
     "Wheelchair accessible vehicle (WAV) driver assessment: passed. Nadia Hussain, 2025.\n"
     "Signature Level 6 NVQ Certificate in British Sign Language. Awarded to Nadia Hussain."),
]


def seed_documents() -> int:
    """Add any sample certificates that are missing. Safe to run repeatedly."""
    added = 0
    with SessionLocal() as db:
        for name, title, text in DOCUMENTS:
            provider = db.scalar(select(Provider).where(Provider.name == name))
            if provider is None or any(d.title == title for d in provider.documents):
                continue
            provider.documents.append(Document(
                title=title, source_type=DocumentSource.pasted, raw_text=clean_text(text)
            ))
            added += 1
        db.commit()
    return added


def seed(reset: bool = False) -> None:
    seed_competencies()

    with SessionLocal() as db:
        if reset:
            db.execute(delete(Provider))
            db.commit()
        has_providers = db.scalar(select(func.count()).select_from(Provider))
    if has_providers:
        print("Providers table is not empty, so no providers added "
              "(run with --reset to replace them).")
    else:
        add_providers()
        print(f"Added {len(PROVIDERS)} providers.")

    print(f"Added {seed_documents()} sample documents. "
          "Run `python verify_all.py` to verify the providers that have documents.")


def add_providers() -> None:
    with SessionLocal() as db:

        competencies = {c.code: c for c in db.scalars(select(Competency))}
        for name, provider_type, city, codes, bio in PROVIDERS:
            latitude, longitude = CITIES[city]
            db.add(Provider(
                name=name,
                provider_type=provider_type,
                bio=bio,
                location=city,
                latitude=latitude,
                longitude=longitude,
                competency_links=[
                    ProviderCompetency(competency=competencies[code]) for code in codes
                ],
            ))
        db.commit()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
