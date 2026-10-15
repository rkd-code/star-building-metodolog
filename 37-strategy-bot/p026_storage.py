"""Изолированное защищённое файловое хранилище решений владельца и черновиков P-026."""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import json
import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_STORAGE_DIR = Path.home() / ".local" / "share" / "star-building" / "dramknote-p026"
ALLOWED_NAME_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ0-9_-]+$")


class PathTraversalError(ValueError):
    """Исключение при попытке обхода каталога или использования некорректного пути."""


class JournalCorruptionError(RuntimeError):
    """Исключение при синтаксическом или структурном повреждении журнала решений."""

ALLOWED_DECISION_STATUSES = {"active", "archived", "superseded"}

def validate_ownership_id(val: Any, field_name: str = "user_id") -> int | None:
    """Строгая типизация идентификаторов актора и чата Telegram:
    Исключает bool (в Python bool является подклассом int: True == 1).
    Разрешает положительные user ID и отрицательные chat ID (-100...).
    """
    if val is None:
        return None
    if type(val) is not int or isinstance(val, bool):
        raise ValueError(f"Поле {field_name} должно быть целым числом (int) и не может быть bool: {val!r}")
    return val

def validate_iso8601_timestamp(ts: Any) -> str:
    """Строгая валидация формата timestamp:
    Требует полный ISO-8601 с датой, временем и явным часовым поясом (timezone offset).
    Date-only (2026-10-15) и naive timestamps без таймзоны отклоняются.
    """
    if not isinstance(ts, str) or not ts.strip():
        raise ValueError("timestamp должен быть непустой строкой")
    ts_clean = ts.strip()
    if "T" not in ts_clean and " " not in ts_clean:
        raise ValueError(f"timestamp '{ts_clean}' должен содержать дату и время, разделенные 'T' или пробелом")
    try:
        dt = datetime.datetime.fromisoformat(ts_clean.replace("Z", "+00:00"))
    except Exception as err:
        raise ValueError(f"Невалидный ISO-8601 timestamp '{ts_clean}': {err}") from err
    if dt.tzinfo is None:
        raise ValueError(f"timestamp '{ts_clean}' должен содержать явный часовой пояс (timezone offset)")
    return ts_clean

def validate_decision_record(
    item: Any,
    idx: int | None = None,
    seen_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Единый канонический валидатор записей решений для чтения и записи.
    Обеспечивает fail-closed валидацию обязательных полей, разрешение алиасов
    и запрет конфликтующих значений.
    """
    prefix = f"Запись #{idx}: " if idx is not None else "Запись решения: "
    if not isinstance(item, dict):
        raise ValueError(f"{prefix}не является объектом словаря")

    # Проверка конфликтующих канонических полей и устаревших алиасов
    if "id" in item and "decision_id" in item and item["id"] != item["decision_id"]:
        raise ValueError(f"{prefix}конфликт канонического поля 'id' ('{item['id']}') и устаревшего алиаса 'decision_id' ('{item['decision_id']}')")
    raw_id = item.get("id") if "id" in item else item.get("decision_id")
    if not raw_id or not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError(f"{prefix}не содержит строкового идентификатора решения ('id')")
    item_id = raw_id.strip()
    if seen_ids is not None:
        if item_id in seen_ids:
            raise ValueError(f"{prefix}содержит дублирующийся идентификатор решения '{item_id}'")
        seen_ids.add(item_id)

    if "question_context" in item and "context" in item and item["question_context"] != item["context"]:
        raise ValueError(f"{prefix}конфликт канонического поля 'question_context' и алиаса 'context'")
    raw_ctx = item.get("question_context") if "question_context" in item else item.get("context")
    if raw_ctx is None or not isinstance(raw_ctx, str) or not raw_ctx.strip():
        raise ValueError(f"{prefix}не содержит строкового поля контекста ('question_context')")

    if "exact_text" in item and "text" in item and item["exact_text"] != item["text"]:
        raise ValueError(f"{prefix}конфликт канонического поля 'exact_text' и алиаса 'text'")
    raw_txt = item.get("exact_text") if "exact_text" in item else item.get("text")
    if raw_txt is None or not isinstance(raw_txt, str) or not raw_txt.strip():
        raise ValueError(f"{prefix}не содержит содержательного текста решения ('exact_text')")

    ts = validate_iso8601_timestamp(item.get("timestamp"))

    status = item.get("status", "active")
    if not status or not isinstance(status, str) or status not in ALLOWED_DECISION_STATUSES:
        raise ValueError(f"{prefix}содержит недопустимый статус '{status}'. Разрешены: {sorted(ALLOWED_DECISION_STATUSES)}")

    author = item.get("author")
    if author is not None and not isinstance(author, str):
        raise ValueError(f"{prefix}автор должен быть строкой")
    author_str = author.strip() if (isinstance(author, str) and author.strip()) else "Руководитель"

    user_id = validate_ownership_id(item.get("user_id"), "user_id")
    chat_id = validate_ownership_id(item.get("chat_id"), "chat_id")

    return {
        "id": item_id,
        "timestamp": ts,
        "author": author_str,
        "user_id": user_id,
        "chat_id": chat_id,
        "question_context": raw_ctx.strip(),
        "exact_text": raw_txt.strip(),
        "status": status,
    }


def get_default_storage_dir() -> Path:
    """Определяет базовый путь хранилища с поддержкой systemd STATE_DIRECTORY."""
    env_override = os.environ.get("DRAMKNOTE_P026_STORAGE_DIR")
    if env_override:
        return Path(env_override)
    state_dir = os.environ.get("STATE_DIRECTORY")
    if state_dir:
        # systemd может передавать несколько путей через двоеточие
        first_dir = state_dir.split(":")[0].strip()
        if first_dir:
            return Path(first_dir)
    return DEFAULT_STORAGE_DIR


class P026Storage:
    _thread_locks: dict[str, threading.RLock] = {}
    _lock_depths = threading.local()

    def __init__(self, base_dir: Path | str | None = None, create_dirs: bool = True) -> None:
        if base_dir is None:
            self.base_dir = get_default_storage_dir()
        else:
            self.base_dir = Path(base_dir)

        # Fail-closed предвалидация базового пути до любых файловых операций
        self._assert_no_symlinks(self.base_dir)

        self.decisions_dir = self.base_dir / "decisions"
        self.drafts_dir = self.base_dir / "drafts"
        self.decisions_file = self.decisions_dir / "decisions.json"
        self.decisions_lock_file = self.decisions_dir / ".decisions.lock"
        self.drafts_lock_file = self.drafts_dir / ".drafts.lock"

        # Предвалидация всех целевых путей до создания каталогов
        for target in (
            self.decisions_dir,
            self.drafts_dir,
            self.decisions_file,
            self.decisions_lock_file,
            self.drafts_lock_file,
        ):
            self._assert_no_symlinks(target)

        if create_dirs:
            self._ensure_dirs()

    def _assert_no_symlinks(self, path: Path | str) -> None:
        """Строгая fail-closed проверка на отсутствие символических ссылок на всех уровнях предков."""
        p = Path(path)
        # 1. Проверяем все компоненты пути в прямом представлении
        curr = p
        while True:
            if curr.is_symlink() or os.path.islink(str(curr)):
                raise PathTraversalError(f"Символические ссылки строго запрещены: {curr}")
            if curr == curr.parent:
                break
            curr = curr.parent

        # 2. Проверяем абсолютное представление без следования по symlink
        abs_p = Path(os.path.abspath(str(p)))
        curr = abs_p
        while True:
            if curr.is_symlink() or os.path.islink(str(curr)):
                raise PathTraversalError(f"Символические ссылки строго запрещены: {curr}")
            if curr == curr.parent:
                break
            curr = curr.parent

    def _ensure_dirs(self) -> None:
        """Создает изолированные каталоги с защитой от symlink-атак."""
        # Предвалидация ВСЕХ путей и их предков ДО любых вызовов mkdir
        for p in (
            self.base_dir,
            self.decisions_dir,
            self.drafts_dir,
            self.decisions_file,
            self.decisions_lock_file,
            self.drafts_lock_file,
        ):
            self._assert_no_symlinks(p)

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._assert_no_symlinks(self.base_dir)

        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        self._assert_no_symlinks(self.decisions_dir)

        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self._assert_no_symlinks(self.drafts_dir)

        if not self.decisions_file.exists():
            with self._exclusive_lock(self.decisions_lock_file):
                if not self.decisions_file.exists():
                    self._write_json_atomic(self.decisions_file, [])

    @contextlib.contextmanager
    def _exclusive_lock(self, lock_file: Path, timeout: float = 10.0):
        """Межпроцессная сериализация через flock с поддержкой реентерабельности и таймаута."""
        self._assert_no_symlinks(lock_file)
        self._assert_no_symlinks(lock_file.parent)
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        key = os.path.abspath(str(lock_file))
        if key not in P026Storage._thread_locks:
            P026Storage._thread_locks[key] = threading.RLock()
        rlock = P026Storage._thread_locks[key]

        start_time = time.monotonic()
        acquired_rlock = rlock.acquire(timeout=timeout)
        if not acquired_rlock:
            raise TimeoutError(f"Таймаут ожидания блокировки потока: {lock_file}")

        depth = getattr(P026Storage._lock_depths, key, 0)
        fd = None
        try:
            if depth == 0:
                self._assert_no_symlinks(lock_file)
                open_flags = os.O_CREAT | os.O_RDWR
                if hasattr(os, "O_NOFOLLOW"):
                    open_flags |= os.O_NOFOLLOW
                try:
                    fd = os.open(str(lock_file), open_flags, 0o600)
                except OSError as err:
                    if lock_file.is_symlink() or os.path.islink(str(lock_file)):
                        raise PathTraversalError(f"Символические ссылки строго запрещены для lock-файла: {lock_file}") from err
                    raise
                while True:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except (BlockingIOError, OSError):
                        if time.monotonic() - start_time >= timeout:
                            raise TimeoutError(f"Таймаут ожидания межпроцессной блокировки: {lock_file}")
                        time.sleep(0.005)
            P026Storage._lock_depths.__dict__[key] = depth + 1
            yield
        finally:
            cur_depth = getattr(P026Storage._lock_depths, key, 1) - 1
            P026Storage._lock_depths.__dict__[key] = cur_depth
            if cur_depth == 0 and fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass
            rlock.release()

    def _validate_safe_name(self, name: str) -> str:
        if not name or not isinstance(name, str):
            raise PathTraversalError("Пустое или некорректное имя")
        if "\x00" in name or "/" in name or "\\" in name or ".." in name:
            raise PathTraversalError(f"Обнаружены запрещённые символы пути в имени: {name}")
        base = name.strip()
        if not ALLOWED_NAME_RE.match(base):
            raise PathTraversalError(
                f"Имя содержит недопустимые символы (разрешены буквы, цифры, дефис, подчеркивание): {name}"
            )
        return base

    def _validate_safe_path(self, target_path: Path, expected_parent: Path) -> Path:
        """Строгая fail-closed валидация без доверия симлинкованным родителям."""
        self._assert_no_symlinks(expected_parent)
        self._assert_no_symlinks(target_path)

        resolved_target = target_path.resolve()
        resolved_parent = expected_parent.resolve()
        resolved_base = self.base_dir.resolve()

        # Символические ссылки запрещены на любых этапах
        if target_path.is_symlink() or expected_parent.is_symlink():
            raise PathTraversalError(f"Символические ссылки запрещены: {target_path}")

        try:
            resolved_target.relative_to(resolved_parent)
            resolved_parent.relative_to(resolved_base)
        except ValueError as err:
            raise PathTraversalError(f"Попытка выхода за пределы изолированного каталога: {target_path}") from err
        return resolved_target

    def _write_json_atomic(self, target: Path, data: Any) -> None:
        """Атомарная запись с fsync временного файла и родительского каталога."""
        self._validate_safe_path(target, target.parent)
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=parent, delete=False, encoding="utf-8") as temp:
            json.dump(data, temp, ensure_ascii=False, indent=2)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = Path(temp.name)

        self._assert_no_symlinks(temp_path)
        temp_path.replace(target)

        # Fsync родительского каталога для надёжности транзакции
        try:
            dir_fd = os.open(str(parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

    def _read_decisions_raw(self) -> list[dict[str, Any]]:
        """Читает журнал решений; при повреждении отправляет в карантин и возвращает отказ."""
        self._validate_safe_path(self.decisions_file, self.decisions_dir)
        if not self.decisions_file.exists():
            return []
        raw_text = self.decisions_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            # Пустой существующий файл журнала (0 байт) является признаком повреждения
            now_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            corrupt_backup = self.decisions_dir / f"decisions_corrupted_{now_ts}.json.bak"
            shutil.copy2(self.decisions_file, corrupt_backup)
            raise JournalCorruptionError(
                f"Журнал решений пуст (0 байт): {self.decisions_file.name}. "
                f"Сохранён в карантин: {corrupt_backup.name}. Операция заблокирована."
            )

        try:
            data = json.loads(raw_text)
            if not isinstance(data, list):
                raise ValueError("Корневой элемент журнала решений должен быть списком")

            normalized_list: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            for idx, item in enumerate(data):
                norm_item = validate_decision_record(item, idx=idx, seen_ids=seen_ids)
                normalized_list.append(norm_item)

            return normalized_list
        except Exception as err:
            # Повреждённый журнал: fail-closed карантин, запрет немой перезаписи
            now_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            corrupt_backup = self.decisions_dir / f"decisions_corrupted_{now_ts}.json.bak"
            shutil.copy2(self.decisions_file, corrupt_backup)
            raise JournalCorruptionError(
                f"Журнал решений повреждён и сохранён в карантин: {corrupt_backup.name}. "
                "Операция заблокирована для сохранения данных."
            ) from err

    def record_decision(
        self,
        author: str,
        question_context: str,
        exact_text: str,
        user_id: int | None = None,
        chat_id: int | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Фиксирует точное решение владельца в журнале с сериализацией и изоляцией."""
        self._ensure_dirs()
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        with self._exclusive_lock(self.decisions_lock_file):
            current = self._read_decisions_raw()
            seen_ids = {r["id"] for r in current}
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            ts_micro = int(datetime.datetime.now().timestamp() * 1_000_000)
            next_num = len(current) + 1
            decision_id = f"dec_{next_num}_{ts_micro}"

            candidate = {
                "id": decision_id,
                "timestamp": now,
                "author": author,
                "user_id": user_id,
                "chat_id": chat_id,
                "question_context": question_context.strip() if isinstance(question_context, str) else "",
                "exact_text": exact_text.strip() if isinstance(exact_text, str) else "",
                "status": status,
            }
            validated_record = validate_decision_record(candidate, seen_ids=seen_ids)
            current.append(validated_record)
            self._write_json_atomic(self.decisions_file, current)
            return validated_record

    def list_decisions(
        self,
        user_id: int | None = None,
        chat_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает список решений со строгой actor/chat фильтрацией."""
        self._ensure_dirs()
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        with self._exclusive_lock(self.decisions_lock_file):
            items = self._read_decisions_raw()

        results = []
        for item in items:
            item_uid = item.get("user_id")
            if user_id is not None:
                if type(item_uid) is not int or isinstance(item_uid, bool) or item_uid != user_id:
                    continue
            item_cid = item.get("chat_id")
            if chat_id is not None:
                if type(item_cid) is not int or isinstance(item_cid, bool) or item_cid != chat_id:
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
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        """Сохраняет версионный рабочий черновик с защитой от коллизий и перезаписи."""
        self._ensure_dirs()
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        safe_name = self._validate_safe_name(doc_name)

        with self._exclusive_lock(self.drafts_lock_file):
            existing = self._list_drafts_unlocked(safe_name)
            next_version = (existing[0]["version"] + 1) if existing else 1

            # Микросекундная точность для исключения коллизий в одну секунду
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{safe_name}_v{next_version}_{now_str}.md"
            draft_path = self.drafts_dir / filename

            # Гарантия неповторяемости имени
            revision_counter = 1
            while draft_path.exists():
                filename = f"{safe_name}_v{next_version}_{now_str}_r{revision_counter}.md"
                draft_path = self.drafts_dir / filename
                revision_counter += 1

            self._validate_safe_path(draft_path, self.drafts_dir)

            header = (
                f"<!-- DRAFT ARTIFACT: {safe_name} | VERSION: v{next_version} | "
                f"AUTHOR: {author} | USER_ID: {user_id} | CHAT_ID: {chat_id} | "
                f"CREATED: {now_str} -->\n\n"
            )

            with tempfile.NamedTemporaryFile("w", dir=self.drafts_dir, delete=False, encoding="utf-8") as temp:
                temp.write(header + content)
                temp.flush()
                os.fsync(temp.fileno())
                temp_path = Path(temp.name)

            self._assert_no_symlinks(temp_path)
            temp_path.replace(draft_path)

            try:
                dir_fd = os.open(str(self.drafts_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass

        return {
            "doc_name": safe_name,
            "version": next_version,
            "filename": filename,
            "path": draft_path,
            "bytes": draft_path.stat().st_size,
            "user_id": user_id,
            "chat_id": chat_id,
        }

    def _list_drafts_unlocked(
        self,
        doc_name: str | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if doc_name:
            safe_name = self._validate_safe_name(doc_name)
            pattern = f"{safe_name}_v*.md"
        else:
            pattern = "*.md"

        results = []
        for path in sorted(self.drafts_dir.glob(pattern), reverse=True):
                if path.is_symlink() or os.path.islink(path):
                    continue
                match = re.search(r"^(.*?)_v(\d+)_([0-9_]+.*?)\.md$", path.name)
                if match:
                    name, ver_str, created_str = match.groups()

                    # Фильтрация по владельцу черновика при необходимости
                    draft_user_id = None
                    draft_chat_id = None
                    try:
                        # Читаем первую строку заголовка для actor isolation
                        with path.open("r", encoding="utf-8") as f:
                            first_line = f.readline()
                        u_match = re.search(r"USER_ID:\s*(-?\d+|None)", first_line)
                        if u_match and u_match.group(1) != "None":
                            draft_user_id = int(u_match.group(1))
                        c_match = re.search(r"CHAT_ID:\s*(-?\d+|None)", first_line)
                        if c_match and c_match.group(1) != "None":
                            draft_chat_id = int(c_match.group(1))
                    except Exception:
                        pass

                    # Строгая fail-closed фильтрация: черновики без подтверждённого владельца
                    # не выдаются при запросе конкретного актора/чата
                    if user_id is not None and (draft_user_id is None or draft_user_id != user_id):
                        continue
                    if chat_id is not None and (draft_chat_id is None or draft_chat_id != chat_id):
                        continue

                    results.append({
                        "doc_name": name,
                        "version": int(ver_str),
                        "created": created_str,
                        "filename": path.name,
                        "path": path,
                        "bytes": path.stat().st_size,
                        "user_id": draft_user_id,
                        "chat_id": draft_chat_id,
                    })
        results.sort(key=lambda x: x["version"], reverse=True)
        return results

    def list_drafts(
        self,
        doc_name: str | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает список сохранённых версионных черновиков (от новых к старым)."""
        self._ensure_dirs()
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        with self._exclusive_lock(self.drafts_lock_file):
            return self._list_drafts_unlocked(doc_name=doc_name, user_id=user_id, chat_id=chat_id)

    def read_draft(self, filename: str, user_id: int | None = None, chat_id: int | None = None) -> str:
        """Безопасное чтение черновика со строгой проверкой symlinks и actor isolation."""
        self._ensure_dirs()
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        if not filename or not isinstance(filename, str):
            raise PathTraversalError("Недопустимое имя файла")
        if (
            "\x00" in filename
            or "/" in filename
            or "\\" in filename
            or ".." in filename
            or "~" in filename
            or filename.startswith(".")
        ):
            raise PathTraversalError(f"Обнаружена попытка обхода каталога в имени файла: {filename}")

        target = self.drafts_dir / filename
        if target.is_symlink() or os.path.islink(target):
            raise PathTraversalError(f"Символические ссылки запрещены: {filename}")
        self._validate_safe_path(target, self.drafts_dir)

        if not target.is_file():
            raise FileNotFoundError(f"Файл не найден: {filename}")

        content = target.read_text(encoding="utf-8")
        first_line = content.split("\n", 1)[0]
        u_match = re.search(r"USER_ID:\s*(-?\d+|None)", first_line)
        c_match = re.search(r"CHAT_ID:\s*(-?\d+|None)", first_line)

        draft_user_id = int(u_match.group(1)) if (u_match and u_match.group(1) != "None") else None
        draft_chat_id = int(c_match.group(1)) if (c_match and c_match.group(1) != "None") else None

        if user_id is not None:
            if draft_user_id is None:
                raise PermissionError("Доступ к черновику без подтверждённого владельца запрещён (fail-closed)")
            if draft_user_id != user_id:
                raise PermissionError(f"Доступ к чужому черновику запрещён: {draft_user_id} != {user_id}")

        if chat_id is not None:
            if draft_chat_id is None:
                raise PermissionError("Доступ к черновику без подтверждённого чата запрещён (fail-closed)")
            if draft_chat_id != chat_id:
                raise PermissionError(f"Доступ к черновику из другого чата запрещён: {draft_chat_id} != {chat_id}")

        return content
