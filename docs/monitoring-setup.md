# Monitoring Stack Setup Guide

This guide explains how to set up and use the Prometheus and Grafana monitoring stack for the Email-Classifier project.

## Overview

The monitoring stack consists of:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboarding

Both services run in Docker containers and are configured to collect metrics from the Email-Classifier application.

## Prerequisites

- Docker and Docker Compose installed
- Email-Classifier application running (for metrics collection)

## Quick Start

1. **Copy the environment template**:

   ```bash
   cp .env.example .env
   ```

2. **Configure environment variables** (optional):
   Edit `.env` file to customize settings:

   ```bash
   # Grafana admin password
   GRAFANA_PASSWORD=your-secure-password

   # n8n host (only needed for V1)
   N8N_HOST=host.docker.internal:5678
   ```

3. **Start the monitoring stack**:

   ```bash
   docker-compose up -d
   ```

4. **Access the services**:
   - Grafana: http://localhost:3000 (admin/grafana123 or your configured password)
   - Prometheus: http://localhost:9090

## Configuration Details

### Environment Variables

| Variable           | Default                     | Description                    |
| ------------------ | --------------------------- | ------------------------------ |
| `GRAFANA_PASSWORD` | `grafana123`                | Grafana admin password         |
| `N8N_HOST`         | `host.docker.internal:5678` | n8n metrics endpoint (V1 only) |

### Prometheus Configuration

Prometheus is configured to scrape metrics from:

- **Prometheus itself** (localhost:9090)
- **Email-Classifier API** (host.docker.internal:8080) - 5s interval
- **n8n workflow engine** (if N8N_HOST is set) - 30s interval
- **Node Exporter** (host.docker.internal:9100) - 30s interval (optional)

Configuration file: `infra/monitoring/prometheus/prometheus.yml`

### Grafana Configuration

Grafana is automatically provisioned with:

- **Prometheus datasource** configured
- **Email Classifier Overview dashboard** pre-loaded

Configuration files:

- Datasource: `infra/monitoring/grafana/provisioning/datasources/prometheus.yml`
- Dashboard provider: `infra/monitoring/grafana/provisioning/dashboards/dashboard.yml`
- Dashboard definition: `infra/monitoring/grafana/dashboards/email-classifier-overview.json`

## Dashboard Metrics

The Email Classifier Overview dashboard includes:

### Performance Metrics

- **HTTP Request Rate**: Requests per second by method and status
- **Request Duration**: 50th, 95th, and 99th percentile response times

### Classification Metrics

- **Email Classification Total**: Number of processed emails
- **Classification Errors**: Number of failed classifications
- **Processing Latency**: Time spent processing emails and RAG retrieval

### System Health

- **Queue Depth**: Current number of emails in processing queue
- **Average Confidence**: Average classification confidence score
- **RAG Hit Rate**: Percentage of successful RAG retrievals
- **API Health**: Service availability status

## Application Metrics Integration

To expose metrics from your Email-Classifier application:

1. **Install prometheus-client**:

   ```bash
   pip install prometheus-client
   ```

2. **Add metrics to your FastAPI application**:

   ```python
   from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

   # Define metrics
   CLASSIFICATION_TOTAL = Counter('email_classification_total', 'Total classifications')
   CLASSIFICATION_ERRORS = Counter('email_classification_errors_total', 'Classification errors')
   PROCESSING_DURATION = Histogram('email_processing_duration_seconds', 'Processing time')

   # Add metrics endpoint
   @app.get("/metrics")
   async def metrics():
       return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
   ```

3. **Update metrics in your classification logic**:
   ```python
   @PROCESSING_DURATION.time()
   def classify_email(email):
       try:
           # Your classification logic here
           CLASSIFICATION_TOTAL.inc()
           return result
       except Exception as e:
           CLASSIFICATION_ERRORS.inc()
           raise
   ```

## Maintenance

### Stopping the Services

```bash
docker-compose down
```

### Viewing Logs

```bash
# Grafana logs
docker-compose logs grafana

# Prometheus logs
docker-compose logs prometheus
```

### Updating Configuration

After modifying configuration files:

```bash
docker-compose restart prometheus grafana
```

### Data Persistence

- Prometheus data: Stored in `prometheus_data` volume (200h retention)
- Grafana data: Stored in `grafana_data` volume (dashboards, users, etc.)

## Troubleshooting

### Grafana Not Accessible

1. Check if the container is running: `docker-compose ps`
2. Check logs: `docker-compose logs grafana`
3. Verify port 3000 is not in use

### Prometheus Not Scraping Metrics

1. Check Prometheus targets: http://localhost:9090/targets
2. Verify application is exposing metrics on `/metrics` endpoint
3. Check network connectivity between containers

### Dashboard Not Showing Data

1. Verify Prometheus is collecting metrics
2. Check dashboard queries match your metric names
3. Ensure time range includes recent data

## Security Considerations

- Change the default Grafana password in production
- Consider enabling authentication for Prometheus
- Use HTTPS in production environments
- Restrict network access to monitoring endpoints

## Next Steps

1. Set up alerts in Grafana for critical metrics
2. Add custom dashboards for specific workflows
3. Configure long-term metric storage
4. Set up log aggregation alongside metrics
