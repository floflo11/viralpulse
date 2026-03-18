from viralpulse.auth import generate_api_key


def test_generate_api_key_format():
    key = generate_api_key()
    parts = key.split("_")
    assert len(parts) == 3  # "42_swift_tiger"
    assert parts[0].isdigit()
    assert parts[1].isalpha()
    assert parts[2].isalpha()
    # Must be valid for Telegram deep links (alphanumeric + underscore only)
    import re
    assert re.match(r'^[A-Za-z0-9_]+$', key)


def test_generate_api_key_readable():
    key = generate_api_key()
    assert len(key) < 25  # short enough to type
    assert len(key) > 8   # long enough to be unique-ish


def test_generate_mostly_unique():
    keys = {generate_api_key() for _ in range(50)}
    # 50 * 50 * 99 = 247,500 possible combos — 50 samples should be mostly unique
    assert len(keys) >= 40
