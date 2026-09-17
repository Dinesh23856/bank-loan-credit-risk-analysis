import os
from slowapi import Limiter
from slowapi.util import get_remote_address

redis_url = os.getenv("REDIS_URL")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120/minute")],
    storage_uri=redis_url if redis_url else "memory://"
)
