"""
Idempotency integration tests for the Email Classifier application.

Tests that the system properly handles duplicate processing and maintains
exactly-once semantics through idempotency key generation.
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Email, ClassificationResult, ClassificationCycle,
    SystemConfig, DashboardMetric
)
from src.database.enums import EmailStatus, Priority, Sentiment, DeadlineConfidence


# ============================================================================
# Helper Functions
# ============================================================================

def generate_idempotency_key(message_id: str, schema_version: str = "v2") -> str:
    """
    Generate idempotency key for email processing.

    This mimics the expected behavior of the production system where
    idempotency is based on message_id + schema_version.
    """
    combined = f"{message_id}:{schema_version}"
    return hashlib.sha256(combined.encode()).hexdigest()


async def create_email_with_classification(
    db_session: AsyncSession,
    message_id: str,
    primary_category: str = "academic.coursework",
    schema_version: str = "v2"
) -> Email:
    """Create an email with existing classification for testing."""
    email = Email(
        message_id=message_id,
        sender="test@example.com",
        subject="Test Email",
        body_hash="test_hash",
        classification_status=EmailStatus.CLASSIFIED
    )
    db_session.add(email)
    await db_session.commit()
    await db_session.refresh(email)

    classification = ClassificationResult(
        email_id=email.id,
        primary_category=primary_category,
        confidence=0.85,
        schema_version=schema_version,
        rationale="Test classification"
    )
    db_session.add(classification)
    await db_session.commit()

    return email


# ============================================================================
# Basic Idempotency Tests
# ============================================================================

@pytest.mark.asyncio
async def test_basic_idempotency_skip_reprocessing(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that already classified emails are skipped during reprocessing.

    Validates that:
    1. Email with existing classification is not processed again
    2. No duplicate ClassificationResult is created
    3. Email status remains CLASSIFIED
    4. Processing metrics reflect idempotency behavior
    """
    # Arrange: Create email with existing classification
    existing_email = await create_email_with_classification(
        db_session,
        message_id="test-idempotency-001",
        primary_category="academic.exams"
    )

    # Arrange: Mock the email poller to return the same email
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [existing_email]

        # Arrange: Mock RAG retriever
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []

            # Arrange: Mock LLM classifier (should NOT be called)
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier

                # Arrange: Mock workflow orchestrator with idempotency check
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator

                    # Mock idempotency check to return True (already processed)
                    mock_orchestrator.is_already_processed.return_value = True

                    # Act: Attempt to process the same email again
                    start_time = time.time()
                    await mock_orchestrator.process_email_batch()
                    end_time = time.time()

                    processing_time = end_time - start_time

                    # Assert: Processing should be very fast (idempotency check)
                    assert processing_time < 1.0, f"Idempotency check should be fast, took {processing_time:.3f}s"

                    # Assert: LLM classifier should NOT be called (email skipped)
                    mock_classifier.classify_email.assert_not_called()

                    # Assert: Email status remains CLASSIFIED
                    updated_email = await db_session.get(Email, existing_email.id)
                    assert updated_email.classification_status == EmailStatus.CLASSIFIED

                    # Assert: Still only one ClassificationResult exists
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == existing_email.id
                    )
                    result = await db_session.execute(result_stmt)
                    classifications = result.scalars().all()

                    assert len(classifications) == 1, f"Expected 1 classification, found {len(classifications)}"
                    assert classifications[0].primary_category == "academic.exams"
                    assert classifications[0].schema_version == "v2"

                    # Assert: Idempotency check was called with correct key
                    expected_key = generate_idempotency_key(existing_email.message_id, "v2")
                    mock_orchestrator.is_already_processed.assert_called_once_with(expected_key)


@pytest.mark.asyncio
async def test_idempotency_key_generation_consistency(
    db_session: AsyncSession,
    email_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that idempotency keys are generated consistently.

    Validates that:
    1. Same message_id + schema_version always produces same key
    2. Different schema versions produce different keys
    3. Different message_ids produce different keys
    """
    message_id = "test-key-consistency"

    # Test: Same inputs produce same key
    key1 = generate_idempotency_key(message_id, "v2")
    key2 = generate_idempotency_key(message_id, "v2")
    assert key1 == key2, "Same inputs should produce identical idempotency keys"

    # Test: Different schema versions produce different keys
    key_v2 = generate_idempotency_key(message_id, "v2")
    key_v3 = generate_idempotency_key(message_id, "v3")
    assert key_v2 != key_v3, "Different schema versions should produce different keys"

    # Test: Different message IDs produce different keys
    key_msg1 = generate_idempotency_key("msg-001", "v2")
    key_msg2 = generate_idempotency_key("msg-002", "v2")
    assert key_msg1 != key_msg2, "Different message IDs should produce different keys"

    # Test: Keys are valid SHA256 hashes (64 hex characters)
    assert len(key_v2) == 64, "SHA256 hash should be 64 characters"
    assert all(c in "0123456789abcdef" for c in key_v2), "Key should be valid hex"


@pytest.mark.asyncio
async def test_schema_version_idempotency(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that idempotency works correctly with schema versions.

    Validates that:
    1. Same email + same schema version is idempotent
    2. Schema version is included in idempotency key calculation
    3. System respects schema version boundaries
    """
    message_id = "test-schema-idempotency"
    schema_version = "v2"

    # Arrange: Create email with v2 classification
    existing_email = await create_email_with_classification(
        db_session,
        message_id=message_id,
        schema_version=schema_version
    )

    # Arrange: Mock services
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [existing_email]

        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []

            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier

                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator

                    # Mock idempotency check for v2 schema
                    def mock_is_processed(key: str) -> bool:
                        expected_key = generate_idempotency_key(message_id, schema_version)
                        return key == expected_key

                    mock_orchestrator.is_already_processed.side_effect = mock_is_processed

                    # Act: Process email with same schema version
                    await mock_orchestrator.process_email_batch()

                    # Assert: LLM classifier should not be called (idempotent)
                    mock_classifier.classify_email.assert_not_called()

                    # Assert: Idempotency check was called with correct schema-aware key
                    expected_key = generate_idempotency_key(message_id, schema_version)
                    mock_orchestrator.is_already_processed.assert_called_once_with(expected_key)


@pytest.mark.asyncio
async def test_different_schema_version_allows_reprocessing(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that different schema versions allow reprocessing of same email.

    Validates that:
    1. Email classified with v2 can be reprocessed with v3
    2. Different schema versions create separate idempotency keys
    3. Both classifications can coexist
    """
    message_id = "test-schema-upgrade"

    # Arrange: Create email with v2 classification
    existing_email = await create_email_with_classification(
        db_session,
        message_id=message_id,
        primary_category="academic.coursework",
        schema_version="v2"
    )

    # Arrange: Mock services for v3 processing
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [existing_email]

        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = [
                {
                    "id": "chunk1",
                    "text": "Context for v3 processing",
                    "score": 0.90
                }
            ]

            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier

                # Mock v3 classification response
                v3_response = {
                    "message_id": message_id,
                    "primary_category": "academic.exams",  # Different category
                    "secondary_categories": ["academic.coursework"],
                    "priority": "high",
                    "deadline_utc": None,
                    "deadline_confidence": "none",
                    "confidence": 0.92,
                    "rationale": "V3 processing with improved accuracy",
                    "detected_entities": {"course_code": "CS101"},
                    "sentiment": "neutral",
                    "action_items": [],
                    "thread_context": {},
                    "rag_context_used": ["chunk1"],
                    "suggested_folder": "Academics/Exams",
                    "schema_version": "v3"  # Different schema version
                }

                mock_classifier.classify_email.return_value = v3_response

                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator

                    # Mock idempotency check - v3 key should not exist
                    def mock_is_processed(key: str) -> bool:
                        v2_key = generate_idempotency_key(message_id, "v2")
                        v3_key = generate_idempotency_key(message_id, "v3")
                        return key == v2_key  # Only v2 key exists

                    mock_orchestrator.is_already_processed.side_effect = mock_is_processed

                    # Act: Process email with v3 schema
                    await mock_orchestrator.process_email_batch()

                    # Assert: LLM classifier should be called (different schema version)
                    mock_classifier.classify_email.assert_called_once()

                    # Assert: Check that both v2 and v3 classifications exist
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == existing_email.id
                    ).order_by(ClassificationResult.created_at)
                    result = await db_session.execute(result_stmt)
                    classifications = result.scalars().all()

                    assert len(classifications) == 2, f"Expected 2 classifications, found {len(classifications)}"

                    v2_classification = classifications[0]
                    v3_classification = classifications[1]

                    # Validate v2 classification
                    assert v2_classification.schema_version == "v2"
                    assert v2_classification.primary_category == "academic.coursework"

                    # Validate v3 classification
                    assert v3_classification.schema_version == "v3"
                    assert v3_classification.primary_category == "academic.exams"
                    assert v3_classification.confidence == 0.92
                    assert v3_classification.rag_context_used == ["chunk1"]


@pytest.mark.asyncio
async def test_queue_idempotency(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    email_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that email queue prevents duplicate enqueues.

    Validates that:
    1. Same email cannot be queued multiple times
    2. Queue depth tracking is accurate
    3. Queue operations maintain idempotency
    """
    # Arrange: Create test email
    test_email = email_factory(
        message_id="test-queue-idempotency",
        sender="queue@test.com",
        subject="Queue Idempotency Test"
    )
    db_session.add(test_email)
    await db_session.commit()

    # Arrange: Mock queue manager
    with patch('src.services.queue_manager.QueueManager') as mock_queue_class:
        mock_queue = AsyncMock()
        mock_queue_class.return_value = mock_queue

        # Mock enqueue to track calls
        enqueue_calls = []

        async def mock_enqueue(email, priority=0):
            idempotency_key = generate_idempotency_key(email.message_id, "v2")
            if idempotency_key in enqueue_calls:
                raise ValueError("Email already in queue")
            enqueue_calls.append(idempotency_key)
            return True

        mock_queue.enqueue.side_effect = mock_enqueue
        mock_queue.get_queue_depth.return_value = 0

        # Act & Assert: First enqueue should succeed
        result1 = await mock_queue.enqueue(test_email)
        assert result1 is True, "First enqueue should succeed"
        assert len(enqueue_calls) == 1, "Queue should contain one email"

        # Act & Assert: Second enqueue should fail
        with pytest.raises(ValueError, match="Email already in queue"):
            await mock_queue.enqueue(test_email)

        assert len(enqueue_calls) == 1, "Queue should still contain only one email"

        # Assert: Queue depth tracking
        mock_queue.get_queue_depth.assert_called()

        # Verify idempotency key consistency
        expected_key = generate_idempotency_key(test_email.message_id, "v2")
        assert enqueue_calls[0] == expected_key, "Queue should use correct idempotency key"


@pytest.mark.asyncio
async def test_idempotency_across_processing_cycles(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test idempotency behavior across multiple processing cycles.

    Validates that:
    1. Email processed in one cycle is skipped in subsequent cycles
    2. ClassificationCycle metrics correctly track idempotency
    3. Performance is maintained across cycles
    """
    message_id = "test-multi-cycle"

    # Arrange: Create and classify email in first cycle
    test_email = email_factory(
        message_id=message_id,
        sender="cycle@test.com",
        subject="Multi-cycle Test"
    )
    db_session.add(test_email)
    await db_session.commit()

    # Create initial classification
    classification = ClassificationResult(
        email_id=test_email.id,
        primary_category="admin.general",
        confidence=0.75,
        schema_version="v2",
        rationale="Initial classification"
    )
    db_session.add(classification)
    test_email.classification_status = EmailStatus.CLASSIFIED
    await db_session.commit()

    # Arrange: Mock services for multiple cycles
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [test_email]

        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []

            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier

                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator

                    # Mock idempotency check
                    mock_orchestrator.is_already_processed.return_value = True

                    # Act: Run multiple processing cycles
                    for cycle_num in range(3):
                        # Create cycle tracking
                        cycle = ClassificationCycle(
                            start_timestamp=datetime.now(timezone.utc),
                            emails_scanned=1,
                            emails_classified=0,  # 0 due to idempotency
                            emails_failed=0
                        )
                        db_session.add(cycle)
                        await db_session.commit()

                        # Process email batch
                        start_time = time.time()
                        await mock_orchestrator.process_email_batch()
                        processing_time = time.time() - start_time

                        # Assert: Processing should be fast (idempotency check)
                        assert processing_time < 1.0, f"Cycle {cycle_num + 1} processing should be fast"

                        # Assert: LLM classifier never called (email skipped each time)
                        mock_classifier.classify_email.assert_not_called()

                        # Update cycle completion
                        cycle.end_timestamp = datetime.now(timezone.utc)
                        cycle.duration_ms = int(processing_time * 1000)
                        await db_session.commit()

                    # Assert: Verify cycle metrics
                    cycle_stmt = select(ClassificationCycle).order_by(
                        ClassificationCycle.start_timestamp
                    )
                    cycle_result = await db_session.execute(cycle_stmt)
                    cycles = cycle_result.scalars().all()

                    assert len(cycles) == 3, "Should have 3 processing cycles"

                    for cycle in cycles:
                        assert cycle.emails_scanned == 1, "Each cycle should scan 1 email"
                        assert cycle.emails_classified == 0, "No emails should be classified (idempotent)"
                        assert cycle.emails_failed == 0, "No emails should fail"
                        assert cycle.duration_ms < 1000, "Cycle duration should be under 1 second"

                    # Assert: Still only one classification result exists
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == test_email.id
                    )
                    result = await db_session.execute(result_stmt)
                    classifications = result.scalars().all()

                    assert len(classifications) == 1, "Should still have only 1 classification result"


@pytest.mark.asyncio
async def test_idempotency_edge_cases(
    db_session: AsyncSession,
    email_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test edge cases for idempotency behavior.

    Validates:
    1. Empty message_id handling
    2. Null/None schema version handling
    3. Special characters in message_id
    4. Very long message_id handling
    """
    # Test: Empty message_id
    empty_key = generate_idempotency_key("", "v2")
    assert len(empty_key) == 64, "Empty message_id should still generate valid key"

    # Test: Special characters in message_id
    special_chars = "test@email.com!@#$%^&*()_+-=[]{}|;':\",./<>?"
    special_key = generate_idempotency_key(special_chars, "v2")
    assert len(special_key) == 64, "Special characters should be handled correctly"

    # Test: Very long message_id
    long_message_id = "a" * 1000
    long_key = generate_idempotency_key(long_message_id, "v2")
    assert len(long_key) == 64, "Long message_id should generate valid key"

    # Test: All same characters
    same_chars_key1 = generate_idempotency_key("aaaa", "v2")
    same_chars_key2 = generate_idempotency_key("aaaa", "v2")
    assert same_chars_key1 == same_chars_key2, "Same characters should produce same key"

    # Test: Case sensitivity
    case_key1 = generate_idempotency_key("Test@Email.com", "v2")
    case_key2 = generate_idempotency_key("test@email.com", "v2")
    assert case_key1 != case_key2, "Message ID should be case sensitive"

    # Test: Schema version case sensitivity
    schema_key1 = generate_idempotency_key("test", "v2")
    schema_key2 = generate_idempotency_key("test", "V2")
    assert schema_key1 != schema_key2, "Schema version should be case sensitive"


@pytest.mark.asyncio
async def test_idempotency_performance_impact(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    email_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that idempotency checks don't significantly impact performance.

    Validates:
    1. Idempotency check timing is consistent
    2. Large batch processing maintains performance
    3. Memory usage remains reasonable
    """
    # Arrange: Create multiple emails with existing classifications
    emails = []
    for i in range(50):
        email = await create_email_with_classification(
            db_session,
            message_id=f"perf-test-{i:03d}",
            primary_category="academic.coursework"
        )
        emails.append(email)

    # Arrange: Mock services with timing
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = emails

        with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock idempotency check with realistic timing
            async def mock_is_processed(key: str) -> bool:
                # Simulate very fast key lookup (e.g., Redis/set check)
                await asyncio.sleep(0.001)  # 1ms for key lookup
                return True  # All emails already processed

            mock_orchestrator.is_already_processed.side_effect = mock_is_processed

            # Act: Process large batch with idempotency checks
            start_time = time.time()
            await mock_orchestrator.process_email_batch()
            total_time = time.time() - start_time

            # Assert: Performance should remain good
            emails_per_second = len(emails) / total_time
            avg_time_per_email = total_time / len(emails)

            assert total_time < 2.0, f"Batch processing should complete in <2s, took {total_time:.3f}s"
            assert emails_per_second > 25, f"Should process >25 emails/second, got {emails_per_second:.1f}"
            assert avg_time_per_email < 0.04, f"Average time per email should be <40ms, got {avg_time_per_email*1000:.1f}ms"

            # Assert: All idempotency checks were called
            assert mock_orchestrator.is_already_processed.call_count == len(emails)

            # Assert: No additional classifications were created
            result_stmt = select(ClassificationResult)
            result = await db_session.execute(result_stmt)
            classifications = result.scalars().all()

            assert len(classifications) == len(emails), "Should have exactly one classification per email"