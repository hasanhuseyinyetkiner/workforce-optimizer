"""Persistence model. Clock columns go through UtcDateTime (WFO-3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UtcDateTime


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    planning_timezone: Mapped[str] = mapped_column(String(80))


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_alias: Mapped[str] = mapped_column(String(120), unique=True)
    weekly_hour_cap: Mapped[int] = mapped_column(Integer)
    cost_per_hour: Mapped[int] = mapped_column(Integer)
    night_preference: Mapped[str] = mapped_column(String(16), default="neutral")
    weekend_preference: Mapped[str] = mapped_column(String(16), default="neutral")
    skills: Mapped[list[Skill]] = relationship(secondary="employee_skills", lazy="selectin")
    availability: Mapped[list[AvailabilityWindow]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="selectin"
    )
    time_off: Mapped[list[TimeOff]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="selectin"
    )


class AvailabilityWindow(Base):
    __tablename__ = "availability_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    start_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    end_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    employee: Mapped[Employee] = relationship(back_populates="availability")


class TimeOff(Base):
    __tablename__ = "time_off"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    start_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    end_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    reason: Mapped[str] = mapped_column(String(200), default="PTO")
    employee: Mapped[Employee] = relationship(back_populates="time_off")


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    start_local: Mapped[str] = mapped_column(String(5))
    end_local: Mapped[str] = mapped_column(String(5))


class ShiftInstance(Base):
    __tablename__ = "shift_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("shift_templates.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(80))
    local_date: Mapped[str] = mapped_column(String(10))
    start_local: Mapped[str] = mapped_column(String(5))
    end_local: Mapped[str] = mapped_column(String(5))
    start_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    end_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    required_count: Mapped[int] = mapped_column(Integer)
    is_night: Mapped[bool] = mapped_column(Boolean, default=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, default=False)
    requirements: Mapped[list[ShiftSkillRequirement]] = relationship(
        back_populates="shift", cascade="all, delete-orphan", lazy="selectin"
    )


class ShiftSkillRequirement(Base):
    __tablename__ = "shift_skill_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shift_instances.id", ondelete="CASCADE"))
    min_count: Mapped[int] = mapped_column(Integer)
    skill_names: Mapped[list[str]] = mapped_column(JSON)
    shift: Mapped[ShiftInstance] = relationship(back_populates="requirements")


class Ruleset(Base):
    __tablename__ = "rulesets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    min_rest_hours: Mapped[float] = mapped_column(Float)
    max_shift_hours: Mapped[int] = mapped_column(Integer)
    max_consecutive_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overtime_threshold_hours: Mapped[int] = mapped_column(Integer)
    relaxed_understaffing: Mapped[bool] = mapped_column(Boolean, default=False)
    weights: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    solver_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    objective: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_bound: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mode: Mapped[str] = mapped_column(String(32))
    random_seed: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[dict] = mapped_column(JSON)
    label: Mapped[str] = mapped_column(String(80), default="current")
    heartbeat_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    diagnostics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    objective_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ruleset_id: Mapped[int | None] = mapped_column(ForeignKey("rulesets.id"), nullable=True)
    schedule: Mapped[ScheduleVersion | None] = relationship(back_populates="run", uselist=False)


class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    optimization_run_id: Mapped[int] = mapped_column(ForeignKey("optimization_runs.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    validation: Mapped[dict] = mapped_column(JSON)
    run: Mapped[OptimizationRun] = relationship(back_populates="schedule")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan", lazy="selectin"
    )


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("schedule_version_id", "employee_id", "shift_instance_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(ForeignKey("schedule_versions.id", ondelete="CASCADE"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    shift_instance_id: Mapped[int] = mapped_column(ForeignKey("shift_instances.id"))
    schedule: Mapped[ScheduleVersion] = relationship(back_populates="assignments")
