from datetime import datetime
from zoneinfo import ZoneInfo

from app.spy import effective_target_date


def test_effective_target_date_uses_previous_day_before_market_close_for_today():
    now = datetime(2026, 5, 13, 12, 0, tzinfo=ZoneInfo("America/New_York"))

    assert effective_target_date("2026-05-13", now=now).isoformat() == "2026-05-12"


def test_effective_target_date_allows_today_after_market_close_buffer():
    now = datetime(2026, 5, 13, 18, 0, tzinfo=ZoneInfo("America/New_York"))

    assert effective_target_date("2026-05-13", now=now).isoformat() == "2026-05-13"
