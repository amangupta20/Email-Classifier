"""
Shared test fixtures for the Email Classifier application.

Provides database, mock services, and test data fixtures to support TDD workflow.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio
import factory
from faker import Faker
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings, Settings
from pydantic_settings import SettingsConfigDict
from src.database.models import (
    Base, Email, ClassificationResult, Tag, ClassificationCycle,
    SystemConfig, UserFeedback, DashboardMetric, SystemHealthStatus
)
from src.database.enums import (
    EmailStatus, Priority, Sentiment, DeadlineConfidence, CategoryType, HealthStatus,
    EmailStatusType, PriorityType, SentimentType, DeadlineConfidenceType,
    CategoryTypeType, HealthStatusType
)
from src.api.app import app as fastapi_app
from httpx import AsyncClient, ASGITransport

# Initialize faker for generating test data
fake = Faker()


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test configuration with safe defaults."""
    from src.config import DatabaseSettings, LLMSettings, VectorDBSettings, EmailSettings, PerformanceSettings, SecuritySettings

    # Create custom settings classes that don't read from env files
    class TestDatabaseSettings(DatabaseSettings):
        model_config = SettingsConfigDict(env_file=None)
    
    class TestLLMSettings(LLMSettings):
        model_config = SettingsConfigDict(env_file=None)
    
    class TestVectorDBSettings(VectorDBSettings):
        model_config = SettingsConfigDict(env_file=None)
    
    class TestEmailSettings(EmailSettings):
        model_config = SettingsConfigDict(env_file=None)
    
    class TestPerformanceSettings(PerformanceSettings):
        model_config = SettingsConfigDict(env_file=None)
    
    class TestSecuritySettings(SecuritySettings):
        model_config = SettingsConfigDict(env_file=None)
    
    class TestSettings(Settings):
        model_config = SettingsConfigDict(env_file=None)
    
    return TestSettings(
        database=TestDatabaseSettings(
            DB_URL="postgresql://test:test@localhost:5432/test_email_classifier"
        ),
        llm=TestLLMSettings(
            ollama_host="http://localhost:11434",
            qwen_model_name="qwen3:8b"
        ),
        vector_db=TestVectorDBSettings(
            qdrant_host="localhost",
            qdrant_port=6333
        ),
        email=TestEmailSettings(
            imap_server="imap.test.com",
            IMAP_USERNAME="test@test.com",
            IMAP_PASSWORD="test123"
        ),
        performance=TestPerformanceSettings(
            email_poll_interval=30,
            classify_concurrency=2
        ),
        security=TestSecuritySettings(
            ENCRYPTION_KEY="a" * 32
        )
    )


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("IMAP_USERNAME", "test@test.com")
    monkeypatch.setenv("IMAP_PASSWORD", "test123")
    monkeypatch.setenv("ENCRYPTION_KEY", "a" * 32)


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_engine(test_settings):
    """Create test database engine."""
    # Convert regular postgresql URL to asyncpg for SQLAlchemy async support
    db_url = test_settings.database.db_url.get_secret_value()
    async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        async_db_url,
        echo=False,
        future=True
    )
    yield engine
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncSession:
    """Create a fresh database session for each test."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session to test
    async with async_session() as session:
        yield session

    # Clean up after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def clean_db(db_session):
    """Ensure clean database state."""
    # Delete all data in reverse dependency order
    await db_session.execute(DashboardMetric.__table__.delete())
    await db_session.execute(UserFeedback.__table__.delete())
    await db_session.execute(ClassificationResult.__table__.delete())
    await db_session.execute(Email.__table__.delete())
    await db_session.execute(ClassificationCycle.__table__.delete())
    await db_session.execute(Tag.__table__.delete())
    await db_session.execute(SystemConfig.__table__.delete())
    await db_session.execute(SystemHealthStatus.__table__.delete())
    await db_session.commit()


# ============================================================================
# Test Data Factories
# ============================================================================

@pytest.fixture
def email_factory():
    """Factory for creating Email test data."""

    def create_email(**overrides):
        """Create an email with optional overrides."""
        defaults = {
            "message_id": str(uuid.uuid4()),
            "sender": fake.email(),
            "subject": fake.sentence(),
            "received_timestamp": datetime.now(timezone.utc),
            "body_hash": fake.sha256(),
            "classification_status": EmailStatus.PENDING
        }
        defaults.update(overrides)
        return Email(**defaults)

    return create_email


@pytest.fixture
def classification_result_factory():
    """Factory for creating ClassificationResult test data."""

    def create_classification_result(**overrides):
        """Create a classification result with optional overrides."""
        defaults = {
            "primary_category": fake.random_element([
                "academic.coursework", "academic.exams", "career.internship",
                "admin.general", "clubs.meeting", "action.deadline_critical"
            ]),
            "secondary_categories": [],
            "priority": Priority.NORMAL,
            "confidence": fake.pyfloat(min_value=0.6, max_value=1.0),
            "rationale": fake.text(max_nb_chars=200),
            "detected_entities": {},
            "sentiment": Sentiment.NEUTRAL,
            "action_items": [],
            "thread_context": {},
            "rag_context_used": [],
            "schema_version": "v2"
        }
        defaults.update(overrides)
        return ClassificationResult(**defaults)

    return create_classification_result


@pytest.fixture
def tag_factory():
    """Factory for creating Tag test data."""

    def create_tag(**overrides):
        """Create a tag with optional overrides."""
        defaults = {
            "name": fake.random_element([
                "academic.coursework", "academic.exams", "academic.projects",
                "career.internship", "career.job_offer", "career.networking",
                "admin.general", "admin.billing", "admin.technical",
                "clubs.meeting", "clubs.event", "sports.training",
                "action.deadline_critical", "action.follow_up", "action.review"
            ]),
            "description": fake.text(max_nb_chars=100),
            "category_type": fake.random_element([
                CategoryType.ACADEMIC, CategoryType.CAREER, CategoryType.ADMIN,
                CategoryType.CLUBS, CategoryType.SPORTS, CategoryType.ACTION
            ]),
            "active": True,
            "priority_order": fake.pyint(min_value=0, max_value=10)
        }
        defaults.update(overrides)
        return Tag(**defaults)

    return create_tag


@pytest.fixture(scope="function")
async def sample_emails(db_session):
    """Create sample email data for testing."""
    emails = [
        Email(
            message_id="msg-001",
            sender="professor@university.edu",
            subject="Midterm Exam Scheduled for Next Week",
            body_hash="hash001",
            classification_status=EmailStatus.PENDING
        ),
        Email(
            message_id="msg-002",
            sender="recruiter@techcompany.com",
            subject="Interview Invitation - Software Engineer Role",
            body_hash="hash002",
            classification_status=EmailStatus.PENDING
        ),
        Email(
            message_id="msg-003",
            sender="admin@university.edu",
            subject="Campus Maintenance Notice - Library Closure",
            body_hash="hash003",
            classification_status=EmailStatus.PENDING
        ),
        Email(
            message_id="msg-004",
            sender="club@university.edu",
            subject="Programming Club Meeting - Algorithm Discussion",
            body_hash="hash004",
            classification_status=EmailStatus.PENDING
        ),
        Email(
            message_id="msg-005",
            sender="deadline.alert@university.edu",
            subject="URGENT: Project Proposal Due Tomorrow",
            body_hash="hash005",
            classification_status=EmailStatus.PENDING
        )
    ]

    for email in emails:
        db_session.add(email)
    await db_session.commit()

    return emails


@pytest.fixture(scope="function")
async def sample_tags(db_session):
    """Create sample tag data for testing."""
    tags = [
        Tag(name="academic.coursework", description="Assignments and homework", category_type=CategoryTypeType.ACADEMIC),
        Tag(name="academic.exams", description="Exam schedules and materials", category_type=CategoryTypeType.ACADEMIC),
        Tag(name="career.internship", description="Internship opportunities", category_type=CategoryTypeType.CAREER),
        Tag(name="admin.general", description="General administrative notices", category_type=CategoryTypeType.ADMIN),
        Tag(name="clubs.meeting", description="Club meetings and events", category_type=CategoryTypeType.CLUBS),
        Tag(name="action.deadline_critical", description="Items requiring immediate attention", category_type=CategoryTypeType.ACTION),
    ]

    for tag in tags:
        db_session.add(tag)
    await db_session.commit()

    return tags


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_imap_server():
    """Mock IMAP server for testing email polling."""
    mock_server = MagicMock()

    # Mock IMAP connection
    mock_conn = MagicMock()
    mock_server.return_value = mock_conn

    # Mock login
    mock_conn.login.return_value = ("OK", ["Login successful"])

    # Mock folder selection
    mock_conn.select.return_value = ("OK", ["INBOX"])

    # Mock email search
    mock_conn.search.return_value = ("OK", [b"1 2 3 4 5"])

    # Mock email fetch
    def mock_fetch(msg_num, data_type):
        if msg_num == "1":
            email_data = {
                "subject": "Midterm Exam Scheduled",
                "sender": "professor@university.edu",
                "body": "Your midterm exam is scheduled for next week.",
                "message_id": "msg-001"
            }
        elif msg_num == "2":
            email_data = {
                "subject": "Interview Invitation",
                "sender": "recruiter@techcompany.com",
                "body": "We'd like to invite you for an interview.",
                "message_id": "msg-002"
            }
        else:
            email_data = {
                "subject": "Test Email",
                "sender": "test@test.com",
                "body": "Test content",
                "message_id": f"msg-{msg_num}"
            }
        return ("OK", [json.dumps(email_data).encode()])

    mock_conn.fetch.side_effect = mock_fetch
    mock_conn.logout.return_value = ("OK", ["BYE"])

    return mock_server


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for LLM classification."""
    mock_client = AsyncMock()

    # Mock classification response
    classification_response = {
        "message": {
            "content": json.dumps({
                "message_id": "msg-001",
                "primary_category": "academic.exams",
                "secondary_categories": ["academic.coursework"],
                "priority": "normal",
                "deadline_utc": None,
                "deadline_confidence": "none",
                "confidence": 0.85,
                "rationale": "Email contains exam scheduling information",
                "detected_entities": {"course": "CS101", "exam_type": "midterm"},
                "sentiment": "neutral",
                "action_items": [{"action": "Study for midterm", "deadline_utc": None, "completed": False}],
                "thread_context": {"is_reply": False},
                "rag_context_used": ["chunk1", "chunk2"],
                "suggested_folder": "Academics/Exams",
                "schema_version": "v2"
            })
        }
    }

    mock_client.chat.return_value = classification_response

    return mock_client


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector search."""
    mock_client = MagicMock()

    # Mock search response
    search_response = [
        {
            "id": "chunk1",
            "score": 0.85,
            "payload": {
                "text": "Previous email about exam scheduling",
                "metadata": {"category": "academic.exams"}
            }
        },
        {
            "id": "chunk2",
            "score": 0.75,
            "payload": {
                "text": "Course syllabus information",
                "metadata": {"category": "academic.coursework"}
            }
        }
    ]

    mock_client.search.return_value = search_response

    # Mock collection operations
    mock_client.get_collection.return_value = {"vectors_count": 1000}
    mock_client.upsert.return_value = {"operation_id": "test-upsert"}

    return mock_client


@pytest.fixture
def mock_gmail_service():
    """Mock Gmail API service for label application."""
    mock_service = AsyncMock()

    # Mock label creation
    mock_service.labels.return_value.create.return_value.execute.return_value = {
        "id": "label_academic_exams",
        "name": "Academic/Exams",
        "type": "user"
    }

    # Mock label application
    mock_service.messages.return_value.modify.return_value.execute.return_value = {
        "id": "msg-001",
        "labelIds": ["INBOX", "label_academic_exams"]
    }

    # Mock label list
    mock_service.labels.return_value.list.return_value.execute.return_value = {
        "labels": [
            {"id": "label_academic", "name": "Academic"},
            {"id": "label_career", "name": "Career"},
            {"id": "label_admin", "name": "Admin"}
        ]
    }

    return mock_service


@pytest_asyncio.fixture(scope="function")
async def api_client() -> AsyncClient:
    """
    Provide a test client for the FastAPI application.
    This client can be used to make requests to the API endpoints in tests.
    """
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================================
# Classification Schema v2 Samples
# ============================================================================

@pytest.fixture
def classification_result_samples():
    """Sample classification results matching schema v2."""
    return {
        "academic_exam": {
            "message_id": "msg-001",
            "primary_category": "academic.exams",
            "secondary_categories": ["academic.coursework"],
            "priority": "normal",
            "deadline_utc": None,
            "deadline_confidence": "none",
            "confidence": 0.85,
            "rationale": "Email contains exam scheduling information with specific date and time",
            "detected_entities": {"course_code": "CS101", "exam_type": "midterm", "location": "Room 201"},
            "sentiment": "neutral",
            "action_items": [
                {"action": "Study chapters 1-5", "deadline_utc": "2025-10-10T10:00:00Z", "completed": False},
                {"action": "Bring calculator", "deadline_utc": "2025-10-10T09:00:00Z", "completed": False}
            ],
            "thread_context": {"is_reply": False, "thread_id": "thread-001"},
            "rag_context_used": ["chunk-001", "chunk-045"],
            "suggested_folder": "Academics/Exams",
            "schema_version": "v2"
        },
        "career_internship": {
            "message_id": "msg-002",
            "primary_category": "career.internship",
            "secondary_categories": ["career.networking", "action.deadline_critical"],
            "priority": "high",
            "deadline_utc": "2025-10-15T23:59:59Z",
            "deadline_confidence": "extracted",
            "confidence": 0.92,
            "rationale": "Internship offer with explicit application deadline",
            "detected_entities": {"company": "TechCorp", "position": "Software Engineer Intern", "location": "Remote"},
            "sentiment": "positive",
            "action_items": [
                {"action": "Submit internship application", "deadline_utc": "2025-10-15T23:59:59Z", "completed": False},
                {"action": "Update resume", "deadline_utc": "2025-10-12T00:00:00Z", "completed": False}
            ],
            "thread_context": {"is_reply": False, "thread_id": "thread-002"},
            "rag_context_used": ["chunk-012", "chunk-034"],
            "suggested_folder": "Career/Internships",
            "schema_version": "v2"
        },
        "admin_general": {
            "message_id": "msg-003",
            "primary_category": "admin.general",
            "secondary_categories": [],
            "priority": "low",
            "deadline_utc": None,
            "deadline_confidence": "none",
            "confidence": 0.78,
            "rationale": "General administrative announcement about campus facilities",
            "detected_entities": {"location": "Main Library", "duration": "2 days"},
            "sentiment": "neutral",
            "action_items": [{"action": "Plan alternative study location", "deadline_utc": "2025-10-08T00:00:00Z", "completed": False}],
            "thread_context": {"is_reply": False, "thread_id": "thread-003"},
            "rag_context_used": ["chunk-078"],
            "suggested_folder": "Admin/General",
            "schema_version": "v2"
        },
        "invalid_schema": {
            "message_id": "msg-invalid",
            "primary_category": "invalid.category",
            "secondary_categories": ["too", "many", "categories", "exceeding", "limit"],
            "priority": "invalid_priority",
            "confidence": 1.5,  # Invalid: > 1.0
            "schema_version": "v1"  # Invalid: wrong version
        }
    }


# ============================================================================
# Performance Test Fixtures
# ============================================================================

@pytest.fixture
def performance_test_data():
    """Generate performance test data with varying volumes."""
    def generate_emails(count: int) -> List[Dict]:
        """Generate specified number of test emails."""
        emails = []
        for i in range(count):
            emails.append({
                "message_id": f"perf-msg-{i:04d}",
                "sender": fake.email(),
                "subject": fake.sentence(),
                "body": fake.text(max_nb_chars=500),
                "received_timestamp": fake.date_time_this_year()
            })
        return emails

    return {
        "small_batch": generate_emails(10),
        "medium_batch": generate_emails(100),
        "large_batch": generate_emails(1000)
    }


# ============================================================================
# Time-based Testing Fixtures
# ============================================================================

@pytest.fixture
def frozen_time():
    """Provide consistent timestamps for testing."""
    with freeze_time("2025-10-05 12:00:00 UTC") as frozen:
        yield frozen


# ============================================================================
# Error Scenario Fixtures
# ============================================================================

@pytest.fixture
def error_scenarios():
    """Mock error scenarios for testing resilience."""
    return {
        "imap_connection_failed": {
            "exception": ConnectionError("IMAP connection failed"),
            "should_retry": True
        },
        "ollama_timeout": {
            "exception": asyncio.TimeoutError("LLM request timeout"),
            "should_retry": True
        },
        "qdrant_not_found": {
            "exception": ValueError("Collection not found"),
            "should_retry": False
        },
        "gmail_rate_limit": {
            "exception": Exception("Rate limit exceeded"),
            "should_retry": True
        },
        "database_constraint": {
            "exception": ValueError("Constraint violation"),
            "should_retry": False
        }
    }


# ============================================================================
# Health Check Fixtures
# ============================================================================

@pytest.fixture
def mock_health_checks():
    """Mock system health check responses."""
    return {
        "healthy": {
            "ollama": {"status": "healthy", "response_time_ms": 150},
            "qdrant": {"status": "healthy", "response_time_ms": 25},
            "postgres": {"status": "healthy", "connection_pool": "4/10"},
            "gmail": {"status": "healthy", "quota_remaining": "95%"}
        },
        "degraded": {
            "ollama": {"status": "degraded", "response_time_ms": 2000, "error": "High latency"},
            "qdrant": {"status": "healthy", "response_time_ms": 30},
            "postgres": {"status": "healthy", "connection_pool": "8/10"},
            "gmail": {"status": "healthy", "quota_remaining": "80%"}
        },
        "unhealthy": {
            "ollama": {"status": "down", "error": "Connection refused"},
            "qdrant": {"status": "healthy", "response_time_ms": 20},
            "postgres": {"status": "healthy", "connection_pool": "2/10"},
            "gmail": {"status": "degraded", "quota_remaining": "10%", "error": "Rate limiting"}
        }
    }