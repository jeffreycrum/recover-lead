"""Tests for the scraper factory registry pattern."""

from __future__ import annotations

import types
from unittest.mock import patch

import pytest

from app.ingestion.factory import (
    SCRAPER_REGISTRY,
    _ensure_scrapers_imported,
    get_scraper,
    register_scraper,
)


def _make_county(**kwargs) -> types.SimpleNamespace:
    defaults = {
        "name": "TestCounty",
        "state": "FL",
        "source_url": "http://example.com",
        "config": {},
        "scraper_class": "PdfScraper",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class TestRegisterScraper:
    def test_register_scraper_adds_to_registry(self):
        """Decorator should insert the class into SCRAPER_REGISTRY under the given name."""
        unique_name = "_TestScraperUnique"
        SCRAPER_REGISTRY.pop(unique_name, None)

        @register_scraper(unique_name)
        class _Dummy:
            pass

        assert SCRAPER_REGISTRY[unique_name] is _Dummy
        SCRAPER_REGISTRY.pop(unique_name, None)

    def test_register_scraper_allows_duplicate_with_warning(self, caplog):
        """Re-registering the same name logs a warning but does NOT raise."""
        import structlog.testing

        unique_name = "_TestDuplicateScraper"
        SCRAPER_REGISTRY.pop(unique_name, None)

        @register_scraper(unique_name)
        class _First:
            pass

        # Second registration should succeed, not crash
        with structlog.testing.capture_logs() as captured:

            @register_scraper(unique_name)
            class _Second:
                pass

        # Warning event emitted
        warning_events = [e for e in captured if e.get("event") == "scraper_already_registered"]
        assert warning_events, "Expected 'scraper_already_registered' warning log"

        # Registry updated to new class
        assert SCRAPER_REGISTRY[unique_name] is _Second
        SCRAPER_REGISTRY.pop(unique_name, None)

    def test_register_scraper_returns_original_class(self):
        """The decorator must return the decorated class unchanged."""
        unique_name = "_TestReturnClass"
        SCRAPER_REGISTRY.pop(unique_name, None)

        @register_scraper(unique_name)
        class _MyClass:
            x = 42

        assert _MyClass.x == 42
        SCRAPER_REGISTRY.pop(unique_name, None)


class TestGetScraper:
    def test_get_scraper_unknown_returns_none(self):
        """A scraper_class not in the registry returns None."""
        county = _make_county(scraper_class="DoesNotExistScraper999")
        result = get_scraper(county)
        assert result is None

    def test_get_scraper_no_scraper_class_returns_none(self):
        """A county with an empty/falsy scraper_class returns None."""
        county = _make_county(scraper_class="")
        assert get_scraper(county) is None

        county_none = _make_county(scraper_class=None)
        assert get_scraper(county_none) is None

    def test_get_scraper_instantiates_with_county_attrs(self):
        """get_scraper should pass county_name, source_url, state, config to the class."""
        name = "_CaptureScraper"
        SCRAPER_REGISTRY.pop(name, None)

        received: dict = {}

        @register_scraper(name)
        class _CaptureScraper:
            def __init__(self, county_name, source_url, state, config):
                received.update(
                    county_name=county_name,
                    source_url=source_url,
                    state=state,
                    config=config,
                )

        county = _make_county(
            name="Gulf",
            state="FL",
            source_url="http://gulf.gov",
            config={"x": 1},
            scraper_class=name,
        )
        instance = get_scraper(county)

        assert instance is not None
        assert received["county_name"] == "Gulf"
        assert received["source_url"] == "http://gulf.gov"
        assert received["state"] == "FL"
        assert received["config"] == {"x": 1}
        SCRAPER_REGISTRY.pop(name, None)


class TestEnsureScrapersImported:
    def test_ensure_scrapers_imported_populates_registry(self):
        """After calling _ensure_scrapers_imported, known scrapers must exist."""
        _ensure_scrapers_imported()
        assert "PdfScraper" in SCRAPER_REGISTRY
        assert "HtmlTableScraper" in SCRAPER_REGISTRY
        assert "XlsxScraper" in SCRAPER_REGISTRY
        assert "GulfHtmlScraper" in SCRAPER_REGISTRY
        assert "CaliforniaExcessProceedsScraper" in SCRAPER_REGISTRY
        assert "SanDiegoFinalReportScraper" in SCRAPER_REGISTRY
        assert "PlaywrightCaliforniaExcessProceedsScraper" in SCRAPER_REGISTRY

    def test_ensure_scrapers_imported_handles_missing_cloudscraper(self):
        """If cloudscraper is missing, _ensure_scrapers_imported must NOT raise."""
        import builtins
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "app.ingestion.cloudscraper_html":
                raise ImportError("cloudscraper not installed")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            # Should not raise
            try:
                _ensure_scrapers_imported()
            except ImportError:
                pytest.fail("_ensure_scrapers_imported raised ImportError for missing cloudscraper")
