"""Skip trace provider factory."""

from app.config import settings
from app.services.skip_trace import SkipTraceProvider
from app.services.skip_trace.tracerfy import TracerfyProvider


def get_skip_trace_provider() -> SkipTraceProvider:
    """Return the configured skip trace provider."""
    return TracerfyProvider(
        api_key=settings.tracerfy_api_key,
        base_url=settings.tracerfy_base_url,
    )
