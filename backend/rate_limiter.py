from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from typing import Optional
from .auth import get_current_user

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# Rate limit decorators
def rate_limit(calls: int = 100, period: int = 3600, user_specific: bool = False):
    """
    Custom rate limit decorator that can handle both IP-based and user-based rate limiting

    Args:
        calls (int): Number of calls allowed
        period (int): Time period in seconds
        user_specific (bool): Whether to use user ID for rate limiting instead of IP
    """

    def decorator(func):
        async def get_key(request: Request):
            if user_specific:
                try:
                    # Get current user from the request
                    user = await get_current_user(request)
                    return f"user:{user.id}"
                except:
                    # Fallback to IP-based limiting if no user is authenticated
                    return f"ip:{request.client.host}"
            return f"ip:{request.client.host}"

        # Apply rate limiting using slowapi
        return limiter.limit(f"{calls}/{period}second", key_func=get_key)(func)

    return decorator


# Rate limit configurations
RATE_LIMITS = {
    "DEFAULT": {"calls": 100, "period": 3600},  # 100 requests per hour
    "STRICT": {"calls": 20, "period": 60},  # 20 requests per minute
    "LENIENT": {"calls": 1000, "period": 3600},  # 1000 requests per hour
    "AUTH": {"calls": 5, "period": 300},  # 5 requests per 5 minutes
}
