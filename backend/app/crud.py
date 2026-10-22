"""Database reads and writes for menu items and orders."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MenuItem, Order, OrderItem
from .schemas import GST_PERCENT, MenuItemCreate, OrderCreate


def create_menu_item(db: Session, item: MenuItemCreate) -> MenuItem:
    record = MenuItem(
        name=item.name, category=item.category.value, price=item.price
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_menu_item(db: Session, item_id: int) -> MenuItem | None:
    return db.get(MenuItem, item_id)


def find_by_name(db: Session, name: str, exclude_id: int | None = None) -> MenuItem | None:
    """Looks for an item already using this name.

    exclude_id leaves the item being edited out of the search, so saving an
    item without renaming it is not a clash with itself.
    """
    statement = select(MenuItem).where(MenuItem.name == name)
    if exclude_id is not None:
        statement = statement.where(MenuItem.id != exclude_id)
    return db.scalars(statement).first()


def update_menu_item(db: Session, record: MenuItem, item: MenuItemCreate) -> MenuItem:
    record.name = item.name
    record.category = item.category.value
    record.price = item.price
    db.commit()
    db.refresh(record)
    return record


def delete_menu_item(db: Session, record: MenuItem) -> None:
    db.delete(record)
    db.commit()


def list_menu_items(db: Session) -> list[MenuItem]:
    statement = select(MenuItem).order_by(MenuItem.created_at.desc(), MenuItem.id.desc())
    return list(db.scalars(statement))


def find_menu_items(db: Session, item_ids: list[int]) -> dict[int, MenuItem]:
    """Fetches the ordered items in one query, keyed by id.

    Ids with no row are simply absent from the result; the caller decides
    what to do about them.
    """
    statement = select(MenuItem).where(MenuItem.id.in_(item_ids))
    return {record.id: record for record in db.scalars(statement)}


def create_order(
    db: Session, order: OrderCreate, menu_items: dict[int, MenuItem]
) -> Order:
    """Saves an order and its lines in one transaction.

    The item name and unit price are copied onto each line rather than read
    through the menu item, and the GST rate is copied onto the order, so a bill
    keeps showing what was actually charged after the menu or the rate changes.
    """
    record = Order(
        customer_name=order.customer_name,
        tax_percent=GST_PERCENT,
        items=[
            OrderItem(
                menu_item_id=line.menu_item_id,
                item_name=menu_items[line.menu_item_id].name,
                unit_price=menu_items[line.menu_item_id].price,
                quantity=line.quantity,
            )
            for line in order.items
        ],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
