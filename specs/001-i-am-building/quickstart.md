# Quickstart & Validation Guide

**Feature**: Intelligent Inbox Email Classification  
**Date**: 2025-10-03  
**Status**: Phase 1 Complete

This document provides step-by-step instructions to set up, run, and validate the email classification system. The goal is to verify all functional requirements are met before full implementation.

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+ recommended) or macOS (for development)
- **Hardware**: CPU with 8+ GB RAM, NVIDIA GPU with 8GB+ VRAM (for Qwen 3 8B), 20GB+ disk space
- **Docker**: Version 20+ with NVIDIA Container Toolkit (for GPU acceleration)
- **Python**: 3.11+ (for backend)
- **Node.js**: 18+ (for frontend)
- **Git**: For version control
- **Network**: Local network access for IMAP (Gmail/Outlook/Thunderbird)

### Initial Setup

1. **Clone repository** (if not already):

   ```bash
   git clone <repo-url> email-classifier
   cd email-classifier
   git checkout 001-i-am-building
   ```

2. **Install Python dependencies**:

   ```bash
   # Backend
   pip install -r backend/requirements.txt
   pip install -r backend/requirements-dev.txt

   # Frontend
   cd frontend
   npm install
   cd ..
   ```

3. **Create environment file** (copy from template):

   ```bash
   cp .env.example .env
   ```

4. **Configure environment variables** in `.env`:

   ```bash
   # Database (PostgreSQL)
   DB_URL=postgresql://classifier:password@localhost:5432/email_classifier

   # LLM (Ollama)
   OLLAMA_HOST=http://localhost:11434
   QWEN_MODEL_NAME=qwen3:8b

   # Vector DB (Qdrant - Primary)
   QDRANT_HOST=localhost
   QDRANT_PORT=6333

   # Alternative: Supabase (Self-Hosted)
   # SUPABASE_URL=http://localhost:8000
   # SUPABASE_KEY=your-anon-key

   # Email Configuration
   IMAP_SERVER=imap.gmail.com
   IMAP_USERNAME=your-email@gmail.com
   IMAP_PASSWORD=app-password  # Use app-specific password for Gmail
   IMAP_FOLDER=INBOX

   # Dashboard
   DASHBOARD_PORT=8080
   DASHBOARD_USERNAME=admin
   DASHBOARD_PASSWORD=secret

   # Monitoring
   GRAFANA_PASSWORD=grafana123

   # Features
   RAG_ENABLED=true
   STORE_RAW_EMAILS=false  # Privacy: don't store email bodies
   RETENTION_DAYS=90

   # Performance
   EMAIL_POLL_INTERVAL=30
   CLASSIFY_CONCURRENCY=2

   # Security
   ENCRYPTION_KEY=your-32-byte-key-here  # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"
   ```

5. **Initialize database**:

   ```bash
   # Create PostgreSQL database
   docker run --name postgres-db -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:16-alpine
   sleep 5  # Wait for startup

   # Run Alembic migrations
   alembic upgrade head
   ```

6. **Pull models** (Ollama):

   ```bash
   # Start Ollama with GPU
   docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

   # Pull models
   docker exec ollama ollama pull qwen3:8b
   docker exec ollama ollama pull embeddinggemma

   # Alternative embedding model
   docker exec ollama ollama pull qwen3:0.6b
   ```

7. **Setup vector database** (Qdrant):

   ```bash
   # Start Qdrant
   docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage --name qdrant qdrant/qdrant
   ```

   **Alternative: Self-Hosted Supabase** (if using pgvector fallback):

   ```bash
   # Start Supabase
   docker compose -f docker-compose.supabase.yml up -d

   # Enable pgvector in Supabase Studio (http://localhost:8000) or via SQL:
   docker exec supabase-db psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

8. **Setup monitoring stack**:

   ```bash
   # Start Prometheus + Grafana
   docker compose up -d prometheus grafana
   ```

9. **Initialize project structure**:

   ```bash
   # Create directories (if not already)
   mkdir -p backend/src/{models,services,database,api,worker,utils}
   mkdir -p frontend/src/{components,services,utils,styles}
   mkdir -p tests/{unit,contract,integration}
   mkdir -p data/{db,logs,models}

   # Create initial files
   touch backend/src/__init__.py backend/src/config.py
   touch frontend/src/index.html frontend/src/main.jsx
   ```

## Running the System

### 1. Start Backend Services

```bash
# Terminal 1: Start PostgreSQL
docker run --name postgres-db -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:16-alpine
sleep 5

# Terminal 2: Start Qdrant (Vector DB)
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage --name qdrant qdrant/qdrant

# Terminal 3: Start Ollama (LLM)
docker run -d --gpus all -v ollama_models:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# Terminal 4: Run database migrations
alembic upgrade head

# Terminal 5: Start backend worker
cd backend
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 6: Start frontend development server
cd frontend
npm run dev  # Vite dev server on port 5173
```

### 2. Verify Services Are Running

Check each component:

- **PostgreSQL**: `docker ps | grep postgres` (port 5432)
- **Qdrant**: `docker ps | grep qdrant` (port 6333)
- **Ollama**: `curl http://localhost:11434/api/tags` (should return model list)
- **Backend**: `curl http://localhost:8000/health` (should return health status)
- **Frontend**: `http://localhost:5173` (should show dashboard)
- **Prometheus**: `http://localhost:9090` (should scrape backend metrics)
- **Grafana**: `http://localhost:3000` (login: admin/grafana123)

## Validation Steps

### Phase 1: Database & Schema (5 minutes)

1. **Verify database connection**:

   ```bash
   # Test PostgreSQL connection
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "\dt"
   # Should show tables: emails, classifications, tags, cycles, config, feedback, metrics, health_checks
   ```

2. **Validate schema**:

   ```bash
   # Check tables exist and have correct structure
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   \d emails;
   \d classifications;
   "
   ```

3. **Insert test configuration**:
   ```bash
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "
   INSERT INTO config (key, value) VALUES
   ('EMAIL_POLL_INTERVAL', '30'),
   ('RAG_ENABLED', 'true'),
   ('RAG_TOP_K', '5')
   ON CONFLICT (key) DO NOTHING;
   "
   ```

### Phase 2: LLM & RAG Integration (10 minutes)

1. **Test Ollama model**:

   ```bash
   # Verify Qwen 3 8B loaded
   docker exec ollama ollama list
   curl -X POST http://localhost:11434/api/generate \
     -H "Content-Type: application/json" \
     -d '{
       "model": "qwen3:8b",
       "prompt": "Test classification: \"Midterm exam tomorrow at 9AM. Review notes now.\"",
       "stream": false,
       "format": "json"
     }'
   # Should return JSON classification (even if schema not perfect)
   ```

2. **Test embedding model**:

   ```bash
   # Test nomic-embed-text
   curl -X POST http://localhost:11434/api/embeddings \
     -H "Content-Type: application/json" \
     -d '{"model": "embeddinggemma", "prompt": "Test embedding"}'
   # Should return 768-dimension vector
   ```

3. **Test Qdrant collection** (if using Qdrant):

   ```bash
   # Create collection (if not already)
   curl -X PUT 'http://localhost:6333/collections/email_rag_kb' \
     -H 'Content-Type: application/json' \
     -d '{
       "vectors": {
         "size": 768,
         "distance": "Cosine"
       }
     }'

   # Add test vector
   curl -X POST 'http://localhost:6333/collections/email_rag_kb/points' \
     -H 'Content-Type: application/json' \
     -d '{
       "points": [
         {
           "id": "test1",
           "vector": [0.1, 0.2, 0.3, ...],  # 768 values
           "payload": {"text": "Sample email text", "category": "test"}
         }
       ]
     }'

   # Test search
   curl -X POST 'http://localhost:6333/collections/email_rag_kb/points/search' \
     -H 'Content-Type: application/json' \
     -d '{
       "vector": [0.1, 0.2, 0.3, ...],  # Same test vector
       "limit": 1,
       "params": {
         "exact": true
       }
     }'
   ```

### Phase 3: Backend Services (15 minutes)

1. **Test email poller**:

   ```bash
   # Run manual poll (if implemented)
   python -c "
   from backend.src.services.email_poller import EmailPoller
   poller = EmailPoller()
   emails = poller.fetch_new()
   print(f'Found {len(emails)} new emails')
   "
   # Should connect to IMAP and return recent emails
   ```

2. **Test schema validation**:

   ```bash
   # Test JSON schema validation
   python -c "
   from backend.src.utils.schema_validator import validate_classification_v2
   test_json = {
       'message_id': 'test123',
       'primary_category': 'academic.exams',
       'confidence': 0.85,
       'schema_version': 'v2'
   }
   result = validate_classification_v2(test_json)
   print('Schema validation:', result)
   "
   # Should validate successfully
   ```

3. **Test metrics endpoint** (start backend first):
   ```bash
   curl http://localhost:8000/metrics/current
   # Should return current metrics (even if all zeros initially)
   ```

### Phase 4: Frontend Dashboard (10 minutes)

1. **Access dashboard**:

   ```bash
   # Backend API
   curl -H "Authorization: Basic YWRtaW46c2VjcmV0" http://localhost:8000/metrics/current

   # Frontend (if running)
   open http://localhost:5173
   # Should show metrics cards, charts, health status
   ```

2. **Verify real-time updates**:

   ```bash
   # Watch metrics update every 5 seconds
   watch -n 5 "curl http://localhost:8000/metrics/current"
   # Should see values change as emails processed
   ```

3. **Test manual operations** (if implemented):

   ```bash
   # Force reclassify (example message_id)
   curl -X POST http://localhost:8000/classifications/reclassify \
     -H "Content-Type: application/json" \
     -H "Authorization: Basic YWRtaW46c2VjcmV0" \
     -d '{"message_ids": ["test123"]}'

   # Trigger RAG reindex
   curl -X POST http://localhost:8000/admin/rag/reindex \
     -H "Authorization: Basic YWRtaW46c2VjcmV0"
   ```

### Phase 5: Monitoring Stack (5 minutes)

1. **Verify Prometheus scraping**:

   ```bash
   # Check if backend metrics are being scraped
   curl http://localhost:9090/api/v1/query?query=up
   # Should show backend target as "1"
   ```

2. **Access Grafana**:

   ```bash
   open http://localhost:3000
   # Login: admin / grafana123
   # Add Prometheus datasource: http://prometheus:9090
   # Import or create dashboard for email_classifier metrics
   ```

3. **Validate time-series data**:
   ```bash
   # Query Prometheus directly
   curl 'http://localhost:9090/api/v1/query?query=avg_processing_time_ms'
   # Should return recent classification times
   ```

### Phase 6: End-to-End Validation (15 minutes)

1. **Load test data** (create sample emails in test inbox):

   ```bash
   # Send test emails to your configured IMAP account
   # Include various categories: academic, career, deadlines, etc.
   # 10-20 emails covering different scenarios
   ```

2. **Run full cycle**:

   ```bash
   # Let system run for 2-3 minutes
   # Verify emails appear in database
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "
   SELECT COUNT(*) FROM emails;
   SELECT COUNT(*) FROM classifications;
   "
   ```

3. **Validate classification results**:

   ```bash
   # Check sample classifications
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "
   SELECT e.subject, c.primary_category, c.confidence
   FROM emails e
   JOIN classifications c ON e.id = c.email_id
   ORDER BY c.processed_timestamp DESC
   LIMIT 5;
   "
   # Verify categories match expected taxonomy
   ```

4. **Test user feedback loop** (if implemented):

   ```bash
   # Submit correction via dashboard or API
   curl -X POST http://localhost:8000/feedback \
     -H "Content-Type: application/json" \
     -H "Authorization: Basic YWRtaW46c2VjcmV0" \
     -d '{
       "email_id": "test123",
       "original_category": "spam.junk",
       "corrected_category": "academic.exams",
       "reason": "Course announcement"
     }'

   # Verify stored in feedback table
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "
   SELECT * FROM feedback WHERE email_id = 'test123';
   "
   ```

5. **Performance benchmarking**:

   ```bash
   # Run end-to-end test with timing
   python -m pytest tests/integration/test_poll_classify_persist.py -v
   # Verify <5s median, <12s p95
   ```

6. **Export metrics**:
   ```bash
   # Download CSV from dashboard
   # Verify contains: timestamp, metric_name, value, unit
   ```

### Phase 7: Manual Quality Checks (5 minutes)

1. **Privacy verification**:

   ```bash
   # Check no raw email bodies stored (if STORE_RAW_EMAILS=false)
   psql postgresql://classifier:password@localhost:5432/email_classifier -c "
   SELECT COUNT(*) FROM emails WHERE body_encrypted IS NOT NULL;
   "
   # Should return 0
   ```

2. **Security verification**:

   ```bash
   # Test unauthorized access
   curl -X GET http://localhost:8000/admin/rag/reindex
   # Should return 401 Unauthorized
   ```

3. **Dashboard functionality**:

   - Verify metrics refresh every 5 seconds
   - Check category distribution chart renders correctly
   - Test time-series graphs for different periods (1h, 24h, 7d)
   - Verify error panel shows recent failures (if any)

4. **Grafana verification**:
   - Create simple dashboard with:
     - Time-series: avg_processing_time_ms (last 24h)
     - Gauge: current queue_depth
     - Stat: emails_classified per hour
   - Verify data appears from backend metrics

### Phase 8: Cleanup and Teardown

```bash
# Stop services
docker stop ollama qdrant postgres-db prometheus grafana
docker rm ollama qdrant postgres-db prometheus grafana

# Remove test data (optional)
psql postgresql://classifier:password@localhost:5432/email_classifier -c "TRUNCATE emails, classifications, metrics;"
```

## Success Criteria

**Completed** (all must pass):

- [ ] Database schema created and validated (8 tables with correct structure)
- [ ] Ollama running with Qwen 3 8B and embedding model loaded
- [ ] Qdrant collection created with test vectors
- [ ] Backend API responds at http://localhost:8000/health
- [ ] Frontend dashboard loads at http://localhost:5173 with metrics
- [ ] 10+ test emails processed and classified in database
- [ ] Categories match expected taxonomy (academic.exams, career.internship, etc.)
- [ ] Manual correction stored in feedback table
- [ ] Metrics exported to CSV with processing times and confidence scores
- [ ] Performance: <5s median classification time verified
- [ ] Privacy: No raw email bodies stored (body_encrypted IS NULL)
- [ ] Security: Admin endpoints require authentication
- [ ] Grafana dashboard shows time-series data from Prometheus

**Performance Targets Met**:

- [ ] <5s median end-to-end classification (measured)
- [ ] <12s p95 classification latency (measured)
- [ ] <500ms p95 dashboard API response (measured)
- [ ] <50ms p95 RAG retrieval latency (measured)

**Resume Documentation Ready**:

- [ ] Screenshots of dashboard with real-time metrics
- [ ] Sample classification results showing hierarchical tags
- [ ] Performance benchmarks (latency, throughput)
- [ ] Docker Compose setup documentation
- [ ] Technology stack summary for portfolio

## Troubleshooting

### Common Issues

1. **Ollama not starting**:

   - Check GPU drivers: `nvidia-smi`
   - Verify Docker NVIDIA runtime: `docker run --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi`
   - Check model download: `docker logs ollama`

2. **PostgreSQL connection failed**:

   - Verify container running: `docker ps | grep postgres`
   - Check credentials in `.env` match docker-compose.yml
   - Wait for startup: `docker logs postgres-db`

3. **Qdrant collection creation failed**:

   - Check port 6333 available: `netstat -tulpn | grep 6333`
   - Verify Docker volume: `docker volume ls | grep qdrant`
   - Test connection: `curl http://localhost:6333/collections`

4. **IMAP authentication failed**:

   - Gmail: Use app-specific password (not account password)
   - Enable 2FA and generate app password in Google Account settings
   - Check IMAP enabled: Gmail Settings → Forwarding and POP/IMAP

5. **Frontend not loading**:

   - Verify Vite dev server: `cd frontend && npm run dev`
   - Check CORS headers in browser dev tools
   - Verify backend API accessible from browser

6. **No metrics in Grafana**:
   - Check Prometheus scraping: `curl http://localhost:9090/targets`
   - Verify backend /metrics endpoint: `curl http://localhost:8000/metrics`
   - Wait 2-3 minutes for data collection after startup
   - Check datasource URL in Grafana: http://prometheus:9090

### Debug Commands

**Backend debugging**:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn src.app:app --reload --log-level debug

# Check database connections
psql postgresql://classifier:password@localhost:5432/email_classifier -c "SELECT * FROM pg_stat_activity;"
```

**System monitoring**:

```bash
# Ollama status
docker logs ollama --tail 20

# Qdrant status
docker logs qdrant --tail 20

# PostgreSQL queries
psql postgresql://classifier:password@localhost:5432/email_classifier -c "
SELECT
  COUNT(*) as total_emails,
  COUNT(*) FILTER (WHERE classification_status = 'classified') as classified,
  AVG(c.confidence) as avg_confidence
FROM emails e
LEFT JOIN classifications c ON e.id = c.email_id
WHERE e.created_at > NOW() - INTERVAL '1 hour';
"
```

**Performance debugging**:

```bash
# Check Ollama GPU usage
docker exec ollama nvidia-smi

# Monitor Python memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"
```

## Next Steps After Validation

1. **Phase 2**: Generate tasks.md with ~40 implementation tasks (TDD order)
2. **Phase 3**: Execute tasks to make contract tests pass
3. **Phase 4**: Implement remaining functionality (worker, scheduler, RAG)
4. **Phase 5**: Run full validation suite, performance benchmarks
5. **Documentation**: Prepare deployment guide, resume screenshots
6. **Demo**: Record video of dashboard showing real-time classification

**Estimated time**: 2-3 days for complete implementation with this validated foundation.
