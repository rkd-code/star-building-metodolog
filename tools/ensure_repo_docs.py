#!/usr/bin/env python3
"""Создает и проверяет обязательную документацию любого Git-репозитория."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

GENERATED_FILES = {
    "PROJECT_CONTEXT.md", "PROJECT_STRUCTURE.md", "PROJECT_MANIFEST.json", "DOCS_INDEX.md",
}
REQUIRED_FILES = [
    "README.md", "AGENTS.md", ".hermes.md", "PROJECT_CONTEXT.md", "PROJECT_STRUCTURE.md",
    "PROJECT_MANIFEST.json", "DOCS_INDEX.md", "DATA_MODEL.md", "DECISIONS.md",
    "KNOWLEDGE_BASE.md", "CHANGELOG.md", "DOCUMENTATION_STANDARD.md",
    ".githooks/pre-commit", ".github/workflows/documentation-integrity.yml", "tools/ensure_repo_docs.py",
]
TOOL_TARGET = "tools/ensure_repo_docs.py"
TEXT_SUFFIXES = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".sh", ".sql", ".csv"}


def run(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=repo, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def repository_remote(repo: Path) -> tuple[str, str]:
    remote = run(repo, "remote", "get-url", "origin", check=False)
    if not remote:
        return "не указано", ""
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    if match:
        slug = match.group(1).removesuffix(".git")
        return f"https://github.com/{slug}", slug
    return remote, ""


def branch_name(repo: Path) -> str:
    branch = run(repo, "branch", "--show-current", check=False)
    return branch or "main"


def project_name(repo: Path) -> str:
    readme = repo / "README.md"
    if readme.exists():
        match = re.search(r"(?m)^#\s+(.+)$", readme.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group(1).strip()
    return repo.name


def staged_paths(repo: Path) -> list[str]:
    paths = set(run(repo, "ls-files", "--cached").splitlines())
    paths.update(GENERATED_FILES)
    return sorted(path for path in paths if path)


def source_tree_hash(repo: Path) -> str:
    lines = []
    for line in run(repo, "ls-files", "-s").splitlines():
        if not line:
            continue
        metadata, path = line.split("\t", 1)
        if path in GENERATED_FILES:
            continue
        lines.append(f"{metadata}\t{path}")
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()


def github_file_url(base: str, branch: str, path: str) -> str:
    if not base.startswith("https://github.com/"):
        return ""
    return f"{base}/blob/{quote(branch, safe='')}/{quote(path, safe='/')}"


def describe_file(path: Path, relative: str) -> str:
    if relative in GENERATED_FILES:
        descriptions = {
            "PROJECT_CONTEXT.md": "Краткий обязательный контекст для начала работы агента.",
            "PROJECT_STRUCTURE.md": "Автоматический указатель структуры и назначения файлов.",
            "PROJECT_MANIFEST.json": "Машиночитаемая структура репозитория и ссылки GitHub.",
            "DOCS_INDEX.md": "Единая точка входа во всю документацию проекта.",
        }
        return descriptions[relative]
    if not path.exists():
        return "Обязательный файл документации проекта."
    if path.suffix.lower() == ".py":
        try:
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8", errors="replace")))
            if doc:
                return re.sub(r"\s+", " ", doc).strip()[:240]
        except SyntaxError:
            pass
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"AGENTS.md", ".hermes.md"}:
        text = path.read_text(encoding="utf-8", errors="replace")[:65536]
        heading = re.search(r"(?m)^#{1,3}\s+(.+)$", text)
        if heading:
            return re.sub(r"\s+", " ", heading.group(1)).strip()[:240]
        plain = re.sub(r"\s+", " ", text).strip()
        if plain:
            return plain[:240]
    labels = {".xlsx": "Книга Excel с проектными данными.", ".docx": "Документ Word.", ".pdf": "Документ PDF.", ".png": "Графическое изображение.", ".jpg": "Графическое изображение."}
    return labels.get(path.suffix.lower(), f"Файл проекта: {path.name}.")


def file_area(relative: str) -> str:
    parts = Path(relative).parts
    return parts[0] if len(parts) > 1 else "Корень репозитория"


def bootstrap_templates(repo: Path) -> dict[str, str]:
    name = project_name(repo)
    return {
        "README.md": f"# {name}\n\n[ТРЕБУЕТ УТОЧНЕНИЯ: назначение, запуск и текущее состояние проекта.]\n",
        "AGENTS.md": "# Обязательные правила для агентов\n\nПеред работой прочитайте `PROJECT_CONTEXT.md` и `DOCS_INDEX.md`. После изменений обновите документацию и выполните `python3 tools/ensure_repo_docs.py --repo . --stage`.\n",
        ".hermes.md": "# Контекст Hermes\n\nОбязательно прочитайте `AGENTS.md`, `PROJECT_CONTEXT.md`, `DOCS_INDEX.md` и `PROJECT_STRUCTURE.md` до изменения проекта.\n",
        "DATA_MODEL.md": "# Модель данных\n\n[ТРЕБУЕТ УТОЧНЕНИЯ: сущности, поля, связи, источники и миграции либо отметка «не применимо».]\n",
        "DECISIONS.md": "# Решения проекта\n\nВсе новые архитектурные и структурные решения фиксируются здесь.\n",
        "KNOWLEDGE_BASE.md": "# База знаний проекта\n\nСсылки на действующие источники, регламенты и проверенные факты проекта.\n",
        "CHANGELOG.md": "# История изменений\n\nЗначимые изменения проекта фиксируются по версиям или датам.\n",
        "DOCUMENTATION_STANDARD.md": documentation_standard(),
    }


def documentation_standard() -> str:
    return """# Обязательный стандарт документации репозитория

## Назначение

Каждый агент обязан оставить репозиторий понятным следующему агенту без обращения к прошлой переписке.

## Обязательные документы

- `README.md` — назначение, запуск, состояние и основные ссылки;
- `AGENTS.md` — обязательные правила для всех агентов;
- `.hermes.md` — наследуемая точка входа Hermes из любой подпапки;
- `PROJECT_CONTEXT.md` — краткий актуальный контекст;
- `PROJECT_STRUCTURE.md` — структура и назначение файлов;
- `PROJECT_MANIFEST.json` — машиночитаемые метаданные и ссылки GitHub;
- `DOCS_INDEX.md` — навигация по документации;
- `DATA_MODEL.md` — сущности, поля, связи и миграции либо «не применимо»;
- `DECISIONS.md` — архитектурные решения;
- `KNOWLEDGE_BASE.md` — проверенные источники и знания;
- `CHANGELOG.md` — значимые изменения.

## Обязанности агента

1. До работы прочитать `AGENTS.md`, `PROJECT_CONTEXT.md`, `DOCS_INDEX.md`, `PROJECT_STRUCTURE.md`, `DATA_MODEL.md`, `DECISIONS.md` и `KNOWLEDGE_BASE.md`.
2. При добавлении файла указать его назначение содержательным заголовком или модульной строкой документации.
3. При изменении поведения обновить `README.md` и `CHANGELOG.md`.
4. При изменении структуры данных обновить `DATA_MODEL.md`.
5. Новые сущности и архитектурные решения зафиксировать в `DECISIONS.md`.
6. Перед коммитом запустить `python3 tools/ensure_repo_docs.py --repo . --stage`.
7. Не обходить проверку `--no-verify`, кроме документированной аварийной ситуации.
8. Не включать в документы и ссылки секреты, токены, пароли и приватные ключи.

## Автоматическая проверка

Предкоммитный обработчик обновляет генерируемые документы и добавляет их в коммит. Проверка GitHub отклоняет коммит, если структура документации устарела или обязательные файлы отсутствуют.
"""


def hook_text() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
if [ -f "$ROOT/34-agent-repository-documentation/ensure_repo_docs.py" ]; then
  TOOL="$ROOT/34-agent-repository-documentation/ensure_repo_docs.py"
elif [ -f "$ROOT/tools/ensure_repo_docs.py" ]; then
  TOOL="$ROOT/tools/ensure_repo_docs.py"
else
  TOOL="$HOME/.hermes/scripts/ensure_repo_documentation.py"
fi
python3 "$TOOL" --repo "$ROOT" --stage
"""


def workflow_text() -> str:
    return """name: Проверка актуальности документации
on:
  push:
  pull_request:
jobs:
  documentation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Проверить обязательную документацию
        run: |
          if [ -f 34-agent-repository-documentation/ensure_repo_docs.py ]; then
            python3 34-agent-repository-documentation/ensure_repo_docs.py --repo . --check
          else
            python3 tools/ensure_repo_docs.py --repo . --check
          fi
"""


def ensure_bootstrap(repo: Path) -> list[str]:
    changed = []
    for relative, content in bootstrap_templates(repo).items():
        path = repo / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8"); changed.append(relative)
    special = {".githooks/pre-commit": hook_text(), ".github/workflows/documentation-integrity.yml": workflow_text()}
    for relative, content in special.items():
        path = repo / relative
        if not path.exists() or path.read_text(encoding="utf-8", errors="replace") != content:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8"); changed.append(relative)
        if relative.endswith("pre-commit"):
            path.chmod(0o755)
    tool = repo / TOOL_TARGET
    source = Path(__file__).resolve()
    if source != tool.resolve() if tool.exists() else True:
        desired = source.read_text(encoding="utf-8")
        if not tool.exists() or tool.read_text(encoding="utf-8") != desired:
            tool.parent.mkdir(parents=True, exist_ok=True); tool.write_text(desired, encoding="utf-8"); tool.chmod(0o755); changed.append(TOOL_TARGET)
    return changed


def build_manifest(repo: Path) -> dict:
    base, slug = repository_remote(repo); branch = branch_name(repo); source_hash = source_tree_hash(repo)
    files = []
    for relative in staged_paths(repo):
        path = repo / relative
        files.append({"path": relative, "name": Path(relative).name, "area": file_area(relative), "description": describe_file(path, relative), "github_url": github_file_url(base, branch, relative)})
    return {
        "schema_version": "1.0", "project": project_name(repo), "repository": base,
        "github_slug": slug or "не указано", "default_branch": branch,
        "source_tree_hash": source_hash, "documentation_files": REQUIRED_FILES,
        "files": files,
    }


def render_generated(repo: Path) -> dict[str, str]:
    manifest = build_manifest(repo); base = manifest["repository"]; branch = manifest["default_branch"]
    docs = []
    for relative in REQUIRED_FILES:
        url = github_file_url(base, branch, relative)
        docs.append(f"- [`{relative}`]({url or relative})")
    context = f"""# Контекст проекта: {manifest['project']}

- **Репозиторий:** {base}
- **Ветка:** `{branch}`
- **Корневая папка:** `{repo}`
- **Отпечаток исходной структуры:** `{manifest['source_tree_hash']}`
- **Файлов в структуре:** {len(manifest['files'])}

## Обязательный порядок знакомства

1. `AGENTS.md` — правила работы.
2. `DOCS_INDEX.md` — вся документация и ссылки.
3. `PROJECT_STRUCTURE.md` — расположение и назначение файлов.
4. `DATA_MODEL.md` — структура данных.
5. `DECISIONS.md` — принятые решения.
6. `KNOWLEDGE_BASE.md` — проверенные знания.

Перед завершением задачи агент обязан обновить затронутую документацию и запустить проверку документации.
"""
    grouped = {}
    for item in manifest["files"]: grouped.setdefault(item["area"], []).append(item)
    structure = [f"# Структура проекта: {manifest['project']}", "", f"Отпечаток исходной структуры: `{manifest['source_tree_hash']}`", ""]
    for area in sorted(grouped):
        structure += [f"## {area}", "", "| Файл | Назначение |", "|---|---|"]
        for item in grouped[area]:
            link = item["github_url"] or item["path"]
            structure.append(f"| [`{item['path']}`]({link}) | {item['description'].replace('|', '—')} |")
        structure.append("")
    index = "# Указатель документации\n\nВсе агенты начинают работу с этого списка.\n\n" + "\n".join(docs) + "\n"
    return {
        "PROJECT_CONTEXT.md": context,
        "PROJECT_STRUCTURE.md": "\n".join(structure),
        "PROJECT_MANIFEST.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        "DOCS_INDEX.md": index,
    }


def ensure_repository(repo: Path, stage: bool = False) -> dict:
    repo = repo.resolve(); changed = ensure_bootstrap(repo)
    if stage and changed:
        run(repo, "add", "--", *changed)
    generated = render_generated(repo)
    for relative, content in generated.items():
        path = repo / relative
        if not path.exists() or path.read_text(encoding="utf-8", errors="replace") != content:
            path.write_text(content, encoding="utf-8"); changed.append(relative)
    if stage:
        run(repo, "add", "--", *sorted(set(changed) | GENERATED_FILES))
    return {"ok": True, "updated": bool(changed), "changed": sorted(set(changed)), "source_tree_hash": source_tree_hash(repo)}


def check_repository(repo: Path) -> dict:
    repo = repo.resolve(); missing = [name for name in REQUIRED_FILES if not (repo / name).exists()]
    missing += [] if (repo / TOOL_TARGET).exists() else [TOOL_TARGET]
    stale = []
    if not missing:
        for relative, expected in render_generated(repo).items():
            if (repo / relative).read_text(encoding="utf-8", errors="replace") != expected:
                stale.append(relative)
    return {"ok": not missing and not stale, "missing": missing, "stale": stale, "source_tree_hash": source_tree_hash(repo)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--repo", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(); mode.add_argument("--stage", action="store_true"); mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        result = check_repository(args.repo); print(json.dumps(result, ensure_ascii=False)); return 0 if result["ok"] else 1
    print(json.dumps(ensure_repository(args.repo, stage=args.stage), ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
