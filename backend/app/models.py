"""Database tables."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, String, Text, TypeDecorator, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .schemas import MAX_NAME_LENGTH

TWO_PLACES = Decimal("0.01")


class DecimalText(TypeDecorator):
    """Stores money as text so it stays exact.

    SQLite has no decimal type, and SQLAlchemy's Numeric falls back to float
    there, which cannot represent values like 0.10 exactly. Writing the
    Decimal out as a string and parsing it back avoids float entirely.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect) -> str | None:
        if value is None:
            return None
        return str(Decimal(value).quantize(TWO_PLACES))

    def process_result_value(self, value: str | None, dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
