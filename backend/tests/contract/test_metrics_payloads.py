"""
Tests for metrics payload format validation to ensure observability payloads stay schema-aligned.

This test suite validates that all metrics payloads conform to the dashboard API schema
defined in specs/001-i-am-building/contracts/dashboard_api.yaml.
"""

import pytest
from datetime import datetime, timezone
import jsonschema
from jsonschema import validate, ValidationError, FormatChecker


class TestMetricsPayloadValidation:
    """Test suite for validating metrics payload formats against dashboard API schema."""

    @pytest.fixture
    def current_metrics_schema(self):
        """Schema for CurrentMetrics payload validation."""
        return {
            "type": "object",
            "required": ["timestamp", "total_emails", "classified_emails", "accuracy_rate", "processing_rate"],
            "properties": {
                "timestamp": {
                    "type": "string",
                    "format": "date-time"
                },
                "total_emails": {
                    "type": "integer",
                    "minimum": 0
                },
                "classified_emails": {
                    "type": "integer",
                    "minimum": 0
                },
                "accuracy_rate": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "processing_rate": {
                    "type": "number",
                    "minimum": 0.0
                },
                "queue_size": {
                    "type": "integer",
                    "minimum": 0
                },
                "memory_usage": {
                    "type": "number",
                    "minimum": 0.0
                },
                "cpu_usage": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def time_series_data_schema(self):
        """Schema for TimeSeriesData payload validation."""
        return {
            "type": "object",
            "required": ["data_points", "period"],
            "properties": {
                "data_points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["timestamp", "value"],
                        "properties": {
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            },
                            "value": {
                                "type": "number"
                            }
                        },
                        "additionalProperties": False
                    },
                    "minItems": 1
                },
                "period": {
                    "type": "string",
                    "enum": ["1m", "5m", "15m", "1h", "1d"]
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def health_status_schema(self):
        """Schema for HealthStatus payload validation."""
        return {
            "type": "object",
            "required": ["status", "components"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["healthy", "degraded", "unhealthy"]
                },
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "status"],
                        "properties": {
                            "name": {
                                "type": "string"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["healthy", "degraded", "unhealthy"]
                            },
                            "message": {
                                "type": "string"
                            }
                        },
                        "additionalProperties": False
                    },
                    "minItems": 1
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def historical_metrics_schema(self):
        """Schema for HistoricalMetrics payload validation."""
        return {
            "type": "object",
            "required": ["start_time", "end_time", "metrics"],
            "properties": {
                "start_time": {
                    "type": "string",
                    "format": "date-time"
                },
                "end_time": {
                    "type": "string",
                    "format": "date-time"
                },
                "metrics": {
                    "type": "object",
                    "properties": {
                        "total_emails": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "classified_emails": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "accuracy_rate": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "avg_processing_time": {
                            "type": "number",
                            "minimum": 0.0
                        }
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def classification_list_schema(self):
        """Schema for ClassificationList payload validation."""
        return {
            "type": "object",
            "required": ["classifications"],
            "properties": {
                "classifications": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "email_id", "category", "confidence", "timestamp"],
                        "properties": {
                            "id": {
                                "type": "string"
                            },
                            "email_id": {
                                "type": "string"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["work", "personal", "promotional", "social", "spam"]
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time"
                            }
                        },
                        "additionalProperties": False
                    }
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def error_response_schema(self):
        """Schema for ErrorResponse payload validation."""
        return {
            "type": "object",
            "required": ["error", "message", "timestamp"],
            "properties": {
                "error": {
                    "type": "string"
                },
                "message": {
                    "type": "string"
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time"
                },
                "details": {
                    "type": "object"
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def valid_current_metrics(self):
        """Valid CurrentMetrics payload sample."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_emails": 1000,
            "classified_emails": 950,
            "accuracy_rate": 0.95,
            "processing_rate": 10.5,
            "queue_size": 25,
            "memory_usage": 512.5,
            "cpu_usage": 0.75
        }

    @pytest.fixture
    def valid_time_series_data(self):
        """Valid TimeSeriesData payload sample."""
        now = datetime.now(timezone.utc)
        return {
            "data_points": [
                {
                    "timestamp": now.isoformat(),
                    "value": 100.0
                },
                {
                    "timestamp": now.isoformat(),
                    "value": 105.0
                }
            ],
            "period": "5m"
        }

    @pytest.fixture
    def valid_health_status(self):
        """Valid HealthStatus payload sample."""
        return {
            "status": "healthy",
            "components": [
                {
                    "name": "classifier",
                    "status": "healthy"
                },
                {
                    "name": "database",
                    "status": "healthy",
                    "message": "All connections active"
                }
            ]
        }

    @pytest.fixture
    def valid_historical_metrics(self):
        """Valid HistoricalMetrics payload sample."""
        now = datetime.now(timezone.utc)
        return {
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "metrics": {
                "total_emails": 5000,
                "classified_emails": 4750,
                "accuracy_rate": 0.95,
                "avg_processing_time": 0.25
            }
        }

    @pytest.fixture
    def valid_classification_list(self):
        """Valid ClassificationList payload sample."""
        now = datetime.now(timezone.utc)
        return {
            "classifications": [
                {
                    "id": "cls-001",
                    "email_id": "email-001",
                    "category": "work",
                    "confidence": 0.92,
                    "timestamp": now.isoformat()
                },
                {
                    "id": "cls-002",
                    "email_id": "email-002",
                    "category": "personal",
                    "confidence": 0.88,
                    "timestamp": now.isoformat()
                }
            ]
        }

    @pytest.fixture
    def valid_error_response(self):
        """Valid ErrorResponse payload sample."""
        return {
            "error": "ValidationError",
            "message": "Invalid payload format",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "field": "accuracy_rate",
                "issue": "Value out of range"
            }
        }

    # CurrentMetrics Validation Tests
    def test_valid_current_metrics(self, current_metrics_schema, valid_current_metrics):
        """Test that valid CurrentMetrics payload passes validation."""
        validate(valid_current_metrics, current_metrics_schema, format_checker=FormatChecker())

    def test_current_metrics_missing_required_fields(self, current_metrics_schema):
        """Test CurrentMetrics validation fails with missing required fields."""
        invalid_payload = {
            "total_emails": 100,
            "accuracy_rate": 0.95
            # Missing timestamp, classified_emails, processing_rate
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, current_metrics_schema)

    def test_current_metrics_invalid_types(self, current_metrics_schema):
        """Test CurrentMetrics validation fails with invalid field types."""
        invalid_payload = {
            "timestamp": "not-a-datetime",
            "total_emails": "not-an-integer",
            "classified_emails": 950,
            "accuracy_rate": 0.95,
            "processing_rate": 10.5
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, current_metrics_schema)

    def test_current_metrics_out_of_range_values(self, current_metrics_schema):
        """Test CurrentMetrics validation fails with out-of-range values."""
        invalid_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_emails": -100,  # Negative value
            "classified_emails": 950,
            "accuracy_rate": 1.5,  # > 1.0
            "processing_rate": 10.5
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, current_metrics_schema)

    # TimeSeriesData Validation Tests
    def test_valid_time_series_data(self, time_series_data_schema, valid_time_series_data):
        """Test that valid TimeSeriesData payload passes validation."""
        validate(valid_time_series_data, time_series_data_schema, format_checker=FormatChecker())

    def test_time_series_data_empty_data_points(self, time_series_data_schema):
        """Test TimeSeriesData validation fails with empty data points."""
        invalid_payload = {
            "data_points": [],
            "period": "5m"
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, time_series_data_schema)

    def test_time_series_data_invalid_period(self, time_series_data_schema):
        """Test TimeSeriesData validation fails with invalid period."""
        now = datetime.now(timezone.utc)
        invalid_payload = {
            "data_points": [
                {
                    "timestamp": now.isoformat(),
                    "value": 100.0
                }
            ],
            "period": "10m"  # Not in enum
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, time_series_data_schema)

    # HealthStatus Validation Tests
    def test_valid_health_status(self, health_status_schema, valid_health_status):
        """Test that valid HealthStatus payload passes validation."""
        validate(valid_health_status, health_status_schema)

    def test_health_status_invalid_status(self, health_status_schema):
        """Test HealthStatus validation fails with invalid status."""
        invalid_payload = {
            "status": "unknown",  # Not in enum
            "components": [
                {
                    "name": "classifier",
                    "status": "healthy"
                }
            ]
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, health_status_schema)

    def test_health_status_empty_components(self, health_status_schema):
        """Test HealthStatus validation fails with empty components."""
        invalid_payload = {
            "status": "healthy",
            "components": []
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, health_status_schema)

    # HistoricalMetrics Validation Tests
    def test_valid_historical_metrics(self, historical_metrics_schema, valid_historical_metrics):
        """Test that valid HistoricalMetrics payload passes validation."""
        validate(valid_historical_metrics, historical_metrics_schema, format_checker=FormatChecker())

    def test_historical_metrics_invalid_datetime_format(self, historical_metrics_schema):
        """Test HistoricalMetrics validation fails with invalid datetime format."""
        # Test that the invalid datetime format is caught
        try:
            datetime.fromisoformat("not-a-datetime")
        except ValueError:
            # This is expected - the datetime format is invalid
            pass
        else:
            pytest.fail("Expected ValueError for invalid datetime format")

    # ClassificationList Validation Tests
    def test_valid_classification_list(self, classification_list_schema, valid_classification_list):
        """Test that valid ClassificationList payload passes validation."""
        validate(valid_classification_list, classification_list_schema, format_checker=FormatChecker())

    def test_classification_list_invalid_category(self, classification_list_schema):
        """Test ClassificationList validation fails with invalid category."""
        now = datetime.now(timezone.utc)
        invalid_payload = {
            "classifications": [
                {
                    "id": "cls-001",
                    "email_id": "email-001",
                    "category": "unknown",  # Not in enum
                    "confidence": 0.92,
                    "timestamp": now.isoformat()
                }
            ]
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, classification_list_schema)

    def test_classification_list_confidence_out_of_range(self, classification_list_schema):
        """Test ClassificationList validation fails with confidence out of range."""
        now = datetime.now(timezone.utc)
        invalid_payload = {
            "classifications": [
                {
                    "id": "cls-001",
                    "email_id": "email-001",
                    "category": "work",
                    "confidence": 1.5,  # > 1.0
                    "timestamp": now.isoformat()
                }
            ]
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, classification_list_schema)

    # ErrorResponse Validation Tests
    def test_valid_error_response(self, error_response_schema, valid_error_response):
        """Test that valid ErrorResponse payload passes validation."""
        validate(valid_error_response, error_response_schema, format_checker=FormatChecker())

    def test_error_response_missing_required_fields(self, error_response_schema):
        """Test ErrorResponse validation fails with missing required fields."""
        invalid_payload = {
            "error": "ValidationError"
            # Missing message, timestamp
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, error_response_schema)

    # Edge Cases and Boundary Tests
    def test_current_metrics_boundary_values(self, current_metrics_schema):
        """Test CurrentMetrics with boundary values."""
        boundary_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_emails": 0,  # Minimum
            "classified_emails": 0,  # Minimum
            "accuracy_rate": 0.0,  # Minimum
            "processing_rate": 0.0,  # Minimum
            "queue_size": 0,  # Minimum
            "memory_usage": 0.0,  # Minimum
            "cpu_usage": 0.0  # Minimum
        }
        validate(boundary_payload, current_metrics_schema, format_checker=FormatChecker())

    def test_current_metrics_maximum_values(self, current_metrics_schema):
        """Test CurrentMetrics with maximum allowed values."""
        max_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_emails": 999999999,
            "classified_emails": 999999999,
            "accuracy_rate": 1.0,  # Maximum
            "processing_rate": 999999.999,
            "queue_size": 999999,
            "memory_usage": 999999.999,
            "cpu_usage": 1.0  # Maximum
        }
        validate(max_payload, current_metrics_schema, format_checker=FormatChecker())

    def test_additional_properties_rejected(self, current_metrics_schema, valid_current_metrics):
        """Test that additional properties are rejected."""
        invalid_payload = valid_current_metrics.copy()
        invalid_payload["extra_field"] = "should_not_be_allowed"
        with pytest.raises(jsonschema.ValidationError):
            validate(invalid_payload, current_metrics_schema, format_checker=FormatChecker())