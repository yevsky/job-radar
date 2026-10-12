from app.auth.hashing import hash_password, verify_password


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password('qwerty123')

    assert verify_password('qwerty123', hashed)


def test_verify_password_mismatch_returns_false() -> None:
    hashed = hash_password('qwerty123')

    assert not verify_password('asdfgh123', hashed)
