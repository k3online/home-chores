from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_money_to_cents(value):
    try:
        cents = (Decimal(str(value).strip()) * Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, AttributeError):
        raise ValueError("Enter a valid dollar amount.")
    return int(cents)


def cents_to_money(cents):
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return "%s$%d.%02d" % (sign, cents // 100, cents % 100)


def decimal_to_shares(value):
    if value is None:
        return ""
    return "%0.6f" % value


def parse_spy_to_cents(value):
    cents = parse_money_to_cents(value)
    if cents <= 0:
        raise ValueError("SPY close must be greater than zero.")
    return cents
