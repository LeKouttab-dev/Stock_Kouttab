"""SQLAlchemy engine + session factory + FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logger import get_logger


logger = get_logger("db")


def _build_engine() -> Engine:
    url = settings.database_url
    connect_args: dict = {}
    engine_kwargs: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "echo": settings.app_debug and settings.app_env != "production",
    }
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine_kwargs.pop("pool_recycle", None)
    else:
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10
    return create_engine(url, connect_args=connect_args, **engine_kwargs)


engine: Engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
