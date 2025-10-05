"""
End-to-end integration test for the email classification workflow.

Tests the complete flow: poll → classify → persist
This test should initially fail and serves as a contract for implementation.
"""

import asyncio
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


@pytest.mark.asyncio
async def test_poll_classify_persist_workflow(
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
    Test the complete email classification workflow from polling to persistence.
    
    This test validates:
    1. Email polling from IMAP using mock_imap_server
    2. RAG context retrieval using mock_qdrant_client
    3. LLM classification using mock_ollama_client
    4. Database persistence using db_session
    5. Email status transitions (PENDING → CLASSIFYING → CLASSIFIED)
    6. Classification output validation against schema v2
    7. Proper relationship creation between Email and ClassificationResult
    8. ClassificationCycle tracking
    9. Confidence scores and category assignments
    10. Performance targets (<5s median, <12s p95)
    """
    # Arrange: Create test email in database
    test_email = email_factory(
        message_id="test-msg-001",
        sender="professor@university.edu",
        subject="Midterm Exam Scheduled for Next Week",
        classification_status=EmailStatus.PENDING
    )
    db_session.add(test_email)
    await db_session.commit()
    await db_session.refresh(test_email)
    
    # Arrange: Create system configuration
    config = SystemConfig(
        key="EMAIL_POLL_INTERVAL",
        value="30",
        value_type="int"
    )
    db_session.add(config)
    await db_session.commit()
    
    # Arrange: Mock the email poller service
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        
        # Mock polling to return our test email
        mock_poller.poll_emails.return_value = [test_email]
        
        # Arrange: Mock the RAG retriever service
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            
            # Mock RAG context retrieval
            mock_rag.retrieve_context.return_value = [
                {
                    "id": "chunk1",
                    "text": "Previous email about exam scheduling",
                    "score": 0.85
                },
                {
                    "id": "chunk2", 
                    "text": "Course syllabus information",
                    "score": 0.75
                }
            ]
            
            # Arrange: Mock the LLM classifier service
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                # Mock classification response matching schema v2
                classification_response = {
                    "message_id": "test-msg-001",
                    "primary_category": "academic.exams",
                    "secondary_categories": ["academic.coursework"],
                    "priority": "normal",
                    "deadline_utc": None,
                    "deadline_confidence": "none",
                    "confidence": 0.85,
                    "rationale": "Email contains exam scheduling information",
                    "detected_entities": {
                        "course_codes": ["CS101"],
                        "event_names": ["Midterm Exam"]
                    },
                    "sentiment": "neutral",
                    "action_items": [
                        {
                            "action": "Study for midterm",
                            "deadline_utc": None,
                            "completed": False
                        }
                    ],
                    "thread_context": {
                        "is_reply": False,
                        "thread_id": None,
                        "previous_categories": []
                    },
                    "rag_context_used": ["chunk1", "chunk2"],
                    "suggested_folder": "Academics/Exams",
                    "schema_version": "v2"
                }
                
                mock_classifier.classify_email.return_value = classification_response
                
                # Arrange: Mock the workflow orchestrator
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    # Act: Execute the complete workflow
                    start_time = time.time()
                    
                    # This should trigger the complete poll → classify → persist flow
                    await mock_orchestrator.process_email_batch()
                    
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    # Assert: Performance targets (<5s median, <12s p95)
                    assert processing_time < 12.0, f"Processing time {processing_time:.2f}s exceeds p95 target of 12s"
                    
                    # Assert: Verify email status transitioned to CLASSIFIED
                    updated_email = await db_session.get(Email, test_email.id)
                    assert updated_email.classification_status == EmailStatus.CLASSIFIED
                    
                    # Assert: Verify ClassificationResult was created
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == test_email.id
                    )
                    result = await db_session.execute(result_stmt)
                    classification_result = result.scalar_one_or_none()
                    
                    assert classification_result is not None, "ClassificationResult should be created"
                    assert classification_result.primary_category == "academic.exams"
                    assert classification_result.confidence == 0.85
                    assert classification_result.schema_version == "v2"
                    assert classification_result.rationale == "Email contains exam scheduling information"
                    assert classification_result.sentiment == Sentiment.NEUTRAL
                    assert classification_result.priority == Priority.NORMAL
                    assert classification_result.deadline_confidence == DeadlineConfidence.NONE
                    
                    # Assert: Validate classification output against schema v2
                    assert "academic.exams" in classification_result.primary_category
                    assert 0.0 <= float(classification_result.confidence) <= 1.0
                    assert classification_result.schema_version == "v2"
                    assert len(classification_result.secondary_categories) <= 3
                    assert len(classification_result.action_items) <= 10
                    assert len(classification_result.rationale) <= 200
                    
                    # Assert: Verify proper relationship between Email and ClassificationResult
                    assert classification_result.email_id == test_email.id
                    assert updated_email.classification.id == classification_result.id
                    
                    # Assert: Verify ClassificationCycle tracking
                    cycle_stmt = select(ClassificationCycle).where(
                        ClassificationCycle.start_timestamp <= datetime.now(timezone.utc)
                    )
                    cycle_result = await db_session.execute(cycle_stmt)
                    cycle = cycle_result.scalar_one_or_none()
                    
                    assert cycle is not None, "ClassificationCycle should be created"
                    assert cycle.emails_scanned >= 1
                    assert cycle.emails_classified >= 1
                    assert cycle.emails_failed == 0
                    assert cycle.duration_ms is not None
                    
                    # Assert: Verify RAG context was used
                    assert "chunk1" in classification_result.rag_context_used
                    assert "chunk2" in classification_result.rag_context_used
                    
                    # Assert: Verify detected entities
                    assert "course_codes" in classification_result.detected_entities
                    assert "CS101" in classification_result.detected_entities["course_codes"]
                    
                    # Assert: Verify action items
                    assert len(classification_result.action_items) > 0
                    assert classification_result.action_items[0]["action"] == "Study for midterm"
                    
                    # Assert: Verify metrics were recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name == "classification_latency_ms"
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    metric = metric_result.scalar_one_or_none()
                    
                    assert metric is not None, "Classification latency metric should be recorded"
                    assert metric.value > 0, "Latency should be positive"


@pytest.mark.asyncio
async def test_poll_classify_persist_error_handling(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    frozen_time,
    clean_db,
    error_scenarios
) -> None:
    """
    Test error handling in the poll → classify → persist workflow.
    
    This test validates that errors are properly handled and emails
    are marked as FAILED when classification cannot be completed.
    """
    # Arrange: Create test email
    test_email = email_factory(
        message_id="test-msg-error",
        sender="error@test.com",
        subject="This email will cause an error",
        classification_status=EmailStatus.PENDING
    )
    db_session.add(test_email)
    await db_session.commit()
    
    # Arrange: Mock services to raise an error
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
                
                # Mock classification to raise an error
                mock_classifier.classify_email.side_effect = error_scenarios["ollama_timeout"]["exception"]
                
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    # Act: Execute workflow with error
                    await mock_orchestrator.process_email_batch()
                    
                    # Assert: Verify email status is FAILED
                    updated_email = await db_session.get(Email, test_email.id)
                    assert updated_email.classification_status == EmailStatus.FAILED
                    
                    # Assert: Verify no ClassificationResult was created
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == test_email.id
                    )
                    result = await db_session.execute(result_stmt)
                    classification_result = result.scalar_one_or_none()
                    
                    assert classification_result is None, "No ClassificationResult should be created on failure"
                    
                    # Assert: Verify ClassificationCycle tracks the failure
                    cycle_stmt = select(ClassificationCycle)
                    cycle_result = await db_session.execute(cycle_stmt)
                    cycle = cycle_result.scalar_one_or_none()
                    
                    assert cycle is not None, "ClassificationCycle should be created"
                    assert cycle.emails_failed >= 1, "Failed emails should be tracked"


@pytest.mark.asyncio
async def test_poll_classify_persist_performance_targets(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db,
    performance_test_data
) -> None:
    """
    Test performance targets with varying email volumes.
    
    This test validates that the system meets performance targets
    with small, medium, and large email batches.
    """
    # Test with small batch (10 emails)
    small_emails = []
    for i, email_data in enumerate(performance_test_data["small_batch"]):
        email = email_factory(
            message_id=email_data["message_id"],
            sender=email_data["sender"],
            subject=email_data["subject"],
            classification_status=EmailStatus.PENDING
        )
        small_emails.append(email)
        db_session.add(email)
    
    await db_session.commit()
    
    # Mock services for batch processing
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = small_emails
        
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []
            
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                # Mock classification for each email
                def mock_classify(email):
                    return {
                        "message_id": email.message_id,
                        "primary_category": "academic.coursework",
                        "confidence": 0.8,
                        "schema_version": "v2"
                    }
                
                mock_classifier.classify_email.side_effect = mock_classify
                
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    # Act: Process batch
                    start_time = time.time()
                    await mock_orchestrator.process_email_batch()
                    end_time = time.time()
                    
                    processing_time = end_time - start_time
                    emails_per_second = len(small_emails) / processing_time
                    
                    # Assert: Performance targets
                    assert processing_time < 12.0, f"Small batch processing time {processing_time:.2f}s exceeds target"
                    assert emails_per_second > 0.8, f"Processing rate {emails_per_second:.2f} emails/s below target"
                    
                    # Assert: All emails were classified
                    for email in small_emails:
                        updated_email = await db_session.get(Email, email.id)
                        assert updated_email.classification_status == EmailStatus.CLASSIFIED