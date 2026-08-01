import uuid
from datetime import date, time

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.academic_calendar.enums import (
    CalendarEventType,
    DayOfWeek,
    HolidayType,
)


class WorkingDay(BaseEntity):
    """
    SQLAlchemy Model representing the configured working days of the week for an academic year.
    """

    __tablename__ = "working_days"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[DayOfWeek] = mapped_column(
        Enum(DayOfWeek, name="calendar_day_of_week"), nullable=False
    )
    is_working: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    default_break_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")


class Holiday(BaseEntity):
    """
    SQLAlchemy Model representing public, regional, school festivals, or emergency holidays.
    """

    __tablename__ = "holidays"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    holiday_type: Mapped[HolidayType] = mapped_column(
        Enum(HolidayType, name="calendar_holiday_type"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")


class SpecialWorkingDay(BaseEntity):
    """
    SQLAlchemy Model representing custom override working days (e.g. Saturdays running on a weekday timetable).
    """

    __tablename__ = "special_working_days"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")


class AcademicCalendar(BaseEntity):
    """
    SQLAlchemy Model representing day-by-day schedule metadata generated for the school academic year.
    """

    __tablename__ = "academic_calendar"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    event_name: Mapped[str] = mapped_column(String(150), nullable=False)
    event_type: Mapped[CalendarEventType] = mapped_column(
        Enum(CalendarEventType, name="calendar_event_type"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    holiday_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    working_day_flag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")
    term = relationship("Term")


# Unique Constraints and Indexes
Index(
    "ix_uq_school_ay_day_of_week",
    WorkingDay.school_id,
    WorkingDay.academic_year_id,
    WorkingDay.day_of_week,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_ay_calendar_date",
    AcademicCalendar.school_id,
    AcademicCalendar.academic_year_id,
    AcademicCalendar.date,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_ay_special_date",
    SpecialWorkingDay.school_id,
    SpecialWorkingDay.academic_year_id,
    SpecialWorkingDay.date,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
