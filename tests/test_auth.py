from apps.api.afs.auth import hash_password, verify_password


def test_password_hash_is_strong_and_verifiable() -> None:
    hashed = hash_password("a sufficiently long test password")
    assert hashed.startswith("$argon2")
    assert verify_password("a sufficiently long test password", hashed)
    assert not verify_password("incorrect password", hashed)
