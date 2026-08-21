#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRAPHIFY_BIN="$(command -v graphify || true)"
if [[ -z "$GRAPHIFY_BIN" && -x /srv/hermes-agent/venv/bin/graphify ]]; then
  GRAPHIFY_BIN=/srv/hermes-agent/venv/bin/graphify
fi

command -v hermes >/dev/null 2>&1 || { echo "Ошибка: команда hermes не найдена" >&2; exit 1; }
[[ -n "$GRAPHIFY_BIN" ]] || { echo "Ошибка: Graphify не найден" >&2; exit 1; }

if hermes profile list | grep -Eq '(^|[[:space:]])orchestrator([[:space:]]|$)'; then
  echo "Ошибка: профиль orchestrator уже существует. Сценарий ничего не перезаписал." >&2
  exit 2
fi
if hermes profile list | grep -Eq '(^|[[:space:]])developer([[:space:]]|$)'; then
  echo "Ошибка: профиль developer уже существует. Сценарий ничего не перезаписал." >&2
  exit 2
fi

# Graphify устанавливает навык в активный профиль. Новые профили клонируют его.
"$GRAPHIFY_BIN" install --platform hermes

test -f "$HOME/.hermes/skills/graphify/SKILL.md" || {
  echo "Ошибка: навык Graphify не установлен в текущий профиль" >&2
  exit 3
}

hermes profile create orchestrator \
  --clone-from default --clone \
  --description "Общий оркестратор: принимает любые задачи, выбирает проект, планирует, передает код разработчику, проверяет результат и отчитывается пользователю."

hermes profile create developer \
  --clone-from default --clone \
  --description "Разработчик: находит проект через Hermes Projects и Graphify, работает в отдельной ветке, меняет и проверяет код, выполняет commit и push, обновляет сведения о проекте."

install -m 600 "$ROOT/orchestrator/SOUL.md" "$HOME/.hermes/profiles/orchestrator/SOUL.md"
install -m 600 "$ROOT/developer/SOUL.md" "$HOME/.hermes/profiles/developer/SOUL.md"

for profile in orchestrator developer; do
  test -f "$HOME/.hermes/profiles/$profile/SOUL.md"
  test -f "$HOME/.hermes/profiles/$profile/skills/graphify/SKILL.md" || {
    echo "Ошибка: навык Graphify отсутствует в профиле $profile" >&2
    exit 4
  }
  hermes profile show "$profile" >/dev/null
done

printf '\nГотово. Созданы независимые профили orchestrator и developer.\n'
printf 'Следующий шаг: зарегистрируйте проекты через register_project.sh.\n'
