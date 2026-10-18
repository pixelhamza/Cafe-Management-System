"""Request and response shapes for menu items.

These rules are the single source of truth for what a valid menu item is.
The browser repeats the same checks in frontend/app.js so the user gets
immediate feedback, but the server never trusts that and re-validates here.
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_serializer, field_validator

MAX_NAME_LENGTH = 100
MAX_PRICE = Decimal("100000.00")


class Category(str, Enum):
    BEVERAGES = "Beverages"
    FOOD = "Food"
    DESSERTS = "Desserts"
    SNACKS = "Snacks"


class MenuItemCreate(BaseModel):
    name: str = Field(..., max_length=MAX_NAME_LENGTH)
    category: Category
    price: Decimal = Field(..., gt=0, le=MAX_PRICE, decimal_places=2)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Item name is required")
        return cleaned


class MenuItemRead(BaseModel):
    name: str
    category: Category
    price: Decimal

    @field_serializer("price")
    def serialize_price(self, price: Decimal) -> str:
        """Always render money with two decimal places."""
        return str(price.quantize(Decimal("0.01")))
