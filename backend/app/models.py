"""Database tables."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, TypeDecorator, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .schemas import MAX_NAME_LENGTH, TWO_PLACES


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


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Blank for a counter sale, so the bill is simply unlabelled.
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The GST rate this bill was charged at, copied in at the time of sale for
    # the same reason the lines copy their price: a past bill must not change
    # when the rate does.
    tax_percent: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )

    @property
    def subtotal(self) -> Decimal:
        """The items alone, summed in Python, deliberately.

        The price column is text (see DecimalText), so SQL SUM() would add
        strings together as floats. Decimal addition here stays exact.
        """
        return sum((item.line_total for item in self.items), Decimal("0.00"))

    @property
    def tax(self) -> Decimal:
        """GST on the subtotal, rounded to paise.

        ROUND_HALF_UP is named explicitly because Decimal rounds half to even
        by default, which would charge 18.06 on a 361.30 subtotal where a
        customer reading the bill expects 18.07.
        """
        charged = self.subtotal * self.tax_percent / Decimal("100")
        return charged.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        """What the customer pays: the items plus the tax on them."""
        return self.subtotal + self.tax


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    # The menu item this line came from, kept for reference only. Plain integer
    # rather than a foreign key: the name and price below are copied at the
    # time of sale, so a past bill must survive its menu item being edited or
    # deleted, and a real constraint would block that deletion instead.
    menu_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(TWO_PLACES)
