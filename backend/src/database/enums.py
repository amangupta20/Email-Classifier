"""
Database enum types for the Email Classifier application.
"""

from enum import Enum
from sqlalchemy import DDL, event
from sqlalchemy.types import Enum as SQLEnum


class EmailStatus(str, Enum):
    """Email classification status enum."""
    PENDING = "pending"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class Priority(str, Enum):
    """Email priority enum."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Sentiment(str, Enum):
    """Email sentiment enum."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    URGENT = "urgent"


class DeadlineConfidence(str, Enum):
    """Deadline confidence level enum."""
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    NONE = "none"


class CategoryType(str, Enum):
    """Category type enum."""
    ACADEMIC = "academic"
    CAREER = "career"
    ADMIN = "admin"
    CLUBS = "clubs"
    SPORTS = "sports"
    CULTURAL = "cultural"
    ACTION = "action"
    FINANCE = "finance"
    PERSONAL = "personal"
    LEARNING = "learning"
    PROMOTION = "promotion"
    SYSTEM = "system"
    SPAM = "spam"


class HealthStatus(str, Enum):
    """System health status enum."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


# SQLAlchemy enum types for database columns
EmailStatusType = SQLEnum(EmailStatus, name="email_status", create_type=False)
PriorityType = SQLEnum(Priority, name="priority", create_type=False)
SentimentType = SQLEnum(Sentiment, name="sentiment", create_type=False)
DeadlineConfidenceType = SQLEnum(DeadlineConfidence, name="deadline_confidence", create_type=False)
CategoryTypeType = SQLEnum(CategoryType, name="category_type", create_type=False)
HealthStatusType = SQLEnum(HealthStatus, name="health_status", create_type=False)