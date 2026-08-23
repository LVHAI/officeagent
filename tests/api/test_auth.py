from app.core.auth import hash_password, verify_password


def test_password_hash_is_not_plaintext():
    encoded = hash_password("correct-horse-battery")
    assert encoded != "correct-horse-battery"
    assert verify_password("correct-horse-battery", encoded)


def test_password_hash_rejects_wrong_password():
    encoded = hash_password("correct-horse-battery")
    assert not verify_password("wrong-password", encoded)


def test_password_hash_uses_unique_salt():
    first = hash_password("correct-horse-battery")
    second = hash_password("correct-horse-battery")
    assert first != second
