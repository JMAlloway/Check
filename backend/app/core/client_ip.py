"""Secure client IP detection for requests behind reverse proxies.

This module provides secure extraction of the real client IP address
when the application runs behind reverse proxies (Nginx, load balancers, etc.).

SECURITY CONSIDERATIONS:
- X-Forwarded-For can be spoofed by clients
- Only trust proxy headers from known, trusted proxy IPs
- The rightmost IP in X-Forwarded-For from a trusted proxy is the client IP
- Fall back to request.client.host when not behind a trusted proxy

Usage:
    from app.core.client_ip import get_client_ip

    @router.get("/endpoint")
    async def endpoint(request: Request):
        client_ip = get_client_ip(request)
"""

import ipaddress
import logging
from functools import lru_cache

from fastapi import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_trusted_proxy_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """
    Parse and cache the trusted proxy IP networks from settings.

    Returns a list of IP networks that are trusted to provide
    accurate X-Forwarded-For headers.
    """
    networks = []

    if not settings.TRUSTED_PROXY_IPS:
        return networks

    for ip_str in settings.TRUSTED_PROXY_IPS.split(","):
        ip_str = ip_str.strip()
        if not ip_str:
            continue

        try:
            # Try parsing as a network (CIDR notation)
            if "/" in ip_str:
                network = ipaddress.ip_network(ip_str, strict=False)
            else:
                # Single IP - convert to /32 or /128 network
                addr = ipaddress.ip_address(ip_str)
                if isinstance(addr, ipaddress.IPv4Address):
                    network = ipaddress.ip_network(f"{ip_str}/32")
                else:
                    network = ipaddress.ip_network(f"{ip_str}/128")
            networks.append(network)
        except ValueError as e:
            logger.warning(f"Invalid trusted proxy IP/network '{ip_str}': {e}")

    return networks


def _is_trusted_proxy(ip_str: str) -> bool:
    """
    Check if an IP address is from a trusted proxy.

    Args:
        ip_str: IP address string to check

    Returns:
        True if the IP is in a trusted proxy network
    """
    try:
        ip_addr = ipaddress.ip_address(ip_str)
        trusted_networks = _get_trusted_proxy_networks()

        for network in trusted_networks:
            if ip_addr in network:
                return True
        return False
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """
    Get the real client IP address from a request.

    This function securely extracts the client IP, accounting for
    reverse proxies. It only trusts X-Forwarded-For headers when
    the direct connection is from a trusted proxy IP.

    Algorithm:
    1. Get the direct connection IP (request.client.host)
    2. If the direct IP is from a trusted proxy, parse X-Forwarded-For
    3. Walk X-Forwarded-For from right to left, finding the first
       non-trusted-proxy IP (the real client)
    4. Fall back to direct IP if parsing fails

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address string, or "unknown" if cannot be determined

    Security:
        - Only processes proxy headers from trusted proxy IPs
        - Validates IP format before returning
        - Handles IPv4 and IPv6 addresses
    """
    # Get direct connection IP
    direct_ip = request.client.host if request.client else None

    if not direct_ip:
        return "unknown"

    # If not from a trusted proxy, return the direct IP
    if not _is_trusted_proxy(direct_ip):
        return direct_ip

    # Check X-Forwarded-For header (standard)
    x_forwarded_for = request.headers.get("X-Forwarded-For")

    if x_forwarded_for:
        # X-Forwarded-For format: "client, proxy1, proxy2, ..."
        # Each proxy appends the IP of the connection it received
        # So we walk from right to left to find the first non-proxy IP
        ips = [ip.strip() for ip in x_forwarded_for.split(",")]

        # Walk from right to left (most recent additions first)
        for ip in reversed(ips):
            if not ip:
                continue

            # Validate it's a proper IP
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                # Invalid IP in chain, skip
                logger.warning(f"Invalid IP in X-Forwarded-For: {ip}")
                continue

            # If this IP is not a trusted proxy, it's the client
            if not _is_trusted_proxy(ip):
                return ip

        # All IPs in chain are trusted proxies - unusual, return leftmost
        if ips and ips[0]:
            try:
                ipaddress.ip_address(ips[0])
                return ips[0]
            except ValueError:
                pass

    # Check X-Real-IP header (Nginx specific)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        x_real_ip = x_real_ip.strip()
        try:
            ipaddress.ip_address(x_real_ip)
            return x_real_ip
        except ValueError:
            logger.warning(f"Invalid X-Real-IP header: {x_real_ip}")

    # Fall back to direct connection IP
    return direct_ip


def clear_trusted_proxy_cache() -> None:
    """
    Clear the cached trusted proxy networks.

    Call this if TRUSTED_PROXY_IPS setting changes at runtime
    (e.g., during testing).
    """
    _get_trusted_proxy_networks.cache_clear()
