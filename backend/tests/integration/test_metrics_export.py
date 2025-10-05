"""
Integration tests for the Prometheus metrics export functionality.

T016: Add monitoring pipeline test validating Prometheus exposure.
"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_metrics_endpoint_returns_404_when_not_implemented(api_client: AsyncClient):
    """
    Tests that the /metrics endpoint returns a 404 Not Found error,
    as it has not been implemented yet. This is the expected failure.
    """
    response = await api_client.get("/metrics")
    assert response.status_code == 404, "The /metrics endpoint should not be found yet."