from typing import Any, Generic, Sequence, Type, TypeVar
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base
from app.exceptions import DatabaseError, DuplicateEntityError

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic Base Repository pattern implementing basic CRUD queries.
    Utilizes type hints, generics, and handles core SQL exceptions.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, entity: ModelType) -> ModelType:
        """Saves a new entity database record."""
        try:
            self.session.add(entity)
            await self.session.flush()
            return entity
        except IntegrityError as e:
            await self.session.rollback()
            raise DuplicateEntityError(f"Database record collision: {str(e)}") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Failed to insert database entity: {str(e)}") from e

    async def get_by_id(self, id: Any) -> ModelType | None:
        """Retrieves an entity database record matching a primary key."""
        try:
            stmt = select(self.model).where(self.model.id == id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to query database entity by ID: {str(e)}") from e

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Retrieves a list sequence of entity database records."""
        try:
            stmt = select(self.model).offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to fetch database entity sequence: {str(e)}") from e

    async def update(self, entity: ModelType) -> ModelType:
        """Updates an existing entity database record."""
        try:
            self.session.add(entity)
            await self.session.flush()
            return entity
        except IntegrityError as e:
            await self.session.rollback()
            raise DuplicateEntityError(f"Database record collision during update: {str(e)}") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Failed to update database entity: {str(e)}") from e

    async def delete(self, entity: ModelType) -> None:
        """Hard-deletes an entity database record."""
        try:
            await self.session.delete(entity)
            await self.session.flush()
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Failed to delete database entity: {str(e)}") from e

    async def exists(self, id: Any) -> bool:
        """Checks if a record with the specified ID exists."""
        try:
            stmt = select(self.model.id).where(self.model.id == id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to check database record existence: {str(e)}") from e

    async def count(self) -> int:
        """Counts total active database records for this model."""
        try:
            stmt = select(func.count()).select_from(self.model)
            result = await self.session.execute(stmt)
            return result.scalar_one()
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to count database records: {str(e)}") from e
