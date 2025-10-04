"""
SQLAlchemy models for the Email Classifier application.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from sqlalchemy import (
    UUID, TEXT, TIMESTAMP, ARRAY, NUMERIC, BOOLEAN, INTEGER, LargeBinary,
    Column, String, ForeignKey, CheckConstraint, Index, UniqueConstraint,
    text, func, FetchedValue, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID, JSONB as PostgreSQLJSONB

from . import Base
from .enums import (
    EmailStatusType, PriorityType, SentimentType, DeadlineConfidenceType,
    CategoryTypeType, HealthStatusType
)


class Email(Base):
    """
    Represents inbound messages from IMAP polling.
    """
    __tablename__ = "emails"

    id = Column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    message_id = Column(TEXT, nullable=False, unique=True)
    sender = Column(TEXT, nullable=False)
    sender_domain = Column(
        TEXT,
        nullable=False,
        server_default=text("split_part(sender, '@', 2)")
    )
    subject = Column(TEXT, nullable=False)
    received_timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    body_hash = Column(TEXT, nullable=False)
    body_encrypted = Column(LargeBinary, nullable=True)
    classification_status = Column(EmailStatusType, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        server_default=FetchedValue()
    )

    # Relationships
    classification = relationship("ClassificationResult", backref="email", uselist=False, cascade="all, delete-orphan")
    feedback_list = relationship("UserFeedback", backref="email", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_emails_message_id", "message_id"),
        Index("idx_emails_sender_domain", "sender_domain"),
        Index("idx_emails_received", "received_timestamp"),
        Index("idx_emails_status", "classification_status"),
        Index("idx_emails_pending", "classification_status", 
              postgresql_where=text("classification_status = 'pending'")),
    )

    def __repr__(self) -> str:
        return f"<Email(id={self.id}, sender={self.sender}, subject={self.subject[:50]}...)>"

    def __str__(self) -> str:
        return f"Email from {self.sender}: {self.subject}"


class ClassificationResult(Base):
    """
    Stores LLM classification outcomes.
    """
    __tablename__ = "classifications"

    id = Column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    email_id = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    primary_category = Column(TEXT, nullable=False)
    secondary_categories = Column(ARRAY(TEXT), nullable=False, default=[])
    priority = Column(PriorityType, nullable=False, default="normal")
    deadline_utc = Column(DateTime(timezone=True), nullable=True)
    deadline_confidence = Column(DeadlineConfidenceType, nullable=False, default="none")
    confidence = Column(NUMERIC(3, 2), nullable=False)
    rationale = Column(TEXT, nullable=True)
    detected_entities = Column(PostgreSQLJSONB, nullable=False, default={})
    sentiment = Column(SentimentType, nullable=False, default="neutral")
    action_items = Column(PostgreSQLJSONB, nullable=False, default=[])
    thread_context = Column(PostgreSQLJSONB, nullable=False, default={})
    rag_context_used = Column(ARRAY(TEXT), nullable=False, default=[])
    suggested_folder = Column(TEXT, nullable=True)
    schema_version = Column(TEXT, nullable=False, default="v2")
    processed_timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    email = relationship("Email", backref="classification")

    # Constraints
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_confidence_range"),
        CheckConstraint("array_length(secondary_categories, 1) <= 3", name="chk_secondary_categories"),
        CheckConstraint("jsonb_array_length(action_items) <= 10", name="chk_action_items"),
        CheckConstraint("length(rationale) <= 200", name="chk_rationale_length"),
        Index("idx_classifications_email", "email_id"),
        Index("idx_classifications_category", "primary_category"),
        Index("idx_classifications_confidence", "confidence"),
        Index("idx_classifications_processed", "processed_timestamp"),
        Index("idx_classifications_entities", "detected_entities", postgresql_using="gin"),
        Index("idx_classifications_actions", "action_items", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<ClassificationResult(id={self.id}, category={self.primary_category}, confidence={self.confidence})>"


class Tag(Base):
    """
    Category definitions from constitution.
    """
    __tablename__ = "tags"

    name = Column(TEXT, primary_key=True)
    description = Column(TEXT, nullable=False)
    category_type = Column(CategoryTypeType, nullable=False)
    active = Column(BOOLEAN, nullable=False, default=True)
    priority_order = Column(INTEGER, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_tags_type", "category_type"),
        Index("idx_tags_active", "active", postgresql_where=text("active = true")),
    )

    def __repr__(self) -> str:
        return f"<Tag(name={self.name}, type={self.category_type})>"


class ClassificationCycle(Base):
    """
    Periodic polling runs.
    """
    __tablename__ = "cycles"

    cycle_id = Column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    start_timestamp = Column(DateTime(timezone=True), nullable=False)
    end_timestamp = Column(DateTime(timezone=True), nullable=True)
    emails_scanned = Column(INTEGER, nullable=False, default=0)
    emails_classified = Column(INTEGER, nullable=False, default=0)
    emails_failed = Column(INTEGER, nullable=False, default=0)
    queue_depth_start = Column(INTEGER, nullable=False, default=0)
    queue_depth_end = Column(INTEGER, nullable=False, default=0)
    duration_ms = Column(INTEGER, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_cycles_start", "start_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ClassificationCycle(id={self.cycle_id}, start={self.start_timestamp})>"


class SystemConfig(Base):
    """
    Runtime configuration.
    """
    __tablename__ = "config"

    key = Column(TEXT, primary_key=True)
    value = Column(TEXT, nullable=False)
    value_type = Column(TEXT, nullable=False, default="string")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'int', 'float', 'bool')",
            name="chk_value_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<SystemConfig(key={self.key}, value={self.value})>"


class UserFeedback(Base):
    """
    Manual corrections for RAG improvement.
    """
    __tablename__ = "feedback"

    id = Column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    email_id = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False
    )
    original_category = Column(TEXT, nullable=False)
    corrected_category = Column(TEXT, nullable=False)
    reason = Column(TEXT, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    incorporated = Column(BOOLEAN, nullable=False, default=False)

    # Relationships
    email = relationship("Email", backref="feedback_list")

    # Indexes
    __table_args__ = (
        Index("idx_feedback_email", "email_id"),
        Index("idx_feedback_timestamp", "timestamp"),
        Index("idx_feedback_pending", "incorporated", 
              postgresql_where=text("incorporated = false")),
    )

    def __repr__(self) -> str:
        return f"<UserFeedback(id={self.id}, original={self.original_category}, corrected={self.corrected_category})>"


class DashboardMetric(Base):
    """
    Aggregated performance metrics.
    """
    __tablename__ = "metrics"

    id = Column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    metric_name = Column(TEXT, nullable=False)
    value = Column(NUMERIC, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    aggregation_period = Column(TEXT, nullable=False, default="5s")
    unit = Column(TEXT, nullable=True)
    labels = Column(PostgreSQLJSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "aggregation_period IN ('5s', '1m', '1h', '1d')",
            name="chk_aggregation_period"
        ),
        Index("idx_metrics_name_time", "metric_name", "timestamp"),
        Index("idx_metrics_labels", "labels", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<DashboardMetric(name={self.metric_name}, value={self.value})>"


class SystemHealthStatus(Base):
    """
    System component health monitoring.
    """
    __tablename__ = "health_checks"

    id = Column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    component_name = Column(TEXT, nullable=False)
    status = Column(HealthStatusType, nullable=False)
    last_check_timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    error_message = Column(TEXT, nullable=True)
    metrics = Column(PostgreSQLJSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_health_component_time", "component_name", "last_check_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<SystemHealthStatus(component={self.component_name}, status={self.status})>"