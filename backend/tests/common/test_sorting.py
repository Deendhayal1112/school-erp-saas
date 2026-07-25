"""
Tests for SQLAlchemy Sorting Engine.
"""

import pytest
from sqlalchemy import Column, Integer, String, select

from app.common.sorting import apply_sorting
from app.db.base import Base
from app.db.session import AsyncSessionLocal


class SortMockModel(Base):
    __tablename__ = "sort_mock_models"
    id = Column(Integer, primary_key=True)
    rank = Column(Integer, nullable=False)
    label = Column(String(50), nullable=False)


@pytest.mark.asyncio
async def test_apply_sorting():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(Base.metadata.create_all, tables=[SortMockModel.__table__])
            await conn.execute(SortMockModel.__table__.delete())

            session.add_all([
                SortMockModel(id=1, rank=10, label="Alpha"),
                SortMockModel(id=2, rank=5, label="Beta"),
                SortMockModel(id=3, rank=20, label="Gamma"),
            ])

        # Test whitelist sort asc
        query = select(SortMockModel)
        q = apply_sorting(query, SortMockModel, "rank", sortable_fields=["rank"])
        res = await session.execute(q)
        results = res.scalars().all()
        assert results[0].rank == 5
        assert results[2].rank == 20

        # Test whitelist sort desc
        q = apply_sorting(query, SortMockModel, "-rank", sortable_fields=["rank"])
        res = await session.execute(q)
        results = res.scalars().all()
        assert results[0].rank == 20
        assert results[2].rank == 5

        # Test ignored sort field not in whitelist
        q = apply_sorting(query, SortMockModel, "label", sortable_fields=["rank"])
        res = await session.execute(q)
        results = res.scalars().all()
        # Should fallback to default sorting or preserve original order (id order)
        assert results[0].id == 1
