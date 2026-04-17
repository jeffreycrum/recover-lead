import logging
import re
import sys
import uuid

import structlog

PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\b(?:\d{3}-\d{2}-\d{4}|\d{9})\b"), "[SSN_REDACTED]"),
    (
        re.compile(
            r"\b\d{1,5}\s+[A-Za-z0-9 .,'#-]{3,40}"
            r"(?:Ave|St|Rd|Blvd|Dr|Ln|Ct|Way|Pl|Ter|Cir|Hwy)\b",
            re.IGNORECASE,
        ),
        "[ADDRESS_REDACTED]",
    ),
]


def pii_filter(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Strip PII from log output."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            for pattern, replacement in PII_PATTERNS:
                value = pattern.sub(replacement, value)
            event_dict[key] = value
    return event_dict


def generate_request_id() -> str:
    return str(uuid.uuid4())


def setup_logging() -> None:
    # Configure Python's stdlib logging to actually output INFO level.
    # structlog.stdlib.filter_by_level uses the stdlib logger levels, so
    # without this the root logger defaults to WARNING and all logger.info
    # calls are silently dropped.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            pii_filter,
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
