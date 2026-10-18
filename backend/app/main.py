"""FastAPI application for the Cafe Management System.

Menu items are validated here but not stored yet; persistence to PostgreSQL
is the next subtask.
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .errors import request_validation_handler
from .schemas import Category, MenuItemCreate, MenuItemRead

app = FastAPI(title="Cafe Management System API", version="0.1.0")

# The frontend is served as static files from a different port in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, request_validation_handler)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def list_categories() -> list[str]:
    """Lets the form populate its category options from one source of truth."""
    return [category.value for category in Category]


@app.post("/api/menu-items", response_model=MenuItemRead)
def create_menu_item(item: MenuItemCreate) -> MenuItemCreate:
    """Validate a menu item.

    Returns 200 with the cleaned item. This becomes a 201 once the item is
    actually written to the database in the next subtask.
    """
    return item
