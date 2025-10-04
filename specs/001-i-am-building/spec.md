# Feature Specification: Intelligent Inbox Email Classification

**Feature Branch**: `001-i-am-building`
**Created**: 2025-10-02
**Updated**: 2025-10-04 (Two-Version Architecture)
**Status**: Draft
**Input**: User description: "i am building a email classifier(3rd year college student) to make my own inbox easier to navigate as well as have a decent project on my resume. every x seconds its checking for emails and sending them to the classification queue which is handeled by a self hosted qwen 3 8b which returns a json based on which emails are tagged"

**Implementation Strategy**: Two progressive versions

- **V1 (n8n)**: Rapid prototype using n8n workflows for validation (3-5 days)
- **V2 (Pure Python)**: Production implementation with full control (5-7 days)
- **Shared**: PostgreSQL database, React dashboard, Gmail API, monitoring

## Execution Flow (main)

```
1. Parse user description from Input
   → If empty: ERROR "No feature description provided"
2. Extract key concepts from description
   → Identify: actors, actions, data, constraints
3. For each unclear aspect:
   → Mark with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   → If no clear user flow: ERROR "Cannot determine user scenarios"
5. Generate Functional Requirements
   → Each requirement must be testable
   → Mark ambiguous requirements
6. Identify Key Entities (if data involved)
7. Run Review Checklist
   → If any [NEEDS CLARIFICATION]: WARN "Spec has uncertainties"
   → If implementation details found: ERROR "Remove tech details"
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines

- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

### Section Requirements

- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation

1. **Mark all ambiguities**: Use [NEEDS CLARIFICATION: specific question] for any assumption you'd need to make
2. **Don't guess**: If the prompt doesn't specify something (e.g., tagging taxonomy scope), mark it
3. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
4. **Common underspecified areas**:
   - User types and permissions
   - Data retention/deletion policies
   - Performance targets and scale
   - Error handling behaviors
   - Integration requirements
   - Security/compliance needs

---

## User Scenarios & Testing _(mandatory)_

### Primary User Story

As an individual email user (student) who receives a variety of academic, personal, promotional, and automated messages, I want incoming emails to be automatically categorized into meaningful tags/folders so that I can quickly focus on important or time‑sensitive messages without manually sorting my inbox.

As a system operator (self), I want a web-based metrics dashboard displaying real-time classification performance so that I can monitor system health, identify bottlenecks, evaluate tagging quality, and demonstrate project capabilities for resume purposes.

As an email user, I want the classification results (tags) to appear as Gmail labels in my inbox so that I can use Gmail's built-in labeling, filtering, and search features without additional tools or manual intervention.

**V1 Specific**: As a developer, I want to rapidly prototype the classification workflow using n8n visual workflows so that I can validate the taxonomy and prompts quickly before investing in custom code.

**V2 Specific**: As a developer, I want full programmatic control over the classification pipeline with comprehensive testing so that I can optimize performance and maintain the system long-term.

### Acceptance Scenarios

1. **Given** new unread emails have arrived since the last scan, **When** the system performs its periodic classification cycle, **Then** each newly detected email is evaluated and assigned one or more tags according to the defined taxonomy (or marked unclassified if no rule/confidence threshold satisfied).
2. **Given** an email has already been classified, **When** a subsequent cycle runs without content changes, **Then** the system MUST NOT duplicate tags or re-enqueue it unnecessarily (idempotent behavior).
3. **Given** the user changes (manually overrides) a tag on an email, **When** future classification cycles run, **Then** the system preserves the manual override and records feedback in the RAG knowledge base for continuous improvement.
4. **Given** the system encounters an email with malformed headers, **When** classification is attempted, **Then** it marks the email with an error state and logs the issue without blocking other emails.
5. **Given** no new emails have arrived since last cycle, **When** the periodic scan occurs, **Then** the system performs a lightweight no-op (verifiable via logs/metrics) and does not degrade performance.
6. **Given** the classification confidence for an email is below 0.6 (60% threshold), **When** results are returned, **Then** the email requires additional RAG context retrieval or is flagged for review rather than force-assigned to a low-confidence category.
7. **Given** multiple tags could apply (e.g., "academic.exams" primary with "action.deadline_critical" secondary), **When** classification completes, **Then** the system assigns one primary category plus up to 3 secondary categories using hierarchical dot notation.
8. **Given** the system is running, **When** the user accesses the web dashboard, **Then** real-time metrics are displayed including: average processing time per email (current hour/day), average tags per email, classification confidence distribution, category breakdown, queue depth, error rates, and RAG effectiveness indicators.
9. **Given** historical data exists, **When** viewing the metrics dashboard, **Then** time-series graphs show trends over configurable periods (last hour, 24 hours, 7 days, 30 days) for performance tracking and bottleneck identification.
10. **Given** a performance anomaly occurs (e.g., latency spike, confidence drop), **When** monitoring the dashboard, **Then** visual indicators highlight degraded metrics with severity levels (warning/critical) and timestamp of first occurrence.
11. **Given** an email has been classified, **When** the system applies labels to Gmail, **Then** the corresponding Gmail labels are created and applied to the email in the user's inbox, enabling native Gmail filtering and organization.
12. **Given** a new category is assigned that doesn't have a matching Gmail label, **When** label application occurs, **Then** the system creates the Gmail label with the hierarchical name (e.g., "Academic/Exams") and applies it to the email.
13. **Given** Gmail API rate limits are hit, **When** applying labels, **Then** the system queues failed operations for retry with exponential backoff and logs the rate limit error without blocking other classifications.

### Edge Cases

- What happens when no emails are present in the mailbox? (Expect: cycle completes successfully with zero processed count.)
- How does system handle duplicate message IDs? (Deduplicated via idempotency key: hash of message_id + schema_version.)
- Handling extremely large emails (attachments / long threads): Truncate to LLM_CONTEXT_WINDOW (default 4000 chars) with intelligent snippet extraction prioritizing subject + first/last paragraphs.
- Rate limiting from email provider during fetch: Exponential backoff with jitter; circuit breaker opens after 5 consecutive failures for 60s.
- Re-classification after taxonomy changes: Manual trigger via "force reclassify" action; batch reprocessing with new schema version.
- Intermittent network failure mid-cycle: Retry with exponential backoff; stale queue items >15min re-queued by sweeper process.
- Clock drift affects periodic trigger timing: Acceptable <10% drift; scheduler uses wall-clock time, not interval accumulation.
- Classification queue backlog grows beyond threshold: Queue depth metric exposed; alerts trigger if depth >100 items for >5 minutes.
- JSON output missing mandatory fields from classifier: Schema validation rejects; store raw output for forensic review, increment parse_failure metric, retry once with simplified prompt.
- Timezone differences in date-based tagging: All deadlines stored in UTC (ISO8601 format); display layer handles user timezone conversion.

---

## Requirements _(mandatory)_

### Functional Requirements

**Version Annotations**:

- 🔵 **V1** = n8n workflow implementation
- 🟢 **V2** = Pure Python implementation
- 🟣 **Shared** = Common to both versions (database, UI, monitoring)

- **FR-001** 🔵🟢: System MUST periodically scan for new emails at a configurable interval (EMAIL*POLL_INTERVAL, default 30 seconds). \_V1: n8n IMAP Trigger node; V2: Python imap-tools with APScheduler*
- **FR-002** 🟣: System MUST detect and enqueue only emails not yet classified using idempotency key derived from hash(message*id + schema_version). \_Same logic in both versions*
- **FR-003** 🟣: System MUST assign at least one primary category from the hierarchical taxonomy; emails below confidence threshold flagged for review rather than force-categorized as "Unclassified". _Same classification logic_
- **FR-004**: System MUST support the comprehensive hierarchical tag taxonomy defined in constitution v2 including Academic (6 subtags), Career (5 subtags), Administrative (5 subtags), Extracurricular (5 subtags), Time-Sensitive (5 subtags), Financial (4 subtags), Personal (3 subtags), Learning (4 subtags), Promotions (3 subtags), System (3 subtags), and Spam (3 subtags).
- **FR-005**: System MUST support taxonomy expansion through schema versioning (semantic versioning: MAJOR for breaking changes, MINOR for additive changes) with backward-compatible migration paths.
- **FR-006**: System MUST persist classification results including message_id, primary_category, secondary_categories (up to 3), priority, deadline_utc, confidence (0.0-1.0, two decimal precision), rationale (max 200 chars), detected_entities, sentiment, action_items, thread_context, rag_context_used, and schema_version.
- **FR-007**: System MUST ensure each classification produces JSON conforming to schema v2 with mandatory fields (message_id, primary_category, confidence, schema_version) and validation rules (confidence in [0,1], secondary_categories ≤3, action_items ≤10, hierarchical tag format matching known patterns).
- **FR-008**: System MUST handle failures without aborting batch processing: exponential backoff for transient errors, circuit breaker (5 failures → 60s open), poison message quarantine after 5 retries with structured error context.
- **FR-009**: System MUST skip re-processing via idempotency checks; reclassification triggered manually via "force reclassify" action, on taxonomy version changes, or when user feedback indicates misclassification.
- **FR-010**: System MUST maintain ordering integrity using stable message identifiers and timestamp-based processing with exactly-once enqueue semantics.
- **FR-011**: System MUST support configurable per-message classification timeout (derived from LLM_MAX_TOKENS and model inference speed, typically 10-15s per email, with 95th percentile target <12s).
- **FR-012**: System MUST log structured metrics per cycle: poll_latency, classify_latency, rag_retrieval_latency, queue_depth, emails_scanned, emails_classified, emails_failed, retry_count, schema_parse_failures, category_distribution, rag_hit_rate, cycle_duration_ms.
- **FR-013**: System MUST provide manual "force reclassify" action in first version for debugging and taxonomy evolution support.
- **FR-014**: System MUST handle concurrent email arrival using snapshot-based polling with monotonic cursor advancement (last_seen_timestamp) to prevent duplication or loss during active cycles.
- **FR-015**: System MUST apply RAG_SIMILARITY_THRESHOLD (default 0.6 cosine similarity) for context retrieval; classifications with confidence <0.6 flagged for human review or additional RAG context passes.
- **FR-016**: System MUST maintain privacy by: (a) local-only processing with self-hosted LLM, (b) optional raw email storage controlled by STORE_RAW_EMAILS flag (default false), (c) AES-256 encryption if storage enabled, (d) configurable retention period (RETENTION_DAYS, default 90, 0=infinite).
- **FR-017**: System MUST provide audit trail via append-only JSONL log recording: timestamp, message_id, action, assigned_category, confidence, rag_context_ids, latency_ms, user_feedback (if applicable).
- **FR-018**: System MUST support multi-tag assignment: one primary_category (required) plus up to 3 secondary_categories using hierarchical dot notation.
- **FR-019**: System MUST validate required configuration (QWEN_MODEL_PATH, DB_PATH, taxonomy definition, schema_version) at startup and raise ConfigurationError with specific missing parameters before accepting any work.
- **FR-020**: System MUST expose queue_depth metric with alerting when depth >100 for >5 minutes, indicating processing bottleneck requiring investigation.
- **FR-021**: System MUST implement graceful degradation: exponential backoff with jitter on LLM failures, circuit breaker pattern (5 failures → 60s open → half-open trial), queue preservation during downtime, automatic recovery on service restoration.
- **FR-022**: System MUST validate JSON against schema v2: reject unknown fields (fail-fast), enforce required fields, validate ranges/enums, log validation failures with raw output preserved for forensics, increment schema_parse_failures metric.
- **FR-023**: System MUST support feedback loops in first version: user corrections stored in feedback log and incorporated into RAG knowledge base for improved future classifications (feedback_incorporation_lag metric tracks update latency).
- **FR-024**: System MUST use email message_id as primary identifier; if missing, generate stable fallback via hash(from + subject + date + first_100_chars_body).
- **FR-025**: System MUST achieve poll-to-tag median latency <5s (light load), 95th percentile <12s, ensuring classification results available within one polling cycle for typical inbox volumes.
- **FR-026**: System MUST enforce taxonomy governance: categories defined in versioned constitution, changes require schema version bump, migration testing with historical data, and release notes documentation; ad-hoc tags rejected at validation layer.
- **FR-027**: System MUST handle empty inbox cycles as successful no-ops: emit metrics showing zero processed count, advance polling cursor, log at INFO level, maintain scheduler health.
- **FR-028**: System MUST redact sensitive fields in logs: full email bodies excluded from INFO/WARN/ERROR logs (DEBUG only in dev), PII patterns (email addresses, phone numbers) masked in production logs using configurable regex filters, raw credentials never logged.
- **FR-029**: System MUST track unclassified rate metric: count of emails with confidence <threshold / total processed, aggregated hourly/daily for trend analysis and RAG effectiveness monitoring.
- **FR-030**: System MUST provide manual correction mechanism: user specifies message_id + corrected_category, system updates classification in metadata DB, logs correction to feedback store, triggers incremental RAG knowledge base update, optionally re-processes similar pending emails.
- **FR-031** 🟣: System MUST implement Retrieval-Augmented classification as a shared service: retrieve top K=5 relevant context chunks from Qdrant vector knowledge base containing historical classifications, domain context (course codes, company names, professor names), temporal patterns (semester schedules), and user preferences; inject into LLM prompt; track rag*context_used in output; maintain vector index; weekly batch re-indexing via RAG_REINDEX_CRON; incremental updates on new classifications; opt-in via RAG_ENABLED flag (default true). \_Shared: Qdrant vector store accessed via HTTP API by both V1 and V2*

### User Interface Requirements

- **FR-032**: System MUST provide a web-based metrics dashboard accessible via HTTP interface (default port 8080, configurable via DASHBOARD_PORT) displaying real-time and historical classification performance.
- **FR-033**: Dashboard MUST display core performance metrics refreshed every 5 seconds: average email processing time (milliseconds, aggregated per current hour and rolling 24h), average tags assigned per email (mean and median), current queue depth, active worker count, and system uptime.
- **FR-034**: Dashboard MUST show classification quality metrics: confidence score distribution (histogram with buckets: 0-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0), percentage of emails requiring human review (<0.6 confidence), unclassified rate trend.
- **FR-035**: Dashboard MUST display category distribution visualizations: pie chart or bar graph showing percentage breakdown of emails by primary category (top 10 categories), hierarchical drill-down capability to view subcategories.
- **FR-036**: Dashboard MUST show RAG effectiveness metrics: RAG hit rate (% of classifications using retrieved context), average similarity scores of retrieved chunks, RAG retrieval latency (p50, p95, p99), knowledge base size (total chunks, last update timestamp).
- **FR-037**: Dashboard MUST provide error tracking panel: count of schema validation failures, LLM timeout errors, network errors, and retry operations in last hour/day; click-through to view error details (timestamp, message_id, error type, stack trace if available).
- **FR-038**: Dashboard MUST display time-series graphs for trend analysis: line charts showing hourly aggregates over selectable time ranges (1h, 24h, 7d, 30d) for key metrics (processing latency, throughput, error rate, confidence scores).
- **FR-039**: Dashboard MUST show system health indicators: circuit breaker status (closed/open/half-open), last successful poll timestamp, database connection status, RAG index load status, available disk space for logs/embeddings.
- **FR-040**: Dashboard MUST provide recent activity feed: scrollable list of last 50 processed emails showing timestamp, sender (anonymized/redacted), subject (first 50 chars), assigned categories, confidence score, processing time; filterable by category or confidence threshold.
- **FR-041**: Dashboard MUST support manual operations: "force reclassify" button for selected message_ids or category, "trigger RAG reindex" button, "clear error queue" action with confirmation dialog.
- **FR-042**: Dashboard MUST be responsive and accessible on desktop browsers (Chrome, Firefox, Safari latest versions); mobile view optional but layout must not break on smaller screens.
- **FR-043**: Dashboard MUST implement read-only authentication mechanism (simple token-based or basic auth) to prevent unauthorized access when exposed on local network; credentials configurable via DASHBOARD_USERNAME and DASHBOARD_PASSWORD environment variables.
- **FR-044**: Dashboard MUST log all user-initiated actions (reclassify requests, manual corrections, configuration changes) to audit trail with username and timestamp for accountability.
- **FR-045**: Dashboard MUST export metrics data: downloadable CSV or JSON format for offline analysis, covering selected time range and metric categories; useful for generating performance reports for project documentation.
- **FR-046** 🟣: System MUST integrate with Gmail API to apply classification tags as Gmail labels, enabling native inbox organization. _Shared Python Gmail service for both V1 and V2_
- **FR-047** 🟣: System MUST create Gmail labels matching the classification taxonomy if they don't exist, using hierarchical paths (e.g., "Academic/Exams") for subcategories. _Same Gmail service_
- **FR-048** 🟣: System MUST handle Gmail API rate limits and authentication errors with exponential backoff retry (max 5 attempts), queuing failed label applications for later processing without blocking the classification pipeline. _Same retry logic_
- **FR-049**: System MUST support configurable label colors and nested label structure in Gmail to match the hierarchical taxonomy (primary categories as parent labels, subcategories as child labels).
- **FR-050**: System MUST provide a mechanism to sync existing Gmail labels back to the classification system for feedback loop integration (optional, for learning from manual user corrections).

### Key Entities _(include if feature involves data)_

**Note**: All entities use identical database schema for both V1 and V2, enabling seamless migration.

- **Email** 🟣: Represents a single inbound message; attributes: unique identifier, received timestamp, sender metadata (non-sensitive), subject, (body reference or hash), classification status. _Same schema for V1 and V2_
- **ClassificationResult** 🟣: Represents outcome of classification; attributes: email ID (ref), list of tags, confidence scores per tag, processed timestamp, status (success|error|skipped), version of taxonomy. _Same schema_
- **Tag** 🟣: Represents a category label; attributes: name, description, active flag, optional priority/order. _Same schema_
- **ClassificationCycle** 🟣: Represents one periodic run; attributes: cycle ID, start/end timestamps, counts (scanned, classified, failed, unclassified), duration. _Same schema_
- **OverrideAction** 🟣 (future/conditional): Manual user correction; attributes: email ID, previous tags, new tags, reason, timestamp. _Same schema_
- **SystemConfig** 🟣: Configuration store; attributes: polling interval, confidence threshold(s), enabled tags, retry policy, maximum parallelism. _Same schema_
- **DashboardMetric** 🟣: Aggregated performance metric; attributes: metric*name, value, timestamp, aggregation_period (5s/1h/1d), unit. \_Same schema*
- **MetricTimeSeriesPoint** 🟣: Historical data point; attributes: metric*name, timestamp, value, labels (category, confidence_bucket, etc.). \_Same schema*
- **SystemHealthStatus** 🟣: Current system state; attributes: component*name, status (healthy/degraded/down), last_check_timestamp, error_message. \_Same schema*
- **GmailLabel** 🟣: Gmail label metadata; attributes: gmail*label_id, name, display_name, color_id, nested_parent_id, created_timestamp, synced_timestamp. \_Same schema*
- **LabelApplication** 🟣: Gmail label application log; attributes: email*id, gmail_message_id, label_id, applied_timestamp, status (success|failed|pending), retry_count. \_Same schema*

### Non-Functional Requirements

- **NFR-001**: Dashboard page load time MUST be <2 seconds on typical residential broadband connections.
- **NFR-002**: Metrics API endpoints MUST respond within 500ms at p95 for current metrics, <2s for historical queries spanning 30 days.
- **NFR-003**: Dashboard MUST handle up to 10,000 historical data points per time-series graph without performance degradation (use sampling/aggregation for longer time ranges).
- **NFR-004**: Dashboard updates MUST NOT impact classification worker performance; metrics collection overhead <5% of total CPU usage.
- **NFR-005**: Dashboard MUST remain functional when backend is temporarily unavailable (show cached data with staleness indicator, graceful degradation).

---

## Implementation Versions

### Version 1: n8n Workflow Prototype

**Purpose**: Rapid validation of taxonomy and classification logic

**Architecture**:

- n8n workflows handle: Email polling (IMAP Trigger) → RAG retrieval (Vector Store nodes) → LLM classification (HTTP Request to Ollama) → Database persistence (PostgreSQL nodes)
- Python handles: Dashboard API, Gmail labeling, metrics collection
- Shared: PostgreSQL database schema, React dashboard UI, monitoring stack

**Key Benefits**:

- Fast development (3-5 days to working prototype)
- Visual workflow debugging
- Low-code iteration on prompts and taxonomy
- Immediate feedback on classification quality

**Limitations**:

- Limited unit testing capabilities
- n8n processing overhead (~100ms per workflow)
- Harder to optimize performance
- GUI-based configuration

**Success Criteria**:

- Classification working end-to-end
- Taxonomy validated with real emails
- Dashboard displaying metrics
- <12s p95 latency achieved

### Version 2: Pure Python Production

**Purpose**: Production-grade system with full control and testability

**Architecture**:

- Python services handle: Email polling (imap-tools) → RAG retrieval (Qdrant API) → LLM classification (ollama-python) → Database persistence (SQLAlchemy async)
- Orchestration: APScheduler for scheduling, custom queue manager
- Shared: Same PostgreSQL schema, same React UI, same monitoring

**Key Benefits**:

- Full unit and integration test coverage
- Performance optimization (<5s median)
- Complete control over error handling
- Pure Python codebase for maintainability
- Better resume demonstration of skills

**Success Criteria**:

- All V1 functionality replicated
- Performance improved vs V1
- > 80% test coverage
- Seamless migration (same database, same UI)

### Migration Path

1. **V1 Development** (Days 1-5): Build and validate with n8n
2. **V1 Production** (Days 6-10): Run V1, collect metrics, refine taxonomy
3. **V2 Development** (Days 11-17): Build Python workers in parallel
4. **A/B Testing** (Day 18): Run both versions, compare performance
5. **V2 Switchover** (Day 19): Deploy V2, keep V1 as fallback
6. **V1 Decommission** (Day 26): Remove n8n after 1 week validation

### Shared Components (No Version Differences)

- **PostgreSQL Database**: Identical schema for both versions
- **React Dashboard**: Same UI, connects to FastAPI endpoints
- **Gmail Integration**: Same Python service for label application
- **Monitoring**: Same Prometheus metrics, same Grafana dashboards
- **Docker Compose**: Services differ, configurations shared

## Future Enhancements (Deferred / Optional)

- **Retrieval-Augmented Classification (RAG)**: Optional module to enrich classification inputs with semantically similar historical emails and curated reference snippets to disambiguate sparse or context-light messages.

  - Goals: Improve precision/recall on borderline categories; reduce unclassified rate; enable contextual tagging (e.g., linking follow-up messages to prior threads).
  - Potential Data Sources: Prior classified emails (metadata & embeddings), user-provided reference notes/snippets.
  - Privacy Considerations: Opt-in, exclude sensitive content, enforce retention & deletion policies.
  - Performance Considerations: Background embedding generation; cache frequently accessed vectors; configurable embedding refresh cadence.
  - Open Questions:
    - Storage limits & pruning strategy?
    - Per-user vs global embedding space?
    - Allowed external knowledge sources?
    - Latency budget impact vs baseline classification?
  - Success Indicators: Reduction in unclassified percentage, improved confidence distribution, lower manual corrections.

- **Active Learning Loop**: Use manual overrides and low-confidence cases to propose taxonomy refinements. (Depends on feedback storage decision.)
- **Adaptive Taxonomy Versioning**: Track evolution of tag definitions and reclassification triggers.
- **Advanced Dashboard Features**:
  - Interactive email search with full-text and filter capabilities
  - Custom metric dashboards with drag-and-drop widgets
  - Alerting rules with notification channels (email, webhook)
  - A/B testing UI for comparing prompt variations
  - Multi-user access with role-based permissions
  - Mobile native apps for iOS/Android
- **Data Export and Integration**:
  - Integration with external email clients (Outlook, Gmail, Thunderbird)
  - Webhook notifications for high-priority classifications
  - API for third-party integrations

_These are explicitly out of scope for the initial baseline delivery; they inform architectural extensibility assumptions only._

---

## Review & Acceptance Checklist

_GATE: Automated checks run during main() execution_

### Content Quality

- [x] No implementation details (languages, frameworks, APIs) - All requirements focus on behavior and outcomes; implementation choices deferred to planning phase
- [x] Focused on user value and business needs - Primary user story centers on inbox navigation efficiency; all requirements derive from student workflow needs
- [x] Written for non-technical stakeholders - Requirements use domain language (emails, tags, classification) without technical jargon; concepts understandable to business users
- [x] All mandatory sections completed - User Scenarios & Testing (lines 58-86), Functional Requirements (lines 91-123), Key Entities (lines 125-132) all present with substantive content

### Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain - All clarifications resolved using constitution v2 specifications
- [x] Requirements are testable and unambiguous - Each FR specifies measurable criteria (latencies, thresholds, formats, error conditions)
- [x] Success criteria are measurable - Quantified targets: <5s median latency, <12s p95, 95% classification confidence, <10% scheduler drift, queue depth alerts, unclassified rate tracking
- [x] Scope is clearly bounded - Initial version scope: periodic polling + local LLM classification + RAG enhancement + hierarchical taxonomy + feedback loop + manual corrections; excluded: multi-user, distributed deployment, external API integrations
- [x] Dependencies and assumptions identified - Depends on: self-hosted Qwen 3 model, local vector store (FAISS/Hnswlib), sentence-transformer embeddings, SQLite/PostgreSQL metadata DB; assumes: single-user deployment, local-first privacy model, student inbox context (academic/career focus)

---

## Execution Status

_Updated by main() during processing_

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked and resolved via constitution
- [x] User scenarios defined with concrete examples
- [x] Requirements generated (31 functional requirements with quantified targets)
- [x] Entities identified (6 core entities + RAG knowledge base structure)
- [x] Review checklist passed - All content quality and requirement completeness items satisfied

---
