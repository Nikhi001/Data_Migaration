"""Metadata API Router.

Provides read-only access to TTS metadata records stored in PostgreSQL:
- GET /api/v1/metadata: Paginated metadata retrieval with limit & offset
- GET /api/v1/metadata/count: Total record count directly queried from database
- GET /api/v1/metadata/columns: Available columns for UI display and filtering
"""

import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import MetaData, Table, func, select, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoSuchTableError, SQLAlchemyError

from app.config import settings
from app.database import engine, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metadata"])

# Cache for reflected table object
_table_cache: Optional[Table] = None


def get_metadata_table() -> Table:
    """Reflect and cache the target metadata table using SQLAlchemy."""
    global _table_cache
    if _table_cache is not None:
        return _table_cache

    try:
        meta = MetaData(schema=settings.metadata_schema)
        table = Table(
            settings.metadata_table,
            meta,
            autoload_with=engine,
        )
        _table_cache = table
        return table
    except NoSuchTableError:
        logger.error(
            "Table '%s' does not exist in schema '%s' on database '%s'.",
            settings.metadata_table,
            settings.metadata_schema,
            settings.db_name,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Configured metadata table '{settings.metadata_table}' in schema "
                f"'{settings.metadata_schema}' was not found on database '{settings.db_name}'. "
                f"Please verify METADATA_TABLE and METADATA_SCHEMA in backend/.env."
            ),
        )
    except SQLAlchemyError as exc:
        err_msg = str(exc).splitlines()[0] if str(exc) else "Connection failed"
        if settings.db_password and settings.db_password in err_msg:
            err_msg = err_msg.replace(settings.db_password, "***")
        logger.error(
            "Database error reflecting table '%s' on %s:%s/%s: %s (%s)",
            settings.metadata_table,
            settings.db_host,
            settings.db_port,
            settings.db_name,
            type(exc).__name__,
            err_msg,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Database service unavailable ({type(exc).__name__}). "
                f"Target: {settings.db_host}:{settings.db_port}/{settings.db_name}. "
                f"Reason: {err_msg}. Please check backend/.env and verify PostgreSQL is running."
            ),
        )


def serialize_cell(value: Any) -> Any:
    """Convert non-serializable database types (date, timedelta, Interval) to JSON-safe types."""
    if value is None:
        return None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return value


def serialize_record(table: Table, row: Any) -> Dict[str, Any]:
    """Serialize a database row mapping into a JSON-compatible dictionary."""
    mapping = row._mapping
    return {col.name: serialize_cell(mapping.get(col.name)) for col in table.columns}


@router.get(
    "",
    summary="Retrieve paginated TTS metadata records",
    response_description="Paginated list of metadata records",
)
def get_metadata(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of records to return (1-100)"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip (>= 0)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve metadata records with pagination.

    - limit: maximum rows to return (between 1 and 100, default: 50)
    - offset: rows to skip (default: 0)
    """
    table = get_metadata_table()

    # Determine stable order column
    order_col = None
    if "id" in table.c:
        order_col = table.c.id
    elif len(table.primary_key.columns) > 0:
        order_col = list(table.primary_key.columns)[0]
    else:
        order_col = table.columns[0]

    stmt = select(table).order_by(order_col).limit(limit).offset(offset)

    try:
        result = db.execute(stmt).fetchall()
        items = [serialize_record(table, row) for row in result]
        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "returned": len(items),
        }
    except SQLAlchemyError as exc:
        logger.error("Error executing metadata query: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metadata records from the database.",
        )


@router.get(
    "/count",
    summary="Get total number of metadata records",
    response_description="Total record count from PostgreSQL",
)
def get_metadata_count(
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    """Calculate the total number of records directly from PostgreSQL."""
    table = get_metadata_table()
    stmt = select(func.count()).select_from(table)

    try:
        count_val = db.execute(stmt).scalar() or 0
        return {"total_records": count_val}
    except SQLAlchemyError as exc:
        logger.error("Error executing count query: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve record count from the database.",
        )


@router.get(
    "/columns",
    summary="Get available columns in the metadata table",
    response_description="List of column names",
)
def get_columns() -> Dict[str, List[str]]:
    """Return the list of columns available in the metadata table."""
    table = get_metadata_table()
    return {"columns": [col.name for col in table.columns]}
