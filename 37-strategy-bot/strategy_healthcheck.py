#!/usr/bin/env python3
"""Проверяет Telegram API, службу и источники стратегического бота без вывода секретов."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = Path.home() / ".config" / "star-building" / "strategy-bot.env"
SERVICE = "star-building-strategy.service"
SOURCE_FILES = (
    ROOT.parent / "35-commercial-marketing-strategy" / "STRATEGY.md",
    ROOT.parent / "35-commercial-marketing-strategy" / "PRESENTATION_THESES.md",
    ROOT.parent / "36-marketing-budget-2026" / "BUDGET_RATIONALE.md",
)


def load_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def telegram_call(token: str, method: str) -> dict:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{method}", timeout=20) as response:
        return json.load(response)


def service_is_active() -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", SERVICE],
        capture_output=True,
    )
    return result.returncode == 0


def sources_are_ready() -> bool:
    return all(path.is_file() and path.stat().st_size > 0 for path in SOURCE_FILES)


def evaluate_bot(expected_username: str, me: dict, webhook: dict, service_active: bool, sources_ready: bool) -> dict:
    problems = []
    actual_username = me.get("result", {}).get("username") if me.get("ok") else None
    webhook_data = webhook.get("result", {}) if webhook.get("ok") else {}
    if actual_username != expected_username:
        problems.append("неверное имя бота")
    if not service_active:
        problems.append("служба не запущена")
    if not sources_ready:
        problems.append("источники стратегии недоступны")
    if webhook_data.get("url"):
        problems.append("активен webhook при режиме polling")
    if webhook_data.get("last_error_message"):
        problems.append(f"Telegram сообщил ошибку: {webhook_data['last_error_message']}")
    return {
        "ok": not problems,
        "username": actual_username,
        "service_active": service_active,
        "sources_ready": sources_ready,
        "pending_updates": webhook_data.get("pending_update_count", 0),
        "problems": problems,
    }


def main() -> int:
    credentials = load_env(ENV_FILE)
    token = credentials.get("STAR_BUILDING_STRATEGY_BOT_TOKEN")
    expected = credentials.get("STAR_BUILDING_STRATEGY_EXPECTED_USERNAME")
    if not token or not expected:
        print(json.dumps({"ok": False, "problems": ["нет учетных данных или ожидаемого имени"]}, ensure_ascii=False))
        return 1
    try:
        result = evaluate_bot(
            expected,
            telegram_call(token, "getMe"),
            telegram_call(token, "getWebhookInfo"),
            service_is_active(),
            sources_are_ready(),
        )
    except Exception as error:
        result = {"ok": False, "problems": [f"ошибка проверки: {type(error).__name__}"]}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
