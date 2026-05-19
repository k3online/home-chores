import csv
import io

from app.dates import parse_import_date
from app.money import parse_money_to_cents


REQUIRED_COLUMNS = {"date", "chore", "amount"}
VALID_ENTRY_TYPES = {"deposit", "withdrawal"}


def parse_chore_csv(content):
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty.")

    fieldnames = {name.strip().lower() for name in reader.fieldnames if name}
    missing = sorted(REQUIRED_COLUMNS - fieldnames)
    if missing:
        raise ValueError("Missing required columns: %s." % ", ".join(missing))

    rows = []
    errors = []
    for line_number, row in enumerate(reader, start=2):
        normalized = {
            (key.strip().lower() if key else ""): (value.strip() if value else "")
            for key, value in row.items()
        }
        entry_date = normalized.get("date", "")
        entry_type = normalized.get("type", "deposit") or "deposit"
        chore = normalized.get("chore", "")
        amount = normalized.get("amount", "")

        if not entry_date:
            errors.append("Line %s: date is required." % line_number)
            continue
        try:
            entry_date = parse_import_date(entry_date)
        except ValueError as exc:
            errors.append("Line %s: %s" % (line_number, exc))
            continue
        if not chore:
            errors.append("Line %s: chore is required." % line_number)
            continue
        if entry_type not in VALID_ENTRY_TYPES:
            errors.append("Line %s: type must be deposit or withdrawal." % line_number)
            continue
        try:
            amount_cents = parse_money_to_cents(amount)
        except ValueError:
            errors.append("Line %s: amount is invalid." % line_number)
            continue
        if amount_cents <= 0:
            errors.append("Line %s: amount must be greater than zero." % line_number)
            continue
        if entry_type == "withdrawal":
            amount_cents = -amount_cents

        rows.append(
            {
                "entry_date": entry_date,
                "entry_type": entry_type,
                "chore": chore,
                "amount_cents": amount_cents,
            }
        )

    if errors:
        raise ValueError(" ".join(errors))
    if not rows:
        raise ValueError("CSV file has no chore rows.")
    return rows
