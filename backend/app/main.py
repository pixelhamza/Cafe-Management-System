"""FastAPI application for the Cafe Management System."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import crud
from .database import Base, engine, get_db
from .errors import request_validation_handler
from .schemas import Category, MenuItemCreate, MenuItemRead

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the table if it is missing. The app still starts when the
    # database is unreachable; requests then fail with a clear 503.
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        logger.warning("Could not prepare the database at startup: %s", exc)
    yield


app = FastAPI(
    title="Cafe Management System API", version="0.2.0", lifespan=lifespan
)

# The frontend is served as static files from a different port in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, request_validation_handler)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Could not reach the database. Please try again."},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def list_categories() -> list[str]:
    """Lets the form populate its category options from one source of truth."""
    return [category.value for category in Category]


@app.get("/api/menu-items", response_model=list[MenuItemRead])
def list_menu_items(db: Session = Depends(get_db)) -> list:
    return crud.list_menu_items(db)


def _get_or_404(db: Session, item_id: int):
    record = crud.get_menu_item(db, item_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That menu item no longer exists. It may have been deleted.",
        )
    return record


def _reject_duplicate_name(
    db: Session, name: str, exclude_id: int | None = None
) -> None:
    """Two items sharing a name leave rows nobody can tell apart.

    Enforced here rather than as a unique constraint because the table already
    exists in deployed databases and the project has no migration tool.
    """
    if crud.find_by_name(db, name, exclude_id=exclude_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'A menu item named "{name}" already exists.',
        )


@app.post(
    "/api/menu-items",
    response_model=MenuItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_item(item: MenuItemCreate, db: Session = Depends(get_db)):
    _reject_duplicate_name(db, item.name)
    return crud.create_menu_item(db, item)


@app.put("/api/menu-items/{item_id}", response_model=MenuItemRead)
def update_menu_item(
    item_id: int, item: MenuItemCreate, db: Session = Depends(get_db)
):
    record = _get_or_404(db, item_id)
    _reject_duplicate_name(db, item.name, exclude_id=item_id)
    return crud.update_menu_item(db, record, item)


@app.delete("/api/menu-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(item_id: int, db: Session = Depends(get_db)) -> None:
    record = _get_or_404(db, item_id)
    crud.delete_menu_item(db, record)
