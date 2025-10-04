
import pytest
from fastapi.testclient import TestClient

# Placeholder for the FastAPI app
# This will be replaced by the actual app from a fixture
class AppPlaceholder:
    pass

client = TestClient(AppPlaceholder())

def test_get_current_metrics():
    """
    Tests the /metrics/current endpoint.
    It should return a 200 OK response with a JSON object
    containing the current metrics.
    """
    response = client.get("/metrics/current")
    assert response.status_code == 200
    data = response.json()
    assert "avg_processing_time_ms" in data
    assert "avg_tags_per_email" in data
    assert "queue_depth" in data
    assert "active_workers" in data
    assert "system_uptime_seconds" in data

def test_get_timeseries_metrics():
    """
    Tests the /metrics/timeseries endpoint.
    It should return a 200 OK response with a list of data points.
    """
    response = client.get("/metrics/timeseries?metric=queue_depth&period=1h")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_classifications():
    """
    Tests the /classifications endpoint.
    It should return a 200 OK response with a list of classifications.
    """
    response = client.get("/classifications?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_post_reclassify():
    """
    Tests the /classifications/reclassify endpoint.
    It should return a 202 Accepted response.
    """
    response = client.post("/classifications/reclassify", json={"message_ids": ["id1", "id2"]})
    assert response.status_code == 202

def test_get_health():
    """
    Tests the /health endpoint.
    It should return a 200 OK response with the health status of components.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert "database" in response.json()
    assert "llm" in response.json()
    assert "vector_store" in response.json()

def test_post_admin_rag_reindex():
    """
    Tests the /admin/rag/reindex endpoint.
    It should return a 202 Accepted response.
    """
    response = client.post("/admin/rag/reindex")
    assert response.status_code == 202

def test_post_admin_queue_clear():
    """
    Tests the /admin/queue/clear endpoint.
    It should return a 202 Accepted response.
    """
    response = client.post("/admin/queue/clear")
    assert response.status_code == 202

