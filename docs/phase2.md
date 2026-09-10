# Phase 2 — Verification Pipeline (V2)

Source: broken out from [detailedroadmap.md](detailedroadmap.md) — that file is the full reference; this is the phase-2-only version so you can work from a shorter checklist.

**Prerequisite:** Phase 1 checkpoint fully passing — you need working provider records to attach verification to.

**Goal at the end of this phase:** a provider can be marked "verified" based on cross-checking their claimed competencies against an uploaded document, with a numeric confidence score and a visible badge.

---

## 2.1 Add document upload

- Add a `POST /providers/{id}/documents` endpoint that accepts a file upload (a certification PDF/image, or just pasted text for this phase's first pass — text is much easier to start with than parsing PDFs/images).
- Store the raw text (or a link to the stored file, if you're keeping the original) in a new `documents` table linked to the provider.
- If you want to handle image certificates, this is where Tesseract OCR comes in (per the README's tech stack) — but treat that as optional polish, not core. Text-only documents are enough to prove the pipeline works.

## 2.2 LLM extraction step

Write a function `extract_claims(bio: str, document_text: str) -> list[Claim]` that:
1. Sends the provider's bio + document text to the LLM.
2. Asks for structured output: a list of claimed competencies, each with the source ("bio" or "document") and the exact supporting text snippet.
3. Parses and validates the JSON response (same defensive pattern as Phase 1's search parsing — this LLM call can also fail or return junk, handle that explicitly).

This is the same "LLM interprets" pattern as search, just extracting claims instead of filters.

## 2.3 Deterministic cross-check

This step must **not** call the LLM — it's plain Python logic comparing two lists:
- Claims found in the bio (self-reported, unverified)
- Claims found in the document (backed by evidence)

For each competency: if it appears in both → "corroborated." If only in bio → "self-reported, unverified." If only in document → "documented, not yet claimed by provider" (worth flagging, might be a mismatch or an opportunity to prompt the provider).

Writing this as plain conditional logic (not another LLM call) is the whole point of the architecture — it's what makes the verification status explainable and testable, rather than a black box.

## 2.4 Confidence score

Turn the cross-check result into a number. Start simple and be able to justify every term:
```
confidence = (corroborated_count / total_claimed_count) * document_quality_weight
```
Where `document_quality_weight` might just be 1.0 for now, or slightly reduced if the document was OCR'd (lower-quality source) versus directly pasted text. Store this score, and store the *inputs* to the calculation (not just the final number) — you'll want that trail later for debugging and for the "why was this provider marked verified" transparency the README promises.

## 2.5 Verified badge + UI

- Add a threshold: e.g. `confidence >= 0.7` → show a "Verified" badge; below that → "Self-reported."
- On the provider card/profile, show *which* competencies are verified vs. self-reported individually (not just one badge for the whole profile) — this is the actual differentiator from the "generic background-checked badge" the README explicitly critiques competitors for.

## 2.6 Start capturing metrics (optional but valuable)

This is the highest-value phase for CV-worthy numbers — don't skip this step even though it's not required for the demo to work:
- Log LLM call latency and token usage per verification call → gives you a cost-per-verification and latency number.
- Build a small hand-labeled eval set: ~30-50 fake provider bios + documents where you've manually decided the "correct" extracted claims. Run your extraction pipeline against it and compute precision/recall. This is the single most defensible accuracy metric you'll produce in this whole project.

---

## ✅ Phase 2 Checkpoint

- [ ] `POST /providers/{id}/documents` accepts a document and stores it, linked to the right provider
- [ ] `extract_claims()` returns structured JSON with claimed competencies + source + supporting snippet
- [ ] A malformed LLM response on extraction is handled gracefully, not a crash
- [ ] Cross-check logic runs with **zero** LLM calls inside it — verify by reading the function, not just testing it
- [ ] Cross-check correctly labels a competency as "corroborated" when it's in both bio and document
- [ ] Cross-check correctly labels a competency as "self-reported" when it's only in the bio
- [ ] Confidence score is computed and stored, along with the raw inputs used to compute it
- [ ] Re-uploading a document and re-running verification changes the confidence score as expected
- [ ] Verified badge appears/disappears correctly based on the threshold
- [ ] UI shows verification status **per competency**, not just one badge for the whole profile
- [ ] (Optional) You have a labeled eval set and a precision/recall number from running extraction against it
- [ ] (Optional) You have latency and token-cost numbers logged per verification call

**You're done with Phase 2 when:** uploading a document for a provider, re-running verification, and seeing their confidence score and per-competency badges update — deterministically, reproducibly, with no LLM call in the scoring path itself.
