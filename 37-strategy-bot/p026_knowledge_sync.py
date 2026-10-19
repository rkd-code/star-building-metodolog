"""Модуль доверенной регистрации и версионного обмена рабочими разработками Драмкнота (FN-015).

Архитектурные требования:
1. Разделение Producer и Registrar: Драмкнот формирует неизменяемый пакет в собственном outbox;
   бот не имеет прав записи во всю общую базу знаний.
2. Идентичность и версионность: явные статусы (draft, confirmed_decision, verified_work_material, archived, superseded).
   Ни одно из этих состояний не является утверждением ГД.
3. Абсолютная неприкосновенность ГД-контура (02_УТВЕРЖДЕНО): строгий запрет записи в 02_УТВЕРЖДЕНО (fail-closed).
4. Авторизованный Consumer: чтение материалов разрешено только авторизованным ролям (Пондер, Драмкнот, КД).
   Бот «Ом», неавторизованные помощники и approved-only контур не имеют доступа к рабочим материалам.
5. Идемпотентность и отказоустойчивость: защита от дубликатов, транзакционность через flock,
   fail-closed карантин поврежденных пакетов.
"""

from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from p026_storage import (
    ALLOWED_NAME_RE,
    PathTraversalError,
    validate_iso8601_timestamp,
    validate_ownership_id,
)

# Статусы жизненного цикла разработок
STATUS_DRAFT = "draft"
STATUS_CONFIRMED_DECISION = "confirmed_decision"
STATUS_VERIFIED_MATERIAL = "verified_work_material"
STATUS_ARCHIVED = "archived"
STATUS_SUPERSEDED = "superseded"

ALLOWED_STATUSES = {
    STATUS_DRAFT,
    STATUS_CONFIRMED_DECISION,
    STATUS_VERIFIED_MATERIAL,
    STATUS_ARCHIVED,
    STATUS_SUPERSEDED,
}

# Синонимы статусов для устойчивой нормализации
STATUS_ALIASES = {
    "черновик": STATUS_DRAFT,
    "предложение": STATUS_DRAFT,
    "draft": STATUS_DRAFT,
    "proposal": STATUS_DRAFT,
    "подтвержденное решение": STATUS_CONFIRMED_DECISION,
    "подтверждённое решение": STATUS_CONFIRMED_DECISION,
    "решение": STATUS_CONFIRMED_DECISION,
    "decision": STATUS_CONFIRMED_DECISION,
    "confirmed_decision": STATUS_CONFIRMED_DECISION,
    "проверенный материал": STATUS_VERIFIED_MATERIAL,
    "проверенный рабочий материал": STATUS_VERIFIED_MATERIAL,
    "verified": STATUS_VERIFIED_MATERIAL,
    "verified_work_material": STATUS_VERIFIED_MATERIAL,
    "архив": STATUS_ARCHIVED,
    "архивная версия": STATUS_ARCHIVED,
    "archived": STATUS_ARCHIVED,
    "замененная версия": STATUS_SUPERSEDED,
    "заменённая версия": STATUS_SUPERSEDED,
    "superseded": STATUS_SUPERSEDED,
}

# Роли доступа
DEFAULT_ALLOWED_AUDIENCE = ["ponder", "developer", "dramknote", "commercial_department"]
DENIED_AUDIENCE_ROLES = {
    "om",
    "ом",
    "consultant",
    "консультант",
    "approved_only",
    "утвержденный_контур",
    "unauthorized",
    "unauthorized_guest",
    "guest",
}


class ApprovedContourImmunityError(PermissionError):
    """Исключение при любой попытке модификации контура 02_УТВЕРЖДЕНО."""


class PackageValidationError(ValueError):
    """Исключение при нарушении схемы или целостности пакета разработки."""


class KnowledgeSyncIntegrityError(RuntimeError):
    """Исключение при нарушении ссылочной или физической целостности зарегистрированных данных."""


def normalize_status(raw_status: str | None) -> str:
    """Нормализует статус разработки к каноническому виду."""
    if not raw_status or not isinstance(raw_status, str):
        raise PackageValidationError("Статус разработки должен быть непустой строкой")
    clean = raw_status.strip().lower()
    if clean in STATUS_ALIASES:
        return STATUS_ALIASES[clean]
    if clean in ALLOWED_STATUSES:
        return clean
    raise PackageValidationError(
        f"Недопустимый статус разработки: '{raw_status}'. "
        f"Разрешены: {sorted(ALLOWED_STATUSES)}"
    )


def assert_no_symlinks(path: Path | str) -> None:
    """Строгая fail-closed проверка на отсутствие символических ссылок на всех уровнях предков."""
    p = Path(path)
    curr = p
    while True:
        if curr.is_symlink() or os.path.islink(str(curr)):
            raise PathTraversalError(f"Символические ссылки строго запрещены: {curr}")
        if curr == curr.parent:
            break
        curr = curr.parent

    abs_p = Path(os.path.abspath(str(p)))
    curr = abs_p
    while True:
        if curr.is_symlink() or os.path.islink(str(curr)):
            raise PathTraversalError(f"Символические ссылки строго запрещены: {curr}")
        if curr == curr.parent:
            break
        curr = curr.parent


def validate_safe_filename(name: str) -> str:
    """Проверяет безопасность имени файла полезной нагрузки."""
    if not name or not isinstance(name, str):
        raise PathTraversalError("Пустое или некорректное имя файла")
    if (
        "\x00" in name
        or "/" in name
        or "\\" in name
        or ".." in name
        or "~" in name
        or name.startswith(".")
    ):
        raise PathTraversalError(f"Обнаружены запрещённые символы пути в имени файла: {name}")
    # Проверяем расширение и базовое имя
    parts = name.rsplit(".", 1)
    base = parts[0]
    if not ALLOWED_NAME_RE.match(base):
        raise PathTraversalError(
            f"Имя файла содержит недопустимые символы: {name}"
        )
    return name


class DramknoteProducer:
    """Компонент формирования пакетов разработки в изолированном outbox Драмкнота."""

    def __init__(self, outbox_dir: Path | str | None = None) -> None:
        if outbox_dir is None:
            from p026_storage import get_default_storage_dir
            self.outbox_dir = get_default_storage_dir() / "outbox"
        else:
            self.outbox_dir = Path(outbox_dir)

        assert_no_symlinks(self.outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def create_package(
        self,
        material_id: str,
        project: str,
        author: str,
        content: str | bytes,
        filename: str,
        material_type: str = "decision",
        version: int | str = 1,
        parent_ref: str | None = None,
        status: str = STATUS_DRAFT,
        audience: list[str] | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Формирует и атомарно сохраняет неизменяемый пакет разработки в outbox."""
        safe_pkg_id = validate_safe_filename(material_id)
        safe_filename = validate_safe_filename(filename)
        canonical_status = normalize_status(status)

        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")

        if not audience:
            audience = list(DEFAULT_ALLOWED_AUDIENCE)
        elif not isinstance(audience, list) or not all(isinstance(x, str) for x in audience):
            raise PackageValidationError("Поле audience должно быть списком строк")

        # Подготовка бинарных данных полезной нагрузки
        payload_bytes = content.encode("utf-8") if isinstance(content, str) else content
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        payload_size = len(payload_bytes)

        # Таймштамп в строгом формате ISO-8601 с часовым поясом UTC
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        package_dir = self.outbox_dir / safe_pkg_id
        assert_no_symlinks(self.outbox_dir)
        package_dir.mkdir(parents=True, exist_ok=True)
        assert_no_symlinks(package_dir)

        payload_path = package_dir / safe_filename
        manifest_path = package_dir / "manifest.json"

        # Запись полезной нагрузки
        with tempfile.NamedTemporaryFile("wb", dir=package_dir, delete=False) as tmp_payload:
            tmp_payload.write(payload_bytes)
            tmp_payload.flush()
            os.fsync(tmp_payload.fileno())
            tmp_payload_path = Path(tmp_payload.name)
        assert_no_symlinks(tmp_payload_path)
        tmp_payload_path.replace(payload_path)

        # Формирование манифеста
        manifest = {
            "id": safe_pkg_id,
            "project": project.strip() if isinstance(project, str) else "P-026",
            "author": author.strip() if isinstance(author, str) else "Руководитель",
            "user_id": user_id,
            "chat_id": chat_id,
            "timestamp": now_ts,
            "material_type": material_type.strip(),
            "version": version,
            "parent_ref": parent_ref,
            "payload_filename": safe_filename,
            "payload_sha256": payload_sha256,
            "payload_size": payload_size,
            "status": canonical_status,
            "audience": audience,
            "metadata": metadata or {},
        }

        # Атомарная запись манифеста
        with tempfile.NamedTemporaryFile("w", dir=package_dir, delete=False, encoding="utf-8") as tmp_m:
            json.dump(manifest, tmp_m, ensure_ascii=False, indent=2)
            tmp_m.flush()
            os.fsync(tmp_m.fileno())
            tmp_m_path = Path(tmp_m.name)
        assert_no_symlinks(tmp_m_path)
        tmp_m_path.replace(manifest_path)

        return {
            "package_id": safe_pkg_id,
            "package_dir": package_dir,
            "payload_path": payload_path,
            "manifest_path": manifest_path,
            "manifest": manifest,
        }


class SharedKnowledgeRegistrar:
    """Доверенная служба валидации и регистрации разработок в общую рабочую базу знаний."""

    _thread_locks: dict[str, threading.RLock] = {}

    def __init__(
        self,
        kb_dir: Path | str | None = None,
        working_dir: Path | str | None = None,
        approved_dir: Path | str | None = None,
        registry_dir: Path | str | None = None,
        quarantine_dir: Path | str | None = None,
    ) -> None:
        self.kb_dir = Path(kb_dir).resolve() if kb_dir else (Path.home() / "knowledge_base").resolve()
        self.working_dir = Path(working_dir).resolve() if working_dir else (self.kb_dir / "01_В_РАБОТЕ").resolve()
        self.approved_dir = Path(approved_dir).resolve() if approved_dir else (self.kb_dir / "02_УТВЕРЖДЕНО").resolve()
        self.registry_dir = Path(registry_dir).resolve() if registry_dir else (self.working_dir / "00_РЕЕСТР_РАЗРАБОТОК").resolve()
        self.quarantine_dir = Path(quarantine_dir).resolve() if quarantine_dir else (self.working_dir / "quarantine").resolve()

        # Абсолютная защита утвержденного контура: рабочий каталог не может быть равен или быть внутри утвержденного
        if (
            self.working_dir == self.approved_dir
            or self.approved_dir in self.working_dir.parents
            or self.working_dir in self.approved_dir.parents
        ):
            raise ApprovedContourImmunityError(
                f"КРИТИЧЕСКАЯ ОШИБКА: Контур 02_УТВЕРЖДЕНО ({self.approved_dir}) неприкосновенен "
                f"и не может использоваться как рабочий каталог регистрации ({self.working_dir})!"
            )

        assert_no_symlinks(self.kb_dir)
        assert_no_symlinks(self.working_dir)
        assert_no_symlinks(self.registry_dir)
        assert_no_symlinks(self.quarantine_dir)

        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.registry_dir / "registry.json"
        self.registry_markdown = self.registry_dir / "REGISTRY.md"
        self.registry_lock_file = self.registry_dir / ".registry.lock"

        # Инициализация файла реестра при его отсутствии
        if not self.registry_file.exists():
            with self._exclusive_lock(self.registry_lock_file):
                if not self.registry_file.exists():
                    init_data = {
                        "schema_version": "1.0.0",
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "records": [],
                    }
                    self._write_json_atomic(self.registry_file, init_data)
                    self._render_markdown_registry(init_data["records"])

    @contextlib.contextmanager
    def _exclusive_lock(self, lock_file: Path, timeout: float = 10.0):
        """Межпроцессная сериализация через flock."""
        assert_no_symlinks(lock_file)
        assert_no_symlinks(lock_file.parent)
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        key = str(lock_file.resolve())
        if key not in SharedKnowledgeRegistrar._thread_locks:
            SharedKnowledgeRegistrar._thread_locks[key] = threading.RLock()
        rlock = SharedKnowledgeRegistrar._thread_locks[key]

        start_time = time.monotonic()
        if not rlock.acquire(timeout=timeout):
            raise TimeoutError(f"Таймаут ожидания потоковой блокировки: {lock_file}")

        fd = None
        try:
            open_flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                open_flags |= os.O_NOFOLLOW
            fd = os.open(str(lock_file), open_flags, 0o600)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (BlockingIOError, OSError):
                    if time.monotonic() - start_time >= timeout:
                        raise TimeoutError(f"Таймаут ожидания flock: {lock_file}")
                    time.sleep(0.005)
            yield
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass
            rlock.release()

    def _write_json_atomic(self, target: Path, data: Any) -> None:
        """Атомарная запись JSON с fsync."""
        assert_no_symlinks(target.parent)
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=parent, delete=False, encoding="utf-8") as temp:
            json.dump(data, temp, ensure_ascii=False, indent=2)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = Path(temp.name)

        assert_no_symlinks(temp_path)
        temp_path.replace(target)
        try:
            dir_fd = os.open(str(parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

    def _render_markdown_registry(self, records: list[dict[str, Any]]) -> None:
        """Обновляет удобочитаемый файл реестра REGISTRY.md."""
        lines = [
            "# Общий реестр рабочих разработок Star Building (FN-015)",
            "",
            "Данный реестр содержит зарегистрированные рабочие материалы, черновики и решения.",
            "**Важно:** материалы данного реестра не являются утвержденными Генеральным директором нормами.",
            "",
            f"Последнее обновление: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
            "",
            "| ID | Проект | Тип | Статус | Версия | Автор | Дата UTC | Файл | SHA-256 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in records:
            file_link = r.get("registered_path", "")
            sha_short = r.get("payload_sha256", "")[:12] + "..."
            lines.append(
                f"| `{r['id']}` | {r.get('project', '-')} | {r.get('material_type', '-')} | "
                f"`{r.get('status', '-')}` | v{r.get('version', 1)} | {r.get('author', '-')} | "
                f"{r.get('timestamp', '-')} | `{file_link}` | `{sha_short}` |"
            )
        lines.append("")

        parent = self.registry_markdown.parent
        with tempfile.NamedTemporaryFile("w", dir=parent, delete=False, encoding="utf-8") as temp:
            temp.write("\n".join(lines))
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = Path(temp.name)
        assert_no_symlinks(temp_path)
        temp_path.replace(self.registry_markdown)

    def _quarantine_package(self, package_dir: Path, reason: str) -> dict[str, Any]:
        """Отправляет поврежденный или невалидный пакет в карантин с сохранением причины."""
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target_q = self.quarantine_dir / f"{package_dir.name}_quarantine_{now_str}"
        target_q.mkdir(parents=True, exist_ok=True)

        # Копируем содержимое пакета в карантин, если каталог существует
        if package_dir.exists() and package_dir.is_dir():
            for item in package_dir.iterdir():
                try:
                    if item.is_file() and not item.is_symlink():
                        shutil.copy2(item, target_q / item.name)
                except Exception:
                    pass

        reason_info = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "original_path": str(package_dir),
            "reason": reason,
        }
        (target_q / "quarantine_info.json").write_text(
            json.dumps(reason_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "ok": False,
            "status": "quarantined",
            "reason": reason,
            "quarantine_path": str(target_q),
        }

    def register_package(self, package_dir: Path | str) -> dict[str, Any]:
        """Доверенная регистрация пакета разработки:
        валидация схемы, проверка хэша, перенос в 01_В_РАБОТЕ и запись в реестр.
        """
        pkg_path = Path(package_dir)
        if not pkg_path.exists() or not pkg_path.is_dir():
            return self._quarantine_package(pkg_path, f"Каталог пакета не существует: {pkg_path}")

        manifest_file = pkg_path / "manifest.json"
        if not manifest_file.exists():
            return self._quarantine_package(pkg_path, "Отсутствует обязательный файл manifest.json")

        try:
            assert_no_symlinks(manifest_file)
            manifest_text = manifest_file.read_text(encoding="utf-8")
            manifest = json.loads(manifest_text)
            if not isinstance(manifest, dict):
                return self._quarantine_package(pkg_path, "Манифест не является JSON-объектом")
        except Exception as err:
            return self._quarantine_package(pkg_path, f"Ошибка чтения/парсинга JSON манифеста: {err}")

        # Проверка обязательных полей
        required_fields = [
            "id", "project", "author", "timestamp", "material_type",
            "payload_filename", "payload_sha256", "payload_size", "status", "audience"
        ]
        for field in required_fields:
            if field not in manifest or manifest[field] is None:
                return self._quarantine_package(pkg_path, f"В манифесте отсутствует обязательное поле: '{field}'")

        pkg_id = str(manifest["id"]).strip()
        try:
            validate_safe_filename(pkg_id)
        except PathTraversalError as err:
            return self._quarantine_package(pkg_path, f"Недопустимый ID пакета (path traversal): {err}")

        # Валидация timestamp
        try:
            validate_iso8601_timestamp(manifest["timestamp"])
        except Exception as err:
            return self._quarantine_package(pkg_path, f"Невалидный timestamp в манифесте: {err}")

        # Валидация статуса
        try:
            canonical_status = normalize_status(manifest["status"])
        except PackageValidationError as err:
            return self._quarantine_package(pkg_path, f"Недопустимый статус разработки: {err}")

        # Проверка path traversal и защита утвержденного контура
        raw_filename = manifest["payload_filename"]
        target_subpath = manifest.get("target_subpath", "")
        if "02_УТВЕРЖДЕНО" in target_subpath or "02_УТВЕРЖДЕНО" in raw_filename:
            return self._quarantine_package(
                pkg_path,
                "КРИТИЧЕСКИЙ ОТКАЗ: Запрещена любая попытка записи в 02_УТВЕРЖДЕНО (path traversal / immutability breach)"
            )

        try:
            safe_filename = validate_safe_filename(raw_filename)
        except PathTraversalError as err:
            return self._quarantine_package(pkg_path, f"Path traversal в имени файла полезной нагрузки: {err}")

        # Проверка полезной нагрузки
        payload_file = pkg_path / safe_filename
        if not payload_file.exists():
            return self._quarantine_package(pkg_path, f"Файл полезной нагрузки '{safe_filename}' не найден в пакете")

        if payload_file.is_symlink() or os.path.islink(str(payload_file)):
            return self._quarantine_package(pkg_path, f"Символические ссылки строго запрещены: {safe_filename}")

        payload_bytes = payload_file.read_bytes()
        actual_size = len(payload_bytes)
        actual_hash = hashlib.sha256(payload_bytes).hexdigest()

        if actual_size != manifest["payload_size"]:
            return self._quarantine_package(
                pkg_path,
                f"Несовпадение заявленного размера ({manifest['payload_size']}) и фактического ({actual_size})"
            )

        if actual_hash != manifest["payload_sha256"]:
            return self._quarantine_package(
                pkg_path,
                f"Несовпадение контрольной суммы хэша ({manifest['payload_sha256']} != {actual_hash})"
            )

        # Регистрация под блокировкой (атомарность и идемпотентность)
        with self._exclusive_lock(self.registry_lock_file):
            assert_no_symlinks(self.registry_file)
            registry_data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            records = registry_data.get("records", [])

            # Проверка идемпотентности
            for existing in records:
                if existing.get("id") == pkg_id:
                    if existing.get("payload_sha256") == actual_hash:
                        return {
                            "ok": True,
                            "status": "already_registered",
                            "record": existing,
                            "registered_path": existing.get("registered_path"),
                        }
                    else:
                        return self._quarantine_package(
                            pkg_path,
                            f"Конфликт хэша: попытка повторной регистрации ID '{pkg_id}' с другим содержимым"
                        )

            # Целевой каталог для артефакта внутри 01_В_РАБОТЕ
            project_dir = self.working_dir / "dramknote_developments" / manifest.get("project", "P-026")
            assert_no_symlinks(self.working_dir)
            project_dir.mkdir(parents=True, exist_ok=True)
            assert_no_symlinks(project_dir)

            dest_filename = f"{pkg_id}_{safe_filename}"
            dest_path = project_dir / dest_filename

            # Строгая защита: проверяем, что dest_path находится внутри working_dir
            if not dest_path.resolve().is_relative_to(self.working_dir.resolve()):
                return self._quarantine_package(pkg_path, "Попытка выхода за пределы рабочего каталога 01_В_РАБОТЕ")

            # Атомарное копирование файла артефакта
            with tempfile.NamedTemporaryFile("wb", dir=project_dir, delete=False) as tmp_dst:
                tmp_dst.write(payload_bytes)
                tmp_dst.flush()
                os.fsync(tmp_dst.fileno())
                tmp_dst_path = Path(tmp_dst.name)
            assert_no_symlinks(tmp_dst_path)
            tmp_dst_path.replace(dest_path)

            # Проверка целостности скопированного артефакта
            if hashlib.sha256(dest_path.read_bytes()).hexdigest() != actual_hash:
                return self._quarantine_package(pkg_path, "Сбой контрольной суммы при записи артефакта на диск")

            # Формирование записи реестра
            record = {
                "id": pkg_id,
                "project": manifest.get("project", "P-026"),
                "author": manifest.get("author", "Руководитель"),
                "user_id": manifest.get("user_id"),
                "chat_id": manifest.get("chat_id"),
                "timestamp": manifest["timestamp"],
                "material_type": manifest["material_type"],
                "version": manifest.get("version", 1),
                "parent_ref": manifest.get("parent_ref"),
                "status": canonical_status,
                "audience": manifest.get("audience", DEFAULT_ALLOWED_AUDIENCE),
                "payload_filename": safe_filename,
                "payload_sha256": actual_hash,
                "payload_size": actual_size,
                "registered_path": str(dest_path),
                "registered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "metadata": manifest.get("metadata", {}),
            }

            records.append(record)
            registry_data["records"] = records
            registry_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            self._write_json_atomic(self.registry_file, registry_data)
            self._render_markdown_registry(records)

            return {
                "ok": True,
                "status": "registered",
                "record": record,
                "registered_path": str(dest_path),
            }

    def process_outbox(self, outbox_dir: Path | str) -> dict[str, Any]:
        """Обрабатывает всю очередь пакетов в каталоге outbox."""
        outbox_path = Path(outbox_dir)
        if not outbox_path.exists() or not outbox_path.is_dir():
            return {"total": 0, "registered": 0, "quarantined": 0, "already_registered": 0}

        results = []
        counts = {"total": 0, "registered": 0, "quarantined": 0, "already_registered": 0}

        for item in sorted(outbox_path.iterdir()):
            if not item.is_dir() or item.name.startswith(".") or item.name == "quarantine":
                continue
            counts["total"] += 1
            res = self.register_package(item)
            results.append(res)
            st = res.get("status")
            if st == "registered":
                counts["registered"] += 1
            elif st == "already_registered":
                counts["already_registered"] += 1
            elif st == "quarantined":
                counts["quarantined"] += 1

        return {**counts, "results": results}


class SharedKnowledgeConsumer:
    """Интерфейс авторизованного доступа к зарегистрированным рабочим материалам."""

    def __init__(
        self,
        kb_dir: Path | str | None = None,
        registry_dir: Path | str | None = None,
    ) -> None:
        self.kb_dir = Path(kb_dir).resolve() if kb_dir else (Path.home() / "knowledge_base").resolve()
        self.working_dir = (self.kb_dir / "01_В_РАБОТЕ").resolve()
        self.registry_dir = Path(registry_dir).resolve() if registry_dir else (self.working_dir / "00_РЕЕСТР_РАЗРАБОТОК").resolve()
        self.registry_file = self.registry_dir / "registry.json"

    def _check_role_authorization(self, requester_role: str, record: dict[str, Any] | None = None) -> bool:
        """Проверяет права роли на чтение рабочих материалов."""
        if not requester_role or not isinstance(requester_role, str):
            return False
        clean_role = requester_role.strip().lower()

        # Запрещенные роли категорически не имеют доступа
        if clean_role in DENIED_AUDIENCE_ROLES:
            return False

        if record is not None:
            audience = record.get("audience", [])
            normalized_aud = [str(x).strip().lower() for x in audience]
            if clean_role not in normalized_aud:
                return False

        return True

    def _read_records_raw(self) -> list[dict[str, Any]]:
        """Читает актуальный реестр разработок."""
        if not self.registry_file.exists():
            return []
        try:
            assert_no_symlinks(self.registry_file)
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            return data.get("records", [])
        except Exception as err:
            raise KnowledgeSyncIntegrityError(f"Сбой чтения реестра разработок: {err}") from err

    def list_materials(
        self,
        requester_role: str,
        project: str | None = None,
        status: str | None = None,
        material_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает список зарегистрированных материалов, доступных данной роли."""
        if not self._check_role_authorization(requester_role):
            return []

        all_records = self._read_records_raw()
        results = []
        for rec in all_records:
            if not self._check_role_authorization(requester_role, rec):
                continue
            if project and rec.get("project") != project:
                continue
            if status and rec.get("status") != normalize_status(status):
                continue
            if material_type and rec.get("material_type") != material_type:
                continue
            results.append(rec)
        return results

    def get_material(self, material_id: str, requester_role: str) -> dict[str, Any]:
        """Возвращает метаданные материала с проверкой прав."""
        if not self._check_role_authorization(requester_role):
            raise PermissionError(
                f"Доступ запрещен: роль '{requester_role}' не имеет прав на рабочие материалы (fail-closed)"
            )

        all_records = self._read_records_raw()
        target_rec = next((r for r in all_records if r.get("id") == material_id), None)
        if not target_rec:
            raise FileNotFoundError(f"Материал с ID '{material_id}' не найден в реестре")

        if not self._check_role_authorization(requester_role, target_rec):
            raise PermissionError(
                f"Доступ запрещен: роль '{requester_role}' не входит в audience материала '{material_id}'"
            )
        return target_rec

    def read_material(self, material_id: str, requester_role: str) -> dict[str, Any]:
        """Считывает содержимое материала с побайтовой верификацией контрольной суммы."""
        record = self.get_material(material_id, requester_role)
        file_path = Path(record["registered_path"])

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Физический файл материала отсутствует на диске: {file_path}")

        if file_path.is_symlink() or os.path.islink(str(file_path)):
            raise PathTraversalError(f"Символические ссылки запрещены для зарегистрированных материалов: {file_path}")

        file_bytes = file_path.read_bytes()
        actual_hash = hashlib.sha256(file_bytes).hexdigest()

        if actual_hash != record["payload_sha256"]:
            raise RuntimeError(
                f"Нарушена целостность зарегистрированного файла на диске: "
                f"ожидался хэш {record['payload_sha256']}, обнаружен {actual_hash}"
            )

        return {
            "ok": True,
            "record": record,
            "content": file_bytes.decode("utf-8", errors="replace"),
            "bytes": len(file_bytes),
        }
