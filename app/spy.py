from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import now_iso
from app.models import SpyPrice


def _date_str(value):
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def get_cached_spy_close(db: Session, price_date):
    price = db.get(SpyPrice, _date_str(price_date))
    return price.spy_close_cents if price else None


def set_spy_close(db: Session, price_date, spy_close_cents, source):
    price_date = _date_str(price_date)
    now = now_iso()
    price = db.get(SpyPrice, price_date)
    if price:
        price.spy_close_cents = spy_close_cents
        price.source = source
        price.updated_at = now
    else:
        price = SpyPrice(
            price_date=price_date,
            spy_close_cents=spy_close_cents,
            source=source,
            created_at=now,
            updated_at=now,
        )
        db.add(price)
    return price


def effective_target_date(price_date, now=None):
    target = datetime.strptime(_date_str(price_date), "%Y-%m-%d").date()
    eastern = ZoneInfo("America/New_York")
    now = now or datetime.now(eastern)
    if now.tzinfo is None:
        now = now.replace(tzinfo=eastern)
    else:
        now = now.astimezone(eastern)

    market_close_buffer = datetime.combine(now.date(), time(17, 0), tzinfo=eastern)
    if target >= now.date() and now < market_close_buffer:
        return now.date() - timedelta(days=1)
    return target


def fetch_spy_close_cents(price_date):
    import requests

    target = effective_target_date(price_date)
    start = target - timedelta(days=7)
    end = target + timedelta(days=2)
    response = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/SPY",
        params={
            "period1": int(datetime.combine(start, time.min, timezone.utc).timestamp()),
            "period2": int(datetime.combine(end, time.min, timezone.utc).timestamp()),
            "interval": "1d",
            "events": "history",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    if response.status_code == 429:
        raise RuntimeError("Yahoo Finance rate limited the SPY price request.")
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError("No SPY close data returned%s." % (": %s" % error if error else ""))

    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    candidates = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(timestamp, timezone.utc).date()
        if day <= target:
            candidates.append((day, close))
    if not candidates:
        raise RuntimeError("No SPY close found on or before %s." % target.isoformat())
    _, close = candidates[-1]
    return int(round(float(close) * 100))


def get_or_fetch_spy_close(db: Session, price_date):
    cached = get_cached_spy_close(db, price_date)
    if cached:
        return cached
    cents = fetch_spy_close_cents(price_date)
    set_spy_close(db, price_date, cents, "yfinance")
    return cents
