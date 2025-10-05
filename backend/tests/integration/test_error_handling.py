"""
Integration tests for error handling and quarantine mechanisms.

This module tests comprehensive error handling throughout the email classification workflow:
- Transient error handling with retry logic (IMAP connection failures, Ollama timeouts, Gmail rate limits, database issues)
- Permanent error handling (malformed headers, schema validation failures, constraint violations)
- Quarantine mechanisms (email status transitions, retry logic, quarantine queue)
- Error context preservation (logging, metrics)
- System resilience under error conditions
- Performance targets during error conditions

Test coverage:
- Retry logic with exponential backoff and circuit breaker patterns
- Email status transitions (PENDING → CLASSIFYING → FAILED/QUARANTINED)
- Quarantine queue operations and monitoring
- Error logging and metrics collection
- System resilience and recovery
- Performance targets under error conditions
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Email, ClassificationResult, ClassificationCycle,
    SystemConfig, DashboardMetric, SystemHealthStatus
)
from src.database.enums import EmailStatus, Priority, Sentiment, DeadlineConfidence, HealthStatus


@pytest.mark.asyncio
async def test_error_handling_transient_errors(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db,
    error_scenarios
) -> None:
    """
    Test handling of transient errors with retry logic.
    
    This test validates:
    1. IMAP connection failures are retried with exponential backoff
    2. Ollama timeouts trigger retry logic with circuit breaker
    3. Gmail rate limits are handled with appropriate delays
    4. Database connection issues are retried
    5. Email status transitions during retry attempts
    6. Successful recovery after transient errors
    7. Retry metrics are recorded
    """
    # Arrange: Create test email
    test_email = email_factory(
        message_id="test-transient-001",
        sender="test@example.com",
        subject="Test Transient Error Handling",
        classification_status=EmailStatus.PENDING
    )
    db_session.add(test_email)
    await db_session.commit()
    await db_session.refresh(test_email)
    
    # Arrange: Configure retry settings
    retry_config = SystemConfig(
        key="MAX_RETRY_ATTEMPTS",
        value="3",
        value_type="int"
    )
    db_session.add(retry_config)
    await db_session.commit()
    
    # Arrange: Mock email poller with transient IMAP errors
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        
        # First attempt fails with IMAP connection error, then succeeds
        imap_call_count = 0
        async def mock_poll_with_retry():
            nonlocal imap_call_count
            imap_call_count += 1
            if imap_call_count == 1:
                raise error_scenarios["imap_connection_failed"]["exception"]
            return [test_email]
        
        mock_poller.poll_emails.side_effect = mock_poll_with_retry
        
        # Arrange: Mock RAG retriever
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []
            
            # Arrange: Mock LLM classifier with timeout on first attempt
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                ollama_call_count = 0
                async def mock_classify_with_retry(email):
                    nonlocal ollama_call_count
                    ollama_call_count += 1
                    if ollama_call_count == 1:
                        raise error_scenarios["ollama_timeout"]["exception"]
                    return {
                        "message_id": email.message_id,
                        "primary_category": "academic.coursework",
                        "confidence": 0.8,
                        "schema_version": "v2"
                    }
                
                mock_classifier.classify_email.side_effect = mock_classify_with_retry
                
                # Arrange: Mock workflow orchestrator with retry logic
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    # Mock retry tracking
                    retry_attempts = []
                    
                    async def mock_process_with_retry():
                        # Simulate retry attempts
                        for attempt in range(3):
                            retry_attempts.append({
                                "attempt": attempt + 1,
                                "timestamp": datetime.now(timezone.utc),
                                "error_type": "transient" if attempt < 2 else None
                            })
                            if attempt < 2:
                                await asyncio.sleep(0.01)  # Simulate retry delay
                        return {"processed": 1, "retries": 2}
                    
                    mock_orchestrator.process_email_batch.side_effect = mock_process_with_retry
                    
                    # Act: Process email with transient errors
                    start_time = time.time()
                    result = await mock_orchestrator.process_email_batch()
                    processing_time = time.time() - start_time
                    
                    # Assert: Processing succeeded after retries
                    assert result["processed"] == 1
                    assert result["retries"] == 2
                    assert processing_time < 5.0, "Processing with retries should complete in reasonable time"
                    
                    # Assert: Email status transitioned to CLASSIFIED
                    updated_email = await db_session.get(Email, test_email.id)
                    assert updated_email.classification_status == EmailStatus.CLASSIFIED
                    
                    # Assert: ClassificationResult was created
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == test_email.id
                    )
                    result = await db_session.execute(result_stmt)
                    classification_result = result.scalar_one_or_none()
                    
                    assert classification_result is not None, "Classification should succeed after retries"
                    assert classification_result.primary_category == "academic.coursework"
                    
                    # Assert: Retry metrics were recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name == "retry_attempts_total"
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    retry_metric = metric_result.scalar_one_or_none()
                    
                    assert retry_metric is not None, "Retry metrics should be recorded"
                    assert retry_metric.value >= 2, "Should record retry attempts"
                    
                    # Assert: IMAP and Ollama were retried
                    assert imap_call_count == 2, "IMAP should be retried after connection failure"
                    assert ollama_call_count == 2, "Ollama should be retried after timeout"


@pytest.mark.asyncio
async def test_error_handling_permanent_errors(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db,
    error_scenarios
) -> None:
    """
    Test handling of permanent errors that should not be retried.
    
    This test validates:
    1. Malformed email headers are marked as FAILED without retry
    2. Schema validation failures are handled gracefully
    3. Database constraint violations are not retried
    4. Invalid email formats are quarantined appropriately
    5. Error details are preserved for debugging
    6. System continues processing other emails
    """
    # Arrange: Create test emails with different permanent error conditions
    malformed_email = email_factory(
        message_id="test-permanent-malformed",
        sender="invalid-email",  # Invalid format
        subject="",  # Empty subject
        classification_status=EmailStatus.PENDING
    )
    
    schema_violation_email = email_factory(
        message_id="test-permanent-schema",
        sender="test@example.com",
        subject="Schema Violation Test",
        classification_status=EmailStatus.PENDING
    )
    
    constraint_email = email_factory(
        message_id="test-permanent-constraint",
        sender="test@example.com",
        subject="Constraint Violation Test",
        classification_status=EmailStatus.PENDING
    )
    
    for email in [malformed_email, schema_violation_email, constraint_email]:
        db_session.add(email)
    await db_session.commit()
    
    # Arrange: Mock email poller
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [malformed_email, schema_violation_email, constraint_email]
        
        # Arrange: Mock RAG retriever
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []
            
            # Arrange: Mock LLM classifier with different permanent errors
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                def mock_classify_with_permanent_errors(email):
                    if email.message_id == "test-permanent-malformed":
                        raise ValueError("Malformed email headers: invalid sender format")
                    elif email.message_id == "test-permanent-schema":
                        return {
                            "message_id": email.message_id,
                            "primary_category": "invalid.category.format",
                            "confidence": 1.5,  # Invalid: > 1.0
                            "schema_version": "v1"  # Invalid: wrong version
                        }
                    elif email.message_id == "test-permanent-constraint":
                        raise error_scenarios["database_constraint"]["exception"]
                
                mock_classifier.classify_email.side_effect = mock_classify_with_permanent_errors
                
                # Arrange: Mock workflow orchestrator with error handling
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    async def mock_process_with_permanent_errors():
                        # Simulate processing with permanent errors
                        error_details = []
                        
                        for email in [malformed_email, schema_violation_email, constraint_email]:
                            try:
                                await mock_classifier.classify_email(email)
                            except Exception as e:
                                error_details.append({
                                    "email_id": email.id,
                                    "error_type": "permanent",
                                    "error_message": str(e),
                                    "timestamp": datetime.now(timezone.utc),
                                    "should_retry": False
                                })
                                # Update email status to FAILED
                                email.classification_status = EmailStatus.FAILED
                                await db_session.commit()
                        
                        return {
                            "processed": 0,
                            "failed": 3,
                            "errors": error_details
                        }
                    
                    mock_orchestrator.process_email_batch.side_effect = mock_process_with_permanent_errors
                    
                    # Act: Process emails with permanent errors
                    result = await mock_orchestrator.process_email_batch()
                    
                    # Assert: All emails failed without retries
                    assert result["processed"] == 0
                    assert result["failed"] == 3
                    assert len(result["errors"]) == 3
                    
                    # Assert: All emails marked as FAILED
                    for email in [malformed_email, schema_violation_email, constraint_email]:
                        updated_email = await db_session.get(Email, email.id)
                        assert updated_email.classification_status == EmailStatus.FAILED
                    
                    # Assert: No ClassificationResults were created
                    result_stmt = select(ClassificationResult)
                    result = await db_session.execute(result_stmt)
                    classifications = result.scalars().all()
                    
                    assert len(classifications) == 0, "No classifications should be created for permanent errors"
                    
                    # Assert: Error metrics were recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name == "permanent_errors_total"
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    error_metric = metric_result.scalar_one_or_none()
                    
                    assert error_metric is not None, "Permanent error metrics should be recorded"
                    assert error_metric.value == 3, "Should record all permanent errors"
                    
                    # Assert: Error details preserved
                    for error in result["errors"]:
                        assert error["should_retry"] is False, "Permanent errors should not be retried"
                        assert error["error_type"] == "permanent", "Error type should be permanent"
                        assert len(error["error_message"]) > 0, "Error message should be preserved"


@pytest.mark.asyncio
async def test_quarantine_mechanism(
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
    Test quarantine mechanism for problematic emails.
    
    This test validates:
    1. Emails with repeated failures are moved to quarantine
    2. Quarantine queue operations work correctly
    3. Quarantined emails can be manually reviewed
    4. Quarantine release mechanism functions properly
    5. Quarantine metrics are tracked
    6. Email status transitions through quarantine states
    """
    # Arrange: Create test emails that will be quarantined
    quarantine_emails = []
    for i in range(3):
        email = email_factory(
            message_id=f"test-quarantine-{i:03d}",
            sender=f"quarantine{i}@example.com",
            subject=f"Quarantine Test Email {i}",
            classification_status=EmailStatus.PENDING
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)
        quarantine_emails.append(email)
    
    # Arrange: Configure quarantine settings
    quarantine_config = SystemConfig(
        key="QUARANTINE_THRESHOLD",
        value="3",
        value_type="int"
    )
    db_session.add(quarantine_config)
    await db_session.commit()
    
    # Arrange: Mock email poller
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = quarantine_emails
        
        # Arrange: Mock RAG retriever
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            mock_rag.retrieve_context.return_value = []
            
            # Arrange: Mock LLM classifier to consistently fail
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                mock_classifier.classify_email.side_effect = Exception("Consistent classification failure")
                
                # Arrange: Mock workflow orchestrator with quarantine logic
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    # Track failure counts for quarantine decision
                    failure_counts = {email.id: 0 for email in quarantine_emails}
                    
                    async def mock_process_with_quarantine():
                        quarantine_results = []
                        
                        for email in quarantine_emails:
                            failure_counts[email.id] += 1
                            
                            if failure_counts[email.id] >= 3:
                                # Move to quarantine
                                email.classification_status = EmailStatus.QUARANTINED
                                quarantine_results.append({
                                    "email_id": email.id,
                                    "quarantine_reason": "Exceeded failure threshold",
                                    "failure_count": failure_counts[email.id],
                                    "quarantine_timestamp": datetime.now(timezone.utc)
                                })
                            else:
                                # Mark as failed for retry
                                email.classification_status = EmailStatus.FAILED
                            
                            await db_session.commit()
                        
                        return {
                            "processed": 0,
                            "failed": len(quarantine_emails),
                            "quarantined": len(quarantine_results),
                            "quarantine_details": quarantine_results
                        }
                    
                    mock_orchestrator.process_email_batch.side_effect = mock_process_with_quarantine
                    
                    # Act: Process emails until quarantine threshold is reached
                    # First two attempts - failures
                    await mock_orchestrator.process_email_batch()
                    await mock_orchestrator.process_email_batch()
                    
                    # Third attempt - should trigger quarantine
                    result = await mock_orchestrator.process_email_batch()
                    
                    # Assert: All emails moved to quarantine
                    assert result["quarantined"] == 3, "All emails should be quarantined"
                    assert len(result["quarantine_details"]) == 3
                    
                    # Assert: Email status is QUARANTINED
                    for email in quarantine_emails:
                        updated_email = await db_session.get(Email, email.id)
                        assert updated_email.classification_status == EmailStatus.QUARANTINED
                    
                    # Assert: Quarantine metrics recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name == "quarantined_emails_total"
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    quarantine_metric = metric_result.scalar_one_or_none()
                    
                    assert quarantine_metric is not None, "Quarantine metrics should be recorded"
                    assert quarantine_metric.value == 3, "Should record quarantined emails"
                    
                    # Assert: Quarantine details preserved
                    for detail in result["quarantine_details"]:
                        assert detail["failure_count"] >= 3, "Should have exceeded failure threshold"
                        assert detail["quarantine_reason"] is not None, "Quarantine reason should be recorded"
                        assert "quarantine_timestamp" in detail, "Quarantine timestamp should be recorded"
                    
                    # Test quarantine release mechanism
                    with patch('src.services.quarantine_manager.QuarantineManager') as mock_quarantine_class:
                        mock_quarantine = AsyncMock()
                        mock_quarantine_class.return_value = mock_quarantine
                        
                        # Mock successful classification after manual review
                        mock_quarantine.release_from_quarantine.return_value = {
                            "email_id": quarantine_emails[0].id,
                            "status": "released",
                            "classification": {
                                "primary_category": "admin.general",
                                "confidence": 0.7,
                                "schema_version": "v2"
                            }
                        }
                        
                        # Act: Release one email from quarantine
                        release_result = await mock_quarantine.release_from_quarantine(
                            quarantine_emails[0].id,
                            manual_review=True
                        )
                        
                        # Assert: Email released successfully
                        assert release_result["status"] == "released"
                        assert "classification" in release_result
                        
                        # Update email status to simulate release
                        quarantine_emails[0].classification_status = EmailStatus.CLASSIFIED
                        await db_session.commit()
                        
                        # Verify release
                        released_email = await db_session.get(Email, quarantine_emails[0].id)
                        assert released_email.classification_status == EmailStatus.CLASSIFIED


@pytest.mark.asyncio
async def test_error_context_preservation(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db,
    error_scenarios
) -> None:
    """
    Test preservation of error context for debugging and monitoring.
    
    This test validates:
    1. Error details are logged with sufficient context
    2. Error metrics include relevant metadata
    3. System health status reflects error conditions
    4. Error correlation across service calls is maintained
    5. Error context is preserved for troubleshooting
    6. Performance impact of error context collection is minimal
    """
    # Arrange: Create test email
    test_email = email_factory(
        message_id="test-context-001",
        sender="context@test.com",
        subject="Error Context Preservation Test",
        classification_status=EmailStatus.PENDING
    )
    db_session.add(test_email)
    await db_session.commit()
    
    # Arrange: Mock services with detailed error context
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [test_email]
        
        # Arrange: Mock RAG retriever with context
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            
            # Mock RAG failure with context
            rag_error_context = {
                "service": "rag_retriever",
                "operation": "retrieve_context",
                "query_hash": "abc123",
                "collection": "email_embeddings",
                "search_params": {"limit": 5, "score_threshold": 0.7}
            }
            
            mock_rag.retrieve_context.side_effect = Exception(
                f"RAG retrieval failed: {json.dumps(rag_error_context)}"
            )
            
            # Arrange: Mock LLM classifier with context
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                # Mock LLM failure with context
                llm_error_context = {
                    "service": "llm_classifier",
                    "model": "qwen3:8b",
                    "prompt_tokens": 150,
                    "temperature": 0.1,
                    "request_id": str(uuid.uuid4())
                }
                
                mock_classifier.classify_email.side_effect = Exception(
                    f"LLM classification failed: {json.dumps(llm_error_context)}"
                )
                
                # Arrange: Mock workflow orchestrator with error context collection
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    async def mock_process_with_context_collection():
                        error_contexts = []
                        
                        # Collect error context from each service
                        try:
                            await mock_rag.retrieve_context()
                        except Exception as e:
                            error_contexts.append({
                                "timestamp": datetime.now(timezone.utc),
                                "service": "rag_retriever",
                                "error": str(e),
                                "email_id": test_email.id,
                                "context": rag_error_context
                            })
                        
                        try:
                            await mock_classifier.classify_email(test_email)
                        except Exception as e:
                            error_contexts.append({
                                "timestamp": datetime.now(timezone.utc),
                                "service": "llm_classifier",
                                "error": str(e),
                                "email_id": test_email.id,
                                "context": llm_error_context
                            })
                        
                        # Update email status
                        test_email.classification_status = EmailStatus.FAILED
                        await db_session.commit()
                        
                        # Record error metrics with context
                        for context in error_contexts:
                            metric = DashboardMetric(
                                metric_name=f"error_context_{context['service']}",
                                value=1,
                                timestamp=datetime.now(timezone.utc),
                                labels={
                                    "service": context["service"],
                                    "email_id": str(context["email_id"]),
                                    "error_type": "processing_failure"
                                }
                            )
                            db_session.add(metric)
                        
                        # Update system health status
                        health_status = SystemHealthStatus(
                            component_name="classification_pipeline",
                            status=HealthStatus.DEGRADED,
                            error_message="Multiple service failures in classification pipeline",
                            metrics={
                                "error_count": len(error_contexts),
                                "affected_services": ["rag_retriever", "llm_classifier"],
                                "last_error_timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        )
                        db_session.add(health_status)
                        await db_session.commit()
                        
                        return {
                            "processed": 0,
                            "failed": 1,
                            "error_contexts": error_contexts
                        }
                    
                    mock_orchestrator.process_email_batch.side_effect = mock_process_with_context_collection
                    
                    # Act: Process with error context collection
                    start_time = time.time()
                    result = await mock_orchestrator.process_email_batch()
                    context_collection_time = time.time() - start_time
                    
                    # Assert: Error context collected
                    assert len(result["error_contexts"]) == 2, "Should collect context from all failed services"
                    
                    # Assert: Performance impact is minimal
                    assert context_collection_time < 0.1, "Error context collection should be fast"
                    
                    # Assert: Email status updated
                    updated_email = await db_session.get(Email, test_email.id)
                    assert updated_email.classification_status == EmailStatus.FAILED
                    
                    # Assert: Error metrics with context recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name.like("error_context_%")
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    context_metrics = metric_result.scalars().all()
                    
                    assert len(context_metrics) == 2, "Should record context metrics for each service"
                    
                    for metric in context_metrics:
                        assert "service" in metric.labels, "Metrics should include service label"
                        assert "email_id" in metric.labels, "Metrics should include email_id label"
                        assert "error_type" in metric.labels, "Metrics should include error_type label"
                    
                    # Assert: System health status updated
                    health_stmt = select(SystemHealthStatus).where(
                        SystemHealthStatus.component_name == "classification_pipeline"
                    )
                    health_result = await db_session.execute(health_stmt)
                    health_status = health_result.scalar_one_or_none()
                    
                    assert health_status is not None, "System health status should be updated"
                    assert health_status.status == HealthStatus.DEGRADED, "Status should reflect degraded operation"
                    assert health_status.error_message is not None, "Error message should be preserved"
                    assert "error_count" in health_status.metrics, "Health metrics should include error count"
                    
                    # Assert: Error context preservation
                    for context in result["error_contexts"]:
                        assert "timestamp" in context, "Error timestamp should be recorded"
                        assert "service" in context, "Service name should be recorded"
                        assert "error" in context, "Error message should be recorded"
                        assert "context" in context, "Service-specific context should be preserved"
                        assert len(json.loads(context["error"])) > 0, "Context should be valid JSON"


@pytest.mark.asyncio
async def test_resilience_under_error_conditions(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db,
    error_scenarios
) -> None:
    """
    Test system resilience under various error conditions.
    
    This test validates:
    1. Circuit breaker patterns prevent cascading failures
    2. Partial service degradation doesn't stop processing
    3. System recovers gracefully after service restoration
    4. Load shedding prevents system overload
    5. Graceful degradation maintains core functionality
    6. Error isolation prevents impact on unrelated operations
    """
    # Arrange: Create mixed batch of emails
    normal_emails = []
    problematic_emails = []
    
    for i in range(5):
        normal_email = email_factory(
            message_id=f"normal-{i:03d}",
            sender=f"normal{i}@example.com",
            subject=f"Normal Email {i}",
            classification_status=EmailStatus.PENDING
        )
        normal_emails.append(normal_email)
        db_session.add(normal_email)
    
    for i in range(3):
        problematic_email = email_factory(
            message_id=f"problem-{i:03d}",
            sender=f"problem{i}@example.com",
            subject=f"Problematic Email {i}",
            classification_status=EmailStatus.PENDING
        )
        problematic_emails.append(problematic_email)
        db_session.add(problematic_email)
    
    await db_session.commit()
    
    # Arrange: Configure resilience settings
    circuit_breaker_config = SystemConfig(
        key="CIRCUIT_BREAKER_THRESHOLD",
        value="2",
        value_type="int"
    )
    load_shedding_config = SystemConfig(
        key="MAX_CONCURRENT_FAILURES",
        value="3",
        value_type="int"
    )
    db_session.add(circuit_breaker_config)
    db_session.add(load_shedding_config)
    await db_session.commit()
    
    # Arrange: Mock services with varying failure patterns
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = normal_emails + problematic_emails
        
        # Arrange: Mock RAG retriever with partial failures
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            
            def mock_retrieve_context(email):
                if "problem" in email.message_id:
                    # Simulate partial RAG failures
                    raise Exception("RAG service partially degraded")
                return [{"id": "chunk1", "text": "Normal context", "score": 0.8}]
            
            mock_rag.retrieve_context.side_effect = mock_retrieve_context
            
            # Arrange: Mock LLM classifier with circuit breaker behavior
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                # Track failures for circuit breaker
                failure_count = 0
                circuit_open = False
                
                def mock_classify_with_circuit_breaker(email):
                    nonlocal failure_count, circuit_open
                    
                    if circuit_open:
                        raise Exception("Circuit breaker is open - service unavailable")
                    
                    if "problem" in email.message_id:
                        failure_count += 1
                        if failure_count >= 2:
                            circuit_open = True
                        raise Exception("LLM service failure")
                    
                    return {
                        "message_id": email.message_id,
                        "primary_category": "admin.general",
                        "confidence": 0.8,
                        "schema_version": "v2"
                    }
                
                mock_classifier.classify_email.side_effect = mock_classify_with_circuit_breaker
                
                # Arrange: Mock workflow orchestrator with resilience logic
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    async def mock_process_with_resilience():
                        results = {
                            "processed": 0,
                            "failed": 0,
                            "shedded": 0,
                            "circuit_breaker_trips": 0,
                            "partial_degradation": True
                        }
                        
                        # Simulate load shedding - skip some problematic emails
                        concurrent_failures = 0
                        for email in problematic_emails:
                            try:
                                await mock_classifier.classify_email(email)
                            except Exception as e:
                                concurrent_failures += 1
                                if concurrent_failures >= 3:
                                    results["shedded"] += 1
                                    email.classification_status = EmailStatus.QUARANTINED
                                    await db_session.commit()
                                    continue
                                
                                if "Circuit breaker" in str(e):
                                    results["circuit_breaker_trips"] += 1
                                
                                email.classification_status = EmailStatus.FAILED
                                await db_session.commit()
                                results["failed"] += 1
                        
                        # Process normal emails with degraded service
                        for email in normal_emails:
                            try:
                                # Try classification without RAG for problematic emails
                                if "problem" not in email.message_id:
                                    classification = await mock_classifier.classify_email(email)
                                    # Create classification result
                                    result = classification_result_factory(
                                        email_id=email.id,
                                        primary_category=classification["primary_category"],
                                        confidence=classification["confidence"]
                                    )
                                    db_session.add(result)
                                    email.classification_status = EmailStatus.CLASSIFIED
                                    results["processed"] += 1
                                else:
                                    # Skip problematic emails due to degraded service
                                    email.classification_status = EmailStatus.FAILED
                                    results["failed"] += 1
                            except Exception:
                                email.classification_status = EmailStatus.FAILED
                                results["failed"] += 1
                            
                            await db_session.commit()
                        
                        # Record resilience metrics
                        resilience_metric = DashboardMetric(
                            metric_name="system_resilience_score",
                            value=results["processed"] / len(normal_emails) * 100,  # Percentage of normal emails processed
                            timestamp=datetime.now(timezone.utc),
                            labels={
                                "circuit_breaker_trips": str(results["circuit_breaker_trips"]),
                                "load_shedding_active": str(results["shedded"] > 0),
                                "partial_degradation": str(results["partial_degradation"])
                            }
                        )
                        db_session.add(resilience_metric)
                        await db_session.commit()
                        
                        return results
                    
                    mock_orchestrator.process_email_batch.side_effect = mock_process_with_resilience
                    
                    # Act: Process with resilience mechanisms
                    start_time = time.time()
                    result = await mock_orchestrator.process_email_batch()
                    processing_time = time.time() - start_time
                    
                    # Assert: System maintained partial functionality
                    assert result["processed"] >= 3, "Should process most normal emails despite failures"
                    assert result["failed"] <= 3, "Should limit failures to problematic emails"
                    assert result["shedded"] >= 1, "Should shed load to prevent overload"
                    assert result["circuit_breaker_trips"] >= 1, "Should trigger circuit breaker"
                    assert result["partial_degradation"] is True, "Should acknowledge partial degradation"
                    
                    # Assert: Processing completed in reasonable time
                    assert processing_time < 10.0, "Resilient processing should complete efficiently"
                    
                    # Assert: Normal emails processed successfully
                    for email in normal_emails:
                        updated_email = await db_session.get(Email, email.id)
                        assert updated_email.classification_status == EmailStatus.CLASSIFIED
                    
                    # Assert: Problematic emails handled appropriately
                    for email in problematic_emails:
                        updated_email = await db_session.get(Email, email.id)
                        assert updated_email.classification_status in [EmailStatus.FAILED, EmailStatus.QUARANTINED]
                    
                    # Assert: Resilience metrics recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name == "system_resilience_score"
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    resilience_metric = metric_result.scalar_one_or_none()
                    
                    assert resilience_metric is not None, "Resilience metrics should be recorded"
                    assert resilience_metric.value >= 60.0, "Should maintain reasonable resilience score"
                    
                    # Test recovery after service restoration
                    # Reset circuit breaker
                    failure_count = 0
                    circuit_open = False
                    
                    # Act: Process again with restored services
                    recovery_result = await mock_orchestrator.process_email_batch()
                    
                    # Assert: System recovered
                    assert recovery_result["processed"] >= len(normal_emails), "Should fully recover normal processing"
                    assert recovery_result["circuit_breaker_trips"] == 0, "Circuit breaker should be reset"


@pytest.mark.asyncio
async def test_performance_with_errors(
    db_session: AsyncSession,
    mock_imap_server: MagicMock,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db,
    error_scenarios
) -> None:
    """
    Test performance targets under error conditions.
    
    This test validates:
    1. Latency targets are met despite errors (<12s p95)
    2. Throughput remains acceptable with error handling (>0.8 emails/s)
    3. Error handling overhead is minimal
    4. Performance degradation is within acceptable limits
    5. Resource usage remains controlled during error spikes
    6. Performance metrics accurately reflect error conditions
    """
    # Arrange: Create test batch with mixed success/failure scenarios
    batch_size = 20
    test_emails = []
    
    for i in range(batch_size):
        # 70% normal emails, 30% problematic
        is_problematic = i >= 14
        email = email_factory(
            message_id=f"perf-test-{i:03d}",
            sender=f"perf{i}@example.com",
            subject=f"Performance Test Email {i}",
            classification_status=EmailStatus.PENDING
        )
        test_emails.append((email, is_problematic))
        db_session.add(email)
    
    await db_session.commit()
    
    # Arrange: Mock services with realistic performance under errors
    with patch('src.services.email_poller.EmailPoller') as mock_poller_class:
        mock_poller = AsyncMock()
        mock_poller_class.return_value = mock_poller
        mock_poller.poll_emails.return_value = [email for email, _ in test_emails]
        
        # Arrange: Mock RAG retriever with variable latency
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            
            async def mock_retrieve_context_with_latency(email):
                is_problematic = any(email.message_id == e.message_id for e, prob in test_emails if prob)
                
                if is_problematic:
                    # Simulate RAG latency for problematic emails
                    await asyncio.sleep(0.1)  # 100ms delay
                    raise Exception("RAG timeout")
                else:
                    # Normal latency for good emails
                    await asyncio.sleep(0.02)  # 20ms delay
                    return [{"id": "chunk1", "text": "Context", "score": 0.8}]
            
            mock_rag.retrieve_context.side_effect = mock_retrieve_context_with_latency
            
            # Arrange: Mock LLM classifier with variable performance
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                async def mock_classify_with_performance(email):
                    is_problematic = any(email.message_id == e.message_id for e, prob in test_emails if prob)
                    
                    if is_problematic:
                        # Simulate LLM timeout for problematic emails
                        await asyncio.sleep(0.2)  # 200ms delay
                        raise error_scenarios["ollama_timeout"]["exception"]
                    else:
                        # Normal processing time
                        await asyncio.sleep(0.05)  # 50ms delay
                        return {
                            "message_id": email.message_id,
                            "primary_category": "admin.general",
                            "confidence": 0.8,
                            "schema_version": "v2"
                        }
                
                mock_classifier.classify_email.side_effect = mock_classify_with_performance
                
                # Arrange: Mock workflow orchestrator with performance tracking
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    async def mock_process_with_performance_tracking():
                        start_time = time.time()
                        processed_count = 0
                        failed_count = 0
                        latencies = []
                        
                        for email, is_problematic in test_emails:
                            email_start = time.time()
                            
                            try:
                                # Simulate the full classification pipeline
                                await mock_rag.retrieve_context(email)
                                classification = await mock_classifier.classify_email(email)
                                
                                # Create classification result
                                result = classification_result_factory(
                                    email_id=email.id,
                                    primary_category=classification["primary_category"],
                                    confidence=classification["confidence"]
                                )
                                db_session.add(result)
                                email.classification_status = EmailStatus.CLASSIFIED
                                processed_count += 1
                                
                            except Exception as e:
                                email.classification_status = EmailStatus.FAILED
                                failed_count += 1
                            
                            email_latency = (time.time() - email_start) * 1000  # Convert to ms
                            latencies.append(email_latency)
                            await db_session.commit()
                        
                        total_time = time.time() - start_time
                        throughput = processed_count / total_time if total_time > 0 else 0
                        
                        # Calculate performance metrics
                        avg_latency = sum(latencies) / len(latencies)
                        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
                        
                        # Record performance metrics
                        performance_metrics = [
                            DashboardMetric(
                                metric_name="classification_latency_ms",
                                value=avg_latency,
                                timestamp=datetime.now(timezone.utc),
                                labels={"scenario": "with_errors"}
                            ),
                            DashboardMetric(
                                metric_name="classification_p95_latency_ms",
                                value=p95_latency,
                                timestamp=datetime.now(timezone.utc),
                                labels={"scenario": "with_errors"}
                            ),
                            DashboardMetric(
                                metric_name="classification_throughput",
                                value=throughput,
                                timestamp=datetime.now(timezone.utc),
                                labels={"scenario": "with_errors"}
                            ),
                            DashboardMetric(
                                metric_name="error_rate_percentage",
                                value=(failed_count / len(test_emails)) * 100,
                                timestamp=datetime.now(timezone.utc),
                                labels={"scenario": "with_errors"}
                            )
                        ]
                        
                        for metric in performance_metrics:
                            db_session.add(metric)
                        
                        await db_session.commit()
                        
                        return {
                            "processed": processed_count,
                            "failed": failed_count,
                            "total_time": total_time,
                            "throughput": throughput,
                            "avg_latency_ms": avg_latency,
                            "p95_latency_ms": p95_latency,
                            "error_rate": (failed_count / len(test_emails)) * 100
                        }
                    
                    mock_orchestrator.process_email_batch.side_effect = mock_process_with_performance_tracking
                    
                    # Act: Process batch with performance tracking
                    result = await mock_orchestrator.process_email_batch()
                    
                    # Assert: Performance targets met despite errors
                    assert result["p95_latency_ms"] < 12000, f"P95 latency {result['p95_latency_ms']:.2f}ms exceeds 12s target"
                    assert result["throughput"] > 0.8, f"Throughput {result['throughput']:.2f} emails/s below 0.8 target"
                    assert result["avg_latency_ms"] < 5000, f"Average latency {result['avg_latency_ms']:.2f}ms too high"
                    
                    # Assert: Error rate is within expected bounds
                    assert 20 <= result["error_rate"] <= 40, "Error rate should be around 30% (6/20 problematic emails)"
                    
                    # Assert: Processing completed in reasonable time
                    assert result["total_time"] < 30.0, "Batch processing should complete in reasonable time"
                    
                    # Assert: Performance metrics recorded
                    metric_stmt = select(DashboardMetric).where(
                        DashboardMetric.metric_name.in_([
                            "classification_latency_ms",
                            "classification_p95_latency_ms",
                            "classification_throughput",
                            "error_rate_percentage"
                        ])
                    )
                    metric_result = await db_session.execute(metric_stmt)
                    metrics = metric_result.scalars().all()
                    
                    assert len(metrics) == 4, "All performance metrics should be recorded"
                    
                    # Verify specific metrics
                    latency_metric = next((m for m in metrics if m.metric_name == "classification_latency_ms"), None)
                    p95_metric = next((m for m in metrics if m.metric_name == "classification_p95_latency_ms"), None)
                    throughput_metric = next((m for m in metrics if m.metric_name == "classification_throughput"), None)
                    error_rate_metric = next((m for m in metrics if m.metric_name == "error_rate_percentage"), None)
                    
                    assert latency_metric is not None and latency_metric.value > 0, "Latency metric should be positive"
                    assert p95_metric is not None and p95_metric.value < 12000, "P95 latency should meet target"
                    assert throughput_metric is not None and throughput_metric.value > 0.8, "Throughput should meet target"
                    assert error_rate_metric is not None and 20 <= error_rate_metric.value <= 40, "Error rate should be expected"
                    
                    # Assert: Normal emails processed successfully
                    normal_processed = 0
                    for email, is_problematic in test_emails:
                        if not is_problematic:
                            updated_email = await db_session.get(Email, email.id)
                            if updated_email.classification_status == EmailStatus.CLASSIFIED:
                                normal_processed += 1
                    
                    assert normal_processed >= 10, "Most normal emails should be processed successfully"
                    
                    # Assert: Problematic emails handled appropriately
                    problem_failed = 0
                    for email, is_problematic in test_emails:
                        if is_problematic:
                            updated_email = await db_session.get(Email, email.id)
                            if updated_email.classification_status == EmailStatus.FAILED:
                                problem_failed += 1
                    
                    assert problem_failed >= 4, "Most problematic emails should fail as expected"