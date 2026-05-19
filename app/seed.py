import argparse

from sqlalchemy import select

from app.auth import create_user
from app.database import SessionLocal, init_db
from app.models import User


def main():
    parser = argparse.ArgumentParser(description="Create the initial admin user.")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--display-name", default="Admin")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.username == args.username)).scalar_one_or_none()
        if existing:
            print("User already exists: %s" % args.username)
            return
        create_user(db, args.username, args.display_name, args.password, "admin")
        db.commit()
        print("Created admin user: %s" % args.username)
    finally:
        db.close()


if __name__ == "__main__":
    main()
