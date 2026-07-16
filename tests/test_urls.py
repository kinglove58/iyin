import pytest
from services.security import UnsafeUrlError, validate_public_url
from services.urls import normalize_url


def test_normalize_url_removes_tracking_and_fragment() -> None:
    assert normalize_url("HTTPS://Example.COM:443/a/?utm_source=x&b=2&a=1#part", resolve_dns=False) == (
        "https://example.com/a?a=1&b=2"
    )


@pytest.mark.security
@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/admin", "http://localhost:9000", "http://169.254.169.254/latest", "file:///etc/passwd"],
)
def test_ssrf_targets_are_blocked(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url, resolve_dns=False)


@pytest.mark.security
def test_credentials_in_url_are_blocked() -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url("https://user:secret@example.com", resolve_dns=False)
