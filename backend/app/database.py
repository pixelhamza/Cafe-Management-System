"""SQLAlchemy engine and session wiring."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

settings.database_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    # SQLite guards connections per thread by default; FastAPI serves
    # requests from a thread pool, so that guard has to be relaxed.
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
