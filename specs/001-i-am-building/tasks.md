# Tasks: Intelligent Inbox Email Classification

**Input**: Design artifacts in `/specs/001-i-am-building/`  
**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)

```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
   → quickstart.md: Extract test scenarios
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`
- Paths follow the structure from plan.md

## Phase 3.1: Setup

- [ ] T001 Create project structure per plan.md: Create `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, `README.md`, `pyproject.toml`, `package.json` in root.
- [ ] T002 Initialize Python backend with dependencies: Install FastAPI, SQLAlchemy, Pydantic v2, Alembic, asyncpg, ollama, qdrant-client, imap-tools, APScheduler, prometheus-client, structlog, cryptography, tenacity, httpx from requirements.txt in `backend/`.
- [ ] T003 Setup Docker Compose for Ollama (GPU), PostgreSQL, Qdrant, Prometheus, Grafana in `docker-compose.yml`, including environment variables and volume mounts for self-hosted Supabase option.
- [ ] T004 [P] Configure Python linting and formatting: Setup ruff, black, pre-commit hooks in `backend/pyproject.toml` and `.pre-commit-config.yaml`.
- [ ] T005 [P] Initialize frontend React app with Vite: Create `frontend/package.json`, install React, Recharts, Axios, date-fns, setup ESLint, Prettier in `frontend/.eslintrc.js` and `frontend/prettier.config.js`.
- [ ] T006 Setup Alembic database migrations: Configure `backend/alembic.ini`, create migration environment in `backend/src/database/migrations/env.py`, prepare initial schema migration.
- [ ] T007 [P] Create configuration loader: Implement `backend/src/config.py` using Pydantic Settings to load `.env` with validation for all env vars (DB_URL, OLLAMA_HOST, QDRANT_HOST, IMAP settings, etc.).

## Phase 3.2: Tests First (TDD) ⚠️ MUST FAIL BEFORE 3.3

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

- [ ] T008 [P] Contract test for JSON schema v2 validation in `backend/tests/contract/test_classification_schema_v2.py`: Load schema from `contracts/classification_schema_v2.json`, test valid/invalid samples (missing fields, wrong types, array lengths).
- [ ] T009 [P] Contract test for dashboard API responses in `backend/tests/contract/test_dashboard_api.py`: Mock FastAPI responses for /metrics, /health, /classifications, validate against OpenAPI schemas from `contracts/dashboard_api.yaml`.
- [ ] T010 [P] Integration test for poll → classify → persist flow in `backend/tests/integration/test_poll_classify_persist.py`: Mock IMAP, Ollama, Qdrant, verify email in DB after full cycle.
- [ ] T011 [P] Integration test for idempotency in `backend/tests/integration/test_idempotency.py`: Process same email twice, assert no duplicate classifications in DB.
- [ ] T012 [P] Integration test for feedback loop in `backend/tests/integration/test_feedback_loop.py`: Submit correction, verify RAG KB update, re-process similar email with improved classification.
- [ ] T013 [P] Integration test for error handling in `backend/tests/integration/test_error_handling.py`: Simulate malformed email, verify quarantine status, batch continues without failure.
- [ ] T014 [P] Integration test for dashboard realtime metrics in `backend/tests/integration/test_dashboard_realtime.py`: Start worker, assert metrics update every 5s via /metrics/current endpoint.
- [ ] T015 [P] Integration test for Gmail label application in `backend/tests/integration/test_gmail_labels.py`: Mock Gmail API, verify labels applied and created if missing, handle rate limits.
- [ ] T016 [P] Frontend component test for MetricsCard in `frontend/tests/components/MetricsCard.test.jsx`: Render with mock data, verify display of processing time, queue depth.
- [ ] T017 [P] Frontend component test for TimeSeriesChart in `frontend/tests/components/TimeSeriesChart.test.jsx`: Verify chart renders with time-series data, updates on prop change.

## Phase 3.3: Core Implementation (ONLY after tests are failing)

- [ ] T018 [P] Implement Pydantic models for Email, ClassificationResult, Tag, etc. in `backend/src/models/email.py`, `backend/src/models/classification.py`, `backend/src/models/config.py`, `backend/src/models/history.py`, `backend/src/models/dashboard.py`, `backend/src/models/gmail.py`.
- [ ] T019 Implement database repositories for CRUD operations in `backend/src/database/repositories.py`: Add methods for emails, classifications, feedback, metrics, health checks using SQLAlchemy async session.
- [ ] T020 Implement email poller service in `backend/src/services/email_poller.py` [depends: T019]: Use imap-tools to fetch new emails, idempotency via body_hash, update status to 'pending'.
- [ ] T021 Implement queue manager with idempotency in `backend/src/services/queue_manager.py` [depends: T019]: In-memory queue or PostgreSQL table for pending emails, exactly-once semantics.
- [ ] T022 Implement RAG retriever in `backend/src/services/rag_retriever.py` [depends: T019]: Connect to Qdrant/Supabase, generate embeddings with Ollama, retrieve top-K=5 contexts.
- [ ] T023 Implement LLM classifier in `backend/src/services/llm_classifier.py` [depends: T022]: Build prompts from constitution, call Ollama qwen3:8b, parse JSON response.
- [ ] T024 Implement schema validator in `backend/src/services/schema_validator.py` [depends: T018]: Use Pydantic v2 to validate LLM output against schema v2, handle parsing errors.
- [ ] T025 Implement metrics collector in `backend/src/services/metrics_collector.py` [depends: T019]: Prometheus metrics for latencies, queue depth, classification stats, export to /metrics.
- [ ] T026 Implement feedback processor in `backend/src/services/feedback_processor.py` [depends: T019, T022]: Store corrections, update RAG KB incrementally, reclassify similar emails.
- [ ] T027 Implement Gmail label manager in `backend/src/services/gmail_labeler.py` [depends: T019]: Use google-api-python-client to create/apply labels, handle rate limits with retry.
- [ ] T028 Implement utils for crypto, circuit breaker, retry in `backend/src/utils/crypto.py`, `backend/src/utils/circuit_breaker.py`, `backend/src/utils/retry.py` [P].

## Phase 3.4: Integration

- [ ] T029 Implement classification worker in `backend/src/worker/classifier_worker.py` [depends: T020-T027]: Orchestrate poll → RAG → LLM → validate → persist → apply Gmail labels → emit metrics.
- [ ] T030 Implement scheduler in `backend/src/worker/scheduler.py` [depends: T029]: Use APScheduler for 30s polling, background RAG reindexing (weekly cron).
- [ ] T031 Setup FastAPI app in `backend/src/api/app.py` [depends: T028]: Configure middleware, dependency injection, CORS, Prometheus instrumentation.
- [ ] T032 Implement /metrics routes in `backend/src/api/routes/metrics.py` [depends: T031, T025]: Current snapshot, time-series, historical aggregates with query params.
- [ ] T033 Implement /health route in `backend/src/api/routes/health.py` [depends: T031]: Check Ollama, Qdrant/Supabase, PostgreSQL, worker status, return component health.
- [ ] T034 Implement /classifications routes in `backend/src/api/routes/classifications.py` [depends: T031, T019]: GET recent, POST reclassify with queue trigger.
- [ ] T035 Implement admin routes in `backend/src/api/routes/admin.py` [depends: T030, T026, T031]: POST rag/reindex, POST queue/clear, log actions to audit.
- [ ] T036 Implement auth middleware in `backend/src/api/middleware.py` [depends: T031]: Basic auth for admin endpoints, token validation.
- [ ] T037 Integrate Gmail label sync into worker [depends: T029, T027]: Call Gmail API after successful classification, retry failed labels.

## Phase 3.5: Frontend Dashboard

- [ ] T038 Setup React app structure in `frontend/src/` [P]: Create components, services, utils directories, main.jsx entry point, Vite config.
- [ ] T039 Implement API client service in `frontend/src/services/api.js` [depends: T038]: Axios wrappers for /metrics, /health, /classifications, auth headers.
- [ ] T040 Implement MetricsCard component in `frontend/src/components/MetricsCard.jsx` [depends: T039]: Display avg processing time, queue depth, tags/email, realtime updates.
- [ ] T041 Implement TimeSeriesChart component in `frontend/src/components/TimeSeriesChart.jsx` [depends: T039]: Recharts line chart for latency, throughput trends.
- [ ] T042 Implement CategoryDistribution component in `frontend/src/components/CategoryDistribution.jsx` [depends: T039]: Pie/bar chart for category breakdown, confidence distribution.
- [ ] T043 Implement ActivityFeed component in `frontend/src/components/ActivityFeed.jsx` [depends: T039]: List recent emails with tags, confidence, manual correction buttons.
- [ ] T044 Implement SystemHealth component in `frontend/src/components/SystemHealth.jsx` [depends: T039]: Status indicators for Ollama, Qdrant, PostgreSQL, error panel.
- [ ] T045 Implement admin controls in `frontend/src/components/AdminControls.jsx` [depends: T039]: Buttons for reclassify, RAG reindex, queue clear with confirmation dialogs.
- [ ] T046 Compose dashboard page in `frontend/src/pages/Dashboard.jsx` [depends: T040-T045]: Layout with metrics, charts, activity feed, health, export CSV functionality.

## Phase 3.6: Polish

- [ ] T047 [P] Add unit tests for models and validators in `backend/tests/unit/test_models.py`.
- [ ] T048 [P] Add unit tests for services in `backend/tests/unit/test_services.py`.
- [ ] T049 [P] Add frontend unit tests in `frontend/tests/components/*.test.jsx`.
- [ ] T050 Performance optimization: Benchmark end-to-end latency, tune Qdrant indexes, optimize LLM prompts.
- [ ] T051 Update documentation: README.md with setup, deployment, API docs from OpenAPI.
- [ ] T052 Run full integration test suite, fix failures, achieve >80% coverage.
- [ ] T053 Validate quickstart.md: Execute all steps, capture screenshots, verify Gmail labels applied.
- [ ] T054 Prepare demo assets: Record video of dashboard showing real-time classification and Gmail integration for resume.

## Dependencies

- Tests T008-T017 before implementation T018-T037 (TDD principle).
- T018-T028 depend on setup T001-T007.
- T029-T037 depend on models/repositories T018-T019.
- API routes T032-T036 depend on app setup T031.
- Frontend T038-T046 depend on API availability T032-T036.
- Polish T047-T054 depend on all phases completing.

## Parallel Execution Example

```
# Phase 3.1 Setup (independent tasks)
Task: T001 Create project structure
Task: T002 Initialize Python backend
Task: T005 Initialize frontend React app
Task: T007 Create configuration loader

# Phase 3.2 Contracts (different files)
Task: T008 Contract test for JSON schema v2
Task: T009 Contract test for dashboard API
Task: T010 Integration test for poll-classify-persist
Task: T011 Integration test for idempotency
```

## Notes

- [P] tasks = different files, no dependencies (parallel safe).
- Follow strict TDD: Run tests first, ensure they fail, implement to pass.
- Commit after each task with descriptive message (e.g., "T008: Add failing JSON schema contract test").
- Use quickstart.md for manual validation after major milestones.
- For Gmail integration, obtain OAuth credentials from Google Cloud Console.

## Validation Checklist

_GATE: Checked before returning_

- [x] All 2 contracts have corresponding tests (T008-T009)
- [x] All 8 entities have model tasks (T018)
- [x] All 6 API endpoints implemented (T032-T036)
- [x] All 8 integration scenarios covered (T010-T017)
- [x] Frontend components for dashboard (T040-T046)
- [x] Polish tasks include performance and docs (T050-T054)

Tasks ready for execution. Total: 54 tasks, estimated 3-5 days implementation time.
