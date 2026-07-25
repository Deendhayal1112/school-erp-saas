"""
Pagination Engines for Database Queries.
"""

import base64
import json
import math
import uuid
from typing import Any, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PageParams(BaseModel):
    """Query parameters mapping standard Page Number pagination requests."""
    page: int = Field(1, ge=1, description="Active target page index (1-indexed).")
    page_size: int = Field(20, ge=1, le=100, description="Count limit of records returned per query page.")


class OffsetParams(BaseModel):
    """Query parameters mapping standard Offset-Limit pagination requests."""
    offset: int = Field(0, ge=0, description="Count offset to skip database records.")
    limit: int = Field(20, ge=1, le=100, description="Limit bound of returned database records.")


class CursorParams(BaseModel):
    """Query parameters mapping Cursor-based pagination requests."""
    cursor: str | None = Field(None, description="Encoded Base64 token cursor mapping page offsets.")
    limit: int = Field(20, ge=1, le=100, description="Limit bound of returned database records.")


async def paginate_by_page(
    session: AsyncSession,
    query: Select,
    params: PageParams,
    request_url: str | None = None,
) -> dict[str, Any]:
    """
    Executes standard Page Number pagination against a SQLAlchemy query.
    Returns results and pagination metadata.
    """
    page = params.page
    page_size = params.page_size

    # 1. Calculate total record count using subquery to support joins/groups correctly
    count_stmt = select(func.count()).select_from(query.subquery())
    count_res = await session.execute(count_stmt)
    total_records = count_res.scalar_one()

    # 2. Slice and fetch subset
    stmt = query.limit(page_size).offset((page - 1) * page_size)
    result_res = await session.execute(stmt)
    results = result_res.scalars().all()

    # 3. Calculate total pages
    total_pages = math.ceil(total_records / page_size) if total_records > 0 else 1

    # 4. Determine next/previous links
    next_link = None
    prev_link = None
    if request_url:
        clean_url = request_url.split("?")[0]
        if page < total_pages:
            next_link = f"{clean_url}?page={page + 1}&page_size={page_size}"
        if page > 1:
            prev_link = f"{clean_url}?page={page - 1}&page_size={page_size}"

    return {
        "results": list(results),
        "pagination": {
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "next": next_link,
            "previous": prev_link,
        },
    }


async def paginate_by_offset(
    session: AsyncSession,
    query: Select,
    params: OffsetParams,
    request_url: str | None = None,
) -> dict[str, Any]:
    """
    Executes Offset pagination against a SQLAlchemy query.
    """
    offset = params.offset
    limit = params.limit

    count_stmt = select(func.count()).select_from(query.subquery())
    count_res = await session.execute(count_stmt)
    total_records = count_res.scalar_one()

    stmt = query.limit(limit).offset(offset)
    result_res = await session.execute(stmt)
    results = result_res.scalars().all()

    total_pages = math.ceil(total_records / limit) if total_records > 0 else 1
    current_page = (offset // limit) + 1

    next_link = None
    prev_link = None
    if request_url:
        clean_url = request_url.split("?")[0]
        if offset + limit < total_records:
            next_link = f"{clean_url}?offset={offset + limit}&limit={limit}"
        if offset > 0:
            prev_link = f"{clean_url}?offset={max(0, offset - limit)}&limit={limit}"

    return {
        "results": list(results),
        "pagination": {
            "total_records": total_records,
            "page": current_page,
            "page_size": limit,
            "total_pages": total_pages,
            "next": next_link,
            "previous": prev_link,
        },
    }


async def paginate_by_cursor(
    session: AsyncSession,
    query: Select,
    params: CursorParams,
    unique_column: Any,
    request_url: str | None = None,
) -> dict[str, Any]:
    """
    Executes Cursor-based pagination sorted on unique_column.
    Cursor carries the serialized value of the last seen unique_column identifier.
    """
    limit = params.limit
    cursor_val = None

    if params.cursor:
        try:
            # Decode cursor base64 string
            decoded = base64.b64decode(params.cursor.encode()).decode()
            cursor_data = json.loads(decoded)
            cursor_val = cursor_data.get("last_val")
        except Exception:
            # Silently ignore malformed cursor
            pass

    # Count total matching records
    count_stmt = select(func.count()).select_from(query.subquery())
    count_res = await session.execute(count_stmt)
    total_records = count_res.scalar_one()

    # Filter by last seen unique value if cursor is active
    stmt = query
    if cursor_val is not None:
        stmt = stmt.where(unique_column > cursor_val)

    # Order by unique_column to ensure cursor sequencing and fetch limit + 1 to check for next pages
    stmt = stmt.order_by(unique_column.asc()).limit(limit + 1)
    result_res = await session.execute(stmt)
    results = list(result_res.scalars().all())

    has_more = len(results) > limit
    results_slice = results[:limit]

    # Generate next cursor
    next_cursor = None
    if has_more and results_slice:
        # Fetch the unique column value of the last record in current page
        last_item = results_slice[-1]
        last_val = getattr(last_item, unique_column.name, None)
        if last_val is not None:
            # Serialize
            if isinstance(last_val, uuid.UUID):
                last_val = str(last_val)
            cursor_data = {"last_val": last_val}
            encoded = base64.b64encode(json.dumps(cursor_data).encode()).decode()
            next_cursor = encoded

    next_link = None
    if next_cursor and request_url:
        clean_url = request_url.split("?")[0]
        next_link = f"{clean_url}?cursor={next_cursor}&limit={limit}"

    return {
        "results": results_slice,
        "pagination": {
            "total_records": total_records,
            "page": 1,
            "page_size": limit,
            "total_pages": math.ceil(total_records / limit) if total_records > 0 else 1,
            "next": next_link,
            "previous": None,  # Cursor pagination typically goes forward only
        },
    }
