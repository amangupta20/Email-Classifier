# Data Model Design

**Feature**: Intelligent Inbox Email Classification  
**Date**: 2025-10-03  
**Status**: Phase 1 Complete

This document defines the database schema and entity relationships based on the feature specification and constitution requirements. Using PostgreSQL with SQLAlchemy 2.0 ORM for type-safe, async-capable data access.

## Design Principles

- **Entity-Relationship Model**: Normalized structure with JSONB for flexible fields (detected_entities, action_items)
- **PostgreSQL Optimization**: Partial indexes for common queries, JSONB for schema evolution, UUID for distributed scaling
- **Async Support**: SQLAlchemy async engine for non-blocking database operations
- **Migration Strategy**: Alembic for versioned schema changes
- **Validation**: Pydantic models for input validation, database constraints for integrity
- **Performance**: Index on frequently queried fields (message_id, timestamp, category), JSONB GIN indexes for metadata search
- **Privacy**: No raw email bodies stored by default, optional encrypted storage

## Core Entities

### 1. Email (emails table)

Represents inbound messages from IMAP polling.

**Fields**:

- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `message_id`: TEXT UNIQUE NOT NULL (IMAP UID or generated hash)
- `sender`: TEXT NOT NULL (email address)
- `sender_domain`: TEXT GENERATED ALWAYS AS (split_part(sender, '@', 2)) STORED (for indexing)
- `subject`: TEXT NOT NULL
- `received_timestamp`: TIMESTAMP WITH TIME ZONE DEFAULT now()
- `body_hash`: TEXT (SHA-256 hash for idempotency, excludes body content)
- `body_encrypted`: BYTEA (optional AES-256 encrypted raw email body)
- `classification_status`: EMAIL_STATUS ENUM ('pending', 'classifying', 'classified', 'failed', 'quarantined') DEFAULT 'pending'
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT now()
- `updated_at`: TIMESTAMP WITH TIME ZONE DEFAULT now() ON UPDATE now()

**Indexes**:

- UNIQUE (message_id)
- INDEX on sender_domain
- INDEX on received_timestamp
- INDEX on classification_status
- PARTIAL INDEX on classification_status = 'pending' (for efficient polling)

**Pydantic Model**:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class EmailStatus(str, Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    FAILED = "failed"
    QUARANTINED = "quarantined"

class Email(BaseModel):
    id: Optional[str] = Field(default=None, description="UUID primary key")
    message_id: str = Field(..., description="Stable email identifier")
    sender: str = Field(..., description="Sender email address")
    subject: str = Field(..., description="Email subject")
    received_timestamp: datetime = Field(..., description="When email was received")
    body_hash: str = Field(..., description="Hash for idempotency")
    body_encrypted: Optional[bytes] = Field(None, description="Optional encrypted body")
    classification_status: EmailStatus = Field(default=EmailStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. ClassificationResult (classifications table)

Stores LLM classification outcomes.

**Fields**:

- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `email_id`: UUID REFERENCES emails(id) ON DELETE CASCADE NOT NULL
- `primary_category`: TEXT NOT NULL (e.g., 'academic.exams')
- `secondary_categories`: TEXT[] DEFAULT ARRAY[]::TEXT[] (up to 3: 'action.deadline_critical', etc.)
- `priority`: PRIORITY ENUM ('low', 'normal', 'high', 'urgent') DEFAULT 'normal'
- `deadline_utc`: TIMESTAMP WITH TIME ZONE
- `deadline_confidence`: DEADLINE_CONFIDENCE ENUM ('extracted', 'inferred', 'none') DEFAULT 'none'
- `confidence`: NUMERIC(3,2) CHECK (confidence >= 0 AND confidence <= 1) NOT NULL
- `rationale`: TEXT (max 200 chars, LLM explanation)
- `detected_entities`: JSONB DEFAULT '{}'::JSONB (course_codes, company_names, etc.)
- `sentiment`: SENTIMENT ENUM ('positive', 'neutral', 'negative', 'urgent') DEFAULT 'neutral'
- `action_items`: JSONB DEFAULT '[]'::JSONB (array of {action, deadline_utc, completed})
- `thread_context`: JSONB DEFAULT '{}'::JSONB (is_reply, thread_id, previous_categories)
- `rag_context_used`: TEXT[] DEFAULT ARRAY[]::TEXT[] (chunk IDs retrieved)
- `suggested_folder`: TEXT
- `schema_version`: TEXT DEFAULT 'v2' NOT NULL
- `processed_timestamp`: TIMESTAMP WITH TIME ZONE DEFAULT now()
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT now()

**Indexes**:

- FOREIGN KEY (email_id)
- INDEX on primary_category
- INDEX on confidence
- INDEX on processed_timestamp
- GIN INDEX on detected_entities
- GIN INDEX on action_items

**Constraints**:

- CHECK (array_length(secondary_categories, 1) <= 3)
- CHECK (jsonb_array_length(action_items) <= 10)

**Pydantic Model**:

```python
class DeadlineConfidence(str, Enum):
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    NONE = "none"

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    URGENT = "urgent"

class ActionItem(BaseModel):
    action: str
    deadline_utc: Optional[datetime]
    completed: bool = False

class ClassificationResult(BaseModel):
    id: Optional[str] = None
    email_id: str
    primary_category: str
    secondary_categories: list[str] = Field(default_factory=list, max_items=3)
    priority: Priority = Priority.NORMAL
    deadline_utc: Optional[datetime] = None
    deadline_confidence: DeadlineConfidence = DeadlineConfidence.NONE
    confidence: float = Field(..., ge=0, le=1)
    rationale: str = Field(..., max_length=200)
    detected_entities: dict = Field(default_factory=dict)
    sentiment: Sentiment = Sentiment.NEUTRAL
    action_items: list[ActionItem] = Field(default_factory=list, max_items=10)
    thread_context: dict = Field(default_factory=dict)
    rag_context_used: list[str] = Field(default_factory=list)
    suggested_folder: Optional[str] = None
    schema_version: str = "v2"
    processed_timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 3. Tag (tags table)

Category definitions from constitution.

**Fields**:

- `name`: TEXT PRIMARY KEY (hierarchical: 'academic.exams')
- `description`: TEXT NOT NULL
- `category_type`: CATEGORY_TYPE ENUM ('academic', 'career', 'admin', etc.) NOT NULL
- `active`: BOOLEAN DEFAULT true
- `priority_order`: INTEGER DEFAULT 0
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT now()

**Indexes**:

- PRIMARY KEY (name)
- INDEX on category_type
- INDEX on active

**Sample Data** (from constitution, ~45 tags):

```sql
INSERT INTO tags (name, description, category_type) VALUES
('academic.coursework', 'Assignments, homework, project updates', 'academic'),
('academic.exams', 'Exam schedules, room assignments, practice tests', 'academic'),
('career.internship', 'Internship offers, application deadlines, interview invitations', 'career'),
('action.deadline_critical', '<24h, requires immediate attention', 'action'),
-- ... 41 more from constitution
```

### 4. ClassificationCycle (cycles table)

Periodic polling runs.

**Fields**:

- `cycle_id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `start_timestamp`: TIMESTAMP WITH TIME ZONE NOT NULL
- `end_timestamp`: TIMESTAMP WITH TIME ZONE
- `emails_scanned`: INTEGER DEFAULT 0
- `emails_classified`: INTEGER DEFAULT 0
- `emails_failed`: INTEGER DEFAULT 0
- `queue_depth_start`: INTEGER DEFAULT 0
- `queue_depth_end`: INTEGER DEFAULT 0
- `duration_ms`: INTEGER
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT now()

**Indexes**:

- INDEX on start_timestamp (for time-series queries)

### 5. SystemConfig (config table)

Runtime configuration.

**Fields**:

- `key`: TEXT PRIMARY KEY (e.g., 'EMAIL_POLL_INTERVAL')
- `value`: TEXT NOT NULL
- `value_type`: TEXT DEFAULT 'string' CHECK (value_type IN ('string', 'int', 'float', 'bool'))
- `updated_at`: TIMESTAMP WITH TIME ZONE DEFAULT now()

**Sample Data**:

```sql
INSERT INTO config (key, value, value_type) VALUES
('EMAIL_POLL_INTERVAL', '30', 'int'),
('RAG_TOP_K', '5', 'int'),
('RAG_SIMILARITY_THRESHOLD', '0.6', 'float'),
('LLM_TEMPERATURE', '0.1', 'float');
```

### 6. UserFeedback (feedback table)

Manual corrections for RAG improvement.

**Fields**:

- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `email_id`: UUID REFERENCES emails(id) ON DELETE CASCADE NOT NULL
- `original_category`: TEXT NOT NULL
- `corrected_category`: TEXT NOT NULL
- `reason`: TEXT (optional explanation)
- `timestamp`: TIMESTAMP WITH TIME ZONE DEFAULT now()
- `incorporated`: BOOLEAN DEFAULT false (RAG KB updated)

**Indexes**:

- FOREIGN KEY (email_id)
- INDEX on timestamp
- INDEX on incorporated = false (pending updates)

### 7. DashboardMetric (metrics table)

Aggregated performance metrics.

**Fields**:

- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `metric_name`: TEXT NOT NULL (e.g., 'avg_processing_time_ms')
- `value`: NUMERIC NOT NULL
- `timestamp`: TIMESTAMP WITH TIME ZONE NOT NULL
- `aggregation_period`: TEXT DEFAULT '5s' CHECK (aggregation_period IN ('5s', '1m', '1h', '1d'))
- `unit`: TEXT (e.g., 'ms', 'tags', '%')
- `labels`: JSONB DEFAULT '{}'::JSONB (category, confidence_bucket, etc.)

**Indexes**:

- INDEX on (metric_name, timestamp) (time-series queries)
- GIN INDEX on labels

**Time-series Queries** (for Grafana):

```sql
-- Last 24h avg processing time
SELECT
    date_trunc('hour', timestamp) as hour,
    AVG(value) as avg_time
FROM metrics
WHERE metric_name = 'avg_processing_time_ms'
    AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;

-- Category distribution (last hour)
SELECT
    labels->>'category' as category,
    AVG(value) as avg_confidence
FROM metrics
WHERE metric_name = 'confidence_by_category'
    AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY category;
```

### 8. SystemHealthStatus (health_checks table)

System component health monitoring.

**Fields**:

- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `component_name`: TEXT NOT NULL (e.g., 'ollama', 'qdrant', 'postgres')
- `status`: HEALTH_STATUS ENUM ('healthy', 'degraded', 'down') NOT NULL
- `last_check_timestamp`: TIMESTAMP WITH TIME ZONE DEFAULT now()
- `error_message`: TEXT
- `metrics`: JSONB DEFAULT '{}'::JSONB (latency, error_count, etc.)

**Indexes**:

- INDEX on component_name, last_check_timestamp

## Entity Relationships

```
Email 1:1 ClassificationResult
Email 1:N UserFeedback
ClassificationResult M:N Tag (via secondary_categories array mapping)
ClassificationCycle 1:N Email (processed in cycle, but denormalized for performance)
SystemConfig 0:N All entities (global settings)
DashboardMetric N:1 ClassificationCycle (metrics per cycle)
SystemHealthStatus 0:N All components
```

**ER Diagram** (conceptual):

```
┌─────────────┐    ┌──────────────────────┐    ┌─────────────┐
│   Email     │1───│ ClassificationResult │*───│   Tag       │
│ - message_id│    │ - primary_category   │    │ - name      │
│ - sender    │    │ - confidence         │    │ - type      │
│ - subject   │    │ - action_items       │    │             │
└─────────────┘    └──────────────────────┘    └─────────────┘
         │                    │
         │1                   │N
         │                    │
         └────────────────────┼──┐
                              │  │
                     ┌────────┼──┼────────┐
                     │        │  │        │
              ┌─────────────┐ │  │ ┌─────────────┐
              │ UserFeedback│ │  │ │DashboardMetric│
              │ - corrected │ │  │ │ - metric_name│
              │ - reason    │ │  │ │ - value      │
              └─────────────┘ │  │ └─────────────┘
                              │  │
                       ┌──────┼──┼──────┐
                       │      │  │      │
                ┌─────────────┐ │  │ ┌─────────────┐
                │Classification│ │  │ │SystemConfig │
                │ Cycle       │ │  │ │ - key       │
                │ - start_time│ │  │ │ - value     │
                └─────────────┘ │  │ └─────────────┘
                               │  │
                        ┌──────┼──┼──────┐
                        │      │  │      │
                 ┌─────────────┐ │  │ ┌─────────────┐
                 │SystemHealth │ │  │ │SystemHealth │
                 │ Status      │ │  │ │  Status     │
                 └─────────────┘ │  │ └─────────────┘
```

## Schema SQL (PostgreSQL)

```sql
-- Enums
CREATE TYPE email_status AS ENUM ('pending', 'classifying', 'classified', 'failed', 'quarantined');
CREATE TYPE priority AS ENUM ('low', 'normal', 'high', 'urgent');
CREATE TYPE sentiment AS ENUM ('positive', 'neutral', 'negative', 'urgent');
CREATE TYPE deadline_confidence AS ENUM ('extracted', 'inferred', 'none');
CREATE TYPE category_type AS ENUM (
    'academic', 'career', 'admin', 'clubs', 'sports', 'cultural',
    'action', 'finance', 'personal', 'learning', 'promotion',
    'system', 'spam'
);

-- Enable extensions (for pgvector if using Supabase option)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;  -- For pgvector in Supabase

-- Tables
CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT UNIQUE NOT NULL,
    sender TEXT NOT NULL,
    sender_domain TEXT GENERATED ALWAYS AS (split_part(sender, '@', 2)) STORED,
    subject TEXT NOT NULL,
    received_timestamp TIMESTAMPTZ DEFAULT now(),
    body_hash TEXT NOT NULL,
    body_encrypted BYTEA,
    classification_status email_status DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_emails_message_id ON emails(message_id);
CREATE INDEX idx_emails_sender_domain ON emails(sender_domain);
CREATE INDEX idx_emails_received ON emails(received_timestamp);
CREATE INDEX idx_emails_status ON emails(classification_status);
CREATE INDEX idx_emails_pending ON emails(classification_status) WHERE classification_status = 'pending';

CREATE TABLE classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE NOT NULL,
    primary_category TEXT NOT NULL,
    secondary_categories TEXT[] DEFAULT '{}',
    priority priority DEFAULT 'normal',
    deadline_utc TIMESTAMPTZ,
    deadline_confidence deadline_confidence DEFAULT 'none',
    confidence NUMERIC(3,2) CHECK (confidence >= 0 AND confidence <= 1) NOT NULL,
    rationale TEXT CHECK (length(rationale) <= 200),
    detected_entities JSONB DEFAULT '{}',
    sentiment sentiment DEFAULT 'neutral',
    action_items JSONB DEFAULT '[]',
    thread_context JSONB DEFAULT '{}',
    rag_context_used TEXT[] DEFAULT '{}',
    suggested_folder TEXT,
    schema_version TEXT DEFAULT 'v2' NOT NULL,
    processed_timestamp TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_classifications_email ON classifications(email_id);
CREATE INDEX idx_classifications_category ON classifications(primary_category);
CREATE INDEX idx_classifications_confidence ON classifications(confidence);
CREATE INDEX idx_classifications_processed ON classifications(processed_timestamp);
CREATE INDEX idx_classifications_entities ON classifications USING GIN (detected_entities);
CREATE INDEX idx_classifications_actions ON classifications USING GIN (action_items);
ALTER TABLE classifications ADD CONSTRAINT chk_secondary_categories CHECK (array_length(secondary_categories, 1) <= 3);
ALTER TABLE classifications ADD CONSTRAINT chk_action_items CHECK (jsonb_array_length(action_items) <= 10);

CREATE TABLE tags (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    category_type category_type NOT NULL,
    active BOOLEAN DEFAULT true,
    priority_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_tags_type ON tags(category_type);
CREATE INDEX idx_tags_active ON tags(active) WHERE active = true;

CREATE TABLE cycles (
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    start_timestamp TIMESTAMPTZ NOT NULL,
    end_timestamp TIMESTAMPTZ,
    emails_scanned INTEGER DEFAULT 0,
    emails_classified INTEGER DEFAULT 0,
    emails_failed INTEGER DEFAULT 0,
    queue_depth_start INTEGER DEFAULT 0,
    queue_depth_end INTEGER DEFAULT 0,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_cycles_start ON cycles(start_timestamp);

CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string' CHECK (value_type IN ('string', 'int', 'float', 'bool')),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE NOT NULL,
    original_category TEXT NOT NULL,
    corrected_category TEXT NOT NULL,
    reason TEXT,
    timestamp TIMESTAMPTZ DEFAULT now(),
    incorporated BOOLEAN DEFAULT false
);

CREATE INDEX idx_feedback_email ON feedback(email_id);
CREATE INDEX idx_feedback_timestamp ON feedback(timestamp);
CREATE INDEX idx_feedback_pending ON feedback(incorporated) WHERE incorporated = false;

CREATE TABLE metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name TEXT NOT NULL,
    value NUMERIC NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    aggregation_period TEXT DEFAULT '5s' CHECK (aggregation_period IN ('5s', '1m', '1h', '1d')),
    unit TEXT,
    labels JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_metrics_name_time ON metrics(metric_name, timestamp);
CREATE INDEX idx_metrics_labels ON metrics USING GIN (labels);

CREATE TABLE health_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_name TEXT NOT NULL,
    status TEXT CHECK (status IN ('healthy', 'degraded', 'down')) NOT NULL,
    last_check_timestamp TIMESTAMPTZ DEFAULT now(),
    error_message TEXT,
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_health_component_time ON health_checks(component_name, last_check_timestamp);
```

## Migration Strategy (Alembic)

**Initial Migration** (alembic/versions/001_initial_schema.py):

```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create enums
    op.execute("CREATE TYPE email_status AS ENUM ('pending', 'classifying', 'classified', 'failed', 'quarantined')")
    # ... other enums

    # Create tables
    op.create_table(
        'emails',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.Text(), nullable=False),
        # ... other columns
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id')
    )
    # ... other tables

    # Create indexes
    op.create_index('idx_emails_message_id', 'emails', ['message_id'], unique=True)
    # ... other indexes

def downgrade():
    # Drop tables in reverse order
    op.drop_table('health_checks')
    # ... reverse operations
```

**Future Migrations**:

- Add new entity fields (e.g., `ai_generated_summary` column)
- Schema version bumps (add `schema_version` column)
- Index optimization based on query patterns
- JSONB column restructuring for schema evolution

## Query Patterns

### 1. Recent Pending Emails (for polling)

```sql
SELECT * FROM emails
WHERE classification_status = 'pending'
    AND received_timestamp > NOW() - INTERVAL '1 hour'
ORDER BY received_timestamp;
```

### 2. Classification Statistics (for dashboard)

```sql
SELECT
    primary_category,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence,
    COUNT(*) FILTER (WHERE confidence < 0.6) as low_confidence
FROM classifications
WHERE processed_timestamp > NOW() - INTERVAL '24 hours'
GROUP BY primary_category
ORDER BY count DESC
LIMIT 10;
```

### 3. Time-series Metrics (for Grafana)

```sql
SELECT
    date_trunc('hour', timestamp) as hour,
    AVG(value) as avg_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95
FROM metrics
WHERE metric_name = 'classification_latency_ms'
    AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;
```

### 4. RAG Context Usage Analysis

```sql
SELECT
    array_length(rag_context_used, 1) as context_count,
    AVG(confidence) as avg_confidence
FROM classifications
WHERE processed_timestamp > NOW() - INTERVAL '24 hours'
    AND cardinality(rag_context_used) > 0
GROUP BY context_count;
```

## Data Volume Estimates

- **Emails table**: 200 emails/day = ~73K/year, ~10MB storage
- **Classifications table**: Same as emails, ~15MB/year (JSONB overhead)
- **Metrics table**: 12 metrics _ 12 intervals/hour _ 24h \* 365 = ~100K rows/year, ~20MB
- **Feedback table**: 5% correction rate = ~10 feedbacks/day, <1MB/year
- **Tags table**: Static ~45 rows, negligible
- **Total**: ~50MB/year, easily handled by PostgreSQL

## Security Considerations

- **Row-Level Security** (PostgreSQL): Enable RLS policies for multi-user future
- **Connection Pooling**: asyncpg pool_size=5 prevents connection exhaustion
- **Query Parameterization**: SQLAlchemy prevents SQL injection
- **Sensitive Data**: body_encrypted uses AES-256, keys via env vars
- **Audit Trail**: All changes logged to JSONL with user_id (for future multi-user)

## Testing Strategy

- **Unit Tests**: Individual entity validation, Pydantic models
- **Integration Tests**: Full CRUD operations with test DB
- **Contract Tests**: JSON schema validation against sample data
- **Performance Tests**: Query optimization, index effectiveness

This data model supports all functional requirements while maintaining extensibility for future enhancements (multi-user, additional entity types, advanced analytics).

**Next**: Generate contracts and quickstart documentation.
