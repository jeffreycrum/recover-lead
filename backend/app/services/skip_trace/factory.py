"""Skip trace provider factory.

Switches between providers based on SKIP_TRACE_PROVIDER env var:
  - "tracerfy"   -> Tracerfy (requires address, $0.02/hit)
  - "skipsherpa" -> Skip Sherpa (name-only ok, $0.08-0.15/hit, deceased+relatives+LLC)
"""

import structlog

from app.config import settings
from app.services.skip_trace import SkipTraceProvider
from app.services.skip_trace.skipsherpa import SkipSherpaProvider
from app.services.skip_trace.tracerfy import TracerfyProvider

logger = structlog.get_logger()


def get_skip_trace_provider() -> SkipTraceProvider:
    """Return the configured skip trace provider."""
    provider_name = (settings.skip_trace_provider or "tracerfy").lower().strip()

    if provider_name == "skipsherpa":
        if not settings.skipsherpa_api_key:
            logger.warning(
                "skipsherpa_not_configured_falling_back_to_tracerfy",
            )
            return TracerfyProvider(
                api_key=settings.tracerfy_api_key,
                base_url=settings.tracerfy_base_url,
            )
        return SkipSherpaProvider(
            api_key=settings.skipsherpa_api_key,
            base_url=settings.skipsherpa_base_url,
        )

    return TracerfyProvider(
        api_key=settings.tracerfy_api_key,
        base_url=settings.tracerfy_base_url,
    )
