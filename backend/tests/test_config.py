"""
Tests for the configuration loader.
"""

import os
import pytest
from unittest.mock import patch

from src.config import (
    Settings,
    DatabaseSettings,
    LLMSettings,
    VectorDBSettings,
    EmailSettings,
    DashboardSettings,
    MonitoringSettings,
    FeatureFlags,
    PerformanceSettings,
    SecuritySettings,
    get_settings,
    validate_required_settings,
)


class TestDatabaseSettings:
    """Test database configuration settings."""
    
    def test_default_db_url(self):
        """Test default database URL."""
        settings = DatabaseSettings()
        assert settings.db_url.get_secret_value() == "postgresql://classifier:password@localhost:5432/email_classifier"
    
    def test_custom_db_url(self):
        """Test custom database URL."""
        custom_url = "postgresql://user:pass@host:5432/db"
        with patch.dict(os.environ, {'DB_URL': custom_url}):
            settings = DatabaseSettings()
            assert settings.db_url.get_secret_value() == custom_url
    
    def test_invalid_db_url(self):
        """Test validation of invalid database URL."""
        with patch.dict(os.environ, {'DB_URL': 'invalid://url'}):
            with pytest.raises(ValueError, match="Database URL must start with postgresql:// or postgres://"):
                DatabaseSettings()


class TestLLMSettings:
    """Test LLM configuration settings."""
    
    def test_default_ollama_host(self):
        """Test default Ollama host."""
        settings = LLMSettings()
        assert settings.ollama_host == "http://localhost:11434"
    
    def test_default_qwen_model_name(self):
        """Test default Qwen model name."""
        settings = LLMSettings()
        assert settings.qwen_model_name == "qwen3:8b"
    
    def test_invalid_ollama_host(self):
        """Test validation of invalid Ollama host."""
        with patch.dict(os.environ, {'OLLAMA_HOST': 'invalid-host'}):
            with pytest.raises(ValueError, match="Ollama host must start with http:// or https://"):
                LLMSettings()


class TestVectorDBSettings:
    """Test vector database configuration settings."""
    
    def test_default_qdrant_settings(self):
        """Test default Qdrant settings."""
        settings = VectorDBSettings()
        assert settings.qdrant_host == "localhost"
        assert settings.qdrant_port == 6333
    
    def test_invalid_qdrant_port(self):
        """Test validation of invalid Qdrant port."""
        with patch.dict(os.environ, {'QDRANT_PORT': '0'}):
            with pytest.raises(ValueError):
                VectorDBSettings()
        
        with patch.dict(os.environ, {'QDRANT_PORT': '65536'}):
            with pytest.raises(ValueError):
                VectorDBSettings()
    
    def test_invalid_supabase_url(self):
        """Test validation of invalid Supabase URL."""
        with patch.dict(os.environ, {'SUPABASE_URL': 'invalid-url'}):
            with pytest.raises(ValueError, match="Supabase URL must start with http:// or https://"):
                VectorDBSettings()


class TestEmailSettings:
    """Test email configuration settings."""
    
    def test_default_imap_settings(self):
        """Test default IMAP settings."""
        with patch.dict(os.environ, {
            'IMAP_USERNAME': 'test@example.com',
            'IMAP_PASSWORD': 'password123'
        }):
            settings = EmailSettings()
            assert settings.imap_server == "imap.gmail.com"
            assert settings.imap_username == "test@example.com"
            assert settings.imap_password.get_secret_value() == "password123"
            assert settings.imap_folder == "INBOX"


class TestDashboardSettings:
    """Test dashboard configuration settings."""
    
    def test_default_dashboard_settings(self):
        """Test default dashboard settings."""
        settings = DashboardSettings()
        assert settings.dashboard_port == 8080
        assert settings.dashboard_username == "admin"
        assert settings.dashboard_password.get_secret_value() == "secret"
    
    def test_invalid_dashboard_port(self):
        """Test validation of invalid dashboard port."""
        with patch.dict(os.environ, {'DASHBOARD_PORT': '0'}):
            with pytest.raises(ValueError):
                DashboardSettings()
        
        with patch.dict(os.environ, {'DASHBOARD_PORT': '65536'}):
            with pytest.raises(ValueError):
                DashboardSettings()


class TestMonitoringSettings:
    """Test monitoring configuration settings."""
    
    def test_default_grafana_password(self):
        """Test default Grafana password."""
        settings = MonitoringSettings()
        assert settings.grafana_password.get_secret_value() == "grafana123"


class TestFeatureFlags:
    """Test feature flags configuration."""
    
    def test_default_feature_flags(self):
        """Test default feature flags."""
        settings = FeatureFlags()
        assert settings.rag_enabled is True
        assert settings.store_raw_emails is False
        assert settings.retention_days == 90
    
    def test_invalid_retention_days(self):
        """Test validation of invalid retention days."""
        with patch.dict(os.environ, {'RETENTION_DAYS': '0'}):
            with pytest.raises(ValueError):
                FeatureFlags()


class TestPerformanceSettings:
    """Test performance configuration settings."""
    
    def test_default_performance_settings(self):
        """Test default performance settings."""
        settings = PerformanceSettings()
        assert settings.email_poll_interval == 30
        assert settings.classify_concurrency == 2
    
    def test_invalid_values(self):
        """Test validation of invalid performance values."""
        with patch.dict(os.environ, {'EMAIL_POLL_INTERVAL': '0'}):
            with pytest.raises(ValueError):
                PerformanceSettings()
        
        with patch.dict(os.environ, {'CLASSIFY_CONCURRENCY': '0'}):
            with pytest.raises(ValueError):
                PerformanceSettings()


class TestSecuritySettings:
    """Test security configuration settings."""
    
    def test_valid_encryption_key(self):
        """Test valid encryption key."""
        # 32-byte key
        valid_key = "a" * 32
        with patch.dict(os.environ, {'ENCRYPTION_KEY': valid_key}):
            settings = SecuritySettings()
            assert settings.encryption_key.get_secret_value() == valid_key
    
    def test_invalid_encryption_key(self):
        """Test validation of invalid encryption key."""
        with patch.dict(os.environ, {'ENCRYPTION_KEY': 'short'}):
            with pytest.raises(ValueError, match="Encryption key must be exactly 32 bytes"):
                SecuritySettings()
        
        with patch.dict(os.environ, {'ENCRYPTION_KEY': 'a' * 33}):
            with pytest.raises(ValueError, match="Encryption key must be exactly 32 bytes"):
                SecuritySettings()


class TestSettings:
    """Test main settings class."""
    
    def test_settings_initialization(self):
        """Test settings initialization with default values."""
        with patch.dict(os.environ, {
            'IMAP_USERNAME': 'test@example.com',
            'IMAP_PASSWORD': 'password123',
            'ENCRYPTION_KEY': 'a' * 32
        }):
            settings = Settings()
            
            # Test database settings
            assert settings.database.db_url.get_secret_value() == "postgresql://classifier:password@localhost:5432/email_classifier"
            
            # Test LLM settings
            assert settings.llm.ollama_host == "http://localhost:11434"
            assert settings.llm.qwen_model_name == "qwen3:8b"
            
            # Test vector DB settings
            assert settings.vector_db.qdrant_host == "localhost"
            assert settings.vector_db.qdrant_port == 6333
            
            # Test email settings
            assert settings.email.imap_server == "imap.gmail.com"
            assert settings.email.imap_username == "test@example.com"
            assert settings.email.imap_password.get_secret_value() == "password123"
            
            # Test dashboard settings
            assert settings.dashboard.dashboard_port == 8080
            assert settings.dashboard.dashboard_username == "admin"
            
            # Test monitoring settings
            assert settings.monitoring.grafana_password.get_secret_value() == "grafana123"
            
            # Test feature flags
            assert settings.features.rag_enabled is True
            assert settings.features.store_raw_emails is False
            assert settings.features.retention_days == 90
            
            # Test performance settings
            assert settings.performance.email_poll_interval == 30
            assert settings.performance.classify_concurrency == 2
            
            # Test security settings
            assert settings.security.encryption_key.get_secret_value() == "a" * 32
    
    def test_get_helper_methods(self):
        """Test helper methods for getting secret values."""
        with patch.dict(os.environ, {
            'IMAP_USERNAME': 'test@example.com',
            'IMAP_PASSWORD': 'password123',
            'ENCRYPTION_KEY': 'a' * 32
        }):
            settings = Settings()
            
            assert settings.get_database_url() == "postgresql://classifier:password@localhost:5432/email_classifier"
            assert settings.get_imap_password() == "password123"
            assert settings.get_dashboard_password() == "secret"
            assert settings.get_grafana_password() == "grafana123"
            assert settings.get_encryption_key() == "a" * 32
            assert settings.get_supabase_key() is None


class TestGlobalSettings:
    """Test global settings instance."""
    
    def test_get_settings(self):
        """Test getting global settings instance."""
        with patch.dict(os.environ, {
            'IMAP_USERNAME': 'test@example.com',
            'IMAP_PASSWORD': 'password123',
            'ENCRYPTION_KEY': 'a' * 32
        }):
            settings = get_settings()
            assert isinstance(settings, Settings)
    
    def test_validate_required_settings_success(self):
        """Test successful validation of required settings."""
        with patch.dict(os.environ, {
            'IMAP_USERNAME': 'test@example.com',
            'IMAP_PASSWORD': 'password123',
            'ENCRYPTION_KEY': 'a' * 32
        }):
            # Should not raise an exception
            validate_required_settings()
    
    def test_validate_required_settings_failure(self):
        """Test validation failure for missing required settings."""
        # Clear the global settings cache
        import src.config
        src.config._settings = None
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variables"):
                validate_required_settings()