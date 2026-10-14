import logging
import uuid

from fastapi import Request


def log_route_exception(logger: logging.Logger, request: Request, event: str, exc: Exception) -> str:
    """Log exception detail on the server and return a client-safe correlation ID."""
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id

    logger.error(
        "event=%s request_id=%s error_type=%s",
        event,
        request_id,
        type(exc).__name__,
    )
    return request_id
