"""Load synthetic CSV scenarios into pure Problem objects."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.errors import DomainError
from app.domain.problem import Employee, Problem, Rules, Shift, SkillRequirement, Weights
from app.domain.timeutil import duration_hours, local_wall_to_utc, parse_hhmm, parse_local_datetime

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
PREFERENCES = {"avoid", "neutral", "prefer"}


@dataclass(frozen=True)
class ScenarioBundle:
    organization_name: str
    planning_timezone: str
    problem: Problem
    templates: tuple[dict[str, str], ...]
    skill_names: dict[int, str]


def scenario_path(scenario: str, filename: str) -> Path:
    if scenario not in {"feasible", "infeasible"}:
        raise DomainError("unknown_scenario", f"Unknown scenario: {scenario}")
    direct = DATA_ROOT / scenario / filename
    if direct.exists():
        return direct
    fallback = DATA_ROOT / "feasible" / filename
    if scenario != "feasible" and fallback.exists():
        return fallback
    raise DomainError("missing_scenario_file", f"Scenario file not found: {direct}")


def load_scenario(scenario: str) -> ScenarioBundle:
    org = json.loads(scenario_path(scenario, "org.json").read_text(encoding="utf-8"))
    rules_payload = json.loads(scenario_path(scenario, "rules.json").read_text(encoding="utf-8"))
    timezone_name = str(org["planning_timezone"])
    organization_name = str(org["name"])
    employees_rows = _read_csv(scenario_path(scenario, "employees.csv"))
    availability_rows = _read_csv(scenario_path(scenario, "availability.csv"))
    time_off_rows = _read_csv(scenario_path(scenario, "time_off.csv"))
    shift_rows = _read_csv(scenario_path(scenario, "shifts.csv"))
    template_rows = _read_csv(scenario_path(scenario, "templates.csv"))

    skill_names = set()
    for row in employees_rows:
        skill_names.update(_split_skills(row.get("skills", "")))
    for row in shift_rows:
        for names, _count in _parse_skill_spec(row.get("skills", "")):
            skill_names.update(names)
    skill_ids = {name: index for index, name in enumerate(sorted(skill_names), start=1)}

    availability: dict[str, list[tuple[datetime, datetime]]] = {}
    for row in availability_rows:
        alias = row["display_alias"].strip()
        availability.setdefault(alias, []).append(
            (
                parse_local_datetime(row["start_local"], timezone_name),
                parse_local_datetime(row["end_local"], timezone_name),
            )
        )
    time_off: dict[str, list[tuple[datetime, datetime]]] = {}
    for row in time_off_rows:
        alias = row["display_alias"].strip()
        time_off.setdefault(alias, []).append(
            (
                parse_local_datetime(row["start_local"], timezone_name),
                parse_local_datetime(row["end_local"], timezone_name),
            )
        )

    employees: list[Employee] = []
    seen_aliases: set[str] = set()
    for index, row in enumerate(employees_rows, start=1):
        alias = row["display_alias"].strip()
        if not alias or alias in seen_aliases:
            raise DomainError("invalid_employee", f"Duplicate or empty display alias in row {index}.")
        seen_aliases.add(alias)
        night = row["night_preference"].strip()
        weekend = row["weekend_preference"].strip()
        if night not in PREFERENCES or weekend not in PREFERENCES:
            raise DomainError("invalid_preference", f"Bad preference for {alias}.")
        owned = frozenset(skill_ids[name] for name in _split_skills(row.get("skills", "")))
        employees.append(
            Employee(
                id=index,
                display_alias=alias,
                skill_ids=owned,
                weekly_hour_cap=int(row["weekly_hour_cap"]),
                cost_per_hour=int(row["cost_per_hour"]),
                night_preference=night,
                weekend_preference=weekend,
                available=tuple(availability.get(alias, ())),
                time_off=tuple(time_off.get(alias, ())),
            )
        )

    shifts = tuple(
        _shift_from_row(index, row, timezone_name, skill_ids)
        for index, row in enumerate(shift_rows, start=1)
    )
    weights_raw = rules_payload["weights"]
    rules = Rules(
        name=str(rules_payload["name"]),
        min_rest_hours=float(rules_payload["min_rest_hours"]),
        max_shift_hours=int(rules_payload["max_shift_hours"]),
        max_consecutive_days=(
            None
            if rules_payload.get("max_consecutive_days") in (None, "")
            else int(rules_payload["max_consecutive_days"])
        ),
        overtime_threshold_hours=int(rules_payload["overtime_threshold_hours"]),
        relaxed_understaffing=bool(rules_payload.get("relaxed_understaffing", False)),
        weights=Weights(
            cost=int(weights_raw["cost"]),
            preference=int(weights_raw["preference"]),
            fairness=int(weights_raw["fairness"]),
            overtime=int(weights_raw["overtime"]),
            night_imbalance=int(weights_raw["night_imbalance"]),
            weekend_imbalance=int(weights_raw["weekend_imbalance"]),
            understaff=int(weights_raw["understaff"]),
        ),
    )
    problem = Problem(
        planning_timezone=timezone_name,
        organization_name=organization_name,
        employees=tuple(employees),
        shifts=shifts,
        rules=rules,
    )
    templates = tuple(
        {
            "name": row["name"].strip(),
            "start_local": row["start_local"].strip(),
            "end_local": row["end_local"].strip(),
        }
        for row in template_rows
    )
    return ScenarioBundle(
        organization_name=organization_name,
        planning_timezone=timezone_name,
        problem=problem,
        templates=templates,
        skill_names={skill_id: name for name, skill_id in skill_ids.items()},
    )


def _shift_from_row(
    shift_id: int,
    row: dict[str, str],
    timezone_name: str,
    skill_ids: dict[str, int],
) -> Shift:
    local_date = datetime.fromisoformat(row["local_date"].strip()).date()
    start_hour, start_minute = parse_hhmm(row["start_local"])
    end_hour, end_minute = parse_hhmm(row["end_local"])
    start_local = datetime(
        local_date.year,
        local_date.month,
        local_date.day,
        start_hour,
        start_minute,
    )
    end_local = datetime(
        local_date.year,
        local_date.month,
        local_date.day,
        end_hour,
        end_minute,
    )
    overnight = end_local <= start_local
    if overnight:
        end_local = end_local + timedelta(days=1)
    start_utc = local_wall_to_utc(start_local, timezone_name)
    end_utc = local_wall_to_utc(end_local, timezone_name)
    duration_hours(start_utc, end_utc)
    requirements = []
    for names, count in _parse_skill_spec(row.get("skills", "")):
        label = " or ".join(names)
        requirements.append(
            SkillRequirement(
                any_of_ids=tuple(skill_ids[name] for name in names),
                label=label,
                min_count=count,
            )
        )
    return Shift(
        id=shift_id,
        label=row["label"].strip(),
        start=start_utc,
        end=end_utc,
        local_start_date=local_date.isoformat(),
        start_local=f"{start_hour:02d}:{start_minute:02d}",
        end_local=f"{end_hour:02d}:{end_minute:02d}",
        overnight=overnight,
        required_count=int(row["required_count"]),
        skill_requirements=tuple(requirements),
        is_night=start_hour >= 20 or start_hour < 6,
        is_weekend=local_date.weekday() >= 5,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _split_skills(text: str) -> list[str]:
    return [part.strip() for part in text.split("|") if part.strip()]


def _parse_skill_spec(text: str) -> list[tuple[tuple[str, ...], int]]:
    raw = text.strip()
    if not raw:
        return []
    parsed: list[tuple[tuple[str, ...], int]] = []
    for part in raw.split(";"):
        piece = part.strip()
        if not piece:
            continue
        if ":" not in piece:
            raise DomainError("invalid_skill_spec", f"Skill spec {piece!r} must look like RN:1 or RN|LPN:1.")
        names_part, count_text = piece.rsplit(":", 1)
        names = tuple(name.strip() for name in names_part.split("|") if name.strip())
        if not names:
            raise DomainError("invalid_skill_spec", f"Skill spec {piece!r} has no skill name.")
        parsed.append((names, int(count_text)))
    return parsed
