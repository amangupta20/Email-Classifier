"""
Test to verify that our shared fixtures are working correctly.
"""

import pytest


def test_mock_imap_server_fixture(mock_imap_server):
    """Test that the IMAP mock server fixture is working."""
    # Test basic setup
    mock_imap_server.return_value.login.assert_not_called()

    # Test connection behavior
    mock_conn = mock_imap_server.return_value
    mock_conn.login.return_value = ("OK", ["Login successful"])

    result = mock_conn.login("test@test.com", "password")
    assert result == ("OK", ["Login successful"])


def test_mock_ollama_client_fixture(mock_ollama_client):
    """Test that the Ollama mock client fixture is working."""
    # Test that it's properly mocked
    assert mock_ollama_client.chat is not None

    # Test chat response
    import asyncio
    response = asyncio.run(mock_ollama_client.chat("test prompt"))
    assert "message" in response
    assert "content" in response["message"]


def test_mock_qdrant_client_fixture(mock_qdrant_client):
    """Test that the Qdrant mock client fixture is working."""
    # Test search functionality
    results = mock_qdrant_client.search("test_collection", "test_vector")
    assert len(results) == 2
    assert "score" in results[0]
    assert "payload" in results[0]


def test_mock_gmail_service_fixture(mock_gmail_service):
    """Test that the Gmail mock service fixture is working."""
    # Test that it's properly mocked
    assert mock_gmail_service.labels is not None
    assert mock_gmail_service.messages is not None

    # Test that the mock returns the expected structure
    mock_gmail_service.labels.return_value.create.return_value.execute.return_value = {
        "id": "label_academic_exams",
        "name": "Academic/Exams",
        "type": "user"
    }

    # Since these are mocks, we can just verify they're callable
    assert callable(mock_gmail_service.labels.return_value.create.return_value.execute)


def test_classification_result_samples_fixture(classification_result_samples):
    """Test that the classification result samples fixture is working."""
    # Test valid academic exam sample
    academic_sample = classification_result_samples["academic_exam"]
    assert academic_sample["primary_category"] == "academic.exams"
    assert academic_sample["schema_version"] == "v2"
    assert academic_sample["confidence"] >= 0.0
    assert academic_sample["confidence"] <= 1.0

    # Test valid career internship sample
    career_sample = classification_result_samples["career_internship"]
    assert career_sample["primary_category"] == "career.internship"
    assert "deadline_utc" in career_sample
    assert career_sample["priority"] == "high"

    # Test invalid schema sample
    invalid_sample = classification_result_samples["invalid_schema"]
    assert invalid_sample["schema_version"] == "v1"  # Invalid version
    assert invalid_sample["confidence"] == 1.5  # Invalid confidence


def test_error_scenarios_fixture(error_scenarios):
    """Test that the error scenarios fixture is working."""
    # Test that we have the expected error scenarios
    assert "imap_connection_failed" in error_scenarios
    assert "ollama_timeout" in error_scenarios
    assert "qdrant_not_found" in error_scenarios
    assert "gmail_rate_limit" in error_scenarios
    assert "database_constraint" in error_scenarios

    # Test error structure
    imap_error = error_scenarios["imap_connection_failed"]
    assert "exception" in imap_error
    assert "should_retry" in imap_error
    assert imap_error["should_retry"] is True


def test_mock_health_checks_fixture(mock_health_checks):
    """Test that the health checks fixture is working."""
    # Test healthy state
    healthy = mock_health_checks["healthy"]
    assert "ollama" in healthy
    assert healthy["ollama"]["status"] == "healthy"

    # Test degraded state
    degraded = mock_health_checks["degraded"]
    assert degraded["ollama"]["status"] == "degraded"
    assert "error" in degraded["ollama"]

    # Test unhealthy state
    unhealthy = mock_health_checks["unhealthy"]
    assert unhealthy["ollama"]["status"] == "down"
    assert unhealthy["gmail"]["status"] == "degraded"


def test_faker_import():
    """Test that the faker import is working correctly."""
    from faker import Faker
    fake = Faker()
    assert fake.email() is not None
    assert fake.sentence() is not None
    assert fake.pyfloat(min_value=0.6, max_value=1.0) is not None


@pytest.mark.asyncio
async def test_email_factory_fixture(email_factory):
    """Test that the email factory fixture creates valid emails."""
    # Test basic email creation
    email = email_factory()
    assert email.message_id is not None
    assert email.sender is not None
    assert email.subject is not None
    assert email.classification_status.value == "pending"

    # Test email with overrides
    custom_email = email_factory(
        sender="custom@test.com",
        subject="Custom Subject"
    )
    assert custom_email.sender == "custom@test.com"
    assert custom_email.subject == "Custom Subject"


@pytest.mark.asyncio
async def test_classification_result_factory_fixture(classification_result_factory):
    """Test that the classification result factory creates valid results."""
    result = classification_result_factory()
    assert result.primary_category is not None
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0
    assert result.schema_version == "v2"

    # Test with overrides
    custom_result = classification_result_factory(
        primary_category="academic.exams",
        confidence=0.95
    )
    assert custom_result.primary_category == "academic.exams"
    assert custom_result.confidence == 0.95


@pytest.mark.asyncio
async def test_tag_factory_fixture(tag_factory):
    """Test that the tag factory creates valid tags."""
    tag = tag_factory()
    assert tag.name is not None
    assert tag.description is not None
    assert tag.active is True

    # Test with overrides
    custom_tag = tag_factory(
        name="test.category",
        active=False
    )
    assert custom_tag.name == "test.category"
    assert custom_tag.active is False


def test_frozen_time_fixture(frozen_time):
    """Test that the frozen time fixture works correctly."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert now.year == 2025
    assert now.month == 10
    assert now.day == 5


def test_performance_test_data_fixture(performance_test_data):
    """Test that the performance test data fixture works correctly."""
    # Test small batch
    small_batch = performance_test_data["small_batch"]
    assert len(small_batch) == 10
    assert "message_id" in small_batch[0]
    assert "sender" in small_batch[0]

    # Test medium batch
    medium_batch = performance_test_data["medium_batch"]
    assert len(medium_batch) == 100

    # Test large batch
    large_batch = performance_test_data["large_batch"]
    assert len(large_batch) == 1000