# Research & Technology Decisions

**Feature**: Intelligent Inbox Email Classification  
**Date**: 2025-10-03  
**Status**: Phase 0 Complete

## Executive Summary

This document captures technology research and decisions for implementing a local-first email classification system using Python 3.11+. All choices prioritize: (1) local execution privacy with GPU acceleration, (2) performance targets (<5s median latency), (3) simplicity per constitution, (4) resume-worthy modern tech stack with self-hosting experience including Supabase and Convex options.

---

## 1. Python LLM Integration for Qwen 3 8B

### Decision: **Ollama**

### Rationale:

- **GPU acceleration**: Native CUDA/ROCm support without manual configuration, dramatically improves inference speed
- **Model management**: Simple `ollama pull qwen3:8b` - no manual GGUF downloads or path management
- **Docker-friendly**: Official Docker images with GPU passthrough, simplifies deployment
- **OpenAI-compatible API**: Python client with clean async interface, easy integration
- **Production-ready**: Handles model loading, unloading, concurrent requests automatically
- **Flexibility**: Can run models locally or point to remote Ollama instance for distributed setups
- **Constitutional alignment**: Supports temperature settings, JSON mode, streaming

### Alternatives Considered:

| Option                | Pros                                                                   | Cons                                                | Verdict                     |
| --------------------- | ---------------------------------------------------------------------- | --------------------------------------------------- | --------------------------- |
| **Ollama**            | GPU acceleration, model management, Docker-friendly, OpenAI-compatible | Requires Ollama daemon                              | ✅ **Selected**             |
| **llama-cpp-python**  | Fast C++ core, low memory, GGUF support, JSON mode                     | Manual GPU setup, no model management               | ❌ More complex setup       |
| **vLLM**              | Fastest inference, batching, OpenAI-compatible API                     | 4GB+ memory overhead, complex setup                 | ❌ Overkill for single-user |
| **transformers (HF)** | Official model support, easy to use                                    | Slower inference, higher memory, PyTorch dependency | ❌ Performance concerns     |
| **LM Studio**         | GUI, easy model management                                             | Not automation-friendly, Windows/Mac focus          | ❌ Not server-oriented      |

### Integration Notes:

```python
import ollama
import asyncio

# Synchronous API
response = ollama.chat(
    model='qwen3:8b',
    messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ],
    format='json',  # Enforce JSON output
    options={
        'temperature': 0.1,  # Deterministic classification
        'num_ctx': 4096,     # Context window
    }
)

# Async API (for FastAPI integration)
async def classify_email_async(prompt: str) -> dict:
    response = await asyncio.to_thread(
        ollama.chat,
        model='qwen3:8b',
        messages=[{'role': 'user', 'content': prompt}],
        format='json'
    )
    return response['message']['content']
```

**Performance validation**: Qwen 3 8B with GPU achieves ~0.5-2s inference (NVIDIA RTX 3060+), meeting <12s p95 with huge headroom. CPU fallback still ~4-6s.

---

## 2. Web Framework for Dashboard + API

### Decision: **FastAPI**

### Rationale:

- **Async-first**: Built on Starlette, async/await throughout for non-blocking I/O
- **Auto-generated OpenAPI docs**: `/docs` endpoint with Swagger UI out-of-box
- **Pydantic integration**: Request/response validation using same models as schema validator
- **Performance**: <1ms overhead per request, easily meets <500ms p95 target
- **Modern Python**: Type hints, dependency injection, middleware support
- **Constitutional alignment**: Contract-first API design via OpenAPI spec

### Alternatives Considered:

| Option           | Pros                                   | Cons                                        | Verdict                 |
| ---------------- | -------------------------------------- | ------------------------------------------- | ----------------------- |
| **FastAPI**      | Async, OpenAPI, Pydantic, modern, fast | Slightly steeper learning curve             | ✅ **Selected**         |
| **Flask**        | Simple, mature, huge ecosystem         | Synchronous (blocks on I/O), manual OpenAPI | ❌ Blocks worker thread |
| **Quart**        | Async Flask clone, familiar API        | Smaller ecosystem, less documentation       | ❌ FastAPI more popular |
| **Starlette**    | Minimal, fast, core of FastAPI         | No built-in validation/OpenAPI              | ❌ Too low-level        |
| **Django + DRF** | Batteries-included, ORM, admin         | Heavy, synchronous ORM, overkill            | ❌ Too much overhead    |

### Integration Notes:

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Email Classifier Dashboard", version="1.0.0")

# CORS for frontend
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/api/internal/metrics")

@app.get("/metrics/current")
async def get_current_metrics():
    return await metrics_service.get_current_snapshot()
```

**SSE Support**: FastAPI supports Server-Sent Events via `StreamingResponse` for real-time dashboard updates (alternative to 5s polling).

---

## 3. Vector Store for RAG Retrieval

### Decision: **Qdrant (Primary) with Self-Hosted Supabase pgvector and Convex as Alternatives**

### Rationale for Qdrant:

- **Purpose-built**: Dedicated vector database with rich filtering capabilities
- **Performance**: Rust-based, <50ms p95 retrieval, HNSW indexing
- **Docker-friendly**: Official images, easy self-hosting alongside PostgreSQL
- **Scalability**: Starts simple, scales to millions of vectors without code changes
- **Features**: Metadata filtering, hybrid search (vector + filters), snapshots, REST + gRPC APIs
- **Python SDK**: Clean async client, integrates well with FastAPI
- **Constitutional alignment**: Incremental updates, atomic operations, snapshots for weekly backups
- **Learning opportunity**: Industry-standard vector DB experience (resume-worthy)

### Self-Hosted Supabase with pgvector (Recommended Alternative):

Supabase is open-source and fully self-hostable, providing PostgreSQL with built-in pgvector extension for vector search. This consolidates database and vector storage.

**Self-Hosting Setup**:

- Use Docker Compose with official Supabase images
- Includes PostgreSQL, pgvector, auth, realtime, storage
- Enable pgvector extension: `CREATE EXTENSION vector;`
- pgvector supports cosine similarity, L2 distance, inner product
- Indexes: IVFFlat or HNSW for fast approximate nearest neighbor search

**Integration Notes (Supabase pgvector)**:

```python
import psycopg2
from supabase import create_client, Client
import numpy as np

# Self-hosted Supabase client
supabase: Client = create_client(
    supabase_url="http://localhost:8000",
    supabase_key="your-anon-key"  # Generated locally
)

# Enable pgvector (run once in SQL editor)
# CREATE EXTENSION IF NOT EXISTS vector;

# Store embedding (vector column)
def store_embedding(email_id: str, embedding: np.ndarray, metadata: dict):
    supabase.table('email_embeddings').insert({
        'email_id': email_id,
        'embedding': embedding.tolist(),  # vector(768)
        'metadata': metadata
    }).execute()

# Vector search with cosine similarity
def retrieve_context(query_embedding: np.ndarray, k: int = 5) -> List[dict]:
    results = supabase.rpc('match_embeddings', {
        'query_embedding': query_embedding.tolist(),
        'match_threshold': 0.6,
        'match_count': k
    }).execute()

    return [row['metadata'] for row in results.data]
```

**Docker Compose for Self-Hosted Supabase**:

```yaml
services:
  supabase-db:
    image: supabase/postgres:15.1.0.147
    environment:
      POSTGRES_PASSWORD: your_password
    volumes:
      - supabase_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  supabase-studio:
    image: supabase/studio:latest
    environment:
      SUPABASE_DB_URL: postgresql://postgres:your_password@supabase-db:5432/postgres
    ports:
      - "8000:3000"
    depends_on:
      - supabase-db

volumes:
  supabase_data:
```

**Pros of Self-Hosted Supabase**:

- **All-in-one**: Database + vector search + auth + realtime in one stack
- **Cost-free**: Open-source, no vendor lock-in
- **Learning**: Full self-hosting experience (Docker, PostgreSQL, extensions)
- **Resume-worthy**: "Self-hosted Supabase with pgvector for RAG"

**Cons**:

- **Performance**: ~2-3x slower than dedicated vector DB for large indexes
- **Complexity**: More services to manage than simple PostgreSQL

### Convex Self-Hosting (Alternative):

Convex is primarily cloud-based but supports self-hosting via their edge deployment platform (Convex Edge).

**Self-Hosting Approach**:

- Run Convex backend on your infrastructure (Docker/Kubernetes)
- Use Convex CLI for local development
- Vector search via Convex's built-in vector indexing
- Real-time subscriptions for dashboard updates

**Integration Notes (Convex)**:

```python
from convex import ConvexClient
import asyncio

client = ConvexClient("http://localhost:3010")  # Self-hosted

# Store embedding
await client.call("storeEmbedding", {
    "emailId": email_id,
    "embedding": embedding.tolist(),
    "metadata": metadata
})

# Search
results = await client.call("searchEmbeddings", {
    "queryEmbedding": query_embedding.tolist(),
    "k": 5,
    "threshold": 0.6
})
```

**Docker for Convex Self-Hosting** (Experimental):
Convex self-hosting is more advanced and may require custom setup. For learning, focus on Supabase which is more mature for self-hosting.

**Pros of Convex Self-Hosting**:

- **Real-time**: Built-in subscriptions for dashboard updates
- **Serverless-like**: Edge functions, automatic scaling
- **Integrated**: Database + auth + realtime in one platform

**Cons**:

- **Proprietary**: Less open-source than Supabase
- **Learning curve**: Edge deployment concepts
- **Maturity**: Self-hosting less documented than Supabase

### Alternatives Considered:

| Option                | Pros                                             | Cons                                                   | Verdict                           |
| --------------------- | ------------------------------------------------ | ------------------------------------------------------ | --------------------------------- |
| **Qdrant**            | Purpose-built, self-hosted, fast, rich filtering | Separate service (Docker)                              | ✅ **Primary** (best performance) |
| **Supabase pgvector** | PostgreSQL extension, same DB, self-hostable     | Slower than dedicated, limited filtering               | ✅ **Fallback** (learning focus)  |
| **Convex**            | Serverless-like, real-time, integrated           | Proprietary, edge deployment complexity                | 🟡 **Alternative** (cloud-hybrid) |
| **FAISS**             | Fast, library-only, no service                   | Manual persistence, no filtering, no concurrent access | ❌ Too low-level                  |
| **ChromaDB**          | Batteries-included, document store               | Heavier, SQLite-based, less production-ready           | ❌ Over-engineered                |

**Recommended Stack**: Start with self-hosted Supabase (PostgreSQL + pgvector) for learning, migrate to Qdrant if vector search performance becomes bottleneck.

---

## 5. Frontend Framework for Metrics Dashboard

### Decision: **React + Recharts**

### Rationale:

- **Component-based**: Modular design (MetricsCard, TimeSeriesChart) aligns with dashboard requirements
- **Recharts library**: Declarative charts, responsive, built for React
- **Modern resume tech**: React dominates job market, demonstrates frontend skills
- **Ecosystem**: Huge npm ecosystem for utilities (axios, date-fns, etc.)
- **Real-time updates**: useState + useEffect for 5s polling, or SSE via EventSource API

### Alternatives Considered:

| Option                    | Pros                                     | Cons                                      | Verdict                            |
| ------------------------- | ---------------------------------------- | ----------------------------------------- | ---------------------------------- |
| **React + Recharts**      | Popular, component-based, good charts    | Larger bundle, React overhead             | ✅ **Selected** (best for resume)  |
| **Vue + ECharts**         | Progressive, ECharts powerful            | Less popular than React                   | ❌ React better for resume         |
| **Svelte + Plotly**       | Smallest bundle, fast, Plotly scientific | Smaller ecosystem, less job demand        | ❌ React more marketable           |
| **Vanilla JS + Chart.js** | No framework, simple, fast               | Manual DOM management, harder to maintain | ❌ Not demonstrating modern skills |
| **Solid.js + Victory**    | Reactive, performant                     | Too new, less documentation               | ❌ Bleeding edge risk              |

### Integration Notes:

```jsx
import React, { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";

function TimeSeriesChart({ metric, period }) {
  const [data, setData] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      const response = await fetch(
        `/api/metrics/timeseries?metric=${metric}&period=${period}`
      );
      setData(await response.json());
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // 5s refresh
    return () => clearInterval(interval);
  }, [metric, period]);

  return (
    <LineChart width={600} height={300} data={data}>
      <XAxis dataKey="timestamp" />
      <YAxis />
      <Tooltip />
      <Line type="monotone" dataKey="value" stroke="#8884d8" />
    </LineChart>
  );
}
```

**Build tool**: Vite for fast development + optimized production builds (<200KB gzipped target).

---

## 6. Task Scheduling for Email Polling

### Decision: **APScheduler (Advanced Python Scheduler)**

### Rationale:

- **Feature-rich**: Interval, cron, date-based triggers; exactly what we need for 30s polling
- **Reliable**: Tracks job execution, handles missed runs (grace period), prevents overlaps
- **Python-native**: No external daemon, runs in-process
- **Async support**: AsyncIOScheduler for non-blocking with FastAPI
- **Monitoring**: Job statistics, next run time, execution history
- **Constitutional alignment**: <10% drift achievable with wall-clock intervals

### Alternatives Considered:

| Option                   | Pros                                      | Cons                                              | Verdict                  |
| ------------------------ | ----------------------------------------- | ------------------------------------------------- | ------------------------ |
| **APScheduler**          | Feature-rich, reliable, async, in-process | Slightly heavy (~1MB)                             | ✅ **Selected**          |
| **schedule**             | Ultra-simple API, lightweight             | Manual async handling, no missed run tracking     | ❌ Too basic             |
| **asyncio-based custom** | Minimal dependencies, full control        | Manual implementation of reliability features     | ❌ Reinventing wheel     |
| **Celery**               | Distributed, scalable, retry logic        | Requires Redis/RabbitMQ broker, massive overkill  | ❌ Too complex           |
| **Prefect/Airflow**      | Workflow orchestration, UI                | Heavy infrastructure, designed for data pipelines | ❌ Enterprise-scale only |

### Integration Notes:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler()

async def poll_and_classify():
    try:
        new_emails = await email_poller.fetch_new()
        for email in new_emails:
            await queue_manager.enqueue(email)
    except Exception as e:
        logger.error(f"Polling failed: {e}")
        circuit_breaker.record_failure()

scheduler.add_job(
    poll_and_classify,
    trigger=IntervalTrigger(seconds=int(os.getenv('EMAIL_POLL_INTERVAL', 30))),
    id='email_poll',
    replace_existing=True,
    max_instances=1,  # Prevent overlapping runs
    coalesce=True,  # Merge missed runs
)

scheduler.start()
```

**Drift mitigation**: APScheduler uses `datetime.now()` for each trigger, not cumulative intervals, naturally correcting drift.

---

## 7. Email Access Library

### Decision: **imap-tools**

### Rationale:

- **High-level API**: Clean abstractions over imaplib, reduces boilerplate
- **Message ID access**: Easy retrieval of stable message-id header
- **Idempotent search**: `UNSEEN` flag, `SINCE` date queries for incremental fetch
- **Pythonic**: Context managers, generator-based iteration
- **Maintained**: Active updates, good documentation
- **Constitutional alignment**: Supports exactly-once enqueue via message-id deduplication

### Alternatives Considered:

| Option               | Pros                                          | Cons                                        | Verdict                               |
| -------------------- | --------------------------------------------- | ------------------------------------------- | ------------------------------------- |
| **imap-tools**       | High-level, clean API, idempotent, maintained | Not async (blocks I/O)                      | ✅ **Selected** (run in executor)     |
| **imaplib (stdlib)** | No dependencies, low-level control            | Verbose, manual parsing, no helpers         | ❌ Too much boilerplate               |
| **aioimaplib**       | Async IMAP, non-blocking                      | Less mature, smaller ecosystem, complex API | ❌ Async not critical for 30s polling |
| **email (stdlib)**   | Parsing only, no IMAP                         | Requires separate IMAP library              | ❌ Not standalone solution            |

### Integration Notes:

```python
from imap_tools import MailBox, AND
from datetime import datetime, timedelta

def fetch_new_emails(since: datetime) -> List[Email]:
    with MailBox('imap.gmail.com').login(username, password) as mailbox:
        # Idempotent fetch: only emails since last poll
        criteria = AND(date_gte=since)
        emails = []

        for msg in mailbox.fetch(criteria, mark_seen=False):
            email = Email(
                message_id=msg.uid,  # Stable identifier
                sender=msg.from_,
                subject=msg.subject,
                body=msg.text or msg.html,
                received_timestamp=msg.date,
            )
            emails.append(email)

        return emails
```

**Async workaround**: Run IMAP fetch in thread pool executor (`asyncio.to_thread()`) to avoid blocking event loop during network I/O.

---

## 8. Additional Technology Decisions

### 8.1 Database: **PostgreSQL with Self-Hosted Supabase Option**

**Decision**: Use PostgreSQL from the start, with self-hosted Supabase as the deployment option.

**Rationale**:

- **Learning goal**: Hands-on experience with production-grade RDBMS (resume-worthy)
- **Self-hosting practice**: Supabase provides complete self-hosting (PostgreSQL + pgvector + auth + realtime)
- **Future-proof**: No migration needed when scaling (JSON columns, full-text search, pgvector for vectors)
- **Docker-friendly**: Official Supabase Docker Compose setup
- **Advanced features**: Partial indexes, JSONB queries, concurrent transactions, better for metrics aggregation
- **Alembic support**: Same migration workflow

**Self-Hosted Supabase Setup**:
Supabase is open-source and fully self-hostable, providing PostgreSQL with built-in extensions.

**Docker Compose for Self-Hosted Supabase**:

```yaml
services:
  supabase-db:
    image: supabase/postgres:15.1.0.147
    environment:
      POSTGRES_PASSWORD: your_password
    volumes:
      - supabase_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  supabase-studio:
    image: supabase/studio:latest
    environment:
      SUPABASE_DB_URL: postgresql://postgres:your_password@supabase-db:5432/postgres
    ports:
      - "8000:3000"
    depends_on:
      - supabase-db

volumes:
  supabase_data:
```

**Connection**:

```python
# SQLAlchemy async engine for Supabase PostgreSQL
engine = create_async_engine(
    "postgresql+asyncpg://postgres:password@localhost/postgres",
    echo=False,
    pool_size=5,
    max_overflow=10
)

# Enable pgvector for vector search
# CREATE EXTENSION IF NOT EXISTS vector;
```

### 8.2 Convex Self-Hosting (Alternative Option)

Convex is primarily cloud-based but supports self-hosting via their edge deployment platform.

**Self-Hosting Approach**:

- Run Convex backend on your infrastructure (Docker/Kubernetes)
- Use Convex CLI for local development
- Vector search via Convex's built-in vector indexing
- Real-time subscriptions for dashboard updates

**Integration Notes (Convex)**:

```python
from convex import ConvexClient
import asyncio

client = ConvexClient("http://localhost:3010")  # Self-hosted Convex

# Store embedding
await client.call("storeEmbedding", {
    "emailId": email_id,
    "embedding": embedding.tolist(),
    "metadata": metadata
})

# Search
results = await client.call("searchEmbeddings", {
    "queryEmbedding": query_embedding.tolist(),
    "k": 5,
    "threshold": 0.6
})
```

**Pros of Convex Self-Hosting**:

- **Real-time**: Built-in subscriptions for dashboard updates
- **Serverless-like**: Edge functions, automatic scaling
- **Integrated**: Database + auth + realtime in one platform

**Cons**:

- **Proprietary**: Less open-source than Supabase
- **Learning curve**: Edge deployment concepts
- **Maturity**: Self-hosting less documented than Supabase

**Recommendation**: Use self-hosted Supabase for PostgreSQL + pgvector (simpler, more open-source). Convex as alternative if real-time features become priority.

### 8.3 ORM: **SQLAlchemy 2.0**

**Decision**: Use SQLAlchemy Core + ORM for type-safe queries.

**Rationale**:

- Modern async support (`asyncio` engine)
- Alembic integration for schema migrations
- Type hints with declarative models
- Both raw SQL (performance) and ORM (convenience) available
- Works seamlessly with Supabase/PostgreSQL

### 8.4 Schema Validation: **Pydantic v2**

**Decision**: Pydantic for all JSON validation (LLM output, API requests/responses).

**Rationale**:

- Strict mode for constitution's "fail-fast on unknown fields"
- Performance (Rust core in v2)
- FastAPI native integration
- JSON Schema export for contract tests

### 8.5 Metrics & Visualization: **Prometheus + Grafana**

**Decision**: Custom dashboard for basic metrics, Grafana for complex visualizations.

**Rationale**:

- **Two-tier approach**:
  - Custom React dashboard: Real-time operational view (5s refresh, current status, recent activity)
  - Grafana: Historical analysis, complex queries, alerting, professional dashboards
- **Prometheus as backbone**: Industry-standard metrics collection, PromQL for queries
- **Grafana benefits**: Pre-built dashboards, alerting rules, threshold visualization, mobile app
- **Learning opportunity**: Industry-standard monitoring stack (resume-worthy)
- **Docker-compose integration**: All services in one stack with Supabase/Qdrant

**Architecture**:

```
FastAPI backend → prometheus-client → /metrics endpoint
                                           ↓
                                      Prometheus (scrapes)
                                           ↓
Custom Dashboard ←──────────────┬──→ Grafana
(real-time ops)                  │     (historical analysis)
                           PostgreSQL/Supabase
                          (time-series metrics)
```

**Grafana setup**:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

**Prometheus config** (prometheus.yml):

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "email-classifier"
    static_configs:
      - targets: ["backend:8000"]
    metrics_path: "/metrics"
```

**Benefits**:

- Custom dashboard: Quick health check, operator-friendly
- Grafana: Deep analysis, trends, alerting (e.g., "Queue depth >100 for 5min")
- Resume: "Implemented full observability stack with Prometheus + Grafana"

### 8.6 Logging: **structlog**

**Decision**: Structured JSON logging via structlog.

**Rationale**:

- Machine-readable logs (timestamp, level, message, context)
- Easy filtering by component/metric
- Production-ready (Datadog, ELK stack compatible)
- Context binding (request_id, message_id propagation)

### 8.7 Configuration: **python-dotenv + Pydantic Settings**

**Decision**: `.env` files loaded via `python-dotenv`, validated via Pydantic `BaseSettings`.

**Rationale**:

- 12-factor app compliance
- Type-safe config with validation
- Clear error messages for missing/invalid config

### 8.8 Encryption: **cryptography library**

**Decision**: `cryptography.fernet` for AES-256 symmetric encryption.

**Rationale**:

- High-level API (no OpenSSL manual mode selection)
- Secure defaults (AES-256-CBC + HMAC)
- Python 3.11+ compatible

---

## 9. Performance Validation Strategy

### Benchmarks to Run (Phase 5):

1. **LLM inference latency**: Measure Qwen 3 8B with GPU acceleration at various context lengths (1K, 2K, 4K chars)
2. **RAG retrieval**: Benchmark Qdrant/Supabase pgvector search with 10K, 50K, 100K vectors
3. **End-to-end classification**: Poll → RAG → LLM → validate → persist (p50, p95, p99)
4. **Dashboard API**: Load test `/metrics/current` endpoint (1K req/s target)
5. **Memory footprint**: Measure RSS with Ollama + Qdrant/Supabase + 10K RAG vectors

### Expected Results:

- Qwen 3 8B (GPU): ~0.5-2s per email (exceeds <12s p95 target significantly)
- Qdrant/Supabase retrieval: ~10-30ms for 10K vectors (<50ms target met)
- End-to-end: <3s median, <5s p95 (exceeds <12s requirement)
- Dashboard: <50ms p95 (exceeds <500ms requirement)
- Memory: ~200MB Ollama client + ~50MB Qdrant/Supabase client + ~50MB Python = ~300MB (well within <1.2GB)

---

## 10. Updated Tech Stack Summary

**For Resume/Portfolio Documentation**:

```
Email Classifier System
├── Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2
├── LLM: Qwen 3 8B via Ollama (GPU-accelerated)
├── Vector DB: Qdrant or Self-Hosted Supabase pgvector (Docker)
├── Embeddings: EmbeddingGemma / qwen3:0.6b via Ollama
├── Database: PostgreSQL via Self-Hosted Supabase
├── Monitoring: Prometheus + Grafana (industry-standard observability)
├── Custom Dashboard: React 18, Recharts (real-time operations)
├── Testing: pytest (80%+ coverage), contract tests, integration tests
├── Deployment: Docker Compose (Ollama + Supabase + Qdrant + Grafana)
└── Key Features:
    ✓ GPU-accelerated LLM inference (~0.5-2s per email)
    ✓ Self-hosted Supabase with pgvector for vector search
    ✓ Dedicated vector database option (Qdrant)
    ✓ Production PostgreSQL self-hosting experience
    ✓ Dual monitoring: Custom ops dashboard + Grafana analytics
    ✓ Full Docker deployment with GPU passthrough
    ✓ 45+ hierarchical email categories
    ✓ Feedback loop for continuous improvement
```

**Skills Demonstrated**:

- Full-stack development (Python backend + React frontend)
- LLM integration with GPU acceleration (Ollama)
- Self-hosted backend services (Supabase, Qdrant)
- Vector database management (pgvector, Qdrant)
- PostgreSQL database design and self-hosting
- Monitoring & observability (Prometheus + Grafana)
- Docker containerization with GPU support
- RESTful API design with OpenAPI
- Real-time data visualization
- Test-driven development (TDD)
- Performance optimization
- System design and architecture

---

## 11. Dependencies List

### Backend (requirements.txt)

```
# Core
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0

# LLM & RAG
ollama==0.1.6  # Ollama Python client
qdrant-client==1.7.0  # Vector database option

# Embedding Models (accessed via Ollama, no separate packages)
# - embeddinggemma (primary)
# - qwen3:0.6b (alternative for testing)

# Database
sqlalchemy[asyncio]==2.0.23
alembic==1.13.0
asyncpg==0.29.0  # PostgreSQL async driver
psycopg2-binary==2.9.9  # PostgreSQL sync driver (for Alembic)

# Email
imap-tools==1.5.0

# Scheduling
apscheduler==3.10.4

# Monitoring
prometheus-client==0.19.0
prometheus-fastapi-instrumentator==6.1.0
structlog==23.2.0

# Security
cryptography==41.0.7

# Utilities
python-dotenv==1.0.0
tenacity==8.2.3  # Retry with exponential backoff
httpx==0.25.2  # For Ollama API calls
```

### Frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.10.3",
    "axios": "^1.6.2",
    "date-fns": "^2.30.0"
  },
  "devDependencies": {
    "vite": "^5.0.5",
    "@vitejs/plugin-react": "^4.2.1",
    "eslint": "^8.55.0",
    "prettier": "^3.1.1"
  }
}
```

### Development (requirements-dev.txt)

```
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2  # For testing FastAPI
black==23.12.0
ruff==0.1.8
mypy==1.7.1
```

---

## Research Complete ✅

All technical unknowns resolved with user-specified preferences integrated. Ready to proceed to Phase 1: Design & Contracts.

**Final Architecture**:

- **LLM**: Ollama (qwen3:8b) - GPU-accelerated, Docker-friendly
- **Vector DB**: Qdrant or Self-Hosted Supabase pgvector - Self-hosting focus
- **Database**: PostgreSQL via Self-Hosted Supabase - Production-grade self-hosting
- **Embeddings**: EmbeddingGemma (primary) / qwen3:0.6b (alternative)
- **Monitoring**: Custom React dashboard + Grafana for complex analysis
- **Deployment**: Full Docker Compose stack with GPU passthrough and self-hosted services

**Next Steps**:

1. Generate `data-model.md` from spec entities (with PostgreSQL/Supabase schema)
2. Create JSON Schema v2 and OpenAPI contracts
3. Write failing contract tests
4. Document quickstart validation steps (including Docker Compose setup for Supabase)
5. Update `.roo/CLAUDE.md` agent context file
