# Email Classifier Constitution

## Core Principles

### I. Purpose-Driven Tagging

Deliver fast, reliable, explainable categorization of incoming emails for a pre–final year college student. Every feature must map to: faster triage, reduced cognitive load, or improved academic / career readiness. No gold‑plating, no speculative complexity.

### II. Local-First Privacy

All classification runs locally using a self-hosted Qwen 3 model. No raw email body, headers, or metadata are sent to external services. Redactions (if any) occur before persistence. Exported analytics must be aggregate + anonymized.

### III. RAG-Enhanced Context Awareness

A local RAG (Retrieval-Augmented Generation) system maintains a knowledge base of:

- Historical classification decisions (user feedback loop for continuous improvement)
- Domain-specific context: course catalog, company lists, event calendars, professor/staff names
- Temporal patterns: semester schedules, exam periods, placement seasons
- Personal preferences: VIP senders, custom tag rules, priority overrides

RAG retrieval injects top-K relevant context chunks into prompts (default K=5) to improve accuracy on ambiguous/context-dependent emails. Knowledge base updated incrementally; embeddings regenerated on schedule (weekly default) or on-demand.

### IV. Deterministic Contracts & Test-First

The LLM output must conform to a strict JSON schema (versioned). Parsing failures are treated as recoverable errors with retry + fallback heuristics. Tests (unit > contract > integration) precede implementation; schemas are locked by snapshot tests. Changes to schema require version bump + migration notes.

### V. Resilient Scheduling & Queueing

A scheduler wakes every X seconds (configurable; default 30s) to poll new emails (idempotent fetch). New messages are enqueued exactly-once (dedupe by stable message-id + hash of (subject, from, date)). Queue supports at-least-once processing with idempotent tagging; poison messages are quarantined after N retries (default 5) with structured error context.

### VI. Observability & Simplicity

Metrics, logs, traces are first-class:

- Metrics: poll_latency, classify_latency, rag_retrieval_latency, queue_depth, retry_count, schema_parse_failures, category_distribution, rag_hit_rate, feedback_incorporation_lag.
- Structured log levels: DEBUG (development only), INFO (state changes), WARN (transient recoverable), ERROR (action required).
  Prefer boring technology (simple file/db store + lightweight worker) over premature distributed systems.

## Architectural & Operational Requirements

### Functional Categories (Enhanced Set)

**Academic (hierarchical sub-tags):**

- `academic.coursework`: assignments, homework, project updates
- `academic.lectures`: lecture notes, recording links, slides
- `academic.exams`: exam schedules, room assignments, practice tests
- `academic.grades`: grade releases, report cards, transcript notifications
- `academic.research`: lab updates, paper submissions, advisor meetings
- `academic.general`: miscellaneous academic communications

**Career & Professional Development:**

- `career.internship`: internship offers, application deadlines, interview invitations
- `career.placement`: campus recruitment, company visits, pre-placement talks
- `career.job_alerts`: off-campus opportunities, job postings
- `career.networking`: alumni connects, mentorship programs, career fairs
- `career.resume_review`: career services appointments, profile feedback

**Administrative & Operations:**

- `admin.registration`: course registration, add/drop, enrollment confirmations
- `admin.fees`: fee reminders, payment deadlines, scholarship disbursements
- `admin.compliance`: document submissions, KYC, policy acknowledgments
- `admin.facilities`: hostel, transport, library, IT services
- `admin.announcements`: university-wide broadcasts, calendar updates

**Extracurricular & Community:**

- `clubs.events`: hackathons, competitions, workshops, guest lectures
- `clubs.recruitment`: club membership drives, elections
- `clubs.updates`: meeting minutes, project progress, volunteer calls
- `sports.tournaments`: sports events, tryouts, fixtures
- `cultural.festivals`: college fests, cultural nights, performances

**Time-Sensitive & Actionable:**

- `action.deadline_critical`: <24h, requires immediate attention
- `action.deadline_soon`: 24h-72h window
- `action.forms`: surveys, feedback forms, consent forms
- `action.rsvp`: event confirmations, attendance tracking
- `action.approval_needed`: permissions, sign-offs, endorsements

**Financial:**

- `finance.tuition`: semester fees, late payment notices
- `finance.stipend`: scholarship credits, stipend confirmations
- `finance.reimbursement`: expense claims, reimbursement status
- `finance.receipts`: payment confirmations, invoices

**Personal & Social:**

- `personal.direct`: one-on-one conversations with known contacts
- `personal.group`: group projects, study groups, peer coordination
- `personal.family`: family correspondence (if using same inbox)

**Learning & Resources:**

- `learning.newsletters`: academic newsletters, research digests
- `learning.moocs`: online course updates (Coursera, edX, etc.)
- `learning.documentation`: technical docs, API references, tutorials
- `learning.webinars`: recorded sessions, live webinar invites

**Promotions & Commercial:**

- `promotion.education`: relevant EdTech, tools, student discounts
- `promotion.general`: generic marketing, retail, services
- `promotion.subscriptions`: renewal reminders, upgrade offers

**System & Automated:**

- `system.notifications`: account alerts, security notices, 2FA codes
- `system.receipts`: order confirmations, booking confirmations
- `system.social_media`: social network notifications (if forwarded)

**Spam & Security:**

- `spam.phishing`: suspected phishing attempts, fraudulent emails
- `spam.junk`: obvious spam, bulk unsolicited mail
- `spam.suspicious`: borderline cases flagged for review

(LLM returns primary_category + up to 3 secondary_categories; hierarchical tags use dot notation.)

### LLM Output JSON Schema (v2)

```json
{
  "message_id": "string",
  "primary_category": "string (hierarchical tag, e.g., 'academic.exams')",
  "secondary_categories": ["string (up to 3)"],
  "priority": "enum[low|normal|high|urgent]",
  "deadline_utc": "ISO8601|null",
  "deadline_confidence": "enum[extracted|inferred|none]",
  "confidence": "number 0..1",
  "rationale": "string (max 200 chars)",
  "detected_entities": {
    "course_codes": ["string"],
    "company_names": ["string"],
    "event_names": ["string"],
    "professor_names": ["string"],
    "amounts": [{ "value": "number", "currency": "string" }],
    "locations": ["string"],
    "phone_numbers": ["string"],
    "urls": ["string"]
  },
  "sentiment": "enum[positive|neutral|negative|urgent]",
  "action_items": [
    {
      "action": "string (brief description)",
      "deadline_utc": "ISO8601|null",
      "completed": false
    }
  ],
  "thread_context": {
    "is_reply": "boolean",
    "thread_id": "string|null",
    "previous_categories": ["string"]
  },
  "rag_context_used": ["string (chunk IDs)"],
  "suggested_folder": "string (mail client folder path)",
  "schema_version": "v2"
}
```

**Parsing MUST validate:**

- required fields: `message_id`, `primary_category`, `confidence`, `schema_version`
- `confidence` in [0,1]
- `primary_category` matches known hierarchical patterns
- `secondary_categories` length ≤ 3
- `action_items` count ≤ 10
- unknown fields rejected (fail fast)
- `deadline_confidence` required if `deadline_utc` present

**Schema Migration v1→v2:**

- Added: `deadline_confidence`, `sentiment`, `action_items`, `thread_context`, `rag_context_used`, `suggested_folder`
- Enhanced: `detected_entities` with additional entity types
- v1 consumers must ignore unknown fields; v2 producers provide backward-compatible subset

### Processing Flow (RAG-Enhanced)

```
poller -> normalizer -> enqueue -> worker:
  1. fetch_raw_email
  2. extract_base_features (subject, from, snippet)
  3. rag_retrieve (query: subject+from+snippet, top_k=5)
  4. construct_enriched_prompt (base + rag_context + few_shot)
  5. llm_classify (Qwen 3 invocation)
  6. json_parse + validation
  7. post_process:
      - deadline_extraction_heuristics (regex fallback)
      - entity_reconciliation (dedupe, normalize)
      - thread_linking (match previous emails in same conversation)
  8. persist (metadata DB + audit log)
  9. feedback_check (if user correction available, update RAG KB)
  10. emit_metrics + structured_log
  11. optional_notifications (urgent/action_required categories)
```

**RAG Knowledge Base Structure:**

- **Historical Decisions**: `{email_hash, assigned_category, user_feedback, timestamp}`
- **Domain Context**: `{entity_type, entity_value, associated_categories, semester, year}`
- **Temporal Patterns**: `{date_range, event_type, typical_categories}`
- **User Preferences**: `{sender_domain, custom_rules, priority_overrides}`

Embeddings: sentence-transformers (local model, e.g., all-MiniLM-L6-v2) for fast retrieval (<50ms p95).
Index: FAISS or Hnswlib for vector search.
Update Strategy: incremental append for new classifications; batch re-indexing weekly or on-demand.

### Performance Targets

- Poll-to-tag median latency < 5s (light load).
- 95th percentile classification < 12s.
- Scheduler drift < 10% of interval.
- Memory footprint (worker) < 1.2 GB with model loaded (tunable).

### Reliability & Fault Handling

- Backoff (exponential with jitter) on LLM invocation failures.
- Circuit breaker after successive failures (open 60s).
- Stale queue items (>15m) re-queued by sweeper.
- Idempotency key = hash(message_id + schema_version).
- Corrupt JSON: store raw output for forensic review, increment metric, retry with simplified prompt once.

### Storage & Persistence

**Metadata Store (SQLite or PostgreSQL):**

- Message index: `{message_id, status, primary_category, secondary_categories, priority, deadline_utc, confidence, timestamp, rag_context_ids}`
- Action items table: `{id, message_id, action, deadline_utc, completed, completed_at}`
- Thread context: `{thread_id, message_ids[], first_seen, last_updated}`

**RAG Knowledge Base:**

- Vector store: FAISS index file (embeddings.index)
- Metadata store: JSON or DB table `{chunk_id, text, embedding_metadata, category_associations, timestamp}`
- User feedback log: `{message_id, original_category, corrected_category, timestamp, reason}`

**Raw Email Storage:**

- Raw email body (optional):
  - Encrypted at rest (AES-256, key via ENV), OR
  - Omitted if only metadata needed (configurable via `STORE_RAW_EMAILS=false`)
- Audit log (append-only JSONL): `{timestamp, message_id, action, category, confidence, rag_hits, latency_ms}`

**Backup & Retention:**

- Metadata: retained indefinitely (or configurable TTL for old messages)
- RAG KB: snapshot weekly, retain last 4 snapshots
- Raw emails: retention policy per privacy requirements (default 90 days)

### Security & Privacy

- No external API calls containing unredacted content.
- Secrets (encryption key, model path) via environment variables; never committed.
- Access controls: write vs read roles (future multi-user adaptation).

### Configuration

**Core Settings:**

- `EMAIL_POLL_INTERVAL`: seconds between poll cycles (default 30)
- `CLASSIFY_CONCURRENCY`: max concurrent classification workers (default 2)
- `CLASSIFY_MAX_RETRIES`: retry limit for failed classifications (default 5)
- `QWEN_MODEL_PATH`: path to local Qwen 3 model weights
- `LOG_LEVEL`: DEBUG|INFO|WARN|ERROR (default INFO)

**RAG Settings:**

- `RAG_ENABLED`: enable/disable RAG augmentation (default true)
- `RAG_TOP_K`: number of context chunks to retrieve (default 5)
- `RAG_EMBEDDING_MODEL`: sentence-transformer model name (default "all-MiniLM-L6-v2")
- `RAG_INDEX_PATH`: path to FAISS index file (default "./data/rag.index")
- `RAG_REINDEX_CRON`: cron schedule for full re-indexing (default "0 2 \* \* 0" = weekly Sunday 2am)
- `RAG_SIMILARITY_THRESHOLD`: min cosine similarity for retrieval (default 0.6)

**Storage Settings:**

- `DB_PATH`: metadata database path (default "./data/emails.db")
- `STORE_RAW_EMAILS`: persist raw email bodies (default false)
- `ENCRYPTION_KEY`: symmetric key for email encryption (required if STORE_RAW_EMAILS=true)
- `AUDIT_LOG_PATH`: append-only audit log location (default "./data/audit.jsonl")
- `RETENTION_DAYS`: email retention period (default 90, 0=infinite)

**Performance Tuning:**

- `LLM_CONTEXT_WINDOW`: max chars sent to LLM (default 4000)
- `LLM_TEMPERATURE`: model temperature for classification (default 0.1 for consistency)
- `LLM_MAX_TOKENS`: max output tokens (default 800)
- `CIRCUIT_BREAKER_THRESHOLD`: failures before circuit opens (default 5)
- `CIRCUIT_BREAKER_TIMEOUT`: seconds circuit stays open (default 60)

### Prompt Strategy (v2 - RAG-Enhanced)

**System Prompt:**

```
You are an email classification assistant for a pre-final year college student. Your task is to:
1. Categorize emails using the hierarchical tag system provided
2. Extract deadlines, action items, and entities accurately
3. Assess priority based on urgency and academic/career relevance
4. Output ONLY valid JSON matching schema v2

Use the provided context from previous similar emails to improve accuracy. Be consistent with historical patterns unless the email clearly differs.
```

**User Prompt Template:**

```
### Email Metadata
From: {sender_email}
Subject: {subject}
Date: {date}
Thread: {is_reply} | {thread_position}

### Email Content (snippet)
{sanitized_body_snippet}

### Retrieved Context (from similar past emails)
{rag_context_chunks}

### Extracted Features
- Detected dates: {extracted_dates}
- Detected course codes: {course_code_patterns}
- Known sender classification: {sender_history}
- Current semester context: {semester_info}

### Few-Shot Examples
{few_shot_examples}

### Task
Classify this email and output JSON conforming to schema v2. Prioritize consistency with retrieved context.
```

**Few-Shot Examples:**

- Maintained in versioned file: `prompts/few_shot_v2.json`
- Covers edge cases: forwarded emails, multi-topic emails, ambiguous deadlines, urgent vs high priority distinction
- Updated via test-driven process: add failing case → add example → verify improvement

**Prompt Versioning:**

- Prompts tracked in git with semantic versions
- A/B testing infrastructure for comparing prompt variations
- Metric: category_accuracy, entity_extraction_f1, deadline_detection_recall

## Development Workflow & Quality Gates

1. Issue Definition: Each change mapped to a tracked requirement or bug; categories immutable unless schema version increments.
2. Test Pyramid:
   - Unit: parsing, validation, scheduler logic.
   - Contract: golden JSON samples vs schema.
   - Integration: end-to-end poll → classify → persist (fixture mailbox).
3. CI Gates (all mandatory):
   - Lint + formatting pass.
   - 100% schema validation coverage on sample set.
   - No increase in critical metrics regression budgets.
4. Review Policy:
   - At least 1 peer review.
   - Any schema change: requires migration note + version bump + backward compatibility strategy or explicit breaking tag.
5. Deployment / Release:
   - Semantic Versioning: MAJOR (schema break), MINOR (additive), PATCH (internal fix).
   - Release notes must list: new categories, schema fields, operational flags.
6. Observability Enforcement:
   - New subsystem must expose ≥1 health metric & structured log entries.
7. Performance Guardrails:
   - PRs adding >10% latency (95p) require explicit waiver.

## Governance

- This constitution is the single authoritative operational + engineering policy for the email classifier.
- Amendments require: proposal doc (motivation, impact), test adjustments, version increment.
- Non-compliant PRs are blocked; exceptions must be documented with expiry date.
- All runtime hotfixes must produce a retro documenting cause + prevention steps.
- Complexity must be justified against: (a) latency reduction, (b) reliability improvement, (c) accuracy improvement via RAG, or (d) privacy reinforcement—else rejected.
- Schema evolution follows: propose → discuss → approve → implement → migrate → release.
- RAG knowledge base changes (new entity types, context sources) require: impact analysis, embedding model compatibility check, migration test with historical data.

**Version**: 2.0.0 | **Ratified**: 2025-10-02 | **Last Amended**: 2025-10-02
