from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Entry, SpyPrice, User


def money_from_shares_cents(shares, spy_close_cents):
    if shares is None or not spy_close_cents:
        return None
    value = shares * Decimal(spy_close_cents)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def share_delta(amount_cents, spy_close_cents):
    if not spy_close_cents:
        return None
    return Decimal(amount_cents) / Decimal(spy_close_cents)


def indexed_value_cents(amount_cents, entry_spy_close_cents, latest_spy_close_cents):
    shares = share_delta(amount_cents, entry_spy_close_cents)
    value = money_from_shares_cents(shares, latest_spy_close_cents)
    return value or 0


def latest_spy_close_cents(db: Session):
    price = db.execute(
        select(SpyPrice).order_by(SpyPrice.price_date.desc()).limit(1)
    ).scalar_one_or_none()
    if price:
        return price.spy_close_cents

    entry = db.execute(
        select(Entry)
        .where(Entry.approval_state == "approved", Entry.spy_close_cents.is_not(None))
        .order_by(Entry.entry_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if entry:
        return entry.spy_close_cents
    return None


def user_balance(db: Session, user_id):
    latest = latest_spy_close_cents(db)
    entries = db.execute(
        select(Entry).where(
            Entry.child_user_id == user_id,
            Entry.approval_state == "approved",
        )
    ).scalars()
    principal = 0
    shares = Decimal("0")
    for entry in entries:
        delta = share_delta(entry.amount_cents, entry.spy_close_cents)
        if delta is None:
            continue
        principal += entry.amount_cents
        shares += delta
    current = money_from_shares_cents(shares, latest) or 0
    return {
        "principal_cents": principal,
        "current_cents": current,
        "latest_spy_cents": latest,
        "share_balance": shares,
    }


def all_kid_balances(db: Session):
    kids = db.execute(select(User).where(User.role == "kid").order_by(User.display_name)).scalars()
    return [(kid, user_balance(db, kid.id)) for kid in kids]


def annotate_running_balances(entries, latest_spy_cents):
    """Return display rows with running balances calculated in ledger order.

    Running balances are per child, chronological by entry date/id, and include
    approved entries only. The returned rows preserve the input display order.
    """
    entries = list(entries)
    ledger_order = sorted(entries, key=lambda entry: (entry.child_user_id, entry.entry_date, entry.id))
    principal_by_child = {}
    shares_by_child = {}
    annotations = {}

    for entry in ledger_order:
        child_id = entry.child_user_id
        principal_by_child.setdefault(child_id, 0)
        shares_by_child.setdefault(child_id, Decimal("0"))

        row_share_delta = None
        row_share_balance = shares_by_child[child_id]
        row_balance_cents = None
        if entry.approval_state == "approved":
            row_share_delta = share_delta(entry.amount_cents, entry.spy_close_cents)
            if row_share_delta is not None:
                principal_by_child[child_id] += entry.amount_cents
                shares_by_child[child_id] += row_share_delta
                row_share_balance = shares_by_child[child_id]
                row_balance_cents = money_from_shares_cents(row_share_balance, entry.spy_close_cents)

        annotations[entry.id] = {
            "entry": entry,
            "share_delta": row_share_delta,
            "share_balance": row_share_balance,
            "running_principal_cents": principal_by_child[child_id],
            "running_current_cents": row_balance_cents,
        }

    return [annotations[entry.id] for entry in entries]
