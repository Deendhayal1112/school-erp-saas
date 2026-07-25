"""
Tests for SQLAlchemy Filtering Engine.
"""

import pytest
from sqlalchemy import Column, Integer, String, select

from app.common.filters import apply_filters
from app.db.base import Base
from app.db.session import AsyncSessionLocal


class FilterMockModel(Base):
    __tablename__ = "filter_mock_models"
    id = Column(Integer, primary_key=True)
    title = Column(String(50), nullable=False)
    category = Column(String(50), nullable=True)


@pytest.mark.asyncio
async def test_apply_filters():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(
                Base.metadata.create_all, tables=[FilterMockModel.__table__]
            )
            await conn.execute(FilterMockModel.__table__.delete())

            session.add_all(
                [
                    FilterMockModel(id=1, title="Math Book", category="Education"),
                    FilterMockModel(id=2, title="Science Book", category="Education"),
                    FilterMockModel(
                        id=3, title="Gaming Console", category="Entertainment"
                    ),
                ]
            )

        # Test Exact Match
        query = select(FilterMockModel)
        q = apply_filters(query, FilterMockModel, {"category__exact": "Education"})
        res = await session.execute(q)
        results = res.scalars().all()
        assert len(results) == 2

        # Test Contains Match
        q = apply_filters(query, FilterMockModel, {"title__contains": "Book"})
        res = await session.execute(q)
        results = res.scalars().all()
        assert len(results) == 2

        # Test In Match
        q = apply_filters(
            query, FilterMockModel, {"category__in": ["Education", "Entertainment"]}
        )
        res = await session.execute(q)
        results = res.scalars().all()
        assert len(results) == 3
