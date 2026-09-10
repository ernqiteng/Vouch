# Phase 1 — Structured Search (V1)

Source: broken out from [detailedroadmap.md](detailedroadmap.md) — that file is the full reference; this is the phase-1-only version so you can work from a shorter checklist.

**Goal at the end of this phase:** a database of providers, an API to search them by tags, and a frontend page where a user can type a plain-English request and see a filtered list of matching providers. No verification, no LLM ranking yet — just correct filtering.

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

If any of these aren't installed, install them before continuing.

### Key vocabulary used throughout

- **API endpoint**: a URL your backend exposes that the frontend (or anything else) can call to get or send data. E.g. `GET /providers` returns a list of providers.
- **Database migration**: a versioned, saved change to your database's structure, so the schema itself is tracked like code.
- **Schema**: the shape of your data — what tables exist, what columns they have, what type each column is.
- **Backend**: the server-side code (Python/FastAPI here) that talks to the database and does the actual logic.
- **Frontend**: the code that runs in the user's browser (React/TypeScript here) and renders the UI.
- **Seed data**: fake/sample data you insert into the database so you have something to test against before real users exist.

---

## 1. Project setup (do this once)

1. Create the project folders inside the repo:
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

## 1.1 Design the provider data model

Decide the columns for a `providers` table. Minimum viable set:

- `id` (unique identifier)
- `name`
- `bio` (free text)
- `provider_type` (`carer` or `driver`)
- `competencies` (a list of tags — e.g. `["hoist_transfer", "bsl_fluent", "first_aid"]`)
- `location` (city or postcode is enough for this phase — don't build real geospatial search yet)
- `created_at`

In SQLAlchemy, this becomes a Python class (a "model") in `backend/models.py`. Competency tags can be stored as a Postgres array column or a separate `competencies` table linked by foreign key — a separate table is more correct long-term (it lets you query "all providers with X tag" efficiently and add new tags without touching the providers table), so do that if you have time; an array column is faster to build if you're racing a clock.

## 1.2 Set up migrations and create the table

```bash
alembic init alembic
```
Configure `alembic.ini` and `alembic/env.py` to point at your `DATABASE_URL` and your models. Then:
```bash
alembic revision --autogenerate -m "create providers table"
alembic upgrade head
```
This creates the actual table in Postgres matching your Python model. Every time you change a model going forward, repeat this two-command pattern.

## 1.3 Build the CRUD API

"CRUD" = Create, Read, Update, Delete. Build these FastAPI endpoints:

- `POST /providers` — create a provider (you'll use this to seed data)
- `GET /providers` — list all providers, with optional query params like `?competency=hoist_transfer`
- `GET /providers/{id}` — get one provider
- (Update/Delete can wait until Phase 5's provider dashboard)

Test each one via the `/docs` page as you build it.

## 1.4 Seed fake data

Write a small script (`backend/seed.py`) that inserts ~20-30 fake providers with varied competencies, types, and locations, and run it against your dev database. You need this to test search and ranking meaningfully.

## 1.5 Natural-language search → structured filter (the first LLM step)

This is the first place the LLM touches the system.

1. Build one endpoint: `POST /search` that accepts `{"query": "I need a carer confident with hoist transfers who can communicate in BSL"}`.
2. Inside that endpoint, call the LLM API with a prompt like:
   > "Extract structured search filters from this user request. Return JSON matching this schema: `{provider_type, required_competencies: [...], location: string|null}`. User request: {query}"
3. Parse the LLM's JSON response (wrap this in a try/except — LLMs occasionally return malformed JSON; if that happens, fall back to an empty filter and log it rather than crashing).
4. Use that structured filter to run a normal, deterministic SQL query against your `providers` table (via SQLAlchemy) — the LLM never touches the database directly, it only produces the filter.
5. Return the matching providers.

Keep the LLM's job narrow: text in, structured JSON out. Nothing else. This is the "LLM interprets, system decides" principle you'll reuse in every later phase.

## 1.6 Build the frontend

- A search bar (plain text input) that posts to `/search`.
- A results list showing provider cards: name, type, competency tags, location.
- Basic loading/empty/error states.

Use `fetch` or a small library like `axios` to call your backend. Keep API calls in one file (e.g. `frontend/src/api.ts`) rather than scattered through components.

---

## ✅ Phase 1 Checkpoint

Check off each item to confirm this phase is actually done before moving to Phase 2:

- [ ] `uvicorn main:app --reload` runs with no errors, and `/health` returns `{"status": "ok"}`
- [ ] `providers` table exists in Postgres (verify with `psql vouch_dev -c "\d providers"`)
- [ ] `POST /providers` successfully creates a row (test via `/docs`)
- [ ] `GET /providers` returns a list, and `?competency=X` correctly filters it
- [ ] Seed script has run and the table has 20+ varied fake providers
- [ ] `POST /search` with a plain-English sentence returns an LLM-parsed JSON filter that looks correct (check the parsed filter, not just the final results)
- [ ] A malformed/unexpected LLM response doesn't crash the endpoint (test by temporarily feeding it a weird query)
- [ ] The frontend search page: typing a sentence and hitting search shows a filtered list of real providers from the database
- [ ] Loading and empty-results states are visibly different from the normal results state

**You're done with Phase 1 when:** you can type "I need a hoist-trained carer" into the search bar and get back only providers tagged `hoist_transfer`, pulled from real Postgres data via a real API, with the filter itself generated by an LLM call you wrote.
