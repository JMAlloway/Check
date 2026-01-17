"""Rate limiting configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter - uses client IP for identification
# Applied to sensitive endpoints like login to prevent brute force attacks
limiter = Limiter(key_func=get_remote_address)
