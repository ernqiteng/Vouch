# Vouch — Roadmap

## Roadmap

| Version | Capability |
|---|---|
| **V1 — Structured search** | Provider profiles with structured accessibility tags; natural-language search parsed into a structured filter query |
| **V2 — Verification pipeline** | Provider uploads a document/certification; LLM extracts competency claims and cross-checks them against the document; confidence score computed; verified badge applied |
| **V3 — Personalized matching** | Persistent user accessibility profile (required competencies, communication needs) automatically applied to every search; results ranked by the competency-weighted scoring function |
| **V4 — Trip-specific booking** | User requests a named, verified provider for a specific pickup, dropoff, and time; system checks availability and service area, confirms booking, and attaches a verification snapshot to the trip record |
| **V5 — Provider-side tools** | Provider dashboard for managing availability windows, uploading additional certifications, and viewing which claims are verified vs. self-reported |
| **V6 — Community layer** | Post-trip feedback loop that feeds back into confidence scoring; roadmap only, not required for core demo |

**Solo-build scope for a hackathon week:** V1 → V3 as the core demo, with V4 (trip booking) as a strong stretch goal if time allows. V5–V6 stay roadmap-only, mentioned in the pitch but not built.
