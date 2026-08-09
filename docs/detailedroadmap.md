# Vouch — Detailed Build Roadmap

This is a step-by-step guide for building Vouch from nothing, written assuming you haven't built a full-stack app with an LLM pipeline before. It expands each version in [roadmap.md](roadmap.md) into concrete tasks, in order, with the "why" explained, not just the "what."

Work through this top to bottom. Don't skip to V3 before V1 works — each version depends on the data models and endpoints the previous one built.

---

## 0. Before you start: what you need installed

| Tool | What it's for | How to check you have it |
|---|---|---|
| **Git** | Version control — saves snapshots of your code so you can undo mistakes | `git --version` |
| **Node.js** (v18+) | Runs the frontend build tools and lets you install JavaScript/TypeScript packages | `node --version` |
| **Python** (3.11+) | Runs the backend | `python --version` |
| **PostgreSQL** (v15+) | The database — stores providers, users, bookings | `psql --version` |
| **A code editor** | VS Code is the standard choice, free | — |
| **An LLM API key** | Claude (console.anthropic.com) or Gemini (aistudio.google.com) — you'll call this from your backend | Sign up, generate an API key, keep it secret |

If any of these aren't installed, install them before continuing — everything below assumes they work from your terminal.

### Key vocabulary used throughout this doc

- **API endpoint**: a URL your backend exposes that the frontend (or anything else) can call to get or send data. E.g. `GET /providers` returns a list of providers.
- **Database migration**: a versioned, saved change to your database's structure (like "add a `verified` column to the `providers` table"), so the database schema itself is tracked like code.
- **Schema**: the shape of your data — what tables exist, what columns they have, what type each column is.
- **Backend**: the server-side code (Python/FastAPI here) that talks to the database and does the actual logic.
- **Frontend**: the code that runs in the user's browser (React/TypeScript here) and renders the UI.
- **Seed data**: fake/sample data you insert into the database so you have something to test against before real users exist.

---

## 1. Project setup (do this once)

1. Create the project folders inside this repo:
   ```
   Vouch/
     backend/
     frontend/
   ```
2. **Backend init:**
   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate        # Windows
   pip install fastapi uvicorn sqlalchemy psycopg2-binary alembic python-dotenv pydantic
   ```
   - `fastapi` — the web framework that defines your API endpoints.
   - `uvicorn` — the server that actually runs FastAPI.
   - `sqlalchemy` — lets you define database tables as Python classes ("ORM") instead of raw SQL.
   - `alembic` — manages database migrations.
   - `python-dotenv` — loads secrets (API keys, DB password) from a `.env` file instead of hardcoding them.

3. **Frontend init:**
   ```bash
   cd frontend
   npm create vite@latest . -- --template react-ts
   npm install
   ```
   Vite is a fast dev server/build tool. `react-ts` gives you React with TypeScript pre-configured.

4. **Database:**
   ```bash
   createdb vouch_dev
   ```
   Create a `.env` file in `backend/` with:
   ```
   DATABASE_URL=postgresql://localhost/vouch_dev
   LLM_API_KEY=your-key-here
   ```
   Add `.env` to `.gitignore` immediately — never commit API keys.

5. Confirm the backend runs: create a minimal `backend/main.py`:
   ```python
   from fastapi import FastAPI
   app = FastAPI()

   @app.get("/health")
   def health():
       return {"status": "ok"}
   ```
   Run `uvicorn main:app --reload` and visit `http://localhost:8000/health` — you should see `{"status": "ok"}`. FastAPI also auto-generates interactive API docs at `http://localhost:8000/docs`, which you'll use constantly to test endpoints without building UI first.

---

## V1 — Structured search

**Goal at the end of V1:** a database of providers, an API to search them by tags, and a frontend page where a user can type a plain-English request and see a filtered list of matching providers. No verification, no LLM ranking yet — just correct filtering.

### 1.1 Design the provider data model

Decide the columns for a `providers` table. Minimum viable set:

- `id` (unique identifier)
- `name`
- `bio` (free text)
- `provider_type` (`carer` or `driver`)
- `competencies` (a list of tags — e.g. `["hoist_transfer", "bsl_fluent", "first_aid"]`)
- `location` (city or postcode is enough for V1 — don't build real geospatial search yet)
- `created_at`

In SQLAlchemy, this becomes a Python class (a "model") in `backend/models.py`. Competency tags can be stored as a Postgres array column or a separate `competencies` table linked by foreign key — a separate table is more correct long-term (it lets you query "all providers with X tag" efficiently and add new tags without touching the providers table), so do that if you have time; an array column is faster to build if you're racing a clock.

### 1.2 Set up migrations and create the table

```bash
alembic init alembic
```
Configure `alembic.ini` and `alembic/env.py` to point at your `DATABASE_URL` and your models. Then:
```bash
alembic revision --autogenerate -m "create providers table"
alembic upgrade head
```
This creates the actual table in Postgres matching your Python model. Every time you change a model going forward, repeat this two-command pattern — it's how your database schema stays in sync with your code and stays version-controlled.

### 1.3 Build the CRUD API

"CRUD" = Create, Read, Update, Delete — the basic operations any data-backed API needs. Build these FastAPI endpoints:

- `POST /providers` — create a provider (you'll use this to seed data)
- `GET /providers` — list all providers, with optional query params like `?competency=hoist_transfer`
- `GET /providers/{id}` — get one provider
- (Update/Delete can wait until V5's provider dashboard)

Test each one via the `/docs` page as you build it — don't wait until the frontend exists to find out an endpoint is broken.

### 1.4 Seed fake data

Write a small script (`backend/seed.py`) that inserts ~20-30 fake providers with varied competencies, types, and locations, and run it against your dev database. You need this to test search and ranking meaningfully — searching a database with 2 rows in it will hide bugs that show up at realistic scale.

### 1.5 Natural-language search → structured filter (the first LLM step)

This is the first place the LLM touches the system, and it's a good place to learn the pattern you'll reuse in V2.

1. Build one endpoint: `POST /search` that accepts `{"query": "I need a carer confident with hoist transfers who can communicate in BSL"}`.
2. Inside that endpoint, call the LLM API with a prompt like:
   > "Extract structured search filters from this user request. Return JSON matching this schema: `{provider_type, required_competencies: [...], location: string|null}`. User request: {query}"
3. Parse the LLM's JSON response (wrap this in a try/except — LLMs occasionally return malformed JSON; if that happens, fall back to an empty filter and log it rather than crashing).
4. Use that structured filter to run a normal, deterministic SQL query against your `providers` table (via SQLAlchemy) — the LLM never touches the database directly, it only produces the filter.
5. Return the matching providers.

This is the pattern stated in the README's design principle — **LLM interprets, system decides** — and you're implementing it for the first time here. Keep the LLM's job narrow: text in, structured JSON out. Nothing else.

### 1.6 Build the frontend

- A search bar (plain text input) that posts to `/search`.
- A results list showing provider cards: name, type, competency tags, location.
- Basic loading/empty/error states — you'll thank yourself later, and it's cheap to add now.

Use `fetch` or a small library like `axios` to call your backend. Keep API calls in one file (e.g. `frontend/src/api.ts`) rather than scattered through components, so V2 onward is easy to extend.

### V1 checkpoint

You're done with V1 when: you can type "I need a hoist-trained carer" into the search bar and get back only providers tagged `hoist_transfer`, pulled from real Postgres data via a real API, with the filter itself generated by an LLM call you wrote.

---

## V2 — Verification pipeline

**Goal at the end of V2:** a provider can be marked "verified" based on cross-checking their claimed competencies against an uploaded document, with a numeric confidence score and a visible badge.

### 2.1 Add document upload

- Add a `POST /providers/{id}/documents` endpoint that accepts a file upload (a certification PDF/image, or just pasted text for V2's first pass — text is much easier to start with than parsing PDFs/images).
- Store the raw text (or a link to the stored file, if you're keeping the original) in a new `documents` table linked to the provider.
- If you want to handle image certificates, this is where Tesseract OCR comes in (per the README's tech stack) — but treat that as optional polish, not core V2. Text-only documents are enough to prove the pipeline works.

### 2.2 LLM extraction step

Write a function `extract_claims(bio: str, document_text: str) -> list[Claim]` that:
1. Sends the provider's bio + document text to the LLM.
2. Asks for structured output: a list of claimed competencies, each with the source ("bio" or "document") and the exact supporting text snippet.
3. Parses and validates the JSON response (same defensive pattern as 1.5 — this LLM call can also fail or return junk, handle that explicitly).

This is the same "LLM interprets" pattern as search, just extracting claims instead of filters.

### 2.3 Deterministic cross-check

This step must **not** call the LLM — it's plain Python logic comparing two lists:
- Claims found in the bio (self-reported, unverified)
- Claims found in the document (backed by evidence)

For each competency: if it appears in both → "corroborated." If only in bio → "self-reported, unverified." If only in document → "documented, not yet claimed by provider" (worth flagging, might be a mismatch or an opportunity to prompt the provider).

Writing this as plain conditional logic (not another LLM call) is the whole point of the architecture — it's what makes the verification status explainable and testable, rather than a black box.

### 2.4 Confidence score

Turn the cross-check result into a number. Start simple and be able to justify every term:
```
confidence = (corroborated_count / total_claimed_count) * document_quality_weight
```
Where `document_quality_weight` might just be 1.0 for now, or slightly reduced if the document was OCR'd (lower-quality source) versus directly pasted text. Store this score, and store the *inputs* to the calculation (not just the final number) — you'll want that trail later for debugging and for the "why was this provider marked verified" transparency the README promises.

### 2.5 Verified badge + UI

- Add a threshold: e.g. `confidence >= 0.7` → show a "Verified" badge; below that → "Self-reported."
- On the provider card/profile, show *which* competencies are verified vs. self-reported individually (not just one badge for the whole profile) — this is the actual differentiator from the "generic background-checked badge" the README explicitly critiques competitors for.

### V2 checkpoint

You're done with V2 when: uploading a document for a provider, re-running verification, and seeing their confidence score and per-competency badges update — deterministically, reproducibly, with no LLM call in the scoring path itself.

*(This is also the stage to start logging LLM latency and cost per call, and to build a small hand-labeled eval set — see [Appendix](#appendix-generating-real-numbers-for-your-cv) — since accuracy/latency numbers for your CV come directly out of this pipeline.)*

---

## V3 — Personalized matching

**Goal at the end of V3:** users have persistent accounts with saved accessibility needs, and search results are ranked (not just filtered) by the weighted scoring formula from the README.

### 3.1 User accounts and accessibility profile

- Add a `users` table and a simple auth flow. For a hackathon, don't build password auth from scratch — use a library (FastAPI has `fastapi-users`, or use a hosted auth provider) or, if time is short, a bare-minimum email+password with hashed passwords via `passlib`. Don't skip hashing even under time pressure.
- Add a `user_profiles` table: mobility device, communication preferences, required competencies — the fields the user would otherwise have to re-type into every search.

### 3.2 Auto-apply profile to search

Modify the `/search` endpoint: if the request comes from a logged-in user, merge their saved profile into the structured filter *before* running the query, so their needs apply automatically without re-selecting filters. Let the user override per-search if they want something different that day.

### 3.3 Build the ranking function

This is where the README's formula gets implemented for real:
```
score = competency_match * 0.40
      + verification_confidence * 0.25
      + availability_at_requested_time * 0.20
      + eta_or_distance * 0.15
```
Each term needs its own small function:
- `competency_match`: fraction of required competencies the provider has (0-1).
- `verification_confidence`: the score from V2, normalized to 0-1.
- `availability_at_requested_time`: 1 if free, 0 if not (V4 will make this real; until then, stub it as always 1).
- `eta_or_distance`: normalize distance/ETA into a 0-1 score, e.g. `1 - (distance / max_search_radius)`.

Compute this in Python after fetching the filtered candidates from Postgres (don't try to do the weighted math inside SQL — it's much easier to read, test, and adjust weights in application code). Sort results by score descending before returning them.

Write a unit test for this function with a few hand-constructed provider examples where you know what the "correct" ranking should be — this is cheap insurance against silently breaking the ranking later.

### V3 checkpoint

You're done with V3 when: two searches for the same query, one from a logged-in user with a saved profile and one without, return differently-ranked results — and you can point to the scoring function and explain every number in the ranking.

---

## V4 — Trip-specific booking (stretch goal)

**Goal at the end of V4:** a logged-in user can book a specific provider for a specific pickup/dropoff/time, the system checks that provider's real availability, and the booking permanently stores a snapshot of that provider's verification status at booking time.

### 4.1 Availability model

Add an `availability` table: provider_id, day/time windows they're free (or simpler for a demo: a list of specific bookable slots rather than recurring windows — much less to build).

### 4.2 Booking flow

- `POST /bookings`: accepts provider_id, pickup, dropoff, requested time.
- Server checks the provider's availability table for that slot — reject with a clear error if unavailable, don't let two users double-book the same slot (wrap this check-and-create in a database transaction so it's not vulnerable to a race condition where two bookings squeak through at once).
- On success, create the booking row **and copy the provider's current verification data into it** (not just a foreign key reference) — e.g. a JSON snapshot column with `{competency: "hoist_transfer", verified: true, confidence: 0.85, verified_at: ...}` for each competency relevant to the trip. This snapshot is the point of V4 per the README: proof of what was confirmed *at the time*, even if the provider's verification status changes later.

### 4.3 Booking confirmation UI

A confirmation screen/page showing the booked provider, trip details, and the verification snapshot that was captured — this is the moment the whole verification pipeline becomes visible and valuable to the user, so don't let it be an afterthought screen.

### V4 checkpoint

You're done with V4 when: you can book a trip, then (as a test) change the provider's verification status afterward, and confirm the old booking still shows the *original* snapshot, not the updated one.

---

## V5 — Provider-side tools (roadmap only unless time allows)

If you get here: a simple authenticated dashboard where a provider can log in, edit their availability windows, upload new certification documents, and see a table of their competencies with verified/self-reported status per row. This is mostly UI work reusing endpoints you already built in V1-V4, plus the Update/Delete endpoints you deferred from 1.3.

## V6 — Community layer (roadmap only, not required for core demo)

Not expected to be built for a hackathon. If you sketch it: a `feedback` table linked to completed bookings, and a plan for how post-trip feedback would adjust `verification_confidence` over time — this stays a paragraph in your pitch deck, not code.

---

## Suggested order for a hackathon week

| Day | Focus |
|---|---|
| 1 | Section 0-1: project setup, provider model, migrations, CRUD API, seed data |
| 2 | 1.5-1.6: LLM search parsing + frontend search page — get V1 fully working |
| 3 | 2.1-2.3: document upload + LLM extraction + cross-check logic |
| 4 | 2.4-2.5: confidence scoring + badges — V2 done |
| 5 | 3.1-3.3: user accounts, profile, ranking function — V3 done |
| 6 | V4 if time allows: availability + booking + snapshot |
| 7 | Polish, fix bugs, prepare demo/pitch, screenshot the UI, write up numbers (see below) |

If you're behind schedule at any point, cut scope from V4 first, then V3's account system (demo the ranking with a hardcoded fake "logged in" profile instead of building real auth) — never cut corners on V2's deterministic cross-check, since that's the architectural claim the whole project is built around.

---

## Appendix: generating real numbers for your CV

Tying back to what's worth measuring as you build each version — don't wait until the end:

- **V1/V3**: log query latency (wrap your `/search` endpoint timing, log p50/p95) — gives you an API performance number for free.
- **V2**: build a labeled eval set of ~30-50 fake provider bios + documents where you've manually decided the "correct" extracted claims. Run your extraction pipeline against it, compute precision/recall. This is the single most valuable number for the CV — it's a real, defensible accuracy metric, not a guess.
- **V2**: log LLM call latency and token usage per verification — gives you a cost-per-verification number.
- **V3**: seed a larger synthetic dataset (1,000-10,000 fake providers) purely to benchmark ranking/search performance at scale — a demo only needs 20 providers, but a benchmark number needs thousands.
- **V4**: log end-to-end booking flow latency.
- **Overall**: `pytest --cov` for test coverage once you have tests; a simple `k6` or `locust` script against your deployed instance for a throughput/requests-per-second number.

Keep a running notes file as you build (not this doc) where you jot down actual numbers as you measure them, so you're not reconstructing them from memory at the end of the week.
