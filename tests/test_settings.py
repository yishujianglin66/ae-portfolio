"""config.settings 单元测试 - 全局配置管理"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings, PROJECT_ROOT


class TestSettings:
    def _make_settings(self, **env_overrides):
        """Helper: create a Settings instance with environment variable overrides"""
        env = os.environ.copy()
        for key, value in env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = str(value)
        
        with patch.dict(os.environ, env, clear=True):
            return Settings()
    
    def test_default_environment(self):
        s = self._make_settings(AEK_ENVIRONMENT=None, AE_VAULT_SECRET_KEY=None)
        assert s.environment == "development"
        assert s.is_development is True
        assert s.is_production is False
    
    def test_production_environment(self):
        s = self._make_settings(AEK_ENVIRONMENT="production", AE_VAULT_SECRET_KEY="test-secret")
        assert s.environment == "production"
        assert s.is_production is True
        assert s.is_development is False
    
    def test_test_environment(self):
        s = self._make_settings(AEK_ENVIRONMENT="test", AE_VAULT_SECRET_KEY="test-key")
        assert s.environment == "test"
        assert s.is_production is False
        assert s.is_development is False
    
    def test_production_without_secret_raises(self):
        with pytest.raises(RuntimeError, match="生产环境必须设置"):
            self._make_settings(AEK_ENVIRONMENT="production", AE_VAULT_SECRET_KEY=None)
    
    def test_development_default_secret(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.jwt_secret is not None
        assert len(s.jwt_secret) > 0
    
    def test_custom_jwt_secret(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY="my-custom-secret-123")
        assert s.jwt_secret == "my-custom-secret-123"
    
    def test_jwt_algorithm(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.jwt_alg == "HS256"
    
    def test_token_ttl_defaults(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.access_token_ttl == 3600
        assert s.refresh_token_ttl == 604800
    
    def test_token_ttl_custom(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            ACCESS_TOKEN_TTL="1800",
            REFRESH_TOKEN_TTL="86400",
        )
        assert s.access_token_ttl == 1800
        assert s.refresh_token_ttl == 86400
    
    def test_api_config_defaults(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.api_host == "0.0.0.0"
        assert s.api_port == 8000
        assert s.api_workers == 1
    
    def test_api_config_custom(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            API_HOST="127.0.0.1",
            API_PORT="9000",
            API_WORKERS="4",
        )
        assert s.api_host == "127.0.0.1"
        assert s.api_port == 9000
        assert s.api_workers == 4
    
    def test_cors_origins_default(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.cors_origins == "*"
        assert s.cors_origin_list == ["*"]
    
    def test_cors_origins_multiple(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            CORS_ORIGINS="http://localhost:3000,http://example.com",
        )
        assert len(s.cors_origin_list) == 2
        assert "http://localhost:3000" in s.cors_origin_list
        assert "http://example.com" in s.cors_origin_list
    
    def test_cors_origins_with_spaces(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            CORS_ORIGINS=" http://a.com , http://b.com ",
        )
        assert len(s.cors_origin_list) == 2
        assert "http://a.com" in s.cors_origin_list
        assert "http://b.com" in s.cors_origin_list
    
    def test_db_path_default(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert "ae_vault.db" in s.db_path
    
    def test_db_path_custom(self, tmp_path):
        custom_db = str(tmp_path / "custom.db")
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            DB_PATH=custom_db,
        )
        assert s.db_path == custom_db
    
    def test_monitoring_defaults(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.metrics_interval == 15.0
        assert s.alert_check_interval == 10.0
    
    def test_monitoring_custom(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            METRICS_INTERVAL="30.0",
            ALERT_CHECK_INTERVAL="20.0",
        )
        assert s.metrics_interval == 30.0
        assert s.alert_check_interval == 20.0
    
    def test_scheduler_workers_default(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.scheduler_workers == 3
    
    def test_scheduler_workers_custom(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY="test",
            SCHEDULER_WORKERS="5",
        )
        assert s.scheduler_workers == 5
    
    def test_data_dir_exists(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.data_dir.exists()
        assert s.logs_dir.exists()
    
    def test_log_level_development(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        assert s.log_level == "DEBUG"
    
    def test_log_level_production(self):
        s = self._make_settings(AEK_ENVIRONMENT="production", AE_VAULT_SECRET_KEY="prod-secret")
        assert s.log_level == "INFO"
    
    def test_log_level_custom(self):
        s = self._make_settings(
            AEK_ENVIRONMENT="development",
            AE_VAULT_SECRET_KEY=None,
            LOG_LEVEL="WARNING",
        )
        assert s.log_level == "WARNING"
    
    def test_summary(self):
        s = self._make_settings(AEK_ENVIRONMENT="development", AE_VAULT_SECRET_KEY=None)
        summary = s.summary()
        assert "environment" in summary
        assert "api_host" in summary
        assert "api_port" in summary
        assert "is_production" in summary
        assert "db_path" in summary
        assert "frontend_dist" in summary
        assert "log_level" in summary
        assert summary["environment"] == "development"
    
    def test_project_root_exists(self):
        assert PROJECT_ROOT is not None
        assert isinstance(PROJECT_ROOT, Path)
        assert PROJECT_ROOT.exists()
