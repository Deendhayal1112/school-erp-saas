import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.timetable_generator.enums import (
    JobStatus,
    ResultStatus,
    RuleType,
)


class GenerationJob(BaseEntity):
    """
    SQLAlchemy Model representing a timetable generation task/job.
    """

    __tablename__ = "generation_jobs"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="timetable_job_status"),
        default=JobStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_classes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_teachers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_subjects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_entries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_entries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")
    term = relationship("Term")
    logs = relationship("GenerationLog", back_populates="job", cascade="all, delete-orphan")
    results = relationship("GenerationResult", back_populates="job", cascade="all, delete-orphan")


class GenerationRule(BaseEntity):
    """
    SQLAlchemy Model storing specialized overrides or configuration metadata for generation.
    """

    __tablename__ = "generation_rules"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_type: Mapped[RuleType] = mapped_column(
        Enum(RuleType, name="timetable_rule_type"), nullable=False
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")
    term = relationship("Term")


class GenerationResult(BaseEntity):
    """
    SQLAlchemy Model representing the schedule outputs produced by a generator job run.
    """

    __tablename__ = "generation_results"

    generation_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timetable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_timetables.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[ResultStatus] = mapped_column(
        Enum(ResultStatus, name="timetable_result_status"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    job = relationship("GenerationJob", back_populates="results")
    school = relationship("School")
    timetable = relationship("ClassTimetable")


class GenerationLog(BaseEntity):
    """
    SQLAlchemy Model recording detailed logs and metrics produced during generator run execution.
    """

    __tablename__ = "generation_logs"

    generation_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    log_level: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job = relationship("GenerationJob", back_populates="logs")
    school = relationship("School")
