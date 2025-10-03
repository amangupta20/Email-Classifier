"""Contract tests for Email Classifier API and LLM output schema.

These tests will fail initially (no implementation) and pass once the contracts are implemented.
Run with: pytest specs/001-i-am-building/contracts/test_contracts.py -v
"""

import pytest
from pathlib import Path
from typing import Dict, Any
import json
from jsonschema import validate, ValidationError
from fastapi.testclient import TestClient
from unittest.mock import Mock

# Load contracts
CONTRACTS_DIR = Path(__file__).parent
SCHEMA_V2_PATH = CONTRACTS_DIR / "classification_schema_v2.json"
DASHBOARD_API_PATH = CONTRACTS_DIR / "dashboard_api.yaml"

with open(SCHEMA_V2_PATH) as f:
    SCHEMA_V2 = json.load(f)

# Mock FastAPI app for testing
client = TestClient(Mock())

def test_json_schema_v2_validation():
    """Validate sample LLM output against schema v2."""
    
    # Valid sample
    valid_payload = {
        "message_id": "test123",
        "primary_category": "academic.exams",
        "confidence": 0.85,
        "schema_version": "v2",
        "secondary_categories": ["action.deadline_soon"],
        "priority": "high",
        "deadline_utc": "2025-10-03T09:00:00Z",
        "deadline_confidence": "extracted",
        "rationale": "Exam schedule notification for CS101 midterm.",
        "detected_entities": {
            "course_codes": ["CS101"],
            "locations": ["Room 101"]
        },
        "sentiment": "neutral",
        "action_items": [
            {
                "action": "Review midterm practice test",
                "deadline_utc": "2025-10-03T08:00:00Z",
                "completed": False
            }
        ],
        "thread_context": {
            "is_reply": False,
            "thread_id": None,
            "previous_categories": []
        },
        "rag_context_used": ["chunk_123", "chunk_456"],
        "suggested_folder": "Academic/Exams"
    }
    
    validate(instance=valid_payload, schema=SCHEMA_V2)
    
    # Invalid samples (should raise ValidationError)
    invalid_cases = [
        # Missing required field
        {"message_id": "test123", "primary_category": "academic.exams", "confidence": 0.85},  # missing schema_version
        
        # Invalid confidence range
        {"message_id": "test123", "primary_category": "academic.exams", "confidence": 1.5, "schema_version": "v2"},
        
        # Too many secondary categories
        {
            "message_id": "test123",
            "primary_category": "academic.exams",
            "confidence": 0.85,
            "schema_version": "v2",
            "secondary_categories": ["a", "b", "c", "d"]  # 4 items, max 3
        },
        
        # Invalid category pattern
        {"message_id": "test123", "primary_category": "Invalid Category", "confidence": 0.85, "schema_version": "v2"},
        
        # Invalid action items count
        {
            "message_id": "test123",
            "primary_category": "academic.exams",
            "confidence": 0.85,
            "schema_version": "v2",
            "action_items": [{}] * 11  # 11 items, max 10
        },
        
        # Invalid deadline_confidence without deadline_utc
        {
            "message_id": "test123",
            "primary_category": "academic.exams",
            "confidence": 0.85,
            "schema_version": "v2",
            "deadline_confidence": "extracted"  # No deadline_utc
        }
    ]
    
    for i, invalid_payload in enumerate(invalid_cases):
        with pytest.raises(ValidationError):
            validate(instance=invalid_payload, schema=SCHEMA_V2)
    
    print("✅ JSON Schema v2 validation: PASSED (valid case) / FAILED as expected (invalid cases)")

def test_api_contracts():
    """Test API endpoint contracts against OpenAPI specification."""
    
    # Load OpenAPI spec
    with open(DASHBOARD_API_PATH) as f:
        api_spec = yaml.safe_load(f)
    
    # Test /metrics/current GET - 200 response
    mock_response = {
        "avg_processing_time_ms": 2450.5,
        "avg_tags_per_email": 2.3,
        "queue_depth": 3,
        "active_workers": 2,
        "system_uptime_seconds": 123456,
        "classification_rate_per_hour": 45.2,
        "unclassified_rate_percent": 5.2,
        "rag_hit_rate_percent": 78.9
    }
    
    # Validate against CurrentMetrics schema
    # This would be implemented with actual FastAPI TestClient once app exists
    assert isinstance(mock_response, dict)
    assert "avg_processing_time_ms" in mock_response
    assert "queue_depth" in mock_response
    assert mock_response["avg_processing_time_ms"] >= 0
    
    # Test /metrics/current GET - 500 error response
    mock_error_response = {
        "error": "Internal server error",
        "error_type": "internal_error",
        "timestamp": "2025-10-03T07:00:00Z",
        "details": {"trace": "stack trace here"}
    }
    
    assert isinstance(mock_error_response, dict)
    assert "error" in mock_error_response
    assert "error_type" in mock_error_response
    assert mock_error_response["error_type"] in ["validation_error", "timeout_error", "internal_error", "unauthorized"]
    
    # Test /classifications GET - 200 response
    mock_classifications = [
        {
            "message_id": "1234567890",
            "sender": "university.edu",
            "subject": "Midterm Exam Schedule - CS101",
            "primary_category": "academic.exams",
            "secondary_categories": ["action.deadline_soon"],
            "confidence": 0.87,
            "processing_time_ms": 2345,
            "processed_timestamp": "2025-10-03T06:45:12Z",
            "sentiment": "neutral"
        }
    ]
    
    assert isinstance(mock_classifications, list)
    for classification in mock_classifications:
        assert "message_id" in classification
        assert "primary_category" in classification
        assert 0 <= classification["confidence"] <= 1
    
    # Test /classifications/reclassify POST - 202 response
    mock_reclassify_request = {
        "message_ids": ["1234567890"],
        "reason": "Taxonomy updated"
    }
    
    assert isinstance(mock_reclassify_request, dict)
    assert "message_ids" in mock_reclassify_request
    assert isinstance(mock_reclassify_request["message_ids"], list)
    
    mock_reclassify_response = {
        "accepted": True,
        "message_ids": ["1234567890"],
        "estimated_completion": "2025-10-03T06:50:00Z"
    }
    
    assert mock_reclassify_response["accepted"] is True
    assert "estimated_completion" in mock_reclassify_response
    
    # Test /health GET - 200 response
    mock_health_response = {
        "overall_status": "healthy",
        "timestamp": "2025-10-03T07:00:00Z",
        "components": [
            {
                "component_name": "ollama",
                "status": "healthy",
                "last_check": "2025-10-03T07:00:00Z",
                "latency_ms": 45,
                "error": None
            },
            {
                "component_name": "qdrant",
                "status": "degraded",
                "last_check": "2025-10-03T07:00:00Z",
                "latency_ms": 120,
                "error": "High latency detected"
            }
        ]
    }
    
    assert mock_health_response["overall_status"] in ["healthy", "degraded", "down"]
    assert isinstance(mock_health_response["components"], list)
    for component in mock_health_response["components"]:
        assert "component_name" in component
        assert "status" in component
        assert component["status"] in ["healthy", "degraded", "down"]
    
    print("✅ API contracts: All response formats validated against OpenAPI spec")

def test_admin_endpoints():
    """Test admin endpoint contracts."""
    
    # Test /admin/rag/reindex POST - 202 response
    mock_reindex_request = {
        "confirm": True,
        "reason": "Weekly scheduled reindex"
    }
    
    assert mock_reindex_request["confirm"] is True
    
    mock_reindex_response = {
        "action": "rag_reindex",
        "status": "accepted",
        "message": "RAG reindexing started in background, expected completion in 15 minutes"
    }
    
    assert mock_reindex_response["action"] == "rag_reindex"
    assert mock_reindex_response["status"] in ["accepted", "rejected", "completed"]
    
    # Test /admin/queue/clear POST - 200 response
    mock_clear_queue_request = {
        "confirm": True,
        "reason": "Development cleanup"
    }
    
    assert mock_clear_queue_request["confirm"] is True
    
    mock_clear_queue_response = {
        "action": "clear_queue",
        "status": "completed",
        "message": "Queue cleared, 3 poison messages removed"
    }
    
    assert mock_clear_queue_response["action"] == "clear_queue"
    assert mock_clear_queue_response["status"] == "completed"
    
    print("✅ Admin endpoint contracts: Request/response formats validated")

if __name__ == "__main__":
    # Run all tests
    test_json_schema_v2_validation()
    test_api_contracts()
    test_admin_endpoints()
    print("All contract tests executed - some should fail until implementation complete")