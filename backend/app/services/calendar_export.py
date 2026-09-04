from datetime import datetime, timezone


def _ics_text(value: str | None) -> str:
    return (value or "").replace("\\", "\\\\").replace("\r", " ").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _ics_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fold_line(line: str) -> list[str]:
    parts: list[str] = []
    current = ""
    limit = 75
    for character in line:
        candidate = current + character
        if current and len(candidate.encode("utf-8")) > limit:
            parts.append(current)
            current = " " + character
            limit = 75
        else:
            current = candidate
    parts.append(current)
    return parts


def render_tasks_ics(tasks: list[object], *, calendar_name: str = "LexFlow") -> str:
    now = _ics_datetime(datetime.now(timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LexFlow//Agenda juridica//PT-BR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_text(calendar_name)}",
    ]
    for task in tasks:
        due_at = getattr(task, "due_at", None)
        if due_at is None:
            continue
        start = _ics_datetime(due_at)
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:task-{_ics_text(str(getattr(task, 'id', '')))}@lexflow",
                f"DTSTAMP:{now}",
                f"DTSTART:{start}",
                f"SUMMARY:{_ics_text(getattr(task, 'title', 'Compromisso'))}",
                f"DESCRIPTION:{_ics_text(getattr(task, 'notes', None))}",
                f"LOCATION:{_ics_text(getattr(task, 'location', None))}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in _fold_line(line)) + "\r\n"
