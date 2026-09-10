# Phase 4 — Trip-Specific Booking (V4, stretch goal)

Source: broken out from [detailedroadmap.md](detailedroadmap.md) — that file is the full reference; this is the phase-4-only version so you can work from a shorter checklist.

**Prerequisite:** Phase 1-3 checkpoints passing. This phase is a stretch goal — if you're behind schedule, it's the first thing to cut (see the hackathon-week schedule in detailedroadmap.md).

**Goal at the end of this phase:** a logged-in user can book a specific provider for a specific pickup/dropoff/time, the system checks that provider's real availability, and the booking permanently stores a snapshot of that provider's verification status at booking time.

---

## 4.1 Availability model

Add an `availability` table: provider_id, day/time windows they're free (or simpler for a demo: a list of specific bookable slots rather than recurring windows — much less to build).

## 4.2 Booking flow

- `POST /bookings`: accepts provider_id, pickup, dropoff, requested time.
- Server checks the provider's availability table for that slot — reject with a clear error if unavailable, don't let two users double-book the same slot (wrap this check-and-create in a database transaction so it's not vulnerable to a race condition where two bookings squeak through at once).
- On success, create the booking row **and copy the provider's current verification data into it** (not just a foreign key reference) — e.g. a JSON snapshot column with `{competency: "hoist_transfer", verified: true, confidence: 0.85, verified_at: ...}` for each competency relevant to the trip. This snapshot is the point of this phase: proof of what was confirmed *at the time*, even if the provider's verification status changes later.

## 4.3 Booking confirmation UI

A confirmation screen/page showing the booked provider, trip details, and the verification snapshot that was captured — this is the moment the whole verification pipeline becomes visible and valuable to the user, so don't let it be an afterthought screen.

---

## ✅ Phase 4 Checkpoint

- [ ] `availability` table exists and can be queried per provider
- [ ] `POST /bookings` correctly rejects a request for a slot the provider doesn't have available
- [ ] Two near-simultaneous booking requests for the same slot don't both succeed (test this deliberately — fire two requests back to back)
- [ ] A successful booking stores a full verification snapshot (not a foreign key reference) as part of the booking record
- [ ] The snapshot includes, at minimum, the competency, verified status, and confidence score at the time of booking
- [ ] Booking confirmation UI displays the trip details and the captured verification snapshot
- [ ] **The key test:** book a trip, then change the provider's verification status afterward (e.g. re-run verification with a different document), and confirm the *original* booking still shows the old snapshot, not the updated one

**You're done with Phase 4 when:** you can book a trip, then (as a test) change the provider's verification status afterward, and confirm the old booking still shows the *original* snapshot, not the updated one.
