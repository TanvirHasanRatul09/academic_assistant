from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_database_engine(database_url: str | None = None):  # type: ignore[no-untyped-def]
    url = database_url or get_settings().database_url
    options = {"pool_pre_ping": True}
    if not url.startswith("sqlite"):
        options.update(pool_recycle=1800, pool_size=5, max_overflow=5, pool_timeout=10)
    return create_engine(url, **options)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


