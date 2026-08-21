#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Использование: $0 <код-проекта> <название> <путь> [исходная-ветка]" >&2
  exit 1
fi

SLUG="$1"
NAME="$2"
REPO="$(realpath "$3")"
BASE_BRANCH="${4:-}"

command -v hermes >/dev/null 2>&1 || { echo "Ошибка: hermes не найден" >&2; exit 1; }
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Ошибка: $REPO не является Git-репозиторием" >&2
  exit 2
}

REMOTE="$(git -C "$REPO" remote get-url origin 2>/dev/null || true)"
if [[ -z "$BASE_BRANCH" ]]; then
  BASE_BRANCH="$(git -C "$REPO" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)"
fi
if [[ -z "$BASE_BRANCH" ]]; then
  BASE_BRANCH="$(git -C "$REPO" branch --show-current)"
fi

if ! hermes kanban boards list | grep -Eq "(^|[[:space:]])${SLUG}([[:space:]]|$)"; then
  hermes kanban boards create "$SLUG" \
    --name "$NAME" \
    --description "Рабочая доска проекта $NAME" \
    --default-workdir "$REPO"
fi

for profile in orchestrator developer; do
  hermes profile show "$profile" >/dev/null 2>&1 || {
    echo "Ошибка: профиль $profile не существует" >&2
    exit 3
  }

  if ! hermes -p "$profile" project list | grep -Eq "(^|[[:space:]])${SLUG}([[:space:]]|$)"; then
    hermes -p "$profile" project create "$NAME" "$REPO" \
      --slug "$SLUG" \
      --primary "$REPO" \
      --description "Репозиторий: ${REMOTE:-не задан}; исходная ветка: ${BASE_BRANCH:-не определена}" \
      --board "$SLUG"
  fi

done

printf 'Проект: %s\n' "$NAME"
printf 'Код: %s\n' "$SLUG"
printf 'Путь: %s\n' "$REPO"
printf 'Репозиторий: %s\n' "${REMOTE:-не задан}"
printf 'Исходная ветка: %s\n' "${BASE_BRANCH:-не определена}"
printf 'Профили: orchestrator, developer\n'
