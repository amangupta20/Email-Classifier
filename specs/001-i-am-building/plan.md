# Implementation Plan: Intelligent Inbox Email Classification

**Branch**: `001-i-am-building` | **Date**: 2025-10-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-i-am-building/spec.md`

## Execution Flow (/plan command scope)

```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 8. Phases 2-4 are executed by other commands:

- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary

Build a local-first email classification system in **two progressive versions**:

**Version 1 (V1) - n8n Workflow**: Rapid prototyping using n8n for email polling, RAG retrieval, and LLM classification workflow. Shared components: PostgreSQL database, React dashboard, Gmail API integration, and Grafana monitoring. This version proves the concept and validates the taxonomy with minimal custom code.

**Version 2 (V2) - Pure Python**: Production-grade implementation replacing n8n workflow with custom Python services while retaining all shared infrastructure. Provides full control, testability, and performance optimization. Migration from V1 is seamless as both versions use identical database schema and APIs.

**Common Target**: <5s median classification latency, <12s p95, 45+ hierarchical categories, privacy-preserving local processing with self-hosted Qwen 3 8B LLM.

## Technical Context

**Implementation Strategy**: Two-version progressive approach (V1 → V2)

**Language/Version**: Python 3.11+ (type hints, async/await, dataclasses) + n8n (V1 workflow automation)

**Primary Dependencies**:

**Version 1 (n8n-based)**:

- **Workflow Engine**: n8n (self-hosted, Docker)
- **n8n Nodes**: IMAP Email, HTTP Request (Ollama), HTTP Request (Qdrant API), PostgreSQL, Gmail
- **LLM Inference**: Ollama (Qwen 3 8B) via HTTP Request nodes
- **Vector Store**: Qdrant (accessed via n8n Vector Store nodes)
- **Database**: PostgreSQL (shared with V2)
- **Web Framework**: FastAPI (for dashboard API only)
- **Email Access**: n8n IMAP Trigger node
- **Validation**: n8n JSON Schema validation + Pydantic (dashboard)
- **Testing**: n8n workflow testing + Python API tests
- **Monitoring**: prometheus-client for metrics export

**Version 2 (Pure Python)**:

- **LLM Inference**: Options evaluated in research phase
- **Vector Store**: Qdrant for RAG embeddings (shared service via API)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Database**: PostgreSQL (same schema as V1)
- **Web Framework**: FastAPI (dashboard + worker API)
- **Task Scheduling**: APScheduler or asyncio-based scheduler
- **Email Access**: imaplib (stdlib) or imap-tools
- **Validation**: Pydantic v2 for schema validation
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Monitoring**: prometheus-client for metrics export (same as V1)

**Shared Components (Both Versions)**:

- PostgreSQL database (identical schema)
- React dashboard (connects to FastAPI backend)
- Gmail API integration (Python service)
- Grafana + Prometheus monitoring
- Docker Compose orchestration

**Storage**:

- PostgreSQL for metadata (message index, classifications, action items, thread context)
- Qdrant for vector embeddings (shared RAG service via API)
- Append-only JSONL for audit trail
- Optional AES-256 encrypted email bodies (cryptography library)

**Testing**:

- pytest with fixtures for email samples
- Contract tests using JSON schema validation
- Integration tests with mock IMAP server
- Performance tests validating <5s median latency target

**Target Platform**:

- Linux server (Ubuntu 22.04+, tested on local development machine)
- Docker containerization for easier deployment
- Single-machine deployment (no distributed systems)

**Project Type**:

- **V1**: n8n workflow + Python API backend + React dashboard
- **V2**: Pure Python worker + API backend + React dashboard (same UI)

**Performance Goals**:

- Poll-to-tag median latency: <5s (light load)
- 95th percentile classification: <12s
- RAG retrieval: <50ms p95
- Dashboard API response: <500ms p95
- Memory footprint: <1.2GB with LLM loaded
- Queue throughput: 100+ emails/hour sustained

**Constraints**:

- Local-only processing (privacy requirement)
- No external API calls with email content
- Schema validation strict (fail-fast on unknown fields)
- Exactly-once enqueue semantics
- Idempotent classification (deterministic for same input)

**Scale/Scope**:

- Single user (college student inbox)
- Expected volume: 50-200 emails/day
- Historical data: 10K+ emails for RAG context
- Dashboard handles 10K data points per graph
- 45+ hierarchical categories with up to 4 tags per email

**Version Comparison**:

| Aspect                | V1 (n8n)                   | V2 (Pure Python)             |
| --------------------- | -------------------------- | ---------------------------- |
| **Workflow Logic**    | n8n visual workflows       | Python services              |
| **Development Speed** | Fast (low-code)            | Slower (custom code)         |
| **Testability**       | Limited (workflow tests)   | Full (unit + integration)    |
| **Performance**       | Good (n8n overhead ~100ms) | Excellent (optimized)        |
| **Maintainability**   | n8n GUI + some Python      | Pure Python codebase         |
| **Database**          | PostgreSQL (shared schema) | PostgreSQL (same schema)     |
| **Dashboard**         | React (shared)             | React (same UI)              |
| **Migration Effort**  | N/A                        | Low (swap workflow only)     |
| **Resume Value**      | n8n + Python skills        | Advanced Python architecture |

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

### Core Principles Compliance

✅ **I. Purpose-Driven Tagging**: All features map to faster email triage, reduced cognitive load for student workflow, and career project demonstration. No gold-plating detected.

✅ **II. Local-First Privacy**: Self-hosted Qwen 3 model, no external API calls with email content, optional local encryption for stored emails, aggregate-only analytics export.

✅ **III. RAG-Enhanced Context Awareness**: Shared Qdrant vector service accessed via API, sentence-transformers embeddings, top-K=5 context retrieval, incremental updates, weekly batch re-indexing.

✅ **IV. Deterministic Contracts & Test-First**: Pydantic v2 for strict JSON schema validation (v2), snapshot tests for schema, contract tests before implementation, versioned schemas with migration notes.

✅ **V. Resilient Scheduling & Queueing**: APScheduler for 30s polling, idempotency via hash(message_id + schema_version), exactly-once enqueue, poison message quarantine after 5 retries, exponential backoff with jitter.

✅ **VI. Observability & Simplicity**: Prometheus metrics (poll_latency, classify_latency, rag_retrieval_latency, queue_depth, category_distribution, rag_hit_rate), structured logging (JSON format with DEBUG/INFO/WARN/ERROR levels), SQLite for simplicity (PostgreSQL optional).

### Architectural Requirements Compliance

✅ **JSON Schema v2**: Full compliance with constitution schema including message_id, primary_category, secondary_categories (≤3), priority, deadline_utc, confidence, rationale, detected_entities, sentiment, action_items, thread_context, rag_context_used, suggested_folder, schema_version.

✅ **Processing Flow**: Follows 11-step flow from constitution (fetch → extract → rag_retrieve → construct_prompt → llm_classify → json_parse → post_process → persist → feedback_check → emit_metrics → optional_notifications).

✅ **Performance Targets**: <5s median, <12s p95 classification, <50ms p95 RAG retrieval, <10% scheduler drift, <1.2GB memory footprint.

✅ **Reliability**: Circuit breaker (5 failures → 60s open), exponential backoff with jitter, stale queue sweeper (>15min), corrupt JSON forensic storage, retry with simplified prompt.

✅ **Storage**: PostgreSQL for metadata (message index, action items, thread context), Qdrant for vectors (shared service), optional encrypted email bodies, audit JSONL log, weekly RAG snapshots (last 4 retained).

✅ **Configuration**: All required env vars from constitution (EMAIL_POLL_INTERVAL, QWEN_MODEL_PATH, RAG settings, storage settings, performance tuning).

### Development Workflow Compliance

✅ **Test Pyramid**: Unit (parsing, validation, scheduler), Contract (JSON schema), Integration (end-to-end poll→classify→persist).

✅ **Quality Gates**: Lint + format, 100% schema validation coverage, no latency regression >10% without waiver.

✅ **Semantic Versioning**: MAJOR (schema break), MINOR (additive), PATCH (internal fix).

### Constitutional Violations

_None detected - design fully compliant with constitution v2.0.0_

## Project Structure

### Documentation (this feature)

```
specs/001-i-am-building/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
│   ├── classification_schema_v2.json
│   ├── dashboard_api.yaml (OpenAPI)
│   └── test_contracts.py
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)

```
# Two-version architecture: V1 (n8n) and V2 (Pure Python)

# ============ VERSION 1: n8n Workflow ============
n8n/
├── workflows/
│   ├── email_classification_main.json     # Main workflow: IMAP → RAG → LLM → DB → Gmail
│   ├── rag_indexer.json                   # Background RAG re-indexing workflow
│   └── feedback_processor.json            # User correction → RAG update workflow
├── credentials/
│   ├── imap_credentials.json              # Email account (encrypted)
│   ├── postgres_credentials.json          # Database connection
│   ├── qdrant_credentials.json            # Vector store
│   ├── ollama_credentials.json            # LLM endpoint
│   └── gmail_oauth.json                   # Gmail API credentials
├── config/
│   └── environment.json                   # n8n environment variables
└── README.md                              # n8n setup instructions

# ============ VERSION 2: Pure Python Worker ============
backend/
├── src/
│   ├── __init__.py
│   ├── config.py                    # Configuration loader (env vars, validation)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── email.py                 # Email, ClassificationResult, Tag entities
│   │   ├── classification.py        # ClassificationCycle, SystemConfig
│   │   ├── dashboard.py             # DashboardMetric, MetricTimeSeriesPoint, SystemHealthStatus
│   │   └── schema_v2.py             # Pydantic models for JSON schema v2
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email_poller.py          # IMAP polling, idempotency checks (V2 only)
│   │   ├── queue_manager.py         # Message queue with exactly-once semantics (V2 only)
│   │   ├── llm_classifier.py        # Qwen 3 integration, prompt construction (V2 only)
│   │   ├── rag_retriever.py         # Qdrant API client for vector search, embeddings (shared service)
│   │   ├── schema_validator.py      # JSON schema validation, parsing (shared)
│   │   ├── metrics_collector.py     # Prometheus metrics, structured logging (shared)
│   │   ├── feedback_processor.py    # User corrections, RAG KB updates (V2 only)
│   │   └── gmail_labeler.py         # Gmail label application (shared)
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py            # PostgreSQL connection management (shared)
│   │   ├── repositories.py          # Data access layer (shared)
│   │   └── migrations/              # Schema migrations (Alembic) (shared)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py                   # FastAPI app initialization (shared)
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py           # GET /metrics (current + historical) (shared)
│   │   │   ├── health.py            # GET /health (system status) (shared)
│   │   │   ├── classifications.py   # GET /classifications, POST /reclassify (shared)
│   │   │   └── admin.py             # POST /rag/reindex, POST /queue/clear (shared)
│   │   └── middleware.py            # Auth, CORS, logging (shared)
│   ├── worker/                      # V2 ONLY - replaces n8n workflows
│   │   ├── __init__.py
│   │   ├── scheduler.py             # APScheduler setup, job definitions
│   │   ├── classifier_worker.py     # Classification job execution
│   │   └── rag_indexer.py           # Background RAG re-indexing
│   └── utils/
│       ├── __init__.py
│       ├── crypto.py                # AES-256 encryption/decryption (shared)
│       ├── circuit_breaker.py       # Circuit breaker pattern implementation (V2 only)
│       └── retry.py                 # Exponential backoff with jitter (V2 only)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures (DB, email samples, mock LLM)
│   ├── unit/
│   │   ├── test_email_poller.py
│   │   ├── test_schema_validator.py
│   │   ├── test_rag_retriever.py
│   │   └── test_circuit_breaker.py
│   ├── contract/
│   │   ├── test_json_schema_v2.py   # Validate sample outputs against schema
│   │   └── test_api_contracts.py    # Validate API responses
│   └── integration/
│       ├── test_poll_classify_persist.py  # End-to-end flow
│       ├── test_feedback_loop.py    # User corrections → RAG update
│       └── test_dashboard_api.py    # Dashboard endpoints
├── data/                            # Runtime data (gitignored)
│   ├── emails.db                    # PostgreSQL database
│   ├── qdrant/                      # Qdrant vector data (managed separately)
│   ├── audit.jsonl                  # Audit log
│   └── prompts/
│       └── few_shot_v2.json         # Few-shot examples
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── Dockerfile                       # Container image definition
├── docker-compose.yml               # Multi-service orchestration
└── README.md                        # Setup instructions

frontend/
├── src/
│   ├── index.html                   # Entry point
│   ├── main.js/ts                   # App initialization
│   ├── components/
│   │   ├── MetricsCard.js           # Performance metric display
│   │   ├── TimeSeriesChart.js       # Line charts (Chart.js/Plotly)
│   │   ├── CategoryDistribution.js  # Pie/bar charts
│   │   ├── ActivityFeed.js          # Recent emails list
│   │   ├── ErrorPanel.js            # Error tracking display
│   │   └── SystemHealth.js          # Health indicators
│   ├── services/
│   │   ├── api.js                   # Axios/fetch wrappers for backend
│   │   └── auth.js                  # Token-based auth
│   ├── utils/
│   │   ├── formatters.js            # Date, number formatting
│   │   └── constants.js             # API URLs, refresh intervals
│   └── styles/
│       └── main.css                 # Dashboard styles
├── tests/
│   └── components/                  # Component tests (Jest/Vitest)
├── package.json                     # NPM dependencies
└── vite.config.js / webpack.config.js  # Build configuration

.env.example                         # Example environment variables
.gitignore                           # Ignore data/, .env, __pycache__, etc.
pyproject.toml                       # Python project metadata (optional)
```

**Structure Decision**:

- **V1**: n8n workflows (visual) + Python API backend + React dashboard
  - n8n handles: Email polling, RAG retrieval, LLM classification, database writes
  - Python handles: Dashboard API, Gmail labeling, metrics collection
- **V2**: Pure Python worker + Python API backend + React dashboard (same UI)
  - Python handles: ALL workflow logic (replaces n8n)
  - Same: Dashboard API, React UI, database schema, monitoring
- **Shared Infrastructure**: PostgreSQL database schema, FastAPI routes, React components, Docker Compose, Grafana dashboards
- **Migration Path**: V1 validates taxonomy → V2 adds production features → Seamless switch (same database, same UI)

## Version-Specific Implementation Notes

### V1 (n8n) Implementation Characteristics

- **Speed**: Rapid prototyping with visual workflows (2-3 days to functional system)
- **Learning Curve**: n8n GUI for workflow logic, minimal Python code
- **Limitations**: Limited unit testing, harder to debug, n8n overhead (~100ms)
- **Best For**: Validating taxonomy, testing prompts, proving concept
- **Components**: n8n workflows + minimal Python (API + Gmail + metrics only)

### V2 (Pure Python) Implementation Characteristics

- **Speed**: Full custom development (5-7 days for production-grade)
- **Learning Curve**: Python services, testing frameworks, async patterns
- **Advantages**: Full control, testable, optimized performance, maintainable
- **Best For**: Production deployment, resume demonstration, learning architecture
- **Components**: Complete Python codebase (worker + API + utilities)

### Shared Components (No Version Differences)

- PostgreSQL database schema (identical for both versions)
- React dashboard UI (connects to same FastAPI endpoints)
- Gmail API integration (same Python service)
- Grafana + Prometheus monitoring (same metrics)
- Docker Compose orchestration (services differ, configs shared)

## Phase 0: Outline & Research

### Research Tasks (Applies to Both Versions)

1. **Python LLM Integration Options**

   - Research: Evaluate Qwen 3 8B integration methods for Python
   - Options: llama-cpp-python, vLLM, transformers (HuggingFace), ctransformers
   - Criteria: Local execution, Python API, performance (<12s p95), memory footprint (<1.2GB)

2. **Web Framework Selection**

   - Research: Compare Python web frameworks for dashboard + API
   - Options: FastAPI (async, OpenAPI), Flask (simple, sync), Quart (async Flask), Starlette (minimal async)
   - Criteria: Async support, OpenAPI docs, performance (<500ms p95), SSE support for real-time updates

3. **Vector Store Implementation**

   - Research: Compare FAISS vs Hnswlib for RAG retrieval
   - Options: FAISS (Facebook, feature-rich), Hnswlib (fast, simple), Annoy (Spotify), ChromaDB (batteries-included)
   - Criteria: Python bindings, <50ms p95 retrieval, incremental updates, persistence

4. **Frontend Framework Decision**

   - Research: Evaluate frontend options for metrics dashboard
   - Options: Vanilla JS + Chart.js (simple), React + Recharts (component-based), Vue + ECharts (progressive), Svelte + Plotly (minimal bundle)
   - Criteria: Real-time updates, charting libraries, bundle size, learning curve for resume project

5. **Task Scheduling Strategy**

   - Research: Compare scheduling libraries for 30s polling
   - Options: APScheduler (feature-rich), schedule (simple), asyncio-based custom (minimal), Celery (overkill?)
   - Criteria: Reliability, drift <10%, Python 3.11+ compatibility, single-process deployment

6. **Email Access Library**
   - Research: Evaluate IMAP libraries for Python
   - Options: imaplib (stdlib, low-level), imap-tools (high-level), aioimaplib (async)
   - Criteria: Idempotent fetch, message-id access, error handling, async support

### Deliverable: research.md

Document each decision with:

- **Decision**: Chosen technology/approach
- **Rationale**: Why selected (performance, maintainability, constitutional alignment)
- **Alternatives Considered**: Other options evaluated with pros/cons
- **Integration Notes**: How it fits into architecture

## Phase 1: Design & Contracts

### 1. Data Model Design (data-model.md)

Extract entities from specification and constitution:

**Core Entities**:

- `Email`: message_id (PK), received_timestamp, sender, subject, body_hash, classification_status (enum), raw_email_encrypted (optional)
- `ClassificationResult`: id (PK), email_id (FK), primary_category, secondary_categories (JSON), priority, deadline_utc, confidence, rationale, detected_entities (JSON), sentiment, action_items (JSON), thread_context (JSON), rag_context_used (JSON), processed_timestamp, schema_version
- `Tag`: name (PK), description, category_type (academic/career/admin/etc), active, priority_order
- `ClassificationCycle`: cycle_id (PK), start_timestamp, end_timestamp, emails_scanned, emails_classified, emails_failed, duration_ms
- `SystemConfig`: key (PK), value, value_type, updated_at
- `UserFeedback`: id (PK), message_id (FK), original_category, corrected_category, reason, timestamp, incorporated (bool)

**Metrics Entities**:

- `DashboardMetric`: metric_name, value, timestamp, aggregation_period (5s/1h/1d), unit
- `MetricTimeSeriesPoint`: id (PK), metric_name, timestamp, value, labels (JSON)
- `SystemHealthStatus`: component_name, status (healthy/degraded/down), last_check_timestamp, error_message

**Relationships**:

- Email 1:1 ClassificationResult (one classification per email, idempotent)
- Email 1:N UserFeedback (multiple corrections possible)
- ClassificationResult M:N Tag (via secondary_categories array)

**State Transitions**:

- Email.classification_status: pending → classifying → classified | failed | quarantined

**Validation Rules**:

- confidence ∈ [0, 1]
- secondary_categories length ≤ 3
- action_items length ≤ 10
- primary*category matches hierarchical pattern regex: `^[a-z]+\.[a-z*]+$`
- deadline_confidence required if deadline_utc present

### 2. API Contracts (contracts/)

**classification_schema_v2.json**: JSON Schema for LLM output

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "message_id",
    "primary_category",
    "confidence",
    "schema_version"
  ],
  "properties": {
    "message_id": { "type": "string" },
    "primary_category": { "type": "string", "pattern": "^[a-z]+\\.[a-z_]+$" },
    "secondary_categories": {
      "type": "array",
      "items": { "type": "string" },
      "maxItems": 3
    },
    "priority": {
      "type": "string",
      "enum": ["low", "normal", "high", "urgent"]
    },
    "deadline_utc": { "type": ["string", "null"], "format": "date-time" },
    "deadline_confidence": {
      "type": "string",
      "enum": ["extracted", "inferred", "none"]
    },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "rationale": { "type": "string", "maxLength": 200 },
    "detected_entities": { "type": "object" },
    "sentiment": {
      "type": "string",
      "enum": ["positive", "neutral", "negative", "urgent"]
    },
    "action_items": { "type": "array", "maxItems": 10 },
    "thread_context": { "type": "object" },
    "rag_context_used": { "type": "array" },
    "suggested_folder": { "type": "string" },
    "schema_version": { "type": "string", "const": "v2" }
  }
}
```

**dashboard_api.yaml**: OpenAPI 3.0 spec

```yaml
openapi: 3.0.0
info:
  title: Email Classifier Dashboard API
  version: 1.0.0
paths:
  /metrics/current:
    get:
      summary: Get current 5-second metrics
      responses:
        "200":
          description: Current metrics snapshot
          content:
            application/json:
              schema:
                type: object
                properties:
                  avg_processing_time_ms: { type: number }
                  avg_tags_per_email: { type: number }
                  queue_depth: { type: integer }
                  active_workers: { type: integer }
                  system_uptime_seconds: { type: integer }
  /metrics/timeseries:
    get:
      summary: Get historical time-series data
      parameters:
        - name: metric
          in: query
          required: true
          schema: { type: string }
        - name: period
          in: query
          schema: { type: string, enum: [1h, 24h, 7d, 30d] }
      responses:
        "200":
          description: Time-series data points
  /classifications:
    get:
      summary: Get recent classifications
      parameters:
        - name: limit
          in: query
          schema: { type: integer, default: 50 }
        - name: confidence_min
          in: query
          schema: { type: number }
      responses:
        "200":
          description: List of recent classifications
  /classifications/reclassify:
    post:
      summary: Trigger manual reclassification
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                message_ids: { type: array, items: { type: string } }
      responses:
        "202": { description: Accepted for processing }
  /health:
    get:
      summary: System health status
      responses:
        "200":
          description: Health indicators for all components
```

### 3. Contract Tests (contracts/test_contracts.py)

Generate failing tests for:

- JSON schema v2 validation with sample outputs
- API endpoint request/response validation
- Dashboard metrics format validation
- Error response schemas

### 4. Integration Test Scenarios (tests/integration/)

From user stories in specification:

- **test_poll_classify_persist**: Poll emails → classify with RAG → persist → verify DB state
- **test_idempotency**: Process same email twice → verify no duplicate classifications
- **test_feedback_loop**: User correction → RAG KB update → improved classification on similar email
- **test_error_handling**: Malformed email → quarantine → continue processing batch
- **test_dashboard_realtime**: Start worker → access dashboard → verify metrics update every 5s

### 5. Quickstart Validation (quickstart.md)

Step-by-step manual validation:

1. Setup: Install dependencies, configure env vars, initialize DB
2. Load sample emails to test inbox
3. Start backend worker
4. Verify classifications appear in DB
5. Access dashboard at http://localhost:8080
6. Validate metrics display: processing time, tags/email, confidence distribution
7. Submit manual correction via dashboard
8. Verify RAG KB updated and similar email reclassified
9. Trigger "force reclassify" action
10. Export metrics to CSV

### 6. Agent-Specific Context File

Run: `.specify/scripts/bash/update-agent-context.sh roo`

This will create/update `.roo/CLAUDE.md` with:

- Project overview (email classifier system)
- Tech stack summary (Python 3.11+, chosen frameworks from research)
- Key directories and their purposes
- Testing approach (pytest, contract tests, integration tests)
- Recent changes (from last 3 git commits or manual notes)
- Constitutional principles for LLM agent guidance

**Output**:

- `specs/001-i-am-building/data-model.md` (entity definitions, relationships, validation rules)
- `specs/001-i-am-building/contracts/classification_schema_v2.json` (JSON Schema)
- `specs/001-i-am-building/contracts/dashboard_api.yaml` (OpenAPI spec)
- `specs/001-i-am-building/contracts/test_contracts.py` (failing contract tests)
- `specs/001-i-am-building/quickstart.md` (manual validation steps)
- `.roo/CLAUDE.md` (agent context file, incremental update)
- `tests/integration/test_*.py` (failing integration tests)

## Phase 2: Task Planning Approach

**Task Generation Strategy** (executed by /tasks command):

**IMPORTANT**: Tasks will be split into two phases:

- **Phase V1**: n8n workflow implementation (T001-T030, estimated 3-5 days)
- **Phase V2**: Pure Python worker implementation (T031-T070, estimated 5-7 days)

1. **Load templates and artifacts**:

   - Load `.specify/templates/tasks-template.md` as base structure
   - Read `data-model.md` for entity implementation tasks
   - Read `contracts/` for API endpoint tasks
   - Read `quickstart.md` for validation tasks

2. **Generate task list for V1 (n8n Prototype)**:

   - **Phase V1.A: Foundation** (shared components)

     - Task V1.001: Setup project structure, Docker Compose
     - Task V1.002: Setup PostgreSQL database, Alembic migrations
     - Task V1.003: Implement Pydantic models for schema v2
     - Task V1.004: Setup n8n Docker container
     - Task V1.005: Create contract tests for JSON schema v2

   - **Phase V1.B: n8n Workflows**

     - Task V1.006: Create IMAP email polling workflow
     - Task V1.007: Create RAG retrieval workflow (Qdrant integration)
     - Task V1.008: Create LLM classification workflow (Ollama HTTP)
     - Task V1.009: Create database persistence workflow
     - Task V1.010: Connect workflows end-to-end
     - Task V1.011: Add error handling and retries
     - Task V1.012: Create RAG indexer background workflow

   - **Phase V1.C: Python Dashboard API** (shared with V2)

     - Task V1.013: Setup FastAPI application
     - Task V1.014: Implement /metrics endpoints
     - Task V1.015: Implement /health endpoint
     - Task V1.016: Implement /classifications endpoints
     - Task V1.017: Implement /admin endpoints
     - Task V1.018: Add authentication middleware

   - **Phase V1.D: Gmail Integration** (shared with V2)

     - Task V1.019: Implement Gmail API OAuth setup
     - Task V1.020: Implement gmail_labeler service
     - Task V1.021: Add label application to n8n workflow

   - **Phase V1.E: Frontend Dashboard** (shared with V2)

     - Task V1.022: Setup React + Vite project
     - Task V1.023: Implement MetricsCard component
     - Task V1.024: Implement TimeSeriesChart component
     - Task V1.025: Implement CategoryDistribution component
     - Task V1.026: Implement ActivityFeed component
     - Task V1.027: Connect to FastAPI backend

   - **Phase V1.F: Monitoring** (shared with V2)
     - Task V1.028: Setup Prometheus metrics collection
     - Task V1.029: Setup Grafana dashboards
     - Task V1.030: Validate V1 end-to-end with quickstart.md

3. **Generate task list for V2 (Pure Python Production)**:

   - **Phase V2.A: Python Worker Foundation**

     - Task V2.001: Implement email_poller service (replace n8n IMAP)
     - Task V2.002: Implement queue_manager service (replace n8n queue)
     - Task V2.003: Implement rag_retriever service (Qdrant API client)
     - Task V2.004: Implement llm_classifier service (replace n8n HTTP)
     - Task V2.005: Implement feedback_processor service
     - Task V2.006: Add circuit breaker and retry utilities

   - **Phase V2.B: Worker Orchestration**

     - Task V2.007: Implement classifier_worker (orchestrate services)
     - Task V2.008: Implement scheduler (APScheduler)
     - Task V2.009: Implement rag_indexer background task
     - Task V2.010: Add graceful shutdown handling

   - **Phase V2.C: Testing & Validation**

     - Task V2.011: Unit tests for email_poller
     - Task V2.012: Unit tests for rag_retriever
     - Task V2.013: Unit tests for llm_classifier
     - Task V2.014: Integration test: poll_classify_persist
     - Task V2.015: Integration test: idempotency
     - Task V2.016: Integration test: feedback_loop
     - Task V2.017: Performance benchmarking (<5s median target)

   - **Phase V2.D: Migration & Validation**
     - Task V2.018: A/B test V1 vs V2 (same database)
     - Task V2.019: Validate identical classification results
     - Task V2.020: Performance comparison report
     - Task V2.021: Switch from V1 to V2 in production
     - Task V2.022: Decommission n8n workflows

4. **Original task list** (for reference, now split into V1/V2):

   - **Phase A: Foundation** (models, schemas, config)

     - Task 001: Setup project structure, dependencies, Docker [P]
     - Task 002: Implement Pydantic models for schema v2 [P]
     - Task 003: Create database schema with Alembic migration [P]
     - Task 004: Implement configuration loader with env validation [P]
     - Task 005: Setup pytest fixtures (DB, sample emails, mock LLM) [P]

   - **Phase B: Contract Tests** (write failing tests)

     - Task 006: Contract test - JSON schema v2 validation [P]
     - Task 007: Contract test - Dashboard API endpoints [P]
     - Task 008: Contract test - Metrics format validation [P]

   - **Phase C: Core Services** (implement to pass contract tests)

     - Task 009: Implement email poller with IMAP [depends: 003, 004]
     - Task 010: Implement queue manager with idempotency [depends: 003]
     - Task 011: Implement RAG retriever (FAISS + sentence-transformers) [depends: 004]
     - Task 012: Implement LLM classifier (Qwen 3 integration) [depends: 004, 011]
     - Task 013: Implement schema validator [depends: 002, 006]
     - Task 014: Implement metrics collector (Prometheus) [depends: 003]

   - **Phase D: Worker Logic** (orchestration)

     - Task 015: Implement classification worker (poll → classify → persist) [depends: 009-014]
     - Task 016: Implement scheduler (APScheduler 30s polling) [depends: 015]
     - Task 017: Implement circuit breaker and retry logic [depends: 015]
     - Task 018: Implement feedback processor [depends: 011, 013]

   - **Phase E: Dashboard API** (web endpoints)

     - Task 019: Setup web framework app (FastAPI/Flask) [depends: 004]
     - Task 020: Implement /metrics endpoints [depends: 014, 019]
     - Task 021: Implement /classifications endpoints [depends: 003, 019]
     - Task 022: Implement /health endpoint [depends: 019]
     - Task 023: Implement admin endpoints (reclassify, reindex) [depends: 016, 018, 019]
     - Task 024: Implement auth middleware [depends: 019]

   - **Phase F: Frontend Dashboard**

     - Task 025: Setup frontend build (Vite/Webpack) [P]
     - Task 026: Implement MetricsCard components [depends: 025]
     - Task 027: Implement TimeSeriesChart components [depends: 025]
     - Task 028: Implement CategoryDistribution visualization [depends: 025]
     - Task 029: Implement ActivityFeed component [depends: 025]
     - Task 030: Implement real-time updates (5s polling) [depends: 026-029]

   - **Phase G: Integration Tests**

     - Task 031: Integration test - poll_classify_persist [depends: 015]
     - Task 032: Integration test - idempotency [depends: 010]
     - Task 033: Integration test - feedback_loop [depends: 018]
     - Task 034: Integration test - error_handling [depends: 017]
     - Task 035: Integration test - dashboard_api [depends: 020-023]

   - **Phase H: Validation & Documentation**
     - Task 036: Execute quickstart.md validation [depends: 031-035]
     - Task 037: Performance testing (latency benchmarks) [depends: 036]
     - Task 038: Write deployment README [depends: 036]
     - Task 039: Generate API documentation [depends: 020-023]
     - Task 040: Prepare demo data and screenshots for resume [depends: 036]

5. **Task Ordering Rules**:

   - Contract tests before implementation
   - Models before services before API before UI
   - Mark [P] for tasks with no dependencies (parallel execution possible)
   - Integration tests after all components implemented
   - Validation after all tests passing

6. **Estimated Breakdown**:
   - Phase A: 5 tasks (foundation)
   - Phase B: 3 tasks (contract tests)
   - Phase C: 6 tasks (core services)
   - Phase D: 4 tasks (worker orchestration)
   - Phase E: 6 tasks (dashboard API)
   - Phase F: 6 tasks (frontend)
   - Phase G: 5 tasks (integration tests)
   - Phase H: 5 tasks (validation & docs)
   - **Total: ~40 tasks**

**IMPORTANT**: This task planning will be executed by the `/tasks` command, NOT by `/plan`. The above describes the strategy that will be followed.

## Phase 3+: Future Implementation

_These phases are beyond the scope of the /plan command_

**Phase 3**: Task execution

- `/tasks` command creates `tasks.md` with full task list
- Tasks executed in order, following TDD approach
- Each task updates progress in `tasks.md`

**Phase 4**: Implementation

- Execute tasks from `tasks.md`
- Follow constitutional principles (test-first, observability, simplicity)
- Update agent context file after major milestones

**Phase 5**: Validation

- Run full test suite (unit + contract + integration)
- Execute `quickstart.md` manual validation
- Performance benchmarking (verify <5s median, <12s p95)
- Dashboard functionality verification
- Resume documentation preparation (screenshots, metrics, architecture diagrams)

## Complexity Tracking

_No constitutional violations detected - all design decisions align with constitution v2.0.0_

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ------------------------------------ |
| None      | N/A        | N/A                                  |

## Progress Tracking

**Phase Status**:

- [ ] Phase 0: Research complete (/plan command) - NEXT
- [ ] Phase 1: Design complete (/plan command)
- [ ] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:

- [x] Initial Constitution Check: PASS
- [ ] Post-Design Constitution Check: PENDING (after Phase 1)
- [x] All NEEDS CLARIFICATION resolved (spec has none remaining)
- [x] Complexity deviations documented (none required)

---

_Based on Constitution v2.0.0 - See `.specify/memory/constitution.md`_
