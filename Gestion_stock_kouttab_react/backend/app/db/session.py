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
        # `pre_ping` teste la connexion avant de la preter : indispensable avec
        # une base distante, qui peut couper une connexion inactive sans que le
        # client en soit informe.
        "pool_pre_ping": True,
        "pool_recycle": settings.db_pool_recycle,
        "echo": settings.app_debug and settings.app_env != "production",
    }
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine_kwargs.pop("pool_recycle", None)
    else:
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow
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
