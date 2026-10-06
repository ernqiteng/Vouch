# Vouch - An Accessibility Services Matching Platform

A verification-first directory that matches disabled users with accessibility-competent carers and transport providers, and lets them book a specific trip against a specific verified match.

## What it is

Most accessibility apps solve one of two problems: "is this place wheelchair accessible" (Roll Mobility, Wheelmap, AccessAble) or "is this route step-free" (Google Maps, Citymapper). Neither answers the question that actually determines whether a trip goes well: **does the specific person showing up know how to help me?**

Can this carer operate a hoist safely? Does this taxi driver know how to fold and secure my wheelchair? Can this driver communicate with me in BSL? Existing platforms either don't ask these questions at all, or answer them with a generic "background-checked" badge that says nothing about the specific competency I need.

Vouch treats accessibility competency as something that should be **searchable, verified, and attached to an actual booking** — not a static profile tag nobody checks.

## The concept

A user describes what they need in plain language:

> "I need a carer confident with hoist transfers who can communicate in BSL."

Vouch converts this into structured requirements, searches verified providers, and returns matches ranked by competency fit and verification confidence — not just proximity or star rating. The user can then request a **specific trip** (pickup, dropoff, time) from a specific verified provider, with that provider's verification snapshot attached to the booking as a record of what was confirmed at the time.

### Why this is a real gap, not a solved problem

This project deliberately doesn't claim to be first to accessibility tech. It sits in a specific, narrow gap between things that already exist:

- **Care.com** verifies caregivers generally — background checks, listed qualifications — but has no accessibility-specific competency verification (no hoist-transfer or BSL-fluency checks) and isn't trip-based.
- **AccessibleGO** verifies specific accessibility needs against a vendor, but does it with a human phone call, not software — a strong signal that automated verification in this space is genuinely hard, and genuinely worth building.
- **Wheelchair taxi operators** claim trained drivers as a blanket company guarantee, not a per-driver, filterable, verified competency.
- **BSL interpreter booking** exists as a completely separate system, with no integration into transport or care booking at all.

Vouch's contribution is combining these: competency-specific verification, shown with its evidence (not a black-box badge), across both carers and transport, tied to an actual bookable trip.

## Core functionality

### 1. Structured provider profiles
Providers (carers, drivers) list their competencies as structured tags — wheelchair transfer training, hoist certification, BSL fluency, first aid, and similar — either self-reported or backed by an uploaded document.

### 2. LLM-based verification pipeline
The core mechanism, and the technical heart of the project:

```
Provider bio / reviews / uploaded certification
                │
                ▼
         LLM extraction
   (free text → structured competency claims)
                │
                ▼
     Deterministic cross-check
   (claim vs. uploaded document, flag mismatches)
                │
                ▼
        Confidence score
                │
                ▼
   Verified badge, or flagged as self-reported
```

The LLM only interprets and extracts — it never decides who is trustworthy. A separate, deterministic scoring function computes the actual confidence and verification status, so the trust logic is auditable rather than opaque.

### 3. Natural-language search with an accessibility profile
Users set their accessibility needs once (mobility device, communication preferences, required competencies), and every search automatically applies them — no re-selecting filters every time.

### 4. Competency-weighted matching and ranking
Results aren't just filtered — they're ranked by a scoring function:

```
score =
    competency_match * 0.40
  + verification_confidence * 0.25
  + availability_at_requested_time * 0.20
  + eta_or_distance * 0.15
```

### 5. Trip-specific booking
Users request a named provider for a specific pickup, dropoff, and time. Vouch checks that provider's availability and service area, confirms the booking, and attaches a snapshot of the provider's verification status at the time of booking — so there's a record of exactly what was confirmed when the trip was made.

## Tech stack

- **Frontend:** React + TypeScript
- **Backend:** Python + FastAPI
- **Database:** PostgreSQL — this is a relational, entity-and-trust problem (providers, users, verification records, structured tags, trips, availability), not a spatial one, so plain Postgres is the right fit
- **LLM:** Claude or Gemini API, used narrowly for two tasks: (1) parsing natural-language user requests into structured requirements, and (2) extracting structured competency claims from provider bios, reviews, and uploaded certification text
- **Distance/ETA:** a single external geocoding/distance API call (e.g. Google Distance Matrix or Mapbox) for trip ETA and distance display — Vouch does not build its own routing engine; that's a solved problem elsewhere and isn't the point of this project
- **Optional:** basic OCR (e.g. Tesseract) if parsing certificate images rather than text uploads

## Running locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### Backend setup (once)

From the repo root:

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Create the database:

```bash
createdb -U postgres vouch_dev
```

Create `backend/.env` (it is gitignored, so never committed):

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost/vouch_dev
GEMINI_API_KEY=your-key-from-aistudio.google.com
JWT_SECRET=a-long-random-string
```

Search uses Gemini's free tier. Get a key from Google AI Studio (no billing needed). `JWT_SECRET` signs login tokens; generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and keep it private.

Create the tables and add sample data:

```bash
alembic upgrade head
python seed.py
python verify_all.py
```

`seed.py` adds sample providers (if there are none) and sample certificates for some of them. `verify_all.py` runs verification on every provider with documents, using one Gemini call each, so their Verified badges appear. `python seed.py --reset` deletes all providers and re-adds the sample set.

### Run the backend

From `backend/`, with the virtual environment active:

```bash
uvicorn main:app --reload
```

The API runs at http://127.0.0.1:8000. Interactive API docs are at http://127.0.0.1:8000/docs.

If PowerShell refuses to run `activate` ("running scripts is disabled"), run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activating and use `venv\Scripts\python -m uvicorn main:app --reload`.

### Run the frontend

From the repo root:

```bash
cd frontend
npm install
npm run dev
```

The app runs at http://localhost:5173.

### Run the tests

From `backend/`, with the virtual environment active:

```bash
pip install -r requirements-dev.txt   # once, adds pytest
pytest
```

To measure claim extraction accuracy against the hand-labelled eval set in `backend/evals/claims_eval.json` (one Gemini call per case, about 4 minutes):

```bash
python -m evals.run_claims_eval
```

It prints precision, recall, latency and token usage, and saves the full results to `backend/evals/results/`.

### After pulling new changes

```bash
pip install -r requirements.txt    # in backend/, if requirements changed
alembic upgrade head               # in backend/, if there are new migrations
npm install                        # in frontend/, if package.json changed
```

## Design principle: LLM interprets, system decides

The same discipline runs through every part of Vouch. The LLM is used only where natural language genuinely needs interpreting — turning a user's request or a provider's bio into structured data. Every decision that actually matters — verification status, confidence score, ranking, matching — is computed by deterministic application code that can be inspected, tested, and explained. This is a deliberate architectural choice, not an accident of scope: it's what makes "verified" mean something rather than being a label the LLM hands out.