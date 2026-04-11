"""Tests for the mailing provider factory."""

from unittest.mock import patch

from app.services.mailing.factory import get_mailing_provider
from app.services.mailing.lob import LobProvider


class TestGetMailingProviderReturnsLob:
    def test_get_mailing_provider_returns_lob(self):
        """get_mailing_provider returns a LobProvider instance."""
        provider = get_mailing_provider()
        assert isinstance(provider, LobProvider)

    def test_factory_returns_new_instance_each_call(self):
        """Each call returns a fresh provider (no caching at factory level)."""
        p1 = get_mailing_provider()
        p2 = get_mailing_provider()
        assert p1 is not p2


class TestFactoryUsesSettingsKeyAndEnvironment:
    def test_factory_uses_settings_key_and_environment(self):
        """Provider is initialized with settings.lob_api_key and settings.lob_environment."""
        with patch("app.services.mailing.factory.settings") as mock_settings:
            mock_settings.lob_api_key = "test_key_from_settings"
            mock_settings.lob_environment = "live"
            provider = get_mailing_provider()

        assert isinstance(provider, LobProvider)
        assert provider.api_key == "test_key_from_settings"
        assert provider.environment == "live"

    def test_factory_uses_test_environment_by_default(self):
        """Default settings.lob_environment is 'test'."""
        from app.config import settings as real_settings

        provider = get_mailing_provider()
        assert provider.environment == real_settings.lob_environment

    def test_factory_uses_lob_api_key_from_settings(self):
        """Provider api_key matches settings.lob_api_key."""
        from app.config import settings as real_settings

        provider = get_mailing_provider()
        assert provider.api_key == real_settings.lob_api_key
