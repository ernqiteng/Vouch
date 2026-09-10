# Phase 3 — Personalized Matching (V3)

Source: broken out from [detailedroadmap.md](detailedroadmap.md) — that file is the full reference; this is the phase-3-only version so you can work from a shorter checklist.

**Prerequisite:** Phase 1 and Phase 2 checkpoints passing — you need real search and real verification confidence scores for the ranking formula to mean anything.

**Goal at the end of this phase:** users have persistent accounts with saved accessibility needs, and search results are ranked (not just filtered) by the weighted scoring formula from the README.

---

## 3.1 User accounts and accessibility profile

- Add a `users` table and a simple auth flow. For a hackathon, don't build password auth from scratch — use a library (FastAPI has `fastapi-users`, or use a hosted auth provider) or, if time is short, a bare-minimum email+password with hashed passwords via `passlib`. Don't skip hashing even under time pressure.
- Add a `user_profiles` table: mobility device, communication preferences, required competencies — the fields the user would otherwise have to re-type into every search.

## 3.2 Auto-apply profile to search

Modify the `/search` endpoint: if the request comes from a logged-in user, merge their saved profile into the structured filter *before* running the query, so their needs apply automatically without re-selecting filters. Let the user override per-search if they want something different that day.

## 3.3 Build the ranking function

This is where the README's formula gets implemented for real:
```
score = competency_match * 0.40
      + verification_confidence * 0.25
      + availability_at_requested_time * 0.20
      + eta_or_distance * 0.15
```
Each term needs its own small function:
- `competency_match`: fraction of required competencies the provider has (0-1).
- `verification_confidence`: the score from Phase 2, normalized to 0-1.
- `availability_at_requested_time`: 1 if free, 0 if not (Phase 4 will make this real; until then, stub it as always 1).
- `eta_or_distance`: normalize distance/ETA into a 0-1 score, e.g. `1 - (distance / max_search_radius)`.

Compute this in Python after fetching the filtered candidates from Postgres (don't try to do the weighted math inside SQL — it's much easier to read, test, and adjust weights in application code). Sort results by score descending before returning them.

Write a unit test for this function with a few hand-constructed provider examples where you know what the "correct" ranking should be — this is cheap insurance against silently breaking the ranking later.

---

## ✅ Phase 3 Checkpoint

- [ ] A new user can sign up, and passwords are stored hashed (never plaintext — check the DB row directly to confirm)
- [ ] A logged-in user can save an accessibility profile (mobility device, comms preference, required competencies)
- [ ] Searching while logged in automatically applies the saved profile without re-entering filters
- [ ] A logged-in user can still override/add filters for a one-off search
- [ ] `competency_match`, `verification_confidence`, `availability_at_requested_time`, and `eta_or_distance` each exist as separate, individually testable functions
- [ ] The overall `score` calculation matches the README's weights (0.40 / 0.25 / 0.20 / 0.15) — check the code against the formula directly
- [ ] Results returned from `/search` are sorted by score, descending
- [ ] A unit test exists with hand-constructed providers where you know the expected ranking order, and it passes
- [ ] Two searches for the same query — one from a logged-in user with a saved profile, one anonymous — return differently-ranked results

**You're done with Phase 3 when:** two searches for the same query, one from a logged-in user with a saved profile and one without, return differently-ranked results — and you can point to the scoring function and explain every number in the ranking.
