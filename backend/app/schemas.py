"""Request and response shapes for menu items and orders.

These rules are the single source of truth for what a valid menu item and
a valid order are.
The browser repeats the same checks in frontend/app.js and frontend/orders.js
so the user gets immediate feedback, but the server never trusts that and
re-validates here.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

MAX_NAME_LENGTH = 100
MAX_PRICE = Decimal("100000.00")
MAX_CUSTOMER_NAME_LENGTH = 100
MAX_QUANTITY = 99
TWO_PLACES = Decimal("0.01")

# GST charged on a cafe bill, as a percentage. Stored per order as well (see
# models.Order.tax_percent) so that changing this figure never alters a bill
# that has already been issued.
GST_PERCENT = Decimal("5.00")


class Category(str, Enum):
    BEVERAGES = "Beverages"
    FOOD = "Food"
    DESSERTS = "Desserts"
    SNACKS = "Snacks"


class MenuItemCreate(BaseModel):
    name: str = Field(..., max_length=MAX_NAME_LENGTH)
    category: Category
    price: Decimal = Field(..., gt=0, le=MAX_PRICE, decimal_places=2)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        """Trims before max_length is applied.

        A mode="after" validator runs second, so the limit used to be checked
        against the raw value and a name that fits once its surrounding spaces
        are gone was rejected as too long.
        """
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Item name is required")
        return value


class MenuItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Category
    price: Decimal

    @field_serializer("price")
    def serialize_price(self, price: Decimal) -> str:
        """Always render money with two decimal places."""
        return str(price.quantize(TWO_PLACES))


class OrderLineCreate(BaseModel):
    menu_item_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1, le=MAX_QUANTITY)


class OrderCreate(BaseModel):
    customer_name: str | None = Field(
        default=None, max_length=MAX_CUSTOMER_NAME_LENGTH
    )
    items: list[OrderLineCreate] = Field(..., min_length=1)

    @field_validator("customer_name", mode="before")
    @classmethod
    def blank_name_means_none(cls, value: object) -> object:
        """A counter sale arrives as an empty box, not as a missing field."""
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("items")
    @classmethod
    def one_line_per_menu_item(
        cls, items: list[OrderLineCreate]
    ) -> list[OrderLineCreate]:
        """Keeps a bill from listing the same item on two lines.

        The browser raises the quantity of an existing line instead of adding
        a second one; this is the same rule, enforced server-side.
        """
        seen = {item.menu_item_id for item in items}
        if len(seen) != len(items):
            raise ValueError("Each menu item may appear only once in an order")
        return items


class OrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: int
    item_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    @field_serializer("unit_price", "line_total")
    def serialize_money(self, amount: Decimal) -> str:
        return str(amount.quantize(TWO_PLACES))


class OrderRead(BaseModel):
    """An order with its charges broken out.

    subtotal is the items, tax is the GST on them at tax_percent, and total is
    what the customer actually pays.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str | None
    created_at: datetime
    items: list[OrderLineRead]
    subtotal: Decimal
    tax_percent: Decimal
    tax: Decimal
    total: Decimal

    @field_serializer("subtotal", "tax", "total")
    def serialize_money(self, amount: Decimal) -> str:
        return str(amount.quantize(TWO_PLACES))

    @field_serializer("tax_percent")
    def serialize_tax_percent(self, percent: Decimal) -> str:
        """Sent as a number, not "5%", so the screen can label it itself."""
        return str(percent.quantize(TWO_PLACES))
