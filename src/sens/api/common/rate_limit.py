"""Rate limiting middleware for API endpoints."""

import time
from collections import defaultdict
from typing import Dict, Tuple

import structlog
from fastapi import HTTPException, Request

logger = structlog.get_logger(__name__)

# In-memory store for rate limiting
# Key: IP address, Value: (request_count, window_start_time)
RATE_LIMIT_STORE: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))

# Configuration
REQUESTS_PER_WINDOW = 100  # Number of requests allowed
WINDOW_SIZE = 60  # Window size in seconds


async def rate_limiter(request: Request) -> bool:
    """Rate limiting dependency.

    Args:
        request: FastAPI request object

    Returns:
        bool: True if request is allowed

    Raises:
        HTTPException: If rate limit is exceeded
    """
    client_ip = request.client.host
    current_time = time.time()

    # Get current count and window start time
    count, window_start = RATE_LIMIT_STORE[client_ip]

    # Reset if window has expired
    if current_time - window_start >= WINDOW_SIZE:
        RATE_LIMIT_STORE[client_ip] = (1, current_time)
        return True

    # Increment count if within window
    if count < REQUESTS_PER_WINDOW:
        RATE_LIMIT_STORE[client_ip] = (count + 1, window_start)
        return True

    # Rate limit exceeded
    logger.warning(
        "rate_limit_exceeded",
        client_ip=client_ip,
        count=count,
        window_start=window_start,
    )
    raise HTTPException(
        status_code=429,
        detail=f"Rate limit exceeded. Maximum {REQUESTS_PER_WINDOW} requests per {WINDOW_SIZE} seconds.",
    )
