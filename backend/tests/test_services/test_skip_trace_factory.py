"""Tests for the skip trace provider factory."""

from __future__ import annotations

from unittest.mock import patch

from app.services.skip_trace.factory import get_skip_trace_provider
from app.services.skip_trace.skipsherpa import SkipSherpaProvider
from app.services.skip_trace.tracerfy import TracerfyProvider


class TestSkipTraceFactory:
    def test_factory_returns_tracerfy_by_default(self):
        """Default provider (tracerfy) must return a TracerfyProvider instance."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = "tracerfy"
            mock_settings.tracerfy_api_key = "tracerfy-key"
            mock_settings.tracerfy_base_url = "https://tracerfy.com/v1/api"

            provider = get_skip_trace_provider()

        assert isinstance(provider, TracerfyProvider)

    def test_factory_returns_tracerfy_when_provider_none(self):
        """None skip_trace_provider must fall back to TracerfyProvider."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = None
            mock_settings.tracerfy_api_key = "tracerfy-key"
            mock_settings.tracerfy_base_url = "https://tracerfy.com/v1/api"

            provider = get_skip_trace_provider()

        assert isinstance(provider, TracerfyProvider)

    def test_factory_returns_skipsherpa_when_configured(self):
        """Setting skip_trace_provider='skipsherpa' with a key returns SkipSherpaProvider."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = "skipsherpa"
            mock_settings.skipsherpa_api_key = "sherpa-api-key"
            mock_settings.skipsherpa_base_url = "https://skipsherpa.com/api/beta6"

            provider = get_skip_trace_provider()

        assert isinstance(provider, SkipSherpaProvider)

    def test_factory_falls_back_to_tracerfy_if_skipsherpa_key_missing(self):
        """skipsherpa provider without an API key must fall back to TracerfyProvider."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = "skipsherpa"
            mock_settings.skipsherpa_api_key = ""  # empty = not configured
            mock_settings.tracerfy_api_key = "tracerfy-key"
            mock_settings.tracerfy_base_url = "https://tracerfy.com/v1/api"

            provider = get_skip_trace_provider()

        assert isinstance(provider, TracerfyProvider)

    def test_factory_skipsherpa_passes_correct_key(self):
        """SkipSherpaProvider must receive the configured API key."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = "skipsherpa"
            mock_settings.skipsherpa_api_key = "my-sherpa-key-xyz"
            mock_settings.skipsherpa_base_url = "https://skipsherpa.com/api/beta6"

            provider = get_skip_trace_provider()

        assert isinstance(provider, SkipSherpaProvider)
        assert provider.api_key == "my-sherpa-key-xyz"

    def test_factory_tracerfy_passes_correct_key(self):
        """TracerfyProvider must receive the configured API key and base URL."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = "tracerfy"
            mock_settings.tracerfy_api_key = "tf-test-key"
            mock_settings.tracerfy_base_url = "https://tracerfy.com/v1/api"

            provider = get_skip_trace_provider()

        assert isinstance(provider, TracerfyProvider)
        assert provider.api_key == "tf-test-key"

    def test_factory_handles_whitespace_in_provider_name(self):
        """Provider name with surrounding whitespace must still match correctly."""
        with patch("app.services.skip_trace.factory.settings") as mock_settings:
            mock_settings.skip_trace_provider = "  skipsherpa  "
            mock_settings.skipsherpa_api_key = "key-123"
            mock_settings.skipsherpa_base_url = "https://skipsherpa.com/api/beta6"

            provider = get_skip_trace_provider()

        assert isinstance(provider, SkipSherpaProvider)
