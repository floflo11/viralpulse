from viralpulse.auth import generate_api_key


def test_generate_api_key():
    key = generate_api_key()
    assert key.startswith("vp_")
    assert len(key) == 27  # "vp_" + 24 chars


def test_generate_unique():
    keys = {generate_api_key() for _ in range(100)}
    assert len(keys) == 100
