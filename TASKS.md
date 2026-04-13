# RecoverLead Tasks

Ordered by phase and severity. Check off tasks as completed.

---

## Phase 1: Deployable MVP (Weeks 1-7)

### P0 — Security (must complete before any user touches production)

- [x] Row-level tenant isolation on all queries (user_leads, letters, contacts, activities)
- [x] Stripe webhook signature verification (`stripe.Webhook.construct_event()`)
- [x] Clerk webhook svix verification
- [x] Atomic credit deduction (no race conditions) — `UPDATE ... WHERE credits_remaining > 0 RETURNING`
- [x] Atomic lead claiming (no double-claims) — idempotent claim via UserLead unique constraint
- [x] Idempotency keys on all mutation POST endpoints (Redis, 24h TTL)
- [x] Input sanitization on scraper-sourced data (strip control chars, limit length)
- [x] LLM output validation (quality_score 1-10, letter content patterns)
- [x] CHECK constraints on all bounded fields (surplus_amount, quality_score, confidence, fee_percentage)
- [x] Free tier email verification required (Clerk Dashboard → Email → require verification — configure at deploy time)
- [x] No PII in logs (structlog filter)
- [x] CORS restricted to known origins (`CORS_ORIGINS` env var)
- [x] HTTPS everywhere (Railway TLS — automatic on Railway custom domains)
- [x] Rate limiting active on all tiers

### P0 — Infrastructure (Week 1-2)

- [x] Project scaffolding: FastAPI app factory, Docker Compose, pyproject.toml
- [x] Alembic setup + initial migration
- [x] Database models: users, leads, user_leads, counties, letters, letter_templates, subscriptions, skip_trace_credits, llm_usage, failed_tasks
- [x] pgvector extension enabled, HNSW index on leads.embedding
- [x] Clerk integration: JWT middleware (`clerk-backend-api`), svix webhook handler, user sync to local users table
- [x] Stripe billing: checkout sessions, webhook handler (signature verification), subscription CRUD, credit metering
- [x] Stripe overage: metered billing for overages, soft wall at 80%, hard prompt at 100% — frontend UI
- [x] structlog setup: JSON output, request_id propagation, PII filter
- [x] Sentry integration: error tracking + performance monitoring
- [x] CORS middleware configuration
- [x] DB connection pool sizing: API (pool_size=5, max_overflow=10), Celery (pool_size=2, max_overflow=3)
- [x] Redis separation: db 0 cache, db 1 rate limiting, db 2 Celery broker
- [x] Railway deployment config: railway.toml, production + staging environments
- [x] CI/CD: GitHub Actions (lint ruff → type check mypy → test → deploy)
- [x] docker-compose.test.yml for Celery integration tests with real Redis
- [x] Health endpoints: GET /health/live, GET /health/ready (Postgres + Redis check)
- [x] Rate limiter: Redis-based, tier-aware, headers (X-RateLimit-*)
- [x] Idempotency middleware: Redis-backed, 24h TTL
- [x] Field-level PII encryption (Fernet EncryptedString on user/lead/contact fields)

### P1 — Core Pipeline (Week 3-4)

- [x] Base scraper framework: abstract base class with fetch(), parse(), normalize()
- [x] PDF scraper: pdfplumber extraction
- [x] HTML table scraper: BeautifulSoup extraction
- [x] CSV scraper
- [x] Normalizer: raw data → Lead schema, hash on normalized business keys (county_id || case_number || parcel_id || owner_name_normalized)
- [x] Seed all 67 FL county configs (top 10 active, rest inactive)
- [x] Build scrapers for top 10 FL counties — 5 active verified (Volusia, Hillsborough, Pinellas, Broward, Polk), 5 pending require manual contact
- [x] Fixture-based scraper tests (saved HTML/CSV fixtures, 13 tests passing)
- [x] Scraper failure alerting via Sentry
- [x] Embedding pipeline: sentence-transformers wrapper, model loaded via worker_init signal
- [x] Vector search: raw pgvector queries (`SELECT ... ORDER BY embedding <=> $1 LIMIT 5`)
- [x] Evaluate LlamaIndex: raw pgvector sufficient, LlamaIndex dropped
- [x] Lead qualification: Jinja2 prompt template + Anthropic SDK + output validation
- [x] Letter generation: Jinja2 templates + Claude + asyncio.run() bridge in Celery
- [x] FL letter templates: tax deed, foreclosure, excess proceeds (Jinja2 prompts created)
- [x] PDF generation: ReportLab for print-ready letters
- [x] Celery app config: Redis broker (db 2), retry policy (exponential backoff, max_retries=3), DLQ
- [x] Celery task timeouts: task_time_limit=600, task_soft_time_limit=540
- [x] Celery rag queue: worker_concurrency=4, Redis semaphore for Anthropic rate limiting
- [x] Ingestion tasks: scrape county → normalize → dedup → store leads → generate embeddings
- [x] Qualification tasks: batch qualify with asyncio.run() bridge
- [x] Letter tasks: batch generate with asyncio.run() bridge
- [x] Celery Beat schedule: daily county scrapes, monthly credit reset
- [x] Lead claim/release service: atomic operations with concurrency protection
- [x] LLM usage logging: input/output tokens, estimated cost per call
- [x] Task status tracking: GET /tasks/{task_id} polling endpoint
- [x] Wire qualify/letter-generate API endpoints to dispatch real Celery tasks

### P1 — API Endpoints (Week 3-4)

- [x] GET /auth/me — current user + subscription
- [x] POST /auth/webhook — Clerk webhook (svix verification)
- [x] DELETE /auth/me — account deletion (30-day grace, CCPA)
- [x] GET /leads — browse all leads (cursor pagination, filters: county, surplus range, sale_date)
- [x] GET /leads/{id} — lead detail
- [x] POST /leads/{id}/claim — atomic claim
- [x] POST /leads/{id}/release — unclaim
- [x] GET /leads/mine — claimed leads with pipeline status
- [x] PATCH /leads/{id} — update status/priority (status transition validation)
- [x] POST /leads/{id}/qualify — trigger qualification (async 202, idempotency key)
- [x] POST /leads/bulk-qualify — batch qualify (async, returns task_id)
- [x] POST /leads/{id}/skip-trace — disabled in MVP, returns 501
- [x] POST /letters/generate — generate single letter (idempotency key)
- [x] POST /letters/generate-batch — batch generate (async)
- [x] GET /letters — list user's letters
- [x] GET /letters/{id} — letter detail
- [x] PATCH /letters/{id} — edit/approve letter
- [x] DELETE /letters/{id} — delete draft letter
- [x] GET /letters/{id}/pdf — download PDF
- [x] GET /counties — list counties with lead counts
- [x] POST /billing/checkout — Stripe checkout session
- [x] GET /billing/subscription — subscription + credits + usage %
- [x] POST /billing/webhook — Stripe webhook (signature verification)
- [x] GET /billing/portal — Stripe billing portal URL
- [x] GET /tasks/{task_id} — poll task status

### P1 — Frontend (Week 5-7)

- [x] React app scaffolding: Vite + shadcn/ui + Tailwind + React Router v6
- [x] Clerk provider: @clerk/clerk-react setup
- [x] React Query provider
- [x] API client: fetch wrapper with Clerk token interceptor
- [x] App shell: sidebar (collapsible) + header + breadcrumbs
- [x] Onboarding wizard: county select → polling progress → top 10 leads → generate letter → edit → download
- [x] Lead browse page: data table with server-side pagination, filters (county, surplus range, sale date)
- [x] My Leads page: claimed leads table with status, quality score filters
- [x] Lead detail drawer: property info, owner, surplus amount, quality score, letters, activities
- [x] Lead claim/release buttons
- [x] Letter preview: view generated letter content
- [x] Letter inline editor: edit content before approving
- [x] Letter approve + PDF download flow
- [x] Letter batch dialog: select multiple leads, generate batch
- [x] Billing: plan selector with tier comparison
- [x] Billing: subscription status + credit usage display
- [x] Billing: usage warning banner at 80%, hard prompt at 100%
- [x] County browser: list with lead counts, last scraped timestamp
- [x] Settings page: profile, subscription management
- [x] Skip trace button: "Coming soon" disabled state
- [x] Empty states: all pages (helpful CTAs)
- [x] Error states: all pages (retry button + support message)
- [x] Loading states: skeleton UI on all data-fetching pages

### P2 — Pre-Launch

- [x] Create pre_ingest.py script for active counties (run at deploy time)
- [ ] Verify staging environment with real Stripe test webhooks
- [ ] Verify staging environment with real Clerk webhooks
- [ ] Run full launch checklist (see Security P0 above)
- [x] Concurrency test: credit deduction under parallel requests
- [x] Concurrency test: lead claiming under parallel requests
- [x] Tenant isolation test: verify user A cannot see user B's data on every endpoint

### Manual Tasks (Human Required)

#### Stripe Configuration
- [x] Create metered overage prices in Stripe Dashboard for each paid plan:
  - Qualification overage: `price_1TJkI5ACGBKrDLNGbmTqHnBN`
  - Letter overage: `price_1TJkI5ACGBKrDLNGMHiuUpgj`
  - Skip trace overage: `price_1TLBNmACGBKrDLNGGuLlUdXu`
  - Mailing overage: `price_1TL9AWACGBKrDLNGCsDQptXj`
  - Price IDs set as env vars on Railway (api + worker)
- [x] Run `scripts/create_stripe_products.sh` if not already done

#### Clerk Configuration
- [x] Enable email verification: Clerk Dashboard > Email, Phone, Username > Require email verification

#### Pending County Data Requests (4 Counties)

These counties do not publish bulk surplus fund lists online. Contact each to request access:

- [ ] **Duval County** — Email Ask.Taxdeeds@DuvalClerk.com:
  > "We are a surplus funds recovery firm. Is there a way to obtain a bulk list of unclaimed surplus/excess proceeds from tax deed sales? We'd prefer CSV or PDF format if available."

- [x] **Lee County** — Public weekly tax deed surplus reports confirmed on Lee Clerk site on 2026-04-12; manual outreach no longer required unless automated access fails.

- [ ] **Miami-Dade County** — Call (305) 275-1155 (Foreclosure Unit):
  > Ask for a list of unclaimed surplus funds from tax deed/foreclosure sales. Ask about format, frequency, and cost.

- [ ] **Palm Beach County** — Call (561) 355-2962 (Clerk of Courts):
  > Ask about the surplus report in Clerk Cart — cost, format, and bulk/recurring options.

- [ ] **Orange County** — Call (407) 836-5116 (Comptroller's Office):
  > Ask whether they maintain a local surplus funds list or if everything goes to fltreasurehunt.gov. Ask if data is available before state transfer.

#### Staging Verification (After Code Complete)
- [ ] Test Stripe webhooks on staging: `stripe listen --forward-to <staging-url>/api/v1/billing/webhook`
- [ ] Test Clerk webhooks on staging: configure endpoint in Clerk Dashboard
- [ ] Run `python scripts/pre_ingest.py` on staging to seed initial leads
- [ ] Verify staging with real Stripe test payment flow
- [ ] Verify staging with real Clerk sign-up flow

---

## Phase 2: Retention & Polish (Weeks 8-12)

### P1

- [x] Email provider integration (SendGrid) — `services/email/sendgrid.py`, Celery email tasks
- [x] Daily lead alerts: email new high-value leads in user's counties — `workers/email_tasks.py`
- [x] SSE endpoint: GET /tasks/{task_id}/stream via Redis pub/sub — `core/sse.py`, frontend `use-task-stream.ts` with polling fallback
- [x] Status transition validation: enforce allowed state machine transitions — `VALID_TRANSITIONS` in `lead_service.py`
- [x] Lead activity timeline / audit log UI — `LeadActivity` model, `activity-timeline.tsx` with infinite scroll + notes
- [x] "Mark deal as paid/closed" flow — `deal-outcome-dialog.tsx`, `feedback_service.py` outcome correlation
- [x] Skip trace integration: abstract interface + SkipSherpa and Tracerfy providers — `services/skip_trace/`, factory pattern, Celery tasks, full frontend UI
- [x] Lob.com integration: letter mailing API — `services/mailing/lob.py`, `workers/mailing_tasks.py`, webhook handler

### P1 — County Scraping Maintenance

- [x] Activate remaining counties: Collier, Columbia, Marion, Martin, Lee, Leon, Polk, Pinellas — all activated via PlaywrightHtmlScraper, PlaywrightPdfScraper, and ParentPagePdfScraper
- [x] Fix 403/bot-blocked scrapers: Pinellas (PlaywrightPdfScraper), Columbia/Lee/Leon (PlaywrightHtmlScraper) — Broward fixed via `cloudscraper_html.py`
- [x] Polk reactivated with new domain polkcountyclerk.net via PlaywrightHtmlScraper
- [x] Pinellas reactivated via PlaywrightPdfScraper (was 403 Cloudflare)
- [x] Refresh county access classifications from live clerk sources (2026-04-12): Alachua→Web Form, Charlotte→Web Form, Citrus→Email, Clay→Web Form, Escambia→Email, Flagler→Web Form, Hernando→Web Form, Lake→Web Form, Monroe→Phone, Nassau→Web Form, St. Johns→Web Form, Sarasota→Web Form, Seminole→Web Form, St. Lucie→Phone
- [x] Monthly scraper URL health check — `scripts/check_county_urls.py` created
- [x] Update `scripts/fl_county_surplus_research.csv` when county URLs change

### Manual Tasks — County Outreach

- [x] **Lee County** — Public weekly tax deed surplus reports confirmed on Lee Clerk site on 2026-04-12; manual outreach no longer required unless automated access fails
- [ ] **Duval County** — Email Ask.Taxdeeds@DuvalClerk.com requesting bulk download (currently interactive search only)
- [ ] **Miami-Dade County** — Call 305-275-1155 (Foreclosure Unit) requesting surplus fund list
- [ ] **Palm Beach County** — Call 561-355-2962 to inquire about Clerk Cart surplus report cost/format
- [ ] **Orange County** — Call 407-836-5116 to confirm data goes to fltreasurehunt.gov or if local list available

### P2

- [x] ROI dashboard: `roi-stats.tsx` — total recovered, fees earned, deals closed, avg days to close
- [x] Pipeline metrics: `pipeline-funnel.tsx` — 7-stage Recharts funnel (new→qualified→contacted→signed→filed→paid→closed)
- [ ] Multi-county upsell prompts ("You've qualified 90% of Hillsborough leads...")
- [ ] Expand to 20+ FL counties — currently 17 active (5 original + 12 new). 33 identified as scrapable.
- [ ] Qualification result caching: skip re-qualification of unchanged leads
- [ ] Contract generation: template-based with Claude filling case-specific fields

---

## Phase 3: Geographic Expansion (Weeks 13-16)

### P1

- [ ] California county parsers (excess proceeds)
- [ ] Georgia, Texas, Ohio county parsers
- [ ] State-specific letter templates and legal disclosures
- [ ] Expand to all 33 scrapable FL counties (see `scripts/fl_county_surplus_research.csv`). Remaining 34 require phone/email/payment.

### P2

- [ ] API access tier for power users
- [ ] E-sign integration (DocuSign/HelloSign)
- [ ] Kanban board for pipeline management (@dnd-kit)
- [ ] Advanced analytics dashboard (recharts)

---

## Phase 4: Attorney Marketplace (After 200+ active users)

### P1

- [ ] Attorney registration + profile management
- [ ] Agent → Attorney matching (manual first, then automated)
- [ ] Referral fee tracking (5-10% per closed deal)

### P2

- [ ] Ratings system
- [ ] Self-serve marketplace (only after proving unit economics with 20+ manually brokered deals)
