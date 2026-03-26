from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="participant")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    reports: Mapped[list["DailyReport"]] = relationship(back_populates="user")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_instructions: Mapped[int] = mapped_column(default=0)
    is_complete: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="reports")
    listing_entries: Mapped[list["ListingEntry"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    instruction_entries: Mapped[list["InstructionEntry"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("user_id", "report_date"),)


class ListingEntry(Base):
    __tablename__ = "listing_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("daily_reports.id", ondelete="CASCADE"), nullable=False
    )
    country_code: Mapped[str] = mapped_column(String(10), nullable=False)
    listing_type: Mapped[str] = mapped_column(String(20), nullable=False, default="processed")
    # listing_type: "processed" (Обработано), "published" (Выставлено), "blocked" (Заблокировано)
    count: Mapped[int] = mapped_column(default=0)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped["DailyReport"] = relationship(back_populates="listing_entries")

    __table_args__ = (UniqueConstraint("report_id", "country_code", "listing_type"),)


class InstructionEntry(Base):
    __tablename__ = "instruction_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("daily_reports.id", ondelete="CASCADE"), nullable=False
    )
    country_code: Mapped[str] = mapped_column(String(10), nullable=False)
    count: Mapped[int] = mapped_column(default=0)

    report: Mapped["DailyReport"] = relationship(back_populates="instruction_entries")

    __table_args__ = (UniqueConstraint("report_id", "country_code"),)


# Listing type constants
LISTING_PROCESSED = "processed"
LISTING_PUBLISHED = "published"
LISTING_BLOCKED = "blocked"

LISTING_TYPE_LABELS = {
    LISTING_PROCESSED: "📋 Обработано",
    LISTING_PUBLISHED: "✅ Выставлено",
    LISTING_BLOCKED: "🚫 Заблокировано",
}
