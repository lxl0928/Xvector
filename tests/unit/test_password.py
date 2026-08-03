from xvector.auth.password import generate_salt, hash_password, verify_password


def test_password_hash_verify():
    salt = generate_salt()
    h = hash_password("secret", salt, iterations=1000)
    assert verify_password("secret", salt, h, iterations=1000)
    assert not verify_password("wrong", salt, h, iterations=1000)
