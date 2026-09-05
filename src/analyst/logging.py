"""Structured logging.

Every pipeline stage logs key=value pairs, not prose. This is the cheap 70% of
observability: on Day 6 these same events become the user-facing reasoning trace.
"""

import logging
import sys

import structlog

from analyst.config import get_settings

# Libraries that emit one INFO line per HTTP call. `basicConfig` sets the root
# logger, and these propagate to it, so at INFO they drown out the pipeline's
# own events: a full index makes ~40 upsert requests and an eval run ~90
# searches, and every one of those lines is saved into the notebook's outputs.
# They carry no information a failure would not raise anyway.
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "qdrant_client")


def configure_logging(quiet_third_party: bool = True) -> None:
    settings = get_settings()
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level)
    if quiet_third_party:
        for name in NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
