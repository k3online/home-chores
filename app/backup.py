import csv
import shutil
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import BACKUP_DIR, DB_PATH
from app.models import Entry, User


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def backup_database():
    BACKUP_DIR.mkdir(exist_ok=True)
    destination = BACKUP_DIR / ("chore_bank-%s.sqlite" % timestamp())
    if not DB_PATH.exists():
        raise FileNotFoundError("Database has not been created yet.")
    shutil.copy2(str(DB_PATH), str(destination))
    return destination


def export_entries_csv(db: Session, output_file):
    rows = db.execute(
        select(Entry, User)
        .join(User, Entry.child_user_id == User.id)
        .order_by(Entry.entry_date.desc(), Entry.id.desc())
    ).all()
    with open(output_file, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "child",
                "entry_date",
                "entry_type",
                "chore",
                "amount_cents",
                "approval_state",
                "spy_close_cents",
                "notes",
                "admin_notes",
                "approved_at",
                "created_at",
            ]
        )
        for entry, child in rows:
            writer.writerow(
                [
                    entry.id,
                    child.display_name,
                    entry.entry_date,
                    entry.entry_type,
                    entry.chore or "",
                    entry.amount_cents,
                    entry.approval_state,
                    entry.spy_close_cents or "",
                    entry.notes or "",
                    entry.admin_notes or "",
                    entry.approved_at or "",
                    entry.created_at,
                ]
            )
    return output_file
