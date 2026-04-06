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
- [ ] Free tier email verification required (Clerk Dashboard → Email → require verification — configure at deploy time)
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
- [ ] Stripe overage: metered billing for overages, soft wall at 80%, hard prompt at 100% — frontend UI needed
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
- [ ] Build scrapers for top 10 FL counties — scraper classes exist, need to verify/customize source URLs per county
- [x] Fixture-based scraper tests (saved HTML/CSV fixtures, 13 tests passing)
- [x] Scraper failure alerting via Sentry
- [x] Embedding pipeline: sentence-transformers wrapper, model loaded via worker_init signal
- [x] Vector search: raw pgvector queries (`SELECT ... ORDER BY embedding <=> $1 LIMIT 5`)
- [ ] Evaluate LlamaIndex: does VectorStoreIndex add value over raw pgvector? Decision: keep or drop
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
- [ ] Onboarding wizard: county select → polling progress → top 10 leads → generate letter → edit → download
- [x] Lead browse page: data table with server-side pagination, filters (county, surplus range, sale date)
- [x] My Leads page: claimed leads table with status, quality score filters
- [x] Lead detail drawer: property info, owner, surplus amount, quality score, letters, activities
- [x] Lead claim/release buttons
- [x] Letter preview: view generated letter content
- [x] Letter inline editor: edit content before approving
- [x] Letter approve + PDF download flow
- [ ] Letter batch dialog: select multiple leads, generate batch
- [x] Billing: plan selector with tier comparison
- [x] Billing: subscription status + credit usage display
- [x] Billing: usage warning banner at 80%, hard prompt at 100%
- [x] County browser: list with lead counts, last scraped timestamp
- [x] Settings page: profile, subscription management
- [ ] Skip trace button: "Coming soon" disabled state
- [x] Empty states: all pages (helpful CTAs)
- [x] Error states: all pages (retry button + support message)
- [x] Loading states: skeleton UI on all data-fetching pages

### P2 — Pre-Launch

- [ ] Run pre_ingest.py for top 10 counties (at deploy time)
- [ ] Verify staging environment with real Stripe test webhooks
- [ ] Verify staging environment with real Clerk webhooks
- [ ] Run full launch checklist (see Security P0 above)
- [ ] Concurrency test: credit deduction under parallel requests
- [ ] Concurrency test: lead claiming under parallel requests
- [ ] Tenant isolation test: verify user A cannot see user B's data on every endpoint

---

## Phase 2: Retention & Polish (Weeks 8-12)

### P1

- [ ] Email provider integration (SendGrid or Postmark)
- [ ] Daily lead alerts: email new high-value leads in user's counties
- [ ] SSE endpoint: GET /tasks/{task_id}/stream via Redis pub/sub
- [ ] Status transition validation: enforce allowed state machine transitions
- [ ] Lead activity timeline / audit log UI
- [ ] "Mark deal as paid/closed" flow — feed outcome data into qualification feedback loop
- [ ] Skip trace integration: abstract interface + one provider (TLO or IDI)
- [ ] Lob.com integration: letter mailing API (close workflow loop)

### P2

- [ ] ROI dashboard: total recovered amount, per-lead ROI, cumulative value
- [ ] Pipeline metrics: Celery Beat aggregation every 15 minutes
- [ ] Multi-county upsell prompts ("You've qualified 90% of Hillsborough leads...")
- [ ] Expand to 20+ FL counties
- [ ] Qualification result caching: skip re-qualification of unchanged leads
- [ ] Contract generation: template-based with Claude filling case-specific fields

---

## Phase 3: Geographic Expansion (Weeks 13-16)

### P1

- [ ] California county parsers (excess proceeds)
- [ ] Georgia, Texas, Ohio county parsers
- [ ] State-specific letter templates and legal disclosures
- [ ] Expand to all 67 FL counties with online lists

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
