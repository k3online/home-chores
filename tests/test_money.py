import pytest

from app.money import cents_to_money, parse_money_to_cents, parse_spy_to_cents


def test_parse_money_to_cents_rounds_half_up():
    assert parse_money_to_cents("10") == 1000
    assert parse_money_to_cents("10.235") == 1024
    assert parse_money_to_cents("0.01") == 1


def test_parse_money_to_cents_rejects_invalid_input():
    with pytest.raises(ValueError):
        parse_money_to_cents("abc")


def test_parse_spy_to_cents_requires_positive_value():
    assert parse_spy_to_cents("500.25") == 50025
    with pytest.raises(ValueError):
        parse_spy_to_cents("0")


def test_cents_to_money_formats_negative_and_positive():
    assert cents_to_money(1234) == "$12.34"
    assert cents_to_money(-567) == "-$5.67"
    assert cents_to_money(None) == ""
