"""Database reads and writes for menu items."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MenuItem
from .schemas import MenuItemCreate


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
