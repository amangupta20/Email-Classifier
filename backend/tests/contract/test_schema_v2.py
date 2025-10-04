"""
Contract test for JSON schema v2 validation.
This test ensures that the classification output conforms to the expected schema v2.
Based on classification_schema_v2.json from specs/001-i-am-building/contracts/classification_schema_v2.json
"""
import json
import pytest
from jsonschema import validate, ValidationError
from pathlib import Path


@pytest.fixture
def classification_schema_v2():
    """Load the classification schema v2 from the contracts directory."""
    schema_path = Path(__file__).parent / "../../../specs/001-i-am-building/contracts/classification_schema_v2.json"
    with open(schema_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def valid_classification_sample():
    """A valid sample classification output that conforms to schema v2."""
    return {
        "message_id": "test-message-123",
        "primary_category": "academic.assignments",
        "secondary_categories": ["academic.group_project", "academic.due_soon"],
        "priority": "high",
        "deadline_utc": "2023-12-15T23:59:59Z",
        "deadline_confidence": "extracted",
        "confidence": 0.85,
        "rationale": "Contains assignment deadline with explicit due date",
        "detected_entities": {
            "course_codes": ["CS101"],
            "company_names": [],
            "event_names": ["Final Project Deadline"],
            "professor_names": ["Dr. Smith"],
            "amounts": [],
            "locations": [],
            "phone_numbers": [],
            "urls": ["https://lms.example.edu/assignments/123"]
        },
        "sentiment": "urgent",
        "action_items": [
            {
                "action": "Submit final project",
                "deadline_utc": "2023-12-15T23:59:59Z",
                "completed": False
            }
        ],
        "thread_context": {
            "is_reply": True,
            "thread_id": "thread-456",
            "previous_categories": ["academic.coursework"]
        },
        "rag_context_used": ["kb_chunk_001", "kb_chunk_002"],
        "suggested_folder": "Academic/CS101",
        "schema_version": "v2"
    }


@pytest.fixture
def minimal_valid_classification():
    """A minimal valid classification with only required fields."""
    return {
        "message_id": "minimal-test-456",
        "primary_category": "career.opportunities",
        "confidence": 0.7,
        "schema_version": "v2"
    }


def test_schema_v2_loads_successfully(classification_schema_v2):
    """Test that the schema v2 can be loaded without errors."""
    assert classification_schema_v2 is not None
    assert "$schema" in classification_schema_v2
    assert classification_schema_v2["schema_version"] == "v2" if "schema_version" in classification_schema_v2 else True
    assert classification_schema_v2["type"] == "object"


def test_valid_classification_passes_validation(classification_schema_v2, valid_classification_sample):
    """Test that a valid classification sample passes schema validation."""
    # This should not raise any exception
    validate(instance=valid_classification_sample, schema=classification_schema_v2)


def test_minimal_valid_classification_passes_validation(classification_schema_v2, minimal_valid_classification):
    """Test that a minimal valid classification passes schema validation."""
    validate(instance=minimal_valid_classification, schema=classification_schema_v2)


def test_classification_fails_without_required_fields(classification_schema_v2):
    """Test that classifications fail validation when missing required fields."""
    # Test missing message_id
    invalid_classification = {
        "primary_category": "academic.assignments",
        "confidence": 0.85,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)

    # Test missing primary_category
    invalid_classification = {
        "message_id": "test-789",
        "confidence": 0.85,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)

    # Test missing confidence
    invalid_classification = {
        "message_id": "test-789",
        "primary_category": "academic.assignments",
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)

    # Test missing schema_version
    invalid_classification = {
        "message_id": "test-789",
        "primary_category": "academic.assignments",
        "confidence": 0.85
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)


def test_classification_fails_with_invalid_values(classification_schema_v2):
    """Test that classifications fail validation with invalid field values."""
    # Test invalid primary_category format (doesn't match pattern)
    invalid_classification = {
        "message_id": "test-invalid-001",
        "primary_category": "invalid-category-format",  # Should be "parent.child"
        "confidence": 0.85,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)

    # Test confidence below 0
    invalid_classification = {
        "message_id": "test-invalid-002",
        "primary_category": "academic.assignments",
        "confidence": -0.1,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)

    # Test confidence above 1
    invalid_classification = {
        "message_id": "test-invalid-003",
        "primary_category": "academic.assignments",
        "confidence": 1.1,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)

    # Test too many secondary categories (>3)
    invalid_classification = {
        "message_id": "test-invalid-004",
        "primary_category": "academic.assignments",
        "secondary_categories": ["cat1", "cat2", "cat3", "cat4", "cat5"],  # More than 3
        "confidence": 0.8,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)


def test_schema_disallows_additional_properties(classification_schema_v2):
    """Test that the schema rejects objects with additional properties."""
    invalid_classification = {
        "message_id": "test-extra-001",
        "primary_category": "academic.assignments",
        "confidence": 0.85,
        "schema_version": "v2",
        "extra_property": "this_should_not_be_allowed"  # This should cause validation to fail
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)


def test_secondary_categories_pattern_validation(classification_schema_v2):
    """Test that secondary categories follow the correct pattern."""
    # Valid secondary categories
    valid_classification = {
        "message_id": "test-secondary-valid",
        "primary_category": "academic.assignments",
        "secondary_categories": ["academic.due_soon", "academic.group_project"],
        "confidence": 0.85,
        "schema_version": "v2"
    }
    validate(instance=valid_classification, schema=classification_schema_v2)
    
    # Invalid secondary category format
    invalid_classification = {
        "message_id": "test-secondary-invalid",
        "primary_category": "academic.assignments",
        "secondary_categories": ["invalid-format"],
        "confidence": 0.85,
        "schema_version": "v2"
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)


def test_schema_version_const_validation(classification_schema_v2):
    """Test that schema_version must be exactly 'v2'."""
    # Valid version
    valid_classification = {
        "message_id": "test-version-valid",
        "primary_category": "academic.assignments",
        "confidence": 0.85,
        "schema_version": "v2"
    }
    validate(instance=valid_classification, schema=classification_schema_v2)
    
    # Invalid version
    invalid_classification = {
        "message_id": "test-version-invalid",
        "primary_category": "academic.assignments",
        "confidence": 0.85,
        "schema_version": "v1"  # This should fail
    }
    
    with pytest.raises(ValidationError):
        validate(instance=invalid_classification, schema=classification_schema_v2)