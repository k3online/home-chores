from decimal import Decimal

from app.ledger import annotate_running_balances, indexed_value_cents, share_delta


class FakeEntry:
    def __init__(
        self,
        entry_id,
        child_user_id,
        entry_date,
        amount_cents,
        spy_close_cents,
        approval_state="approved",
        entry_type="deposit",
    ):
        self.id = entry_id
        self.child_user_id = child_user_id
        self.entry_date = entry_date
        self.amount_cents = amount_cents
        self.spy_close_cents = spy_close_cents
        self.approval_state = approval_state
        self.entry_type = entry_type


def test_indexed_value_cents_scales_deposits():
    assert indexed_value_cents(5000, 50000, 75000) == 7500


def test_share_delta_converts_withdrawals_to_negative_shares():
    shares = share_delta(-2000, 40000)

    assert shares == Decimal("-0.05")


def test_indexed_value_cents_returns_zero_without_prices():
    assert indexed_value_cents(1000, None, 50000) == 0
    assert indexed_value_cents(1000, 50000, None) == 0


def test_annotate_running_balances_preserves_display_order_and_splits_children():
    entries = [
        FakeEntry(3, 1, "2026-01-03", 1000, 50000),
        FakeEntry(2, 2, "2026-01-02", 2000, 50000),
        FakeEntry(1, 1, "2026-01-01", 5000, 50000),
        FakeEntry(4, 1, "2026-01-04", 999, None, "pending"),
        FakeEntry(5, 1, "2026-01-05", -2000, 50000, entry_type="withdrawal"),
    ]

    rows = annotate_running_balances(entries, latest_spy_cents=75000)

    assert [row["entry"].id for row in rows] == [3, 2, 1, 4, 5]
    assert rows[0]["share_delta"] == Decimal("0.02")
    assert rows[0]["share_balance"] == Decimal("0.12")
    assert rows[0]["running_current_cents"] == 6000
    assert rows[1]["share_balance"] == Decimal("0.04")
    assert rows[1]["running_current_cents"] == 2000
    assert rows[2]["share_balance"] == Decimal("0.10")
    assert rows[2]["running_current_cents"] == 5000
    assert rows[3]["share_delta"] is None
    assert rows[3]["running_current_cents"] is None
    assert rows[4]["share_delta"] == Decimal("-0.04")
    assert rows[4]["share_balance"] == Decimal("0.08")
    assert rows[4]["running_current_cents"] == 4000
