"""Shared hard-constraint predicates. No OR-Tools imports."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.domain.problem import Employee, Problem, Shift
from app.domain.timeutil import rest_threshold


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def gap_too_short(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
    minimum: timedelta,
) -> bool:
    """True when two half-open intervals overlap or the gap is under the minimum rest."""
    if overlaps(start_a, end_a, start_b, end_b):
        return True
    if end_a <= start_b:
        return (start_b - end_a) < minimum
    if end_b <= start_a:
        return (start_a - end_b) < minimum
    return True


def rest_conflict(shift_a: Shift, shift_b: Shift, min_rest_hours: float) -> bool:
    return gap_too_short(
        shift_a.start,
        shift_a.end,
        shift_b.start,
        shift_b.end,
        rest_threshold(min_rest_hours),
    )


def covered_by(windows: tuple[tuple[datetime, datetime], ...], start: datetime, end: datetime) -> bool:
    return any(window_start <= start and end <= window_end for window_start, window_end in windows)


def employee_block_reason(employee: Employee, shift: Shift, problem: Problem) -> str | None:
    """Return a stable reason code when the employee cannot take the shift."""
    if shift.duration_hours > problem.rules.max_shift_hours:
        return "max_shift_hours"
    if not covered_by(employee.available, shift.start, shift.end):
        return "unavailable"
    if any(overlaps(shift.start, shift.end, start, end) for start, end in employee.time_off):
        return "time_off"
    minimum = rest_threshold(problem.rules.min_rest_hours)
    for prior in employee.prior_shifts:
        if gap_too_short(shift.start, shift.end, prior.start, prior.end, minimum):
            return "prior_conflict"
    return None


def week_key(iso_date: str) -> tuple[int, int]:
    parsed = date.fromisoformat(iso_date)
    iso = parsed.isocalendar()
    return (iso.year, iso.week)


def horizon_dates(problem: Problem) -> list[date]:
    if not problem.shifts and not any(employee.prior_shifts for employee in problem.employees):
        return []
    dates: list[date] = [date.fromisoformat(shift.local_start_date) for shift in problem.shifts]
    for employee in problem.employees:
        dates.extend(date.fromisoformat(prior.local_start_date) for prior in employee.prior_shifts)
    start, end = min(dates), max(dates)
    span: list[date] = []
    cursor = start
    while cursor <= end:
        span.append(cursor)
        cursor += timedelta(days=1)
    return span
