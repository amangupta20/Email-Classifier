# Tasks: Intelligent Inbox Email Classification

**Input**: Design artifacts in `/specs/001-i-am-building/`
**Prerequisites**: [`plan.md`](specs/001-i-am-building/plan.md), [`research.md`](specs/001-i-am-building/research.md), [`data-model.md`](specs/001-i-am-building/data-model.md), [`contracts/`](specs/001-i-am-building/contracts/), [`quickstart.md`](specs/001-i-am-building/quickstart.md)

---

## Initiative Snapshot

- **Architecture**: Two-phase delivery
  - **V1 (Rapid Validation)**: n8n workflows orchestrate the IMAP → RAG → LLM → PostgreSQL pipeline while FastAPI + React provide the dashboard.
  - **V2 (Production Worker)**: Pure Python services replace n8n while preserving the shared API, React UI, Gmail integration, monitoring, and schema.
- **Targets**: <5s median poll-to-tag latency, <12s p95, strict schema v2 validation, local-only processing, Gmail labels synced with taxonomy, complete observability.
- **Shared Components**: PostgreSQL (self-hostable via Supabase), Prometheus + Grafana, FastAPI dashboard, React UI, Gmail automation, contract/integration test suite, dockerized infrastructure.
- **Validation**: [`quickstart.md`](specs/001-i-am-building/quickstart.md) defines end-to-end acceptance flows; contract tests live in [`contracts/test_contracts.py`](specs/001-i-am-building/contracts/test_contracts.py).

---

## Findings in Prior Task List (Outdated / Incomplete)

1. **Phase coverage gap** – Previous list omitted every n8n workflow deliverable despite being mandatory for V1 validation.
2. **Status drift** – Setup tasks marked `[x]` although branches/files show incomplete work (Alembic, config loader, tests).
3. **TDD violation** – Tests were enumerated once but not ordered per subsystem; several V2 components lacked pre-implementation failing tests.
4. **Schema alignment** – Model/repository tasks referenced files not defined in [`plan.md`](specs/001-i-am-building/plan.md) (e.g., `history.py`) and missed entities defined in [`data-model.md`](specs/001-i-am-building/data-model.md).
5. **Dependency clarity** – Cross-cutting services (metrics, Gmail) lacked explicit dependencies, making sequencing ambiguous.
6. **Validation gap** – Contract coverage ignored [`contracts/dashboard_api.yaml`](specs/001-i-am-building/contracts/dashboard_api.yaml) sections (e.g., `/admin` endpoints) and no tasks ensured quickstart execution.
7. **Migration path** – No tasks described V1→V2 A/B testing, switchover, or V1 decommissioning outlined in the implementation plan.

---

## Format

`[ID] [P?] Description — Rationale — Depends on`

- `[P]` indicates tasks that can run in parallel (different files, no shared migration state).
- File references use repository-relative paths.

---

## Phase 0 — Environment & Foundations

### Setup (shared for V1 & V2)

- [x] T001 Bring repo state to clean baseline (ensure `.venv`, docker volumes, seed data) — Aligns working copy with plan prerequisites — Depends on: none
- [x] T002 Configure Alembic scaffolding in [`backend/alembic.ini`](backend/alembic.ini) and [`backend/src/database/migrations/env.py`](backend/src/database/migrations/env.py) — Enables versioned schema delivery — Depends on: T001
- [x] T003 [P] Generate initial migration for entities defined in [`data-model.md`](specs/001-i-am-building/data-model.md) — Creates authoritative DB schema for both versions — Depends on: T002
- [x] T004 [P] Implement configuration loader in [`backend/src/config.py`](backend/src/config.py) with Pydantic Settings validating `.env` contract — Guarantees deterministic environment checks — Depends on: T001
- [x] T005 [P] Harden Docker Compose stack with services for Ollama, PostgreSQL/Supabase, Qdrant, Prometheus, Grafana, n8n — Provides deployable infra baseline — Depends on: T001
- [x] T006 [P] Provision shared fixtures in [`backend/tests/conftest.py`](backend/tests/conftest.py) for DB, IMAP, Ollama, Qdrant, Gmail stubs — Supports TDD workflow — Depends on: T001

---

## Phase 1 — Test-First Safety Net

### Contract Tests (Shared)

- [x] T007 [P] Add JSON schema v2 contract suite in [`backend/tests/contract/test_schema_v2.py`](backend/tests/contract/test_schema_v2.py) using `classification_schema_v2.json` fixtures — Enforces deterministic classifier output — Depends on: T006
- [x] T008 [P] Add dashboard API contract tests in [`backend/tests/contract/test_dashboard_api.py`](backend/tests/contract/test_dashboard_api.py) covering `/metrics`, `/metrics/timeseries`, `/classifications`, `/classifications/reclassify`, `/health`, `/admin` endpoints — Locks API surface before implementation — Depends on: T006
- [x] T009 [P] Add metrics format validation in [`backend/tests/contract/test_metrics_payloads.py`](backend/tests/contract/test_metrics_payloads.py) — Ensures observability payloads stay schema-aligned — Depends on: T006

### Integration Scenarios (Shared Quickstart)

- [x] T010 Write failing end-to-end poll→classify→persist test in [`backend/tests/integration/test_poll_classify_persist.py`](backend/tests/integration/test_poll_classify_persist.py) — Validates primary user flow described in spec — Depends on: T006
- [ ] T011 [P] Add idempotency scenario test in [`backend/tests/integration/test_idempotency.py`](backend/tests/integration/test_idempotency.py) — Guarantees duplicate protection — Depends on: T006
- [ ] T012 [P] Add feedback loop test in [`backend/tests/integration/test_feedback_loop.py`](backend/tests/integration/test_feedback_loop.py) — Secures learning requirements — Depends on: T006
- [ ] T013 [P] Add error-handling/quarantine test in [`backend/tests/integration/test_error_handling.py`](backend/tests/integration/test_error_handling.py) — Covers resilience mandate — Depends on: T006
- [ ] T014 [P] Add dashboard realtime regression test in [`backend/tests/integration/test_dashboard_realtime.py`](backend/tests/integration/test_dashboard_realtime.py) — Confirms 5s refresh behavior — Depends on: T006
- [ ] T015 [P] Add Gmail labeling integration test in [`backend/tests/integration/test_gmail_labels.py`](backend/tests/integration/test_gmail_labels.py) — Guarantees label sync semantics — Depends on: T006
- [ ] T016 [P] Add monitoring pipeline test validating Prometheus exposure in [`backend/tests/integration/test_metrics_export.py`](backend/tests/integration/test_metrics_export.py) — Protects observability story — Depends on: T006
- [ ] T017 [P] Add frontend component smoke tests (MetricsCard, TimeSeriesChart) in [`frontend/tests/components/`](frontend/tests/components/) — Locks UI contract pre-implementation — Depends on: T006

---

## Phase 2 — Version 1 (n8n Prototype Delivery)

### V1.A Foundation (Shared Components)

- [ ] T018 Populate taxonomy/tag seed migration in [`backend/src/database/migrations/`](backend/src/database/migrations/) — Ensures schema ships with constitution tags — Depends on: T003
- [ ] T019 Populate `.env.example` & secrets template aligning with [`quickstart.md`](specs/001-i-am-building/quickstart.md) — Removes ambiguity for operators — Depends on: T004
- [ ] T020 Define Prometheus collectors + Grafana provisioning in [`infra/monitoring/`](infra/monitoring/) — Prepares monitoring stack for V1 validation — Depends on: T005

### V1.B Workflow Authoring (n8n)

- [ ] T021 Build IMAP polling workflow [`n8n/workflows/email_classification_main.json`](n8n/workflows/email_classification_main.json) step 1 — Establishes periodic fetch based on EMAIL_POLL_INTERVAL — Depends on: T005, T010
- [ ] T022 Extend workflow with RAG retrieval node sequence using Qdrant [`n8n/workflows/email_classification_main.json`](n8n/workflows/email_classification_main.json) step 2 — Provides contextual prompts — Depends on: T021, T010
- [ ] T023 Add Ollama HTTP classification step with JSON validation guard — Implements classifier call — Depends on: T022, T007
- [ ] T024 Connect persistence branch to PostgreSQL node — Writes outputs respecting schema v2 — Depends on: T023, T003
- [ ] T025 Wire Gmail label application sub-flow — Applies primary/secondary categories — Depends on: T024, T015
- [ ] T026 Create error-handling lane with retries + quarantine queue — Satisfies resilience requirements — Depends on: T024, T013
- [ ] T027 Author RAG indexer workflow [`n8n/workflows/rag_indexer.json`](n8n/workflows/rag_indexer.json) — Supports weekly refresh — Depends on: T020, T022
- [ ] T028 Create feedback processor workflow [`n8n/workflows/feedback_processor.json`](n8n/workflows/feedback_processor.json) — Closes learning loop — Depends on: T012

### V1.C Python Services Shared with V2

- [ ] T029 Scaffold FastAPI app in [`backend/src/api/app.py`](backend/src/api/app.py) with DI + middleware skeleton — Prepares API hosting of dashboard — Depends on: T008
- [ ] T030 Implement metrics exporter service in [`backend/src/services/metrics_collector.py`](backend/src/services/metrics_collector.py) for Prometheus counters/histograms — Provides observability for V1 workflows — Depends on: T009, T020
- [ ] T031 Implement schema validator utility in [`backend/src/services/schema_validator.py`](backend/src/services/schema_validator.py) bridging n8n output to Pydantic models — Ensures workflow output compliance — Depends on: T007
- [ ] T032 Implement Gmail client wrapper in [`backend/src/services/gmail_labeler.py`](backend/src/services/gmail_labeler.py) with retries & rate limit handling — Supports V1 workflow actions — Depends on: T015
- [ ] T033 Implement dashboard routes `/metrics`, `/metrics/timeseries`, `/health`, `/classifications`, `/classifications/reclassify`, `/admin` in [`backend/src/api/routes/`](backend/src/api/routes/) — Serves React UI — Depends on: T029, T030

### V1.D React Dashboard Deliverables

- [ ] T034 Bootstrap Vite + React structure per [`frontend/`](frontend/) plan — Provides foundation for UI tasks — Depends on: T033
- [ ] T035 Implement API client in [`frontend/src/services/api.js`](frontend/src/services/api.js) including auth header handling — Abstracts HTTP calls — Depends on: T033
- [ ] T036 Implement metrics visualisations (MetricsCard, TimeSeriesChart, CategoryDistribution) in [`frontend/src/components/`](frontend/src/components/) — Meets monitoring requirements — Depends on: T035
- [ ] T037 Implement ActivityFeed, SystemHealth, AdminControls components in [`frontend/src/components/`](frontend/src/components/) — Supports remediation workflows — Depends on: T035
- [ ] T038 Compose dashboard page [`frontend/src/pages/Dashboard.jsx`](frontend/src/pages/Dashboard.jsx) with layout, auto-refresh, CSV export — Delivers spec’d UI — Depends on: T036, T037

### V1.E Monitoring & Validation

- [ ] T039 Configure Prometheus scrape for FastAPI + n8n exporters in [`infra/monitoring/prometheus/prometheus.yml`](infra/monitoring/prometheus/prometheus.yml) — Enables metric collection — Depends on: T030
- [ ] T040 Provision Grafana dashboard per plan in [`infra/monitoring/grafana/dashboards/backend-overview.json`](infra/monitoring/grafana/dashboards/backend-overview.json) — Visual validation for resume — Depends on: T039
- [ ] T041 Execute quickstart validation steps capturing screenshots & notes — Confirms V1 readiness — Depends on: T021-T040
- [ ] T042 Document V1 operational guide in [`README.md`](README.md) / `docs/` as per quickstart — Supports transition to V2 — Depends on: T041

---

## Phase 3 — Version 2 (Pure Python Worker)

### V2.A Core Services

- [ ] T043 Implement entity models in [`backend/src/models/`](backend/src/models/) (Email, ClassificationResult, Tag, ClassificationCycle, SystemConfig, UserFeedback, DashboardMetric, SystemHealthStatus) per [`data-model.md`](specs/001-i-am-building/data-model.md) — Establishes Python data layer — Depends on: T003, T007
- [ ] T044 Implement repositories in [`backend/src/database/repositories.py`](backend/src/database/repositories.py) for CRUD/query patterns — Enables worker persistence — Depends on: T043
- [ ] T045 Implement email_poller service in [`backend/src/services/email_poller.py`](backend/src/services/email_poller.py) using imap-tools with idempotency keys — Replaces n8n trigger — Depends on: T044, T011
- [ ] T046 Implement queue_manager in [`backend/src/services/queue_manager.py`](backend/src/services/queue_manager.py) (exactly-once semantics) — Manages pipeline flow — Depends on: T044, T011
- [ ] T047 Implement rag_retriever in [`backend/src/services/rag_retriever.py`](backend/src/services/rag_retriever.py) supporting Qdrant/Supabase — Supplies context for classifier — Depends on: T044, T022
- [ ] T048 Implement llm_classifier in [`backend/src/services/llm_classifier.py`](backend/src/services/llm_classifier.py) with Ollama client + JSON parsing — Provides classification engine — Depends on: T047, T007
- [ ] T049 Implement feedback_processor in [`backend/src/services/feedback_processor.py`](backend/src/services/feedback_processor.py) updating RAG KB — Maintains learning loop — Depends on: T044, T012
- [ ] T050 Implement metrics_collector (Python worker flavours) in [`backend/src/services/metrics_collector.py`](backend/src/services/metrics_collector.py) — Extends observability to V2 — Depends on: T030
- [ ] T051 Implement circuit breaker & retry utilities in [`backend/src/utils/`](backend/src/utils/) — Enforces resilience policies — Depends on: T013

### V2.B Orchestration & API Integration

- [ ] T052 Assemble classifier_worker orchestrator in [`backend/src/worker/classifier_worker.py`](backend/src/worker/classifier_worker.py) covering poll→classify→persist→label→emit metrics — Core runtime loop — Depends on: T045-T050
- [ ] T053 Implement scheduler in [`backend/src/worker/scheduler.py`](backend/src/worker/scheduler.py) (APScheduler + graceful shutdown) — Guarantees interval compliance — Depends on: T052
- [ ] T054 Integrate worker with Gmail labeler & feedback_processor hooks — Keeps Gmail + learning consistent — Depends on: T032, T049, T052
- [ ] T055 Wire API routes to repositories/services ensuring parity with V1 endpoints — Maintains shared contract — Depends on: T033, T044

### V2.C Test-hardening & Performance

- [ ] T056 Expand integration tests to cover Python worker path (reuse T010-T016 with real services) — Confirms parity with V1 — Depends on: T052-T055
- [ ] T057 Add unit tests per service (`tests/unit/`) ensuring coverage >80% — Delivers maintainability — Depends on: T045-T055
- [ ] T058 Benchmark end-to-end latency & memory, tune configuration, capture results — Confirms performance targets — Depends on: T056
- [ ] T059 Document performance findings & tuning guide in [`docs/performance.md`](docs/performance.md) — Provides resume-ready data — Depends on: T058

### V2.D Migration & Decommission

- [ ] T060 Run A/B comparison (V1 vs V2) using shared DB, log deltas — Validates equivalence — Depends on: T041, T056
- [ ] T061 Implement switchover playbook (toggle env flags, scheduler enable/disable) — Ensures reversible launch — Depends on: T060
- [ ] T062 Decommission n8n workflows (archive JSON, update docs) — Finalizes migration — Depends on: T061

---

## Phase 4 — Polish & Release Readiness

- [ ] T063 Compile final quickstart walkthrough with screenshots & video for portfolio — Storytelling requirement — Depends on: T041, T062
- [ ] T064 Update root [`README.md`](README.md) + deployment instructions covering both versions & switchover — Ensures newcomer onboarding — Depends on: T063
- [ ] T065 Run full automation suite (`pytest`, lint, type-check, contract tests) and publish coverage badge — Project quality bar — Depends on: T057
- [ ] T066 Prepare resume/demo artifacts (Grafana exports, dashboard GIF, architecture diagram) — Completes initiative goal — Depends on: T063, T058

---

## Dependency Summary

- Phase 0 precedes all; contract + integration tests (Phase 1) must fail before implementation begins.
- V1 tasks (Phase 2) depend on successful test scaffolding and shared infrastructure.
- V2 tasks (Phase 3) rely on repositories, utilities, and validated V1 contracts to ensure parity.
- Polish (Phase 4) requires functional V2 and documented migration.
- Parallel `[P]` tasks only when files and state are isolated to prevent merge conflicts.

---

## Parallel Execution Examples

```
# Example 1 – Early setup
T002 (Alembic env) → T003 [P] (initial migration)
T004 [P] (config loader) alongside T005 [P] (docker updates)

# Example 2 – Contract stage
T007 [P], T008 [P], T009 [P] can run concurrently once fixtures (T006) exist.

# Example 3 – n8n workflows
T021 → T022 → T023 must remain sequential, while T027 [P] and T028 [P] can proceed after T022.

# Example 4 – Python worker services
T045-T048 share repositories; after T047 completes, T048 and T049 [P] can run in parallel.
```

---

## Validation Checklist

- [ ] All contracts and integration tests fail before implementation, then pass post-implementation
- [ ] Schema v2 enforced end-to-end (n8n + Python)
- [ ] Dashboard renders metrics, activity, health, admin controls with 5s refresh
- [ ] Gmail labels created/applied per taxonomy (primary + <=3 secondary)
- [ ] Prometheus + Grafana dashboards operational with historical data
- [ ] Median latency <5s, p95 <12s verified after V2 switchover
- [ ] Migration plan executed: V1 validated → V2 A/B → switchover → n8n decommissioned
- [ ] Documentation updated (quickstart, deployment, performance, resume assets)

_Total: 66 tasks (approx. 3–5 days for V1, 5–7 days for V2, excluding polish)._
Commit after each task using the task ID (e.g., `T021: scaffold IMAP polling workflow`).
Execute tasks on branches named after the task ID to comply with repo policy.
