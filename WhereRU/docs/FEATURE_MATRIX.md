# Feature coverage and remaining work

The master specification is a product vision; this ZIP implements a bounded backend MVP. No frontend is bundled.

| Feature group | Package status | Limits / remaining setup |
|---|---|---|
| Email accounts, sign-in/out, sessions | Implemented | Console mode is local-only; SMTP needs credentials |
| Passwords/reset | Intentionally replaced | Email-code authentication does not store passwords |
| Profile/preferences/My Activity | Implemented | No account-deletion or moderator roles workflow |
| Lost/found reports and ownership | Implemented | Legacy ownerless reports need explicit local assignment if desired |
| Private reports and identifying evidence | Implemented | Trusted-helper/direct-recipient audiences deferred |
| Sensitive categories | Implemented | Private-only categories; no guarantee of automatic PII detection |
| Search, filters, pagination, resolved handling | Implemented | Small SQLite single-host deployment |
| Photos | Implemented | Five per report, private by default; no claim proof attachments |
| Gemini image/text suggestions | Adapter implemented and mocked tests pass | Live service needs key/model access and user consent |
| Semantic matching | Implemented optional embedding index | Both owners index their reports; live quality unmeasured |
| Deterministic cross-campus matching | Implemented | Explainable prototype weights; validate with real examples |
| Private match notifications | Implemented | In-app only; no push/email event notifications |
| Claims, decisions, private evidence | Implemented | Finder review; no staff/moderator dispute resolution |
| Private claim-linked messages | Implemented | No block/report or attachments |
| Meetup/hand-in and two-party confirmation | Implemented | Staffed custody remains user-reported, never falsely verified |
| Status/history | Implemented | Adds CLOSED for withdrawals/self-recovery |
| Reputation | Implemented contribution ledger | Duplicate/self-return prevention; collusion detection deferred |
| Monetary reward field | Implemented | No payments or escrow |
| Selected potential locations | Implemented | User picks places and explicitly chooses sharing |
| App-wide density heatmap API | Implemented | Only eligible shared report places; no private trails |
| Per-item search cloud API | Implemented | Reporter-weighted search areas, not validated loss probabilities |
| Optional location recording storage | Implemented | Phone GPS collection/native background recording not included |
| Classroom reference recognition | Adapter, catalog format and validation implemented | Empty catalog until labeled photos supplied; accuracy unmeasured |
| Multi-item photo → drafts | Optional adapter implemented | Live Gemini required; no auto-publication |
| Benchmark and tests | Included | Synthetic evaluation; live AI benchmark not yet run |
| Legacy import, backup, cleanup | Implemented | Old accounts, photos, secrets and sessions are not migrated |
| Deployment | Configuration and instructions included | Hosting, HTTPS and external credentials must be configured |
| Institutional integration/lockers/payments | Not included | Future scope |

Room recognition, semantic embeddings and image understanding are not falsely presented as verified live AI results. Demo/fallback output is labeled. Public listing access is signed-in only, as requested in the master specification.
