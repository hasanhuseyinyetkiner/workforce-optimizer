"""Planning-timezone conversion. DST gaps and overlaps are rejected."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.errors import DomainError


def require_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise DomainError("invalid_timezone", f"Unknown planning timezone: {name}") from exc


def _wall(value: datetime) -> tuple[int, int, int, int, int, int]:
    return (value.year, value.month, value.day, value.hour, value.minute, value.second)


def local_wall_to_utc(local_naive: datetime, timezone_name: str) -> datetime:
    """Convert a planning-local wall time to aware UTC.

    Nonexistent times (spring-forward gap) and ambiguous times (fall-back
    overlap) raise DomainError. The caller must pass a naive datetime.
    """
    if local_naive.tzinfo is not None and local_naive.utcoffset() is not None:
        raise DomainError(
            "offset_not_allowed",
            "Pass a naive planning-local datetime; the organization timezone is applied by the server.",
        )
    tz = require_timezone(timezone_name)
    naive = local_naive.replace(tzinfo=None, fold=0)
    fold0 = naive.replace(tzinfo=tz, fold=0)
    fold1 = naive.replace(tzinfo=tz, fold=1)
    back = fold0.astimezone(UTC).astimezone(tz)
    if _wall(back) != _wall(naive):
        raise DomainError(
            "nonexistent_local_time",
            f"{naive.isoformat(timespec='minutes')} does not exist in {timezone_name} (DST gap).",
        )
    if fold0.utcoffset() != fold1.utcoffset():
        raise DomainError(
            "ambiguous_local_time",
            f"{naive.isoformat(timespec='minutes')} is ambiguous in {timezone_name} (DST overlap).",
        )
    return fold0.astimezone(UTC)


def utc_to_local_naive(utc_dt: datetime, timezone_name: str) -> datetime:
    if utc_dt.tzinfo is None or utc_dt.utcoffset() is None:
        raise DomainError("naive_datetime", "Expected a timezone-aware UTC datetime.")
    local = utc_dt.astimezone(require_timezone(timezone_name))
    return local.replace(tzinfo=None)


def format_local(utc_dt: datetime, timezone_name: str) -> str:
    return utc_to_local_naive(utc_dt, timezone_name).strftime("%Y-%m-%dT%H:%M")


def parse_local_datetime(text: str, timezone_name: str) -> datetime:
    raw = text.strip()
    if raw.endswith("Z") or "+" in raw[10:] or raw.count("-") > 2:
        raise DomainError(
            "offset_not_allowed",
            "Local datetimes must not include a UTC offset or Z suffix.",
        )
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise DomainError("invalid_local_datetime", f"Cannot parse local datetime: {text}") from exc
    return local_wall_to_utc(parsed, timezone_name)


def parse_hhmm(text: str) -> tuple[int, int]:
    raw = text.strip()
    parts = raw.split(":")
    if len(parts) != 2:
        raise DomainError("invalid_time", f"Expected HH:MM, got {text!r}.")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise DomainError("invalid_time", f"Expected HH:MM, got {text!r}.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise DomainError("invalid_time", f"Clock time out of range: {text}.")
    return hour, minute


def duration_hours(start: datetime, end: datetime) -> int:
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        raise DomainError("invalid_shift", "Shift end must be after its start.")
    if seconds > 24 * 3600:
        raise DomainError("invalid_shift", "Shifts longer than 24 hours are rejected.")
    if seconds % 3600 != 0:
        raise DomainError(
            "invalid_shift",
            "Shift length must be a whole number of hours in this version.",
        )
    return int(seconds // 3600)


def rest_threshold(min_rest_hours: float) -> timedelta:
    minutes = min_rest_hours * 60
    rounded = round(minutes)
    if abs(minutes - rounded) > 1e-6:
        raise DomainError(
            "invalid_rest",
            "Minimum rest must be an integer number of minutes.",
        )
    return timedelta(minutes=int(rounded))
