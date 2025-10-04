"""
Configuration loader for Email-Classifier using Pydantic Settings.

This module provides type-safe configuration management with validation
for all environment variables used by the Email-Classifier application.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
# This follows the same pattern as in database/migrations/env.py
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    db_url: SecretStr = Field(
        default="postgresql://classifier:password@localhost:5432/email_classifier",
        description="PostgreSQL connection string",
        alias="DB_URL"
    )
    
    @field_validator('db_url')
    @classmethod
    def validate_db_url(cls, v: SecretStr) -> SecretStr:
        """Validate that the database URL is properly formatted."""
        url = v.get_secret_value()
        if not url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('Database URL must start with postgresql:// or postgres://')
        return v


class LLMSettings(BaseSettings):
    """LLM (Ollama) configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server host URL",
        alias="OLLAMA_HOST"
    )
    
    qwen_model_name: str = Field(
        default="qwen3:8b",
        description="Name of the Qwen model to use",
        alias="QWEN_MODEL_NAME"
    )
    
    @field_validator('ollama_host')
    @classmethod
    def validate_ollama_host(cls, v: str) -> str:
        """Validate that the Ollama host URL is properly formatted."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Ollama host must start with http:// or https://')
        return v


class VectorDBSettings(BaseSettings):
    """Vector database (Qdrant/Supabase) configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant server host",
        alias="QDRANT_HOST"
    )
    
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant server port",
        alias="QDRANT_PORT",
        ge=1, le=65535
    )
    
    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase server URL",
        alias="SUPABASE_URL"
    )
    
    supabase_key: Optional[SecretStr] = Field(
        default=None,
        description="Supabase API key",
        alias="SUPABASE_KEY"
    )
    
    @field_validator('supabase_url')
    @classmethod
    def validate_supabase_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate Supabase URL format if provided."""
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError('Supabase URL must start with http:// or https://')
        return v


class EmailSettings(BaseSettings):
    """Email (IMAP) configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    imap_server: str = Field(
        default="imap.gmail.com",
        description="IMAP server address",
        alias="IMAP_SERVER"
    )
    
    imap_username: str = Field(
        description="Email username",
        alias="IMAP_USERNAME"
    )
    
    imap_password: SecretStr = Field(
        description="Email password or app-specific password",
        alias="IMAP_PASSWORD"
    )
    
    imap_folder: str = Field(
        default="INBOX",
        description="IMAP folder to monitor",
        alias="IMAP_FOLDER"
    )


class DashboardSettings(BaseSettings):
    """Web dashboard configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    dashboard_port: int = Field(
        default=8080,
        description="Dashboard server port",
        alias="DASHBOARD_PORT",
        ge=1, le=65535
    )
    
    dashboard_username: str = Field(
        default="admin",
        description="Dashboard username",
        alias="DASHBOARD_USERNAME"
    )
    
    dashboard_password: SecretStr = Field(
        default="secret",
        description="Dashboard password",
        alias="DASHBOARD_PASSWORD"
    )


class MonitoringSettings(BaseSettings):
    """Monitoring (Grafana/Prometheus) configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    grafana_password: SecretStr = Field(
        default="grafana123",
        description="Grafana admin password",
        alias="GRAFANA_PASSWORD"
    )


class FeatureFlags(BaseSettings):
    """Application feature toggles."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    rag_enabled: bool = Field(
        default=True,
        description="Enable/disable RAG functionality",
        alias="RAG_ENABLED"
    )
    
    store_raw_emails: bool = Field(
        default=False,
        description="Store raw email bodies",
        alias="STORE_RAW_EMAILS"
    )
    
    retention_days: int = Field(
        default=90,
        description="Data retention period in days",
        alias="RETENTION_DAYS",
        ge=1
    )


class PerformanceSettings(BaseSettings):
    """Performance tuning parameters."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    email_poll_interval: int = Field(
        default=30,
        description="Email polling interval in seconds",
        alias="EMAIL_POLL_INTERVAL",
        ge=1
    )
    
    classify_concurrency: int = Field(
        default=2,
        description="Number of concurrent classification workers",
        alias="CLASSIFY_CONCURRENCY",
        ge=1
    )


class SecuritySettings(BaseSettings):
    """Encryption and authentication settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    encryption_key: SecretStr = Field(
        description="32-byte encryption key for sensitive data",
        alias="ENCRYPTION_KEY"
    )
    
    @field_validator('encryption_key')
    @classmethod
    def validate_encryption_key(cls, v: SecretStr) -> SecretStr:
        """Validate that the encryption key is 32 bytes."""
        key = v.get_secret_value()
        if len(key.encode()) != 32:
            raise ValueError('Encryption key must be exactly 32 bytes')
        return v


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    
    def get_database_url(self) -> str:
        """Get the database URL as a string."""
        return self.database.db_url.get_secret_value()
    
    def get_imap_password(self) -> str:
        """Get the IMAP password as a string."""
        return self.email.imap_password.get_secret_value()
    
    def get_dashboard_password(self) -> str:
        """Get the dashboard password as a string."""
        return self.dashboard.dashboard_password.get_secret_value()
    
    def get_grafana_password(self) -> str:
        """Get the Grafana password as a string."""
        return self.monitoring.grafana_password.get_secret_value()
    
    def get_encryption_key(self) -> str:
        """Get the encryption key as a string."""
        return self.security.encryption_key.get_secret_value()
    
    def get_supabase_key(self) -> Optional[str]:
        """Get the Supabase key as a string if available."""
        if self.vector_db.supabase_key:
            return self.vector_db.supabase_key.get_secret_value()
        return None


# Global settings instance (lazy initialization)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the application settings instance.
    
    Returns:
        Settings: The application settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings




def validate_required_settings() -> None:
    """
    Validate that all required settings are present and valid.
    
    Raises:
        ValueError: If any required setting is missing or invalid
    """
    try:
        current_settings = get_settings()
        required_fields = [
            ('email.imap_username', current_settings.email.imap_username),
            ('email.imap_password', current_settings.email.imap_password),
            ('security.encryption_key', current_settings.security.encryption_key),
        ]
        
        missing_fields = []
        for field_name, field_value in required_fields:
            if not field_value:
                missing_fields.append(field_name)
        
        if missing_fields:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")
    except Exception as e:
        # Re-raise any validation error as ValueError with a clear message
        if "Field required" in str(e) or "missing" in str(e).lower():
            raise ValueError("Missing required environment variables") from e
        raise