from app.core.hashing import hash_password, verify_password


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password('qwerty123')

    assert verify_password('qwerty123', hashed)


def test_verify_password_mismatch_returns_false() -> None:
    hashed = hash_password('qwerty123')

    assert not verify_password('asdfgh123', hashed)


def test_same_password_produces_different_verifiable_hashes() -> None:
    h1 = hash_password('qwerty123')
    h2 = hash_password('qwerty123')

    assert h1 != h2
    assert verify_password('qwerty123', h1)
    assert verify_password('qwerty123', h2)
