"""
URL Validator - SSRF Protection

Validates URLs to prevent Server-Side Request Forgery (SSRF) attacks.
Blocks requests to internal networks, localhost, cloud metadata endpoints.

Usage:
    from app.services.url_validator import is_safe_url, validate_url

    if not is_safe_url(user_provided_url):
        raise ValueError("URL blocked for security reasons")
"""

import socket
from ipaddress import ip_address, IPv4Address, IPv6Address
from urllib.parse import urlparse
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

# Blocked hostnames (case-insensitive)
BLOCKED_HOSTNAMES = {
    'localhost',
    'localhost.localdomain',
    'local',
    '127.0.0.1',
    '::1',
    '0.0.0.0',
    # AWS metadata
    '169.254.169.254',
    # GCP metadata
    'metadata.google.internal',
    'metadata',
    # Azure metadata
    '169.254.169.254',
    # Kubernetes
    'kubernetes',
    'kubernetes.default',
    'kubernetes.default.svc',
}

# Blocked URL schemes
ALLOWED_SCHEMES = {'http', 'https'}


def is_private_ip(ip_str: str) -> bool:
    """Check if IP address is private/internal."""
    try:
        ip = ip_address(ip_str)
        return (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_multicast or
            ip.is_reserved or
            ip.is_unspecified
        )
    except ValueError:
        return False


def resolve_hostname(hostname: str) -> Optional[str]:
    """Resolve hostname to IP address for validation."""
    try:
        # Get first IP address for hostname
        result = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if result:
            return result[0][4][0]
    except (socket.gaierror, socket.herror, socket.timeout):
        pass
    return None


def is_safe_url(url: str, resolve_dns: bool = True) -> bool:
    """
    Validate URL is not pointing to internal/private resources.

    Args:
        url: URL to validate
        resolve_dns: Whether to resolve DNS and check IP (slower but more secure)

    Returns:
        True if URL is safe to request, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Block non-HTTP(S) schemes
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            logger.warning("Blocked URL with invalid scheme", url=url, scheme=parsed.scheme)
            return False

        hostname = parsed.hostname
        if not hostname:
            logger.warning("Blocked URL with no hostname", url=url)
            return False

        hostname_lower = hostname.lower()

        # Block known dangerous hostnames
        if hostname_lower in BLOCKED_HOSTNAMES:
            logger.warning("Blocked URL with dangerous hostname", url=url, hostname=hostname)
            return False

        # Block .local domains
        if hostname_lower.endswith('.local') or hostname_lower.endswith('.internal'):
            logger.warning("Blocked URL with internal domain", url=url, hostname=hostname)
            return False

        # Check if hostname is a direct IP address
        if is_private_ip(hostname):
            logger.warning("Blocked URL with private IP", url=url, ip=hostname)
            return False

        # Optionally resolve DNS and check resulting IP
        if resolve_dns:
            resolved_ip = resolve_hostname(hostname)
            if resolved_ip and is_private_ip(resolved_ip):
                logger.warning(
                    "Blocked URL resolving to private IP",
                    url=url,
                    hostname=hostname,
                    resolved_ip=resolved_ip
                )
                return False

        return True

    except Exception as e:
        logger.warning("URL validation failed", url=url, error=str(e))
        return False


def validate_url(url: str, resolve_dns: bool = True) -> str:
    """
    Validate URL and return normalized form.

    Args:
        url: URL to validate

    Returns:
        Normalized URL if safe

    Raises:
        ValueError: If URL is unsafe
    """
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    url = url.rstrip('/')

    if not is_safe_url(url, resolve_dns=resolve_dns):
        raise ValueError(f"URL blocked for security reasons: {url}")

    return url


# Convenience function for scrapers
def validate_website_url(website: str) -> str:
    """
    Validate a website URL for scraping.

    Args:
        website: Website URL (e.g., "acme.com" or "https://acme.com")

    Returns:
        Validated and normalized URL

    Raises:
        ValueError: If URL is unsafe to scrape
    """
    return validate_url(website, resolve_dns=True)
