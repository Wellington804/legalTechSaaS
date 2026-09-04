"""Deterministic deadline calculation from an already reviewed, versioned rule.

This module deliberately contains no legal inference. The caller must select an
active rule and provide the triggering instant. Missing rules fail closed.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ENGINE_VERSION = "1.0"
MAX_CALCULATION_DAYS = 5000
MAX_EXPLAINED_EXCLUSIONS = 500


class DeadlineCalculationError(ValueError):
    pass


@dataclass(frozen=True)
class DeadlineRuleSpec:
    id: str
    rule_key: str
    version: int
    rite: str
    act_type: str
    tribunal: str
    local_code: str | None
    days: int
    counting_method: str
    start_mode: str
    due_adjustment: str
    timezone_name: str
    due_hour: int
    due_minute: int
    legal_sources: list[dict[str, str]]


@dataclass(frozen=True)
class CalendarExceptionSpec:
    scope_kind: str
    scope_code: str
    kind: str
    name: str
    starts_on: date
    ends_on: date
    source_url: str
    source_name: str


@dataclass(frozen=True)
class DeadlineCalculation:
    due_at: datetime
    explanation: dict


def _rule_digest(rule: DeadlineRuleSpec) -> str:
    material = {
        "id": rule.id,
        "rule_key": rule.rule_key,
        "version": rule.version,
        "rite": rule.rite,
        "act_type": rule.act_type,
        "tribunal": rule.tribunal,
        "local_code": rule.local_code,
        "days": rule.days,
        "counting_method": rule.counting_method,
        "start_mode": rule.start_mode,
        "due_adjustment": rule.due_adjustment,
        "timezone_name": rule.timezone_name,
        "due_hour": rule.due_hour,
        "due_minute": rule.due_minute,
        "legal_sources": rule.legal_sources,
    }
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def calculate_deadline(
    triggered_at: datetime,
    rule: DeadlineRuleSpec,
    exceptions: list[CalendarExceptionSpec],
) -> DeadlineCalculation:
    if triggered_at.tzinfo is None or triggered_at.utcoffset() is None:
        raise DeadlineCalculationError("termo de referencia deve informar fuso horario")
    if not 1 <= rule.days <= 3650:
        raise DeadlineCalculationError("quantidade de dias fora do limite")
    if rule.counting_method not in {"business_days", "calendar_days"}:
        raise DeadlineCalculationError("metodo de contagem nao suportado")
    if rule.start_mode not in {"next_business_day", "same_business_day", "next_calendar_day"}:
        raise DeadlineCalculationError("regra de termo inicial nao suportada")
    if rule.due_adjustment not in {"none", "next_business_day"}:
        raise DeadlineCalculationError("ajuste de vencimento nao suportado")
    try:
        zone = ZoneInfo(rule.timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise DeadlineCalculationError("fuso horario da regra nao existe") from exc

    local_trigger = triggered_at.astimezone(zone)
    excluded: dict[str, dict] = {}

    def closures(day: date) -> list[CalendarExceptionSpec]:
        return [item for item in exceptions if item.starts_on <= day <= item.ends_on]

    def record_closed(day: date) -> None:
        reasons: list[dict[str, str]] = []
        if day.weekday() >= 5:
            reasons.append({"kind": "weekend", "name": "Fim de semana"})
        for item in closures(day):
            reasons.append(
                {
                    "kind": item.kind,
                    "name": item.name,
                    "scope": f"{item.scope_kind}:{item.scope_code}",
                    "source_name": item.source_name,
                    "source_url": item.source_url,
                }
            )
        if reasons:
            excluded[day.isoformat()] = {"date": day.isoformat(), "reasons": reasons}

    def is_business_day(day: date) -> bool:
        return day.weekday() < 5 and not closures(day)

    def next_business_day(day: date) -> date:
        candidate = day
        for _ in range(MAX_CALCULATION_DAYS):
            if is_business_day(candidate):
                return candidate
            record_closed(candidate)
            candidate += timedelta(days=1)
        raise DeadlineCalculationError("calendario nao possui dia util dentro do limite")

    if rule.start_mode == "next_business_day":
        term_start = next_business_day(local_trigger.date() + timedelta(days=1))
    elif rule.start_mode == "same_business_day":
        term_start = next_business_day(local_trigger.date())
    else:
        term_start = local_trigger.date() + timedelta(days=1)

    if rule.counting_method == "business_days":
        if not is_business_day(term_start):
            raise DeadlineCalculationError("termo inicial da regra nao e dia util")
        current = term_start
        counted = 0
        for _ in range(MAX_CALCULATION_DAYS):
            if is_business_day(current):
                counted += 1
                if counted == rule.days:
                    due_date = current
                    break
            else:
                record_closed(current)
            current += timedelta(days=1)
        else:
            raise DeadlineCalculationError("prazo excede o limite de calculo")
    else:
        due_date = term_start + timedelta(days=rule.days - 1)

    unadjusted_due_date = due_date
    if rule.due_adjustment == "next_business_day":
        due_date = next_business_day(due_date)

    due_local = datetime.combine(
        due_date,
        time(hour=rule.due_hour, minute=rule.due_minute),
        tzinfo=zone,
    )
    exclusion_items = list(excluded.values())
    explanation = {
        "engine_version": ENGINE_VERSION,
        "rule": {
            "id": rule.id,
            "key": rule.rule_key,
            "version": rule.version,
            "snapshot_sha256": _rule_digest(rule),
            "rite": rule.rite,
            "act_type": rule.act_type,
            "tribunal": rule.tribunal,
            "local_code": rule.local_code,
            "legal_sources": rule.legal_sources,
        },
        "triggered_at": triggered_at.astimezone(timezone.utc).isoformat(),
        "triggered_at_local": local_trigger.isoformat(),
        "term_start": term_start.isoformat(),
        "days": rule.days,
        "counting_method": rule.counting_method,
        "start_mode": rule.start_mode,
        "due_adjustment": rule.due_adjustment,
        "unadjusted_due_date": unadjusted_due_date.isoformat(),
        "due_date": due_date.isoformat(),
        "due_at_local": due_local.isoformat(),
        "due_at_utc": due_local.astimezone(timezone.utc).isoformat(),
        "timezone": rule.timezone_name,
        "excluded_dates": exclusion_items[:MAX_EXPLAINED_EXCLUSIONS],
        "excluded_dates_count": len(exclusion_items),
        "excluded_dates_truncated": len(exclusion_items) > MAX_EXPLAINED_EXCLUSIONS,
    }
    return DeadlineCalculation(due_at=due_local.astimezone(timezone.utc), explanation=explanation)
