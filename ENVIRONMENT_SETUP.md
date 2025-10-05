

# Environment Configuration Guide

This guide explains how to configure the environment variables for the Intelligent Inbox Email Classification system.

## Quick Setup

1. **Copy the environment templates**:
   ```bash
   cp .env.example .env
   cp .env.secrets.template .env.secrets
   ```

2. **Add secrets to .gitignore** (if not already present):
   ```bash
   echo ".env" >> .gitignore
   echo ".env.secrets" >> .gitignore
   echo "*.key" >> .gitignore
   echo "credentials/" >> .gitignore
   ```

3. **Edit the configuration files**:
   - `.env` - Non-sensitive configuration (ports, hosts, feature flags)
   - `.env.secrets` - Sensitive credentials (passwords, API keys)

## Configuration Files

### `.env.example` → `.env`
Contains all non-sensitive environment variables with reasonable defaults. This file is tracked in version control.

**Key sections**:
- Database connection settings
- Service ports and hosts
- Feature flags
- Performance tuning
- Logging configuration

### `.env.secrets.template` → `.env.secrets`
Contains sensitive information that should never be committed. This template provides the structure but you must fill in actual values.

**Key sections**:
- Encryption keys
- Passwords and credentials
- API keys
- SSL certificates
- Backup encryption

## Required Environment Variables

### Core Services
```bash
# Database
DB_URL=postgresql://classifier:password@localhost:5432/email_classifier

# LLM (Ollama)
OLLAMA_HOST=http://localhost:11434
QWEN_MODEL_NAME=qwen3:8b

# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Email IMAP
IMAP_SERVER=imap.gmail.com
IMAP_USERNAME=your-email@gmail.com
IMAP_PASSWORD=app-password
```

### Security
```bash
# Encryption (required for sensitive data)
ENCRYPTION_KEY=your-32-byte-encryption-key-here

# Dashboard authentication
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=secure-password
```

### Features
```bash
# Core features
RAG_ENABLED=true
STORE_RAW_EMAILS=false
RETENTION_DAYS=90

# Performance
EMAIL_POLL_INTERVAL=30
CLASSIFY_CONCURRENCY=2
```

## Security Best Practices

### 1. Generate Strong Encryption Keys
```bash
# Generate Fernet key for data encryption
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"

# Generate random password
openssl rand -base64 32
```

### 2. Use App-Specific Passwords
For Gmail, always use app-specific passwords:
1. Go to Google Account settings
2. Enable 2-factor authentication
3. Generate app-specific password
4. Use it in `IMAP_PASSWORD`

### 3. Environment-Specific Configuration
Create different configurations for different environments:

**Development (.env.dev)**:
```bash
DEBUG=true
LOG_LEVEL=DEBUG
EMAIL_POLL_INTERVAL=60  # Less frequent in dev
```

**Production (.env.prod)**:
```bash
DEBUG=false
LOG_LEVEL=INFO
EMAIL_POLL_INTERVAL=30
STORE_RAW_EMAILS=false
```

### 4. Docker Compose Integration
Use environment files with Docker Compose:
```bash
docker compose --env-file .env --env-file .env.secrets up -d
```

## Configuration Validation

The system validates required environment variables at startup:

```bash
# Test configuration
python -c "
from src.config import Settings
settings = Settings()
print('✅ Configuration valid')
"
```

Common validation errors:
- Missing `ENCRYPTION_KEY`
- Invalid database URL
- Missing IMAP credentials
- Invalid port numbers

## Environment Variable Reference

### Database
- `DB_URL` - PostgreSQL connection string
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Alternative to DB_URL

### LLM Configuration
- `OLLAMA_HOST` - Ollama server endpoint
- `QWEN_MODEL_NAME` - Model name (e.g., qwen3:8b)
- `LLM_TEMPERATURE` - Sampling temperature (0.0-1.0)
- `LLM_MAX_TOKENS` - Maximum response tokens

### Vector Database
- `QDRANT_HOST`, `QDRANT_PORT` - Qdrant connection
- `SUPABASE_URL`, `SUPABASE_KEY` - Alternative Supabase setup

### Email Processing
- `IMAP_SERVER` - IMAP server hostname
- `IMAP_USERNAME`, `IMAP_PASSWORD` - Email credentials
- `IMAP_FOLDER` - Mailbox to monitor (default: INBOX)
- `EMAIL_POLL_INTERVAL` - Seconds between polls

### Dashboard
- `DASHBOARD_PORT` - FastAPI server port
- `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD` - Admin credentials

### Monitoring
- `GRAFANA_PASSWORD` - Grafana admin password
- `PROMETHEUS_PORT` - Prometheus port
- `METRICS_ENABLED` - Enable metrics collection

### Features
- `RAG_ENABLED` - Enable retrieval-augmented generation
- `STORE_RAW_EMAILS` - Store encrypted email bodies
- `RETENTION_DAYS` - Data retention period

### Performance
- `CLASSIFY_CONCURRENCY` - Parallel classification jobs
- `RAG_TOP_K` - RAG context chunks to retrieve
- `RAG_SIMILARITY_THRESHOLD` - Minimum similarity score

### Security
- `ENCRYPTION_KEY` - 32-byte Fernet key
- `DEBUG` - Enable debug mode (production: false)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Verify PostgreSQL is running
   - Check DB_URL format and credentials
   - Ensure database exists

2. **Ollama Connection Failed**
   - Verify Ollama service is running
   - Check OLLAMA_HOST URL
   - Ensure model is downloaded

3. **IMAP Authentication Failed**
   - Use app-specific password for Gmail
   - Verify IMAP server settings
   - Check username/password

4. **Encryption Key Error**
   - Generate new Fernet key
   - Ensure key is 32 bytes URL-safe base64 encoded
   - Check key is not truncated

### Debug Mode
Enable debug mode for detailed logging:
```bash
DEBUG=true LOG_LEVEL=DEBUG
```

### Port Conflicts
Change default ports if conflicts occur:
```bash
DASHBOARD_PORT=8081
QDRANT_PORT=6334
```

## Production Deployment

For production deployment:

1. **Use environment-specific .env files**
2. **Set strong passwords and encryption keys**
3. **Disable debug mode**
4. **Configure proper logging**
5. **Set up SSL certificates**
6. **Configure backup encryption**
7. **Monitor environment variable usage**

Example production `.env`:
```bash
DEBUG=false
LOG_LEVEL=INFO
STORE_RAW_EMAILS=false
RETENTION_DAYS=365
EMAIL_POLL_INTERVAL=30
CLASSIFY_CONCURRENCY=4
```

