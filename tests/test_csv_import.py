import pytest

from app.csv_import import parse_chore_csv


def test_parse_chore_csv_accepts_required_columns():
    rows = parse_chore_csv(b"date,chore,amount\n2026-05-01,Dishes,3.50\n")

    assert rows == [
        {
            "entry_date": "2026-05-01",
            "entry_type": "deposit",
            "chore": "Dishes",
            "amount_cents": 350,
        }
    ]


def test_parse_chore_csv_accepts_withdrawals():
    rows = parse_chore_csv(
        b"date,type,chore,amount\n2026-05-01,deposit,Dishes,3.50\n2026-05-02,withdrawal,Cash out,2.00\n"
    )

    assert rows[0]["entry_type"] == "deposit"
    assert rows[0]["amount_cents"] == 350
    assert rows[1]["entry_type"] == "withdrawal"
    assert rows[1]["amount_cents"] == -200


def test_parse_chore_csv_normalizes_slash_dates():
    rows = parse_chore_csv(b"date,type,chore,amount\n5/1/2026,deposit,Dishes,3.50\n")

    assert rows[0]["entry_date"] == "2026-05-01"


def test_parse_chore_csv_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing required columns"):
        parse_chore_csv(b"date,amount\n2026-05-01,3.50\n")


def test_parse_chore_csv_rejects_bad_rows():
    with pytest.raises(ValueError, match="amount is invalid"):
        parse_chore_csv(b"date,chore,amount\n2026-05-01,Dishes,nope\n")


def test_parse_chore_csv_rejects_bad_type():
    with pytest.raises(ValueError, match="type must be deposit or withdrawal"):
        parse_chore_csv(b"date,type,chore,amount\n2026-05-01,bonus,Dishes,3.50\n")
