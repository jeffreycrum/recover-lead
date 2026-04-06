# RecoverLead Tasks

Ordered by phase and severity. Check off tasks as completed.

---

## Phase 1: Deployable MVP (Weeks 1-7)

### P0 — Security (must complete before any user touches production)

- [ ] Row-level tenant isolation on all queries (user_leads, letters, contacts, activities)
- [ ] Stripe webhook signature verification (`stripe.Webhook.construct_event()`)
- [ ] Clerk webhook svix verification
- [ ] Atomic credit deduction (no race conditions) — `UPDATE ... WHERE credits_remaining > 0 RETURNING`
- [ ] Atomic lead claiming (no double-claims) — `UPDATE ... WHERE user_id IS NULL RETURNING`
- [ ] Idempotency keys on all mutation POST endpoints (Redis, 24h TTL)
- [ ] Input sanitization on scraper-sourced data (strip control chars, limit length)
- [ ] LLM output validation (quality_score 1-10, letter content patterns)
- [ ] CHECK constraints on all bounded fields (surplus_amount, quality_score, confidence, fee_percentage)
- [ ] Free tier email verification required (Clerk setting)
- [ ] No PII in logs (structlog filter)
- [ ] CORS restricted to known origins (`CORS_ORIGINS` env var)
- [ ] HTTPS everywhere (Railway TLS)
- [ ] Rate limiting active on all tiers

### P0 — Infrastructure (Week 1-2)

- [ ] Project scaffolding: FastAPI app factory, Docker Compose, pyproject.toml
- [ ] Alembic setup + initial migration
- [ ] Database models: users, leads, user_leads, counties, letters, letter_templates, subscriptions, skip_trace_credits, llm_usage, failed_tasks
- [ ] pgvector extension enabled, HNSW index on leads.embedding
- [ ] Clerk integration: JWT middleware (`clerk-backend-api`), svix webhook handler, user sync to local users table
- [ ] Stripe billing: checkout sessions, webhook handler (signature verification), subscription CRUD, credit metering
- [ ] Stripe overage: metered billing for overages, soft wall at 80%, hard prompt at 100%
- [ ] structlog setup: JSON output, request_id propagation, PII filter
- [ ] Sentry integration: error tracking + performance monitoring
- [ ] CORS middleware configuration
- [ ] DB connection pool sizing: API (pool_size=5, max_overflow=10), Celery (pool_size=2, max_overflow=3)
- [ ] Redis separation: db 0 cache, db 1 rate limiting, db 2 Celery broker
- [ ] Railway deployment config: railway.toml, production + staging environments
- [ ] CI/CD: GitHub Actions (lint ruff/eslint → type check mypy/tsc → test → deploy to Railway on main)
- [ ] docker-compose.test.yml for Celery integration tests with real Redis
- [ ] Health endpoints: GET /health/live, GET /health/ready (Postgres + Redis check)
- [ ] Rate limiter: Redis-based, tier-aware, headers (X-RateLimit-*)
- [ ] Idempotency middleware: Redis-backed, 24h TTL

### P1 — Core Pipeline (Week 3-4)

- [ ] Base scraper framework: abstract base class with fetch(), parse(), normalize()
- [ ] PDF scraper: pdfplumber extraction
- [ ] HTML table scraper: BeautifulSoup extraction
- [ ] CSV scraper
- [ ] Normalizer: raw data → Lead schema, hash on normalized business keys (county_id || case_number || parcel_id || owner_name_normalized)
- [ ] Seed all 67 FL county configs (top 10 active, rest inactive)
- [ ] Build scrapers for top 10 FL counties: Hillsborough, Miami-Dade, Broward, Orange, Palm Beach, Pinellas, Duval, Lee, Polk, Volusia
- [ ] Fixture-based scraper tests (saved HTML/PDF from actual county sites)
- [ ] Scraper failure alerting via Sentry
- [ ] Embedding pipeline: sentence-transformers wrapper, model loaded via worker_init signal
- [ ] Vector search: raw pgvector queries (`SELECT ... ORDER BY embedding <=> $1 LIMIT 5`)
- [ ] Evaluate LlamaIndex: does VectorStoreIndex add value over raw pgvector? Decision: keep or drop
- [ ] Lead qualification: Jinja2 prompt template + Anthropic SDK + output validation
- [ ] Letter generation: Jinja2 templates + Claude + asyncio.run() bridge in Celery
- [ ] FL letter templates: tax deed, foreclosure, excess proceeds
- [ ] PDF generation: ReportLab for print-ready letters
- [ ] Celery app config: Redis broker (db 2), retry policy (exponential backoff, max_retries=3), DLQ
- [ ] Celery task timeouts: task_time_limit=600, task_soft_time_limit=540
- [ ] Celery rag queue: worker_concurrency=4, Redis semaphore for Anthropic rate limiting
- [ ] Ingestion tasks: scrape county → normalize → dedup → store leads → generate embeddings
- [ ] Qualification tasks: batch qualify with asyncio.run() bridge
- [ ] Letter tasks: batch generate with asyncio.run() bridge
- [ ] Celery Beat schedule: daily county scrapes, monthly credit reset
- [ ] Lead claim/release service: atomic operations with concurrency protection
- [ ] LLM usage logging: input/output tokens, estimated cost per call
- [ ] Task status tracking: GET /tasks/{task_id} polling endpoint

### P1 — API Endpoints (Week 3-4)

- [ ] GET /auth/me — current user + subscription
- [ ] POST /auth/webhook — Clerk webhook (svix verification)
- [ ] DELETE /auth/me — account deletion (30-day grace, CCPA)
- [ ] GET /leads — browse all leads (cursor pagination, filters: county, surplus range, sale_date)
- [ ] GET /leads/{id} — lead detail
- [ ] POST /leads/{id}/claim — atomic claim
- [ ] POST /leads/{id}/release — unclaim
- [ ] GET /leads/mine — claimed leads with pipeline status
- [ ] PATCH /leads/{id} — update status/priority (status transition validation)
- [ ] POST /leads/{id}/qualify — trigger qualification (async 202, idempotency key)
- [ ] POST /leads/bulk-qualify — batch qualify (async, returns task_id)
- [ ] POST /leads/{id}/skip-trace — disabled in MVP, returns 501
- [ ] POST /letters/generate — generate single letter (idempotency key)
- [ ] POST /letters/generate-batch — batch generate (async)
- [ ] GET /letters — list user's letters
- [ ] GET /letters/{id} — letter detail
- [ ] PATCH /letters/{id} — edit/approve letter
- [ ] DELETE /letters/{id} — delete draft letter
- [ ] GET /letters/{id}/pdf — download PDF
- [ ] GET /counties — list counties with lead counts
- [ ] POST /billing/checkout — Stripe checkout session
- [ ] GET /billing/subscription — subscription + credits + usage %
- [ ] POST /billing/webhook — Stripe webhook (signature verification)
- [ ] GET /billing/portal — Stripe billing portal URL
- [ ] GET /tasks/{task_id} — poll task status

### P1 — Frontend (Week 5-7)

- [ ] React app scaffolding: Vite + shadcn/ui + Tailwind + React Router v6
- [ ] Clerk provider: @clerk/clerk-react setup
- [ ] React Query provider
- [ ] API client: fetch wrapper with Clerk token interceptor
- [ ] App shell: sidebar (collapsible) + header + breadcrumbs
- [ ] Onboarding wizard: county select → polling progress → top 10 leads → generate letter → edit → download
- [ ] Lead browse page: data table with server-side pagination, filters (county, surplus range, sale date)
- [ ] My Leads page: claimed leads table with status, quality score filters
- [ ] Lead detail drawer: property info, owner, surplus amount, quality score, letters, activities
- [ ] Lead claim/release buttons
- [ ] Letter preview: view generated letter content
- [ ] Letter inline editor: edit content before approving
- [ ] Letter approve + PDF download flow
- [ ] Letter batch dialog: select multiple leads, generate batch
- [ ] Billing: plan selector with tier comparison
- [ ] Billing: subscription status + credit usage display
- [ ] Billing: usage warning banner at 80%, hard prompt at 100%
- [ ] County browser: list with lead counts, last scraped timestamp
- [ ] Settings page: profile, subscription management
- [ ] Skip trace button: "Coming soon" disabled state
- [ ] Empty states: all pages (helpful CTAs)
- [ ] Error states: all pages (retry button + support message)
- [ ] Loading states: skeleton UI on all data-fetching pages

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
