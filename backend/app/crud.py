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


def update_menu_item(db: Session, record: MenuItem, item: MenuItemCreate) -> MenuItem:
    record.name = item.name
    record.category = item.category.value
    record.price = item.price
    db.commit()
    db.refresh(record)
    return record


def list_menu_items(db: Session) -> list[MenuItem]:
    statement = select(MenuItem).order_by(MenuItem.created_at.desc(), MenuItem.id.desc())
    return list(db.scalars(statement))
