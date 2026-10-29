"""Database Connection and Session Management Module.

Creates the SQLAlchemy engine, configures connection pooling with pool_pre_ping,
and provides safe connection verification and session factories.
"""

import logging
from typing import Generator, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with safe URL
try:
    # Validate configuration on startup
    settings.validate()
    db_url = settings.get_database_url()
except Exception as exc:
    logger.warning("Database configuration validation warning: %s", exc)
    db_url = settings.get_database_url()

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base model class for declarative definitions."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> Tuple[bool, str]:
    """Test the PostgreSQL connection without leaking passwords or sensitive info.

    Returns:
        Tuple[bool, str]: (is_successful, status_or_safe_error_message)
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return True, f"Connected successfully to database '{settings.db_name}' at {settings.db_host}:{settings.db_port}"
    except SQLAlchemyError as err:
        err_msg = str(err).splitlines()[0] if str(err) else "Connection failed"
        if settings.db_password and settings.db_password in err_msg:
            err_msg = err_msg.replace(settings.db_password, "***")
        logger.error("Database connection failure to %s:%s/%s: %s", settings.db_host, settings.db_port, settings.db_name, err_msg)
        safe_msg = (
            f"Unable to connect to database '{settings.db_name}' at {settings.db_host}:{settings.db_port} "
            f"({type(err).__name__}: {err_msg}). Verify database status and credentials in backend/.env"
        )
        return False, safe_msg
    except Exception as exc:
        return False, f"Unexpected error occurred while testing database connection: {type(exc).__name__}"
