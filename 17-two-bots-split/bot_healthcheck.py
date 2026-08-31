#!/usr/bin/env python3
"""Проверяет учетные данные, Telegram API и службы двух ботов."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

BOT_ENV = Path.home() / ".config/star-building/bots.env"
BOTS = (
    {
        "name": "Смотритель",
        "username": "ReglamentSB_bot",
        "token_var": "STAR_BUILDING_CODIFIER_BOT_TOKEN",
        "service": "star-building-codifier.service",
    },
    {
        "name": "Ом",
        "username": "star_building_help_bot",
        "token_var": "STAR_BUILDING_CONSULTANT_BOT_TOKEN",
        "service": "star-building-consultant.service",
    },
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
    with urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/{method}", timeout=20
    ) as response:
        return json.load(response)


def service_is_active(name: str) -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", name],
        capture_output=True,
    )
    return result.returncode == 0


def evaluate_bot(
    expected_username: str,
    me: dict,
    webhook: dict,
    service_active: bool,
) -> dict:
    problems = []
    actual_username = me.get("result", {}).get("username") if me.get("ok") else None
    webhook_data = webhook.get("result", {}) if webhook.get("ok") else {}
    if actual_username != expected_username:
        problems.append("неверное имя бота")
    if not service_active:
        problems.append("служба не запущена")
    if webhook_data.get("url"):
        problems.append("активен webhook при режиме polling")
    if webhook_data.get("last_error_message"):
        problems.append(f"Telegram сообщил ошибку: {webhook_data['last_error_message']}")
    return {
        "ok": not problems,
        "username": actual_username,
        "service_active": service_active,
        "pending_updates": webhook_data.get("pending_update_count", 0),
        "problems": problems,
    }


def main() -> int:
    credentials = load_env(BOT_ENV)
    results = []
    for bot in BOTS:
        token = credentials.get(bot["token_var"])
        if not token:
            results.append({"name": bot["name"], "ok": False, "problems": ["нет учетных данных"]})
            continue
        try:
            status = evaluate_bot(
                bot["username"],
                telegram_call(token, "getMe"),
                telegram_call(token, "getWebhookInfo"),
                service_is_active(bot["service"]),
            )
        except Exception as error:
            status = {"ok": False, "problems": [f"ошибка проверки: {type(error).__name__}"]}
        results.append({"name": bot["name"], **status})
    summary = {"ok": all(item["ok"] for item in results), "bots": results}
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
