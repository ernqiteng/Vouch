# Phase 5 — Provider-Side Tools (V5, roadmap only unless time allows)

Source: broken out from [detailedroadmap.md](detailedroadmap.md) — that file is the full reference; this is the phase-5-only version so you can work from a shorter checklist.

**Prerequisite:** Phases 1-4. This phase is roadmap-only scope — build it only if you have time left after Phase 4 (or Phase 3, if Phase 4 was cut).

**Goal at the end of this phase:** a simple authenticated dashboard where a provider can log in, edit their availability windows, upload new certification documents, and see a table of their competencies with verified/self-reported status per row.

Most of this phase is UI work reusing endpoints you already built:
- Provider login (same auth pattern as Phase 3's user accounts, applied to the `providers` table instead)
- Availability management UI, calling the same `availability` table from Phase 4 (add Update/Delete endpoints for it if you haven't already)
- Document upload UI, calling the same `POST /providers/{id}/documents` endpoint from Phase 2
- A competency table view showing verified vs. self-reported status per row, using the per-competency badge data from Phase 2
- The Update/Delete provider endpoints deferred from Phase 1's CRUD API (`PUT /providers/{id}`, `DELETE /providers/{id}`)

---

## ✅ Phase 5 Checkpoint

- [ ] A provider can log in to a dashboard separate from the regular user search UI
- [ ] A provider can add/edit/remove their own availability windows through the UI (not just via `/docs`)
- [ ] A provider can upload a new document through the dashboard and see verification re-run
- [ ] The dashboard shows a per-competency table: which are verified, which are self-reported, with confidence scores visible
- [ ] `PUT /providers/{id}` and `DELETE /providers/{id}` exist and are restricted so a provider can only edit their own profile, not anyone else's

**You're done with Phase 5 when:** a provider can manage their own availability and documents end-to-end through the dashboard, without you touching the database or `/docs` directly.

---

## A note on Phase 6 (Community layer)

The README and roadmap describe a V6 "community layer" — a post-trip feedback loop that feeds into confidence scoring over time. This is explicitly **not required** for a hackathon build. There's no `phase6.md` because it isn't expected to become code during this project — if you want it in your pitch, describe it as a paragraph in your deck: post-trip feedback → adjusts `verification_confidence` → future searches re-rank accordingly. That's enough to show you've thought about where the product goes next without spending build time on it.
