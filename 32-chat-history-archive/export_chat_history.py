#!/usr/bin/env python3
"""Ежедневно выгружает переписку Hermes по профилям."""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HOME = Path.home()
HERMES_HOME = HOME / ".hermes"
DEFAULT_ARCHIVE = HOME / "Hermes-переписка"
DEFAULT_TIMEZONE = "Asia/Almaty"
ALLOWED_ROLES = {"user": "Пользователь", "assistant": "Hermes"}
INTERNAL_PREFIXES = ("[CONTEXT COMPACTION — REFERENCE ONLY]",)


def safe_profile_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яЁё._-]+", "_", value.strip())
    return cleaned or "default"


def clean_session_title(title: str | None, display_name: str | None) -> str:
    if title and not title.lstrip().startswith(("{", "[")):
        return title
    return display_name or "Без названия"


def discover_profiles(hermes_home: Path = HERMES_HOME) -> set[str]:
    profiles = {"default"}
    profile_root = hermes_home / "profiles"
    if profile_root.exists():
        profiles.update(path.name for path in profile_root.iterdir() if path.is_dir())
    return profiles


def discover_databases(hermes_home: Path = HERMES_HOME) -> list[tuple[Path, str]]:
    specs: list[tuple[Path, str]] = []
    central = hermes_home / "state.db"
    if central.exists():
        specs.append((central, "default"))
    profile_root = hermes_home / "profiles"
    if profile_root.exists():
        for profile in sorted(path for path in profile_root.iterdir() if path.is_dir()):
            database = profile / "state.db"
            if database.exists():
                specs.append((database, profile.name))
    return specs


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def read_database(path: Path, fallback_profile: str, timezone: ZoneInfo) -> list[dict]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    connection.execute("PRAGMA busy_timeout=30000")
    session_columns = table_columns(connection, "sessions")
    profile_expression = "s.profile_name" if "profile_name" in session_columns else "NULL"
    title_expression = "s.title" if "title" in session_columns else "NULL"
    display_expression = "s.display_name" if "display_name" in session_columns else "NULL"
    source_expression = "s.source" if "source" in session_columns else "NULL"
    rows = connection.execute(
        f"""
        SELECT m.id, m.session_id, m.role, m.content, m.timestamp,
               {profile_expression}, {title_expression}, {display_expression}, {source_expression}
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.role IN ('user', 'assistant')
          AND m.content IS NOT NULL
          AND trim(m.content) <> ''
        ORDER BY m.timestamp, m.id
        """
    ).fetchall()
    connection.close()
    messages = []
    for message_id, session_id, role, content, timestamp, profile, title, display_name, source in rows:
        if role == "user" and content.startswith(INTERNAL_PREFIXES):
            continue
        local_time = datetime.fromtimestamp(float(timestamp), tz=timezone)
        messages.append({
            "dedup": (str(path.resolve()), message_id),
            "session_id": session_id,
            "role": role,
            "content": content.strip(),
            "timestamp": local_time,
            "date": local_time.date(),
            "profile": safe_profile_name(profile or fallback_profile),
            "title": clean_session_title(title, display_name),
            "display_name": display_name or "—",
            "source": source or "не указан",
        })
    return messages


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def render_file(day: date, profile: str, timezone_name: str, messages: list[dict]) -> str:
    lines = [
        "ИСТОРИЯ ПЕРЕПИСКИ HERMES",
        f"Дата: {day.isoformat()}",
        f"Профиль: {profile}",
        f"Часовой пояс: {timezone_name}",
        "",
    ]
    if not messages:
        lines.append("Переписки за этот день нет.")
        return "\n".join(lines) + "\n"

    grouped: dict[str, list[dict]] = defaultdict(list)
    for message in messages:
        grouped[message["session_id"]].append(message)
    sessions = sorted(grouped.values(), key=lambda values: values[0]["timestamp"])
    for index, session_messages in enumerate(sessions, 1):
        first = session_messages[0]
        lines.extend([
            "=" * 78,
            f"ДИАЛОГ {index}: {first['title']}",
            f"Источник: {first['source']} | Собеседник: {first['display_name']}",
            f"Идентификатор сеанса: {first['session_id']}",
            "=" * 78,
            "",
        ])
        for message in session_messages:
            stamp = message["timestamp"].strftime("%H:%M:%S")
            lines.extend([
                f"[{stamp}] {ALLOWED_ROLES[message['role']]}",
                message["content"],
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def atomic_private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def export_history(
    database_specs: list[tuple[Path, str]],
    archive_root: Path,
    timezone_name: str = DEFAULT_TIMEZONE,
    today: date | None = None,
    discovered_profiles: set[str] | None = None,
) -> dict:
    timezone = ZoneInfo(timezone_name)
    current_day = today or datetime.now(timezone).date()
    profiles = {safe_profile_name(value) for value in (discovered_profiles or {"default"})}
    all_messages: list[dict] = []
    seen = set()
    for database, fallback_profile in database_specs:
        for message in read_database(Path(database), fallback_profile, timezone):
            if message["dedup"] in seen:
                continue
            seen.add(message["dedup"])
            profiles.add(message["profile"])
            all_messages.append(message)

    by_day_profile: dict[tuple[date, str], list[dict]] = defaultdict(list)
    for message in all_messages:
        by_day_profile[(message["date"], message["profile"])].append(message)

    earliest = min((message["date"] for message in all_messages), default=current_day)
    earliest = min(earliest, current_day)
    files_written = 0
    for day in daterange(earliest, current_day):
        month_folder = archive_root / day.strftime("%Y-%m")
        for profile in sorted(profiles):
            file_path = month_folder / f"{day.isoformat()}__{profile}.txt"
            content = render_file(day, profile, timezone_name, by_day_profile[(day, profile)])
            atomic_private_write(file_path, content)
            files_written += 1

    os.chmod(archive_root, 0o700)
    return {
        "files_written": files_written,
        "profiles": sorted(profiles),
        "messages": len(all_messages),
        "from": earliest.isoformat(),
        "through": current_day.isoformat(),
        "archive_root": str(archive_root),
        "timezone": timezone_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    result = export_history(
        database_specs=discover_databases(),
        archive_root=args.archive_root,
        timezone_name=args.timezone,
        discovered_profiles=discover_profiles(),
    )
    if args.verbose:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
