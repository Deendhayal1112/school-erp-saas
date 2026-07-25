"""
Tests for Pagination Engines.
"""

import pytest
from sqlalchemy import Column, Integer, String, select

from app.common.pagination import (
    CursorParams,
    OffsetParams,
    PageParams,
    paginate_by_cursor,
    paginate_by_offset,
    paginate_by_page,
)
from app.db.base import Base
from app.db.session import AsyncSessionLocal


class PaginationMockModel(Base):
    __tablename__ = "pagination_mock_models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)


@pytest.mark.asyncio
async def test_pagination_by_page_and_offset():
    # Setup test table structure dynamically in db
    async with AsyncSessionLocal() as session:
        # Create test records
        async with session.begin():
            # Check if tables exists or create them
            conn = await session.connection()
            await conn.run_sync(
                Base.metadata.create_all, tables=[PaginationMockModel.__table__]
            )

            # Clear old records
            await conn.execute(PaginationMockModel.__table__.delete())

            # Add 25 records
            session.add_all(
                [PaginationMockModel(id=i, name=f"Item {i}") for i in range(1, 26)]
            )

        # Test Page Number Pagination
        query = select(PaginationMockModel)
        params = PageParams(page=2, page_size=10)
        res = await paginate_by_page(session, query, params, "http://localhost/items")

        assert len(res["results"]) == 10
        assert res["pagination"]["total_records"] == 25
        assert res["pagination"]["total_pages"] == 3
        assert res["pagination"]["page"] == 2
        assert "page=3" in res["pagination"]["next"]
        assert "page=1" in res["pagination"]["previous"]

        # Test Offset Pagination
        offset_params = OffsetParams(offset=20, limit=10)
        offset_res = await paginate_by_offset(
            session, query, offset_params, "http://localhost/items"
        )
        assert len(offset_res["results"]) == 5
        assert offset_res["pagination"]["page"] == 3

        # Test Cursor Pagination
        cursor_params = CursorParams(limit=10)
        cursor_res = await paginate_by_cursor(
            session,
            query,
            cursor_params,
            PaginationMockModel.id,
            "http://localhost/items",
        )
        assert len(cursor_res["results"]) == 10
        assert cursor_res["pagination"]["next"] is not None
