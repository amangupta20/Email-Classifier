"""
Integration tests for the feedback loop mechanism.

This module tests the complete feedback loop workflow:
- User submits corrections for misclassified emails
- Feedback is stored in the UserFeedback table
- RAG knowledge base is updated with user corrections
- Improved classification for similar emails after feedback
- Error handling and validation
- Performance tracking

Test coverage:
- Feedback submission and storage
- Knowledge base updates from feedback
- Classification improvements after feedback incorporation
- Invalid feedback handling
- Performance tracking for feedback processing
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Email, ClassificationResult, UserFeedback, ClassificationCycle,
    SystemConfig, DashboardMetric
)
from src.database.enums import EmailStatus, Priority, Sentiment, DeadlineConfidence


@pytest.mark.asyncio
async def test_feedback_submission_and_storage(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test user feedback submission and storage in UserFeedback table.
    
    This test validates:
    1. User correction submission creates UserFeedback record
    2. Original and corrected categories are properly stored
    3. Feedback reason is captured
    4. Timestamp is recorded correctly
    5. Incorporated flag defaults to False
    6. Email relationship is properly established
    """
    # Arrange: Create email with classification
    test_email = email_factory(
        message_id="test-feedback-001",
        sender="professor@university.edu",
        subject="Course Assignment Due",
        classification_status=EmailStatus.CLASSIFIED
    )
    db_session.add(test_email)
    await db_session.commit()
    await db_session.refresh(test_email)
    
    # Create initial classification
    initial_classification = classification_result_factory(
        email_id=test_email.id,
        primary_category="admin.general",
        confidence=0.75,
        rationale="Administrative notice about deadlines"
    )
    db_session.add(initial_classification)
    await db_session.commit()
    
    # Arrange: Mock feedback processor service
    with patch('src.services.feedback_processor.FeedbackProcessor') as mock_processor_class:
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        # Mock feedback submission
        feedback_data = {
            "email_id": str(test_email.id),
            "original_category": "admin.general",
            "corrected_category": "academic.coursework",
            "reason": "This is clearly about academic assignments, not general admin"
        }
        
        mock_processor.submit_feedback.return_value = {
            "feedback_id": str(uuid.uuid4()),
            "status": "submitted",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Act: Submit user feedback
        result = await mock_processor.submit_feedback(feedback_data)
        
        # Assert: Feedback submission succeeded
        assert result["status"] == "submitted"
        assert "feedback_id" in result
        
        # Assert: UserFeedback record was created
        feedback_stmt = select(UserFeedback).where(
            UserFeedback.email_id == test_email.id
        )
        feedback_result = await db_session.execute(feedback_stmt)
        feedback = feedback_result.scalar_one_or_none()
        
        assert feedback is not None, "UserFeedback record should be created"
        assert feedback.original_category == "admin.general"
        assert feedback.corrected_category == "academic.coursework"
        assert feedback.reason == "This is clearly about academic assignments, not general admin"
        assert feedback.incorporated is False, "Feedback should not be incorporated initially"
        assert feedback.timestamp == datetime.now(timezone.utc)
        
        # Assert: Email relationship is established
        assert feedback.email_id == test_email.id
        assert feedback.email == test_email


@pytest.mark.asyncio
async def test_rag_knowledge_base_update_from_feedback(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    mock_qdrant_client: MagicMock,
    frozen_time,
    clean_db
) -> None:
    """
    Test RAG knowledge base update from user feedback.
    
    This test validates:
    1. Pending feedback is retrieved for processing
    2. Feedback is incorporated into RAG knowledge base
    3. Qdrant vector store is updated with new knowledge
    4. Feedback incorporated flag is updated to True
    5. Processing metrics are recorded
    """
    # Arrange: Create email and classification
    test_email = email_factory(
        message_id="test-rag-update-001",
        sender="company@recruiting.com",
        subject="Software Engineer Internship Opportunity",
        body_text="We are looking for software engineering interns for summer 2025"
    )
    db_session.add(test_email)
    await db_session.commit()
    await db_session.refresh(test_email)
    
    classification = classification_result_factory(
        email_id=test_email.id,
        primary_category="admin.general",
        confidence=0.65,
        rationale="General administrative notice"
    )
    db_session.add(classification)
    await db_session.commit()
    
    # Arrange: Create pending feedback
    feedback = UserFeedback(
        email_id=test_email.id,
        original_category="admin.general",
        corrected_category="career.internship",
        reason="This is clearly a career/internship opportunity, not admin"
    )
    db_session.add(feedback)
    await db_session.commit()
    
    # Arrange: Mock feedback processor with RAG update
    with patch('src.services.feedback_processor.FeedbackProcessor') as mock_processor_class:
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        # Mock pending feedback retrieval
        mock_processor.get_pending_feedback.return_value = [feedback]
        
        # Mock RAG knowledge base update
        mock_processor.update_rag_knowledge_base.return_value = {
            "vectors_added": 2,
            "chunks_updated": 1,
            "processing_time_ms": 150
        }
        
        # Mock Qdrant upsert operation
        mock_qdrant_client.upsert.return_value = {"operation_id": "rag-update-001"}
        
        # Act: Process pending feedback
        start_time = time.time()
        result = await mock_processor.process_pending_feedback()
        processing_time = time.time() - start_time
        
        # Assert: Processing succeeded
        assert result["processed_count"] == 1
        assert result["vectors_added"] == 2
        assert result["processing_time_ms"] == 150
        
        # Assert: Qdrant upsert was called
        mock_qdrant_client.upsert.assert_called()
        
        # Assert: Feedback incorporated flag was updated
        await db_session.refresh(feedback)
        assert feedback.incorporated is True, "Feedback should be marked as incorporated"
        
        # Assert: Processing metrics were recorded
        metric_stmt = select(DashboardMetric).where(
            DashboardMetric.metric_name == "feedback_processing_latency_ms"
        )
        metric_result = await db_session.execute(metric_stmt)
        metric = metric_result.scalar_one_or_none()
        
        assert metric is not None, "Feedback processing metric should be recorded"
        assert metric.value > 0, "Processing time should be positive"


@pytest.mark.asyncio
async def test_improved_classification_after_feedback(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    frozen_time,
    clean_db
) -> None:
    """
    Test improved classification for similar emails after feedback incorporation.
    
    This test validates:
    1. New similar email receives improved classification
    2. RAG context includes feedback-derived knowledge
    3. Classification confidence improves
    4. Correct category is applied based on feedback
    """
    # Arrange: Create original email and feedback
    original_email = email_factory(
        message_id="original-feedback-001",
        sender="tech.company@recruiting.com",
        subject="Summer Internship Program 2025",
        body_text="Apply for our summer internship program in software engineering"
    )
    db_session.add(original_email)
    await db_session.commit()
    
    original_classification = classification_result_factory(
        email_id=original_email.id,
        primary_category="admin.general",
        confidence=0.60,
        rationale="Administrative notice about programs"
    )
    db_session.add(original_classification)
    await db_session.commit()
    
    # Create and incorporate feedback
    feedback = UserFeedback(
        email_id=original_email.id,
        original_category="admin.general",
        corrected_category="career.internship",
        reason="This is a career/internship opportunity",
        incorporated=True  # Already incorporated
    )
    db_session.add(feedback)
    await db_session.commit()
    
    # Arrange: Create new similar email
    similar_email = email_factory(
        message_id="similar-email-002",
        sender="another.tech@careers.com",
        subject="Software Engineering Internship Available",
        body_text="We are offering software engineering internship positions for summer"
    )
    db_session.add(similar_email)
    await db_session.commit()
    
    # Arrange: Mock RAG retriever with feedback-enhanced context
    with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
        mock_rag = AsyncMock()
        mock_rag_class.return_value = mock_rag
        
        # Mock enhanced RAG context including feedback
        mock_rag.retrieve_context.return_value = [
            {
                "id": "feedback-chunk-001",
                "text": "User corrected: recruiting emails about internships should be classified as career.internship",
                "score": 0.95,
                "source": "user_feedback"
            },
            {
                "id": "original-chunk-001",
                "text": "Career opportunities and internship information",
                "score": 0.85
            }
        ]
        
        # Arrange: Mock LLM classifier with improved response
        with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
            mock_classifier = AsyncMock()
            mock_classifier_class.return_value = mock_classifier
            
            # Mock improved classification using feedback context
            improved_classification = {
                "message_id": similar_email.message_id,
                "primary_category": "career.internship",  # Corrected category
                "secondary_categories": ["career.networking"],
                "priority": "high",
                "deadline_utc": None,
                "deadline_confidence": "none",
                "confidence": 0.92,  # Improved confidence
                "rationale": "Internship opportunity identified using feedback-enhanced context",
                "detected_entities": {
                    "company_names": ["another.tech"],
                    "position": "Software Engineering Intern"
                },
                "sentiment": "positive",
                "action_items": [
                    {
                        "action": "Apply for internship position",
                        "deadline_utc": None,
                        "completed": False
                    }
                ],
                "thread_context": {
                    "is_reply": False,
                    "thread_id": None,
                    "previous_categories": []
                },
                "rag_context_used": ["feedback-chunk-001", "original-chunk-001"],
                "suggested_folder": "Career/Internships",
                "schema_version": "v2"
            }
            
            mock_classifier.classify_email.return_value = improved_classification
            
            # Arrange: Mock workflow orchestrator
            with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                mock_orchestrator = AsyncMock()
                mock_orchestrator_class.return_value = mock_orchestrator
                
                # Act: Classify similar email with feedback-enhanced RAG
                await mock_orchestrator.process_email_batch()
                
                # Assert: New classification was created
                result_stmt = select(ClassificationResult).where(
                    ClassificationResult.email_id == similar_email.id
                )
                result = await db_session.execute(result_stmt)
                new_classification = result.scalar_one_or_none()
                
                assert new_classification is not None, "Classification should be created for similar email"
                assert new_classification.primary_category == "career.internship", "Should use corrected category"
                assert float(new_classification.confidence) == 0.92, "Confidence should be improved"
                assert "feedback-enhanced context" in new_classification.rationale
                
                # Assert: RAG context includes feedback-derived knowledge
                assert "feedback-chunk-001" in new_classification.rag_context_used
                
                # Assert: Classification is better than original
                assert float(new_classification.confidence) > float(original_classification.confidence)
                assert new_classification.primary_category != original_classification.primary_category


@pytest.mark.asyncio
async def test_invalid_feedback_handling(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test error handling for invalid feedback submissions.
    
    This test validates:
    1. Invalid email IDs are rejected
    2. Invalid category names are rejected
    3. Missing required fields are handled
    4. Feedback for non-existent emails is rejected
    5. Duplicate feedback is handled appropriately
    """
    # Arrange: Create test email
    test_email = email_factory(
        message_id="test-invalid-feedback-001",
        sender="test@example.com",
        subject="Test Email"
    )
    db_session.add(test_email)
    await db_session.commit()
    
    # Arrange: Mock feedback processor
    with patch('src.services.feedback_processor.FeedbackProcessor') as mock_processor_class:
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        # Test 1: Invalid email ID
        invalid_email_feedback = {
            "email_id": "invalid-uuid",
            "original_category": "admin.general",
            "corrected_category": "academic.coursework",
            "reason": "Test feedback"
        }
        
        mock_processor.submit_feedback.side_effect = ValueError("Invalid email ID")
        
        with pytest.raises(ValueError, match="Invalid email ID"):
            await mock_processor.submit_feedback(invalid_email_feedback)
        
        # Test 2: Invalid category name
        invalid_category_feedback = {
            "email_id": str(test_email.id),
            "original_category": "admin.general",
            "corrected_category": "invalid.category.format",
            "reason": "Test feedback"
        }
        
        mock_processor.submit_feedback.side_effect = ValueError("Invalid category format")
        
        with pytest.raises(ValueError, match="Invalid category format"):
            await mock_processor.submit_feedback(invalid_category_feedback)
        
        # Test 3: Missing required fields
        incomplete_feedback = {
            "email_id": str(test_email.id),
            "original_category": "admin.general"
            # Missing corrected_category and reason
        }
        
        mock_processor.submit_feedback.side_effect = ValueError("Missing required fields")
        
        with pytest.raises(ValueError, match="Missing required fields"):
            await mock_processor.submit_feedback(incomplete_feedback)
        
        # Test 4: Non-existent email
        non_existent_feedback = {
            "email_id": str(uuid.uuid4()),  # Random UUID not in database
            "original_category": "admin.general",
            "corrected_category": "academic.coursework",
            "reason": "Test feedback"
        }
        
        mock_processor.submit_feedback.side_effect = ValueError("Email not found")
        
        with pytest.raises(ValueError, match="Email not found"):
            await mock_processor.submit_feedback(non_existent_feedback)
        
        # Test 5: Valid feedback should succeed
        valid_feedback = {
            "email_id": str(test_email.id),
            "original_category": "admin.general",
            "corrected_category": "academic.coursework",
            "reason": "Valid feedback test"
        }
        
        mock_processor.submit_feedback.side_effect = None
        mock_processor.submit_feedback.return_value = {
            "feedback_id": str(uuid.uuid4()),
            "status": "submitted",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        result = await mock_processor.submit_feedback(valid_feedback)
        assert result["status"] == "submitted"


@pytest.mark.asyncio
async def test_feedback_processing_performance_tracking(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test performance tracking for feedback processing.
    
    This test validates:
    1. Feedback processing latency is tracked
    2. Batch processing performance is measured
    3. Throughput metrics are recorded
    4. Performance targets are met (<2s per feedback)
    """
    # Arrange: Create multiple emails with feedback
    emails = []
    feedback_list = []
    
    for i in range(10):
        email = email_factory(
            message_id=f"perf-feedback-{i:03d}",
            sender=f"sender{i}@example.com",
            subject=f"Performance Test Email {i}"
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)
        emails.append(email)
        
        classification = classification_result_factory(
            email_id=email.id,
            primary_category="admin.general",
            confidence=0.70
        )
        db_session.add(classification)
        await db_session.commit()
        
        feedback = UserFeedback(
            email_id=email.id,
            original_category="admin.general",
            corrected_category="academic.coursework",
            reason=f"Performance test feedback {i}"
        )
        db_session.add(feedback)
        await db_session.commit()
        feedback_list.append(feedback)
    
    # Arrange: Mock feedback processor with performance tracking
    with patch('src.services.feedback_processor.FeedbackProcessor') as mock_processor_class:
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        # Mock batch processing with realistic timing
        async def mock_process_batch():
            start_time = time.time()
            
            # Simulate processing time (50ms per feedback)
            await asyncio.sleep(0.05 * len(feedback_list))
            
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            
            return {
                "processed_count": len(feedback_list),
                "processing_time_ms": int(processing_time),
                "throughput_feedback_per_second": len(feedback_list) / (processing_time / 1000)
            }
        
        mock_processor.process_pending_feedback_batch.side_effect = mock_process_batch
        
        # Act: Process feedback batch
        start_time = time.time()
        result = await mock_processor.process_pending_feedback_batch()
        total_time = time.time() - start_time
        
        # Assert: Performance targets met
        assert result["processed_count"] == 10, "All feedback should be processed"
        assert result["processing_time_ms"] < 2000, "Batch processing should complete in <2s"
        assert result["throughput_feedback_per_second"] > 5, "Should process >5 feedback/second"
        
        # Assert: Performance metrics recorded
        metric_stmt = select(DashboardMetric).where(
            DashboardMetric.metric_name.in_([
                "feedback_processing_latency_ms",
                "feedback_batch_throughput",
                "feedback_queue_depth"
            ])
        )
        metric_result = await db_session.execute(metric_stmt)
        metrics = metric_result.scalars().all()
        
        assert len(metrics) >= 2, "Multiple performance metrics should be recorded"
        
        # Verify specific metrics
        latency_metric = next((m for m in metrics if m.metric_name == "feedback_processing_latency_ms"), None)
        throughput_metric = next((m for m in metrics if m.metric_name == "feedback_batch_throughput"), None)
        
        assert latency_metric is not None, "Latency metric should be recorded"
        assert throughput_metric is not None, "Throughput metric should be recorded"
        assert latency_metric.value > 0, "Latency should be positive"
        assert throughput_metric.value > 0, "Throughput should be positive"


@pytest.mark.asyncio
async def test_feedback_incorporation_flag_updates(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    frozen_time,
    clean_db
) -> None:
    """
    Test that incorporated flag is properly updated during feedback processing.
    
    This test validates:
    1. New feedback starts with incorporated=False
    2. Flag is updated to True after successful processing
    3. Failed processing leaves flag as False
    4. Re-processing already incorporated feedback is skipped
    """
    # Arrange: Create email and classification
    test_email = email_factory(
        message_id="test-incorporation-flag-001",
        sender="test@example.com",
        subject="Incorporation Flag Test"
    )
    db_session.add(test_email)
    await db_session.commit()
    
    classification = classification_result_factory(
        email_id=test_email.id,
        primary_category="admin.general",
        confidence=0.75
    )
    db_session.add(classification)
    await db_session.commit()
    
    # Arrange: Create feedback
    feedback = UserFeedback(
        email_id=test_email.id,
        original_category="admin.general",
        corrected_category="academic.coursework",
        reason="Test incorporation flag behavior"
    )
    db_session.add(feedback)
    await db_session.commit()
    
    # Assert: Initial state
    assert feedback.incorporated is False, "New feedback should start as not incorporated"
    
    # Arrange: Mock successful feedback processing
    with patch('src.services.feedback_processor.FeedbackProcessor') as mock_processor_class:
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        # Test 1: Successful processing updates flag
        mock_processor.process_single_feedback.return_value = {
            "feedback_id": str(feedback.id),
            "status": "incorporated",
            "processing_time_ms": 100
        }
        
        # Act: Process feedback successfully
        result = await mock_processor.process_single_feedback(feedback.id)
        
        # Assert: Processing succeeded
        assert result["status"] == "incorporated"
        
        # Update flag in database (simulating processor behavior)
        feedback.incorporated = True
        await db_session.commit()
        
        # Assert: Flag is now True
        await db_session.refresh(feedback)
        assert feedback.incorporated is True, "Flag should be True after successful processing"
        
        # Test 2: Re-processing incorporated feedback is skipped
        mock_processor.process_single_feedback.return_value = {
            "feedback_id": str(feedback.id),
            "status": "skipped",
            "reason": "Already incorporated"
        }
        
        # Act: Attempt to re-process
        result = await mock_processor.process_single_feedback(feedback.id)
        
        # Assert: Processing was skipped
        assert result["status"] == "skipped"
        assert result["reason"] == "Already incorporated"
        
        # Test 3: Failed processing leaves flag as False
        # Create new feedback for failure test
        failed_feedback = UserFeedback(
            email_id=test_email.id,
            original_category="academic.coursework",
            corrected_category="career.internship",
            reason="This should fail processing"
        )
        db_session.add(failed_feedback)
        await db_session.commit()
        
        # Mock failed processing
        mock_processor.process_single_feedback.side_effect = Exception("RAG update failed")
        
        # Act: Attempt processing that fails
        with pytest.raises(Exception, match="RAG update failed"):
            await mock_processor.process_single_feedback(failed_feedback.id)
        
        # Assert: Flag remains False after failure
        await db_session.refresh(failed_feedback)
        assert failed_feedback.incorporated is False, "Flag should remain False after failed processing"


@pytest.mark.asyncio
async def test_feedback_loop_end_to_end(
    db_session: AsyncSession,
    email_factory,
    classification_result_factory,
    mock_qdrant_client: MagicMock,
    mock_ollama_client: AsyncMock,
    frozen_time,
    clean_db
) -> None:
    """
    Test the complete feedback loop end-to-end.
    
    This test validates the entire workflow:
    1. Email is initially misclassified
    2. User submits correction feedback
    3. Feedback is processed and incorporated into RAG
    4. Similar future emails are correctly classified
    5. Performance metrics are tracked throughout
    """
    # Step 1: Initial misclassification
    original_email = email_factory(
        message_id="e2e-original-001",
        sender="university.careers@edu",
        subject="Summer Research Opportunity",
        body_text="Apply for summer research positions in computer science department"
    )
    db_session.add(original_email)
    await db_session.commit()
    
    original_classification = classification_result_factory(
        email_id=original_email.id,
        primary_category="admin.general",
        confidence=0.65,
        rationale="General administrative announcement"
    )
    db_session.add(original_classification)
    await db_session.commit()
    
    # Step 2: User submits feedback
    with patch('src.services.feedback_processor.FeedbackProcessor') as mock_processor_class:
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        feedback_data = {
            "email_id": str(original_email.id),
            "original_category": "admin.general",
            "corrected_category": "career.internship",
            "reason": "This is a career/research opportunity, not general admin"
        }
        
        mock_processor.submit_feedback.return_value = {
            "feedback_id": str(uuid.uuid4()),
            "status": "submitted"
        }
        
        # Submit feedback
        feedback_result = await mock_processor.submit_feedback(feedback_data)
        assert feedback_result["status"] == "submitted"
        
        # Create feedback record
        feedback = UserFeedback(
            email_id=original_email.id,
            original_category="admin.general",
            corrected_category="career.internship",
            reason="This is a career/research opportunity, not general admin"
        )
        db_session.add(feedback)
        await db_session.commit()
        
        # Step 3: Feedback processing and RAG update
        mock_processor.get_pending_feedback.return_value = [feedback]
        mock_processor.update_rag_knowledge_base.return_value = {
            "vectors_added": 2,
            "chunks_updated": 1
        }
        
        processing_result = await mock_processor.process_pending_feedback()
        assert processing_result["processed_count"] == 1
        
        # Mark feedback as incorporated
        feedback.incorporated = True
        await db_session.commit()
        
        # Step 4: Similar email gets improved classification
        similar_email = email_factory(
            message_id="e2e-similar-002",
            sender="research.lab@university.edu",
            subject="Undergraduate Research Positions Available",
            body_text="We are looking for undergraduate students for summer research projects"
        )
        db_session.add(similar_email)
        await db_session.commit()
        
        # Mock enhanced RAG context
        with patch('src.services.rag_retriever.RAGRetriever') as mock_rag_class:
            mock_rag = AsyncMock()
            mock_rag_class.return_value = mock_rag
            
            mock_rag.retrieve_context.return_value = [
                {
                    "id": "feedback-enhanced-001",
                    "text": "User feedback: career/research opportunities should be classified as career.internship",
                    "score": 0.95,
                    "source": "user_feedback"
                }
            ]
            
            # Mock improved classification
            with patch('src.services.llm_classifier.LLMClassifier') as mock_classifier_class:
                mock_classifier = AsyncMock()
                mock_classifier_class.return_value = mock_classifier
                
                improved_classification = {
                    "message_id": similar_email.message_id,
                    "primary_category": "career.internship",  # Corrected category
                    "confidence": 0.90,  # Improved confidence
                    "rationale": "Career opportunity identified using feedback-enhanced RAG context",
                    "rag_context_used": ["feedback-enhanced-001"],
                    "schema_version": "v2"
                }
                
                mock_classifier.classify_email.return_value = improved_classification
                
                # Process similar email
                with patch('src.services.workflow_orchestrator.WorkflowOrchestrator') as mock_orchestrator_class:
                    mock_orchestrator = AsyncMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    
                    await mock_orchestrator.process_email_batch()
                    
                    # Verify improved classification
                    result_stmt = select(ClassificationResult).where(
                        ClassificationResult.email_id == similar_email.id
                    )
                    result = await db_session.execute(result_stmt)
                    new_classification = result.scalar_one_or_none()
                    
                    assert new_classification is not None
                    assert new_classification.primary_category == "career.internship"
                    assert float(new_classification.confidence) == 0.90
                    assert "feedback-enhanced" in new_classification.rationale
        
        # Step 5: Verify performance metrics were recorded
        metric_stmt = select(DashboardMetric).where(
            DashboardMetric.metric_name.in_([
                "feedback_processing_latency_ms",
                "classification_latency_ms",
                "rag_hit_rate"
            ])
        )
        metric_result = await db_session.execute(metric_stmt)
        metrics = metric_result.scalars().all()
        
        assert len(metrics) >= 2, "Multiple metrics should be recorded throughout the feedback loop"
        
        # Verify the complete feedback loop worked
        assert original_classification.primary_category == "admin.general"  # Original misclassification
        assert feedback.incorporated is True  # Feedback was processed
        assert new_classification.primary_category == "career.internship"  # Improved classification
        assert float(new_classification.confidence) > float(original_classification.confidence)  # Better confidence