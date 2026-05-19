from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    entries = relationship("Entry", foreign_keys="Entry.child_user_id", back_populates="child")

    __table_args__ = (CheckConstraint("role IN ('admin', 'kid')", name="ck_users_role"),)


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    entry_date: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String, nullable=False)
    chore: Mapped[str] = mapped_column(Text, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_state: Mapped[str] = mapped_column(String, nullable=False, index=True)
    spy_close_cents: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[str] = mapped_column(String, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    child = relationship("User", foreign_keys=[child_user_id], back_populates="entries")
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        CheckConstraint("entry_type IN ('deposit', 'withdrawal')", name="ck_entries_type"),
        CheckConstraint(
            "approval_state IN ('pending', 'approved', 'rejected')",
            name="ck_entries_approval_state",
        ),
    )


class SpyPrice(Base):
    __tablename__ = "spy_prices"

    price_date: Mapped[str] = mapped_column(String, primary_key=True)
    spy_close_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("source IN ('yfinance', 'manual')", name="ck_spy_prices_source"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    old_value_json: Mapped[str] = mapped_column(Text, nullable=True)
    new_value_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    actor = relationship("User")
