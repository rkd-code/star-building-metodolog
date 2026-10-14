"""Изолированное защищённое файловое хранилище решений владельца и черновиков P-026."""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_STORAGE_DIR = Path.home() / ".local" / "share" / "star-building" / "dramknote-p026"
ALLOWED_NAME_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ0-9_-]+$")


class PathTraversalError(ValueError):
    """Исключение при попытке обхода каталога или использования некорректного пути."""


class P026Storage:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            env_override = os.environ.get("DRAMKNOTE_P026_STORAGE_DIR")
            self.base_dir = Path(env_override) if env_override else DEFAULT_STORAGE_DIR
        else:
            self.base_dir = Path(base_dir)

        self.decisions_dir = self.base_dir / "decisions"
        self.drafts_dir = self.base_dir / "drafts"
        self.decisions_file = self.decisions_dir / "decisions.json"

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        if not self.decisions_file.exists():
            self._write_json_atomic(self.decisions_file, [])

    def _validate_safe_name(self, name: str) -> str:
        if not name or not isinstance(name, str):
            raise PathTraversalError("Пустое или некорректное имя")
        if "\x00" in name or "/" in name or "\\" in name or ".." in name:
            raise PathTraversalError(f"Обнаружены запрещённые символы пути в имени: {name}")
        base = name.strip()
        if not ALLOWED_NAME_RE.match(base):
            raise PathTraversalError(f"Имя содержит недопустимые символы (разрешены буквы, цифры, дефис, подчеркивание): {name}")
        return base

    def _validate_safe_path(self, target_path: Path, expected_parent: Path) -> Path:
        resolved = target_path.resolve()
        parent_resolved = expected_parent.resolve()
        if target_path.is_symlink() or resolved.is_symlink():
            raise PathTraversalError(f"Символические ссылки запрещены: {target_path}")
        try:
            resolved.relative_to(parent_resolved)
        except ValueError as err:
            raise PathTraversalError(f"Попытка выхода за пределы изолированного каталога: {target_path}") from err
        return resolved

    def _write_json_atomic(self, target: Path, data: Any) -> None:
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=parent, delete=False, encoding="utf-8") as temp:
            json.dump(data, temp, ensure_ascii=False, indent=2)
            temp_path = Path(temp.name)
        temp_path.replace(target)

    def _read_decisions_raw(self) -> list[dict[str, Any]]:
        if not self.decisions_file.exists():
            return []
        try:
            data = json.loads(self.decisions_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []

    def record_decision(
        self,
        author: str,
        question_context: str,
        exact_text: str,
        user_id: int | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Фиксирует точное решение владельца в журнале."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        current = self._read_decisions_raw()
        next_num = len(current) + 1
        decision_id = f"dec_{next_num}_{int(datetime.datetime.now().timestamp())}"

        record = {
            "id": decision_id,
            "timestamp": now,
            "author": author,
            "user_id": user_id,
            "question_context": question_context.strip(),
            "exact_text": exact_text.strip(),
            "status": status,
        }
        current.append(record)
        self._write_json_atomic(self.decisions_file, current)
        return record

    def list_decisions(self, user_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        """Возвращает список зафиксированных решений с опциональной фильтрацией."""
        items = self._read_decisions_raw()
        results = []
        for item in items:
            if user_id is not None and item.get("user_id") != user_id:
                continue
            if status is not None and item.get("status") != status:
                continue
            results.append(item)
        return results

    def save_draft(
        self,
        doc_name: str,
        content: str,
        author: str = "Руководитель",
    ) -> dict[str, Any]:
        """Сохраняет версионный рабочий черновик без перезаписи оригиналов."""
        safe_name = self._validate_safe_name(doc_name)
        existing = self.list_drafts(safe_name)
        next_version = (existing[0]["version"] + 1) if existing else 1

        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_v{next_version}_{now_str}.md"
        draft_path = self.drafts_dir / filename
        self._validate_safe_path(draft_path, self.drafts_dir)

        # Атомарная запись черновика
        with tempfile.NamedTemporaryFile("w", dir=self.drafts_dir, delete=False, encoding="utf-8") as temp:
            header = (
                f"<!-- DRAFT ARTIFACT: {safe_name} | VERSION: v{next_version} | "
                f"AUTHOR: {author} | CREATED: {now_str} -->\n\n"
            )
            temp.write(header + content)
            temp_path = Path(temp.name)
        temp_path.replace(draft_path)

        return {
            "doc_name": safe_name,
            "version": next_version,
            "filename": filename,
            "path": draft_path,
            "bytes": draft_path.stat().st_size,
        }

    def list_drafts(self, doc_name: str | None = None) -> list[dict[str, Any]]:
        """Возвращает список сохранённых версионных черновиков (от новых к старым)."""
        if doc_name:
            safe_name = self._validate_safe_name(doc_name)
            pattern = f"{safe_name}_v*.md"
        else:
            pattern = "*.md"

        results = []
        for path in sorted(self.drafts_dir.glob(pattern), reverse=True):
            if path.is_symlink():
                continue
            match = re.search(r"^(.*?)_v(\d+)_(\d+_\d+)\.md$", path.name)
            if match:
                name, ver_str, created_str = match.groups()
                results.append({
                    "doc_name": name,
                    "version": int(ver_str),
                    "created": created_str,
                    "filename": path.name,
                    "path": path,
                    "bytes": path.stat().st_size,
                })
        # Сортировка по номеру версии по убыванию
        results.sort(key=lambda x: x["version"], reverse=True)
        return results

    def read_draft(self, filename: str) -> str:
        """Безопасное чтение черновика с защитой от path traversal и симлинков."""
        if not filename or not isinstance(filename, str):
            raise PathTraversalError("Недопустимое имя файла")
        if "\x00" in filename or "/" in filename or "\\" in filename or ".." in filename or "~" in filename or filename.startswith("."):
            raise PathTraversalError(f"Обнаружена попытка обхода каталога в имени файла: {filename}")
        target = self.drafts_dir / filename
        if target.is_symlink():
            raise PathTraversalError(f"Символические ссылки запрещены: {filename}")
        self._validate_safe_path(target, self.drafts_dir)
        if not target.is_file():
            raise FileNotFoundError(f"Файл не найден: {filename}")
        return target.read_text(encoding="utf-8")
