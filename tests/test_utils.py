from bot.utils import parse_duration, locked_permissions, all_permissions

def test_parse_duration():
    assert parse_duration("30m") == 30
    assert parse_duration("2h") == 120
    assert parse_duration("1d") == 1440
    assert parse_duration("bad") == 60

def test_permissions():
    assert all(locked_permissions().values()) is False
    assert all(all_permissions().values()) is True
