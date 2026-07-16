from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .security import validate_public_url

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}


def normalize_url(url: str, *, validate: bool = True, resolve_dns: bool = False) -> str:
    value = url.strip()
    if validate:
        validate_public_url(value, resolve_dns=resolve_dns)
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS
        and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query)), ""))
