import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    pass


BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.aws.internal"}


def validate_public_url(url: str, *, resolve_dns: bool = True) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("Only absolute HTTP and HTTPS URLs are accepted")
    host = parsed.hostname.rstrip(".").lower()
    if host in BLOCKED_HOSTS or host.endswith(".localhost"):
        raise UnsafeUrlError("Local and metadata hosts are blocked")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URLs containing credentials are blocked")
    addresses: set[str] = set()
    try:
        addresses.add(str(ipaddress.ip_address(host)))
    except ValueError:
        if resolve_dns:
            try:
                addresses.update(str(info[4][0]) for info in socket.getaddrinfo(host, None))
            except socket.gaierror as exc:
                raise UnsafeUrlError("The hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise UnsafeUrlError("Private, loopback, reserved, and link-local addresses are blocked")
        if ip in ipaddress.ip_network("169.254.169.254/32"):
            raise UnsafeUrlError("Cloud metadata endpoints are blocked")
    return url
