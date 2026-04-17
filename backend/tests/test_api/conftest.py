"""Shared fixtures for API test suite.

Every test in tests/test_api/ hits at least one rate-limited endpoint,
which pulls in two external dependencies:
  - get_current_subscription_plan  → real DB query via asyncpg
  - check_rate_limit               → real Redis pipeline

Both are mocked here so individual tests don't need Redis/DB connections
just to satisfy the rate-limiter middleware, and so asyncpg connections
from one test's event loop can't bleed into the next test's loop.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.main import app

_RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit": 5,
    "X-RateLimit-Remaining": 4,
    "X-RateLimit-Reset": 9_999_999_999,
}


@pytest.fixture(autouse=True)
def mock_rate_limiting_deps():
    from app.dependencies import get_current_subscription_plan

    app.dependency_overrides[get_current_subscription_plan] = lambda: "free"
    with patch(
        "app.dependencies.check_rate_limit",
        new=AsyncMock(return_value=_RATE_LIMIT_HEADERS),
    ):
        yield
    app.dependency_overrides.pop(get_current_subscription_plan, None)
