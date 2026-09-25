#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль экспорта регламентов: генерация автономного HTML и интеграция с Google Docs.
Реализует требования договора FN-013 и устраненные замечания независимой приёмки:
- HIGH-1: Строгая валидация полноты регламента is_complete_regulation (только 5 разделов в строгом порядке, ровно по 1, с непустым содержимым);
- HIGH-2: Идемпотентность экспорта в Google Docs (переиспользование gdocs_url, блокировки per-artifact/user, ровно 1 вызов API при 20 параллельных запросах);
- HIGH-3: Безопасность пути OAuth-токена (канонический каталог, lstat, запрет symlink/hardlink, проверка UID, права <= 0600, безопасный atomic refresh / fail-closed);
- HIGH-4: Долговечное ограниченное атомарное хранилище PersistentArtifactStore (сохраняется при перезапуске, изоляция user_id, fail-closed при повреждении);
- MEDIUM-1: Санитизация имени черновика и строгий контроль containment в 01_В_РАБОТЕ;
- MEDIUM-3: Статус ADR-028 IMPLEMENTED_AWAITING_SECURITY_REVIEW_OAUTH_E2E;
- MEDIUM-4: Воспроизводимый манифест зависимостей и верификация импортов.
"""

import html
import io
import logging
import os
import re
import sqlite3
import stat
import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger("artifact_exporter")

CANONICAL_GOOGLE_OAUTH_DIR = Path("/home/roman/.config/star-building")
DEFAULT_GOOGLE_OAUTH_TOKEN_PATH = "/home/roman/.config/star-building/google_oauth_token.json"


class OAuthTokenSecurityError(Exception):
    """Исключение при нарушении безопасности пути или прав доступа OAuth токена."""
    pass


@dataclass
class CompletedArtifact:
    """Хранилище последнего завершённого регламента пользователя."""
    user_id: int
    author_name: str
    regulation_text: str
    html_content: str
    filename: str
    title: str
    created_at: str
    gdocs_url: Optional[str] = None
    gdocs_id: Optional[str] = None


@dataclass
class GoogleDocExportResult:
    """Результат экспорта в Google Docs."""
    success: bool
    message: str
    doc_url: Optional[str] = None
    doc_id: Optional[str] = None


REQUIRED_SECTION_PATTERNS = [
    (1, re.compile(r"^1\.\s+Цель и ключевые результаты", re.IGNORECASE)),
    (2, re.compile(r"^2\.\s+Область применения и роли", re.IGNORECASE)),
    (3, re.compile(r"^3\.\s+Пошаговый алгоритм выполнения", re.IGNORECASE)),
    (4, re.compile(r"^4\.\s+Контроль и точки аудита", re.IGNORECASE)),
    (5, re.compile(r"^5\.\s+Документооборот,\s*формы и шаблоны", re.IGNORECASE)),
]


def is_complete_regulation(text: str) -> bool:
    """
    HIGH-1: Строгая проверка полноты регламента:
    - Присутствуют только 5 точных заголовков 2-го уровня в строгом порядке (1..5);
    - Ровно по одному каждого заголовка (без дублей и лишних разделов);
    - Каждый раздел имеет непустое содержательное наполнение;
    - Документы только с маркерами (marker-only) или нарушенным порядком (out-of-order) возвращают False.
    """
    if not text or not isinstance(text, str):
        return False

    lines = text.splitlines()
    level2_headers: List[Tuple[int, str]] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        # Заголовок 2-го уровня начинается с ## и не является ###
        if stripped.startswith("## ") and not stripped.startswith("### "):
            header_title = stripped[3:].strip()
            level2_headers.append((idx, header_title))

    # Должно быть ровно 5 заголовков 2-го уровня
    if len(level2_headers) != 5:
        return False

    # Проверяем точное соответствие заголовков 1..5 и строгий порядок
    for (sec_num, pattern), (line_idx, header_title) in zip(REQUIRED_SECTION_PATTERNS, level2_headers):
        if not pattern.search(header_title):
            return False

    # Проверяем непустое наполнение каждого раздела
    for i in range(len(level2_headers)):
        start_line = level2_headers[i][0] + 1
        end_line = level2_headers[i + 1][0] if i + 1 < len(level2_headers) else len(lines)
        section_content = "\n".join(lines[start_line:end_line]).strip()
        if not section_content:
            # Раздел пуст (marker-only)
            return False

    return True


def detect_export_intent(text: str) -> bool:
    """
    Детерминированно определяет, является ли сообщение пользователя запросом на экспорт
    (выдачу файла, HTML, Google Docs, скачивание) до вызова языковой модели.
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip().lower()

    # Если это длинный черновик с разделами или кодом регламента, это не запрос на экспорт
    if len(cleaned) > 250 or is_complete_regulation(text):
        return False

    # Точные и фразовые шаблоны запроса на экспорт
    export_patterns = [
        r"^/?(файл|file|html|gdocs|docs|google\s*docs|гугл\s*докс|гугл\s*док|скачать|экспорт|выгрузка)$",
        r"(?:выдай|дай|скинь|отправь|пришли|сохрани|выгрузи|сделай|скачай)\w*\s+(?:мне\s+)?(?:этот\s+|последний\s+)?(?:файл|документ|html|хтмл|gdocs|google\s*docs|гугл\s*докс|гугл\s*док|ссылку\s+на\s+док|регламент(?:\s+файлом)?)",
        r"(?:экспорт|экспортируй|выгрузи|сохрани)\w*\s+(?:в|как)?\s*(?:файл|html|хтмл|gdocs|google\s*docs|гугл\s*докс|гугл\s*док|документ|гугл)",
        r"(?:скачать|выгрузить|сохранить)\s+(?:регламент|файл|документ|html|google\s*docs)",
        r"^(?:дай|скинь|отправь|пришли)\s+(?:ссылку|линк)\s+(?:на\s+)?(?:google\s*docs|gdocs|гугл\s*док|документ)$",
    ]

    for pattern in export_patterns:
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            return True

    return False


class FilenameSanitizer:
    """Безопасная санитизация, ограничение длины и контроль расположения файлов экспорта."""

    @staticmethod
    def sanitize_base_name(raw_name: str, max_length: int = 48) -> str:
        if not raw_name:
            return ""
        # Удаляем пути и недопустимые символы
        cleaned = raw_name.replace("\\", "/").split("/")[-1]
        cleaned = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*#~`!@$%^&+=;.]', '_', cleaned)
        cleaned = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ_-]', '', cleaned)
        cleaned = re.sub(r'_+', '_', cleaned).strip('_-')
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length].rstrip('_-')
        return cleaned

    @staticmethod
    def sanitize(
        raw_name: str,
        default_prefix: str = "reglament",
        suffix: str = ".html",
        max_length: int = 64,
    ) -> str:
        if not suffix.startswith("."):
            suffix = f".{suffix}"

        max_base_len = max(8, max_length - len(suffix))
        base = FilenameSanitizer.sanitize_base_name(raw_name, max_length=max_base_len)

        if not base:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"{default_prefix}_{timestamp}"
            if len(base) > max_base_len:
                base = base[:max_base_len].rstrip('_-')

        return f"{base}{suffix}"

    @staticmethod
    def verify_path_containment(base_dir: Path | str, target_path: Path | str) -> Path:
        """
        MEDIUM-1: Проверка нахождения целевого пути строго внутри базового каталога.
        Защищает от path traversal.
        """
        resolved_base = Path(base_dir).resolve()
        resolved_target = Path(target_path).resolve()

        try:
            common = os.path.commonpath([str(resolved_base), str(resolved_target)])
        except ValueError as e:
            raise ValueError(f"Ошибка проверки пути: {e}")

        if common != str(resolved_base) or resolved_target.parent != resolved_base:
            raise ValueError(
                f"Нарушение границ каталога (path containment violation): "
                f"целевой путь {resolved_target} находится вне {resolved_base}"
            )
        return resolved_target


class OAuthTokenValidator:
    """
    HIGH-3: Строгая проверка безопасности пути и файла OAuth-токена:
    - lstat без перехода по символическим ссылкам;
    - Запрет symlink;
    - Запрет hardlink (st_nlink == 1);
    - Проверка владельца (runtime UID);
    - Права доступа <= 0600 (запрет доступа для группы и остальных);
    - Безопасные права родительского каталога (<= 0700, владелец UID);
    - Атомарная запись при refresh с сохранением прав 0600.
    """

    @staticmethod
    def validate_token_file(token_path: str | Path, allow_custom_dir: bool = False) -> Tuple[bool, str]:
        if not token_path:
            return False, "Путь к OAuth токену не указан"

        path_obj = Path(token_path)

        # 1. Проверяем существование без разыменования symlink
        if not os.path.lexists(path_obj):
            return False, f"Файл токена не существует: {path_obj}"

        # 2. Читаем lstat целевого файла
        try:
            st = os.lstat(path_obj)
        except OSError as e:
            return False, f"Ошибка чтения lstat файла токена: {e}"

        # Запрет символических ссылок
        if os.path.islink(path_obj) or stat.S_ISLNK(st.st_mode):
            return False, "Символические ссылки на файл токена строго запрещены"

        # Только обычный файл
        if not stat.S_ISREG(st.st_mode):
            return False, "Файл токена должен быть обычным файлом"

        # Запрет hardlinks (st_nlink == 1)
        if st.st_nlink != 1:
            return False, f"Обнаружены жесткие ссылки (st_nlink={st.st_nlink}), разрешено ровно 1"

        # Проверка владельца (runtime UID)
        current_uid = os.getuid()
        if st.st_uid != current_uid:
            return False, f"Неверный владелец файла токена: UID={st.st_uid} (ожидается {current_uid})"

        # Проверка прав доступа: mode <= 0600, запрет группе и остальным
        mode_permissions = st.st_mode & 0o777
        if (st.st_mode & 0o077) != 0 or mode_permissions > 0o600:
            return False, f"Небезопасные права доступа к файлу токена: {mode_permissions:04o} (требуется <= 0600)"

        # 3. Проверка родительского каталога
        parent_dir = path_obj.parent
        if not os.path.lexists(parent_dir):
            return False, f"Каталог токена не существует: {parent_dir}"

        try:
            parent_st = os.lstat(parent_dir)
        except OSError as e:
            return False, f"Ошибка чтения lstat каталога токена: {e}"

        if os.path.islink(parent_dir) or stat.S_ISLNK(parent_st.st_mode):
            return False, "Родительский каталог токена не может быть символической ссылкой"

        if not stat.S_ISDIR(parent_st.st_mode):
            return False, "Родительский путь токена не является каталогом"

        if parent_st.st_uid != current_uid:
            return False, f"Неверный владелец каталога токена: UID={parent_st.st_uid} (ожидается {current_uid})"

        # Каталог токена: права <= 0700, запрет доступа группе и остальным
        parent_mode = parent_st.st_mode & 0o777
        if (parent_st.st_mode & 0o077) != 0 or parent_mode > 0o700:
            return False, f"Небезопасные права доступа к каталогу токена: {parent_mode:04o} (требуется <= 0700)"

        # 4. Проверка канонического каталога (если не тестовый режим)
        if not allow_custom_dir and CANONICAL_GOOGLE_OAUTH_DIR.exists():
            try:
                resolved_canonical = CANONICAL_GOOGLE_OAUTH_DIR.resolve()
                resolved_file = path_obj.resolve()
                if os.path.commonpath([str(resolved_canonical), str(resolved_file)]) != str(resolved_canonical):
                    return False, f"Файл токена должен находиться в каноническом каталоге {resolved_canonical}"
            except Exception as e:
                return False, f"Ошибка проверки канонического каталога: {e}"

        return True, "OK"

    @staticmethod
    def atomic_write_token_file(token_path: str | Path, content: str | bytes) -> None:
        """Атомарное безопасное сохранение файла токена с правами 0600."""
        path_obj = Path(token_path)
        parent_dir = path_obj.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(parent_dir, 0o700)

        tmp_path = parent_dir / f".token_tmp_{os.getpid()}_{int(datetime.now().timestamp() * 1000)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(tmp_path, flags, 0o600)
        try:
            data = content.encode("utf-8") if isinstance(content, str) else content
            os.write(fd, data)
        finally:
            os.close(fd)

        os.replace(tmp_path, path_obj)
        os.chmod(path_obj, 0o600)


class HtmlRenderer:
    """Генерация автономного защищенного HTML-документа регламента."""

    @staticmethod
    def _escape_and_format_content(markdown_text: str) -> str:
        """Безопасное преобразование Markdown в HTML с обязательным экранированием."""
        lines = markdown_text.splitlines()
        html_lines = []
        in_table = False
        in_ul = False
        in_ol = False
        in_code_block = False
        code_block_lines = []

        def close_lists():
            nonlocal in_ul, in_ol
            res = []
            if in_ul:
                res.append("</ul>")
                in_ul = False
            if in_ol:
                res.append("</ol>")
                in_ol = False
            return res

        def close_table():
            nonlocal in_table
            if in_table:
                in_table = False
                return ["</tbody></table></div>"]
            return []

        for line in lines:
            stripped = line.strip()

            # Обработка блоков кода
            if stripped.startswith("```"):
                if in_code_block:
                    in_code_block = False
                    code_content = "\n".join(code_block_lines)
                    html_lines.append(f"<pre><code>{html.escape(code_content, quote=True)}</code></pre>")
                    code_block_lines = []
                else:
                    html_lines.extend(close_lists())
                    html_lines.extend(close_table())
                    in_code_block = True
                    code_block_lines = []
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Пустая строка
            if not stripped:
                html_lines.extend(close_lists())
                html_lines.extend(close_table())
                continue

            # Таблицы Markdown
            if stripped.startswith("|") and stripped.endswith("|"):
                html_lines.extend(close_lists())
                if re.match(r"^\|(\s*:?-+:?\s*\|)+$", stripped):
                    continue

                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                escaped_cells = [html.escape(c, quote=True) for c in cells]

                if not in_table:
                    in_table = True
                    th_html = "".join(f"<th>{c}</th>" for c in escaped_cells)
                    html_lines.append(f'<div class="table-container"><table><thead><tr>{th_html}</tr></thead><tbody>')
                else:
                    td_html = "".join(f"<td>{c}</td>" for c in escaped_cells)
                    html_lines.append(f"<tr>{td_html}</tr>")
                continue
            else:
                html_lines.extend(close_table())

            # Заголовки
            if stripped.startswith("# "):
                html_lines.extend(close_lists())
                title_text = html.escape(stripped[2:].strip(), quote=True)
                html_lines.append(f'<h1 class="doc-title">{title_text}</h1>')
                continue
            elif stripped.startswith("## "):
                html_lines.extend(close_lists())
                sec_text = html.escape(stripped[3:].strip(), quote=True)
                html_lines.append(f'<h2 class="section-title">{sec_text}</h2>')
                continue
            elif stripped.startswith("### "):
                html_lines.extend(close_lists())
                subsec_text = html.escape(stripped[4:].strip(), quote=True)
                html_lines.append(f'<h3 class="subsection-title">{subsec_text}</h3>')
                continue

            # Маркированные списки
            if stripped.startswith(("- ", "* ", "• ")):
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                if not in_ul:
                    in_ul = True
                    html_lines.append("<ul>")
                item_text = html.escape(stripped[2:].strip(), quote=True)
                item_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item_text)
                html_lines.append(f"<li>{item_text}</li>")
                continue

            # Нумерованные списки
            ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
            if ol_match:
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                if not in_ol:
                    in_ol = True
                    html_lines.append("<ol>")
                item_text = html.escape(ol_match.group(2).strip(), quote=True)
                item_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item_text)
                html_lines.append(f"<li>{item_text}</li>")
                continue

            # Обычный текст / параграф
            html_lines.extend(close_lists())
            escaped_text = html.escape(stripped, quote=True)
            escaped_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped_text)
            escaped_text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped_text)

            if "⚠️" in escaped_text or "АНАЛИЗ ПЕРЕСЕЧЕНИЙ" in escaped_text:
                html_lines.append(f'<div class="callout-warning"><p>{escaped_text}</p></div>')
            elif "[ТРЕБУЕТ УТОЧНЕНИЯ" in escaped_text:
                html_lines.append(f'<div class="callout-clarify"><p>{escaped_text}</p></div>')
            else:
                html_lines.append(f"<p>{escaped_text}</p>")

        html_lines.extend(close_lists())
        html_lines.extend(close_table())
        return "\n".join(html_lines)

    def render(self, markdown_text: str, author_name: str = "Сотрудник", title: Optional[str] = None) -> str:
        """Сборка полного автономного HTML-документа."""
        if not title:
            match = re.search(r"^#\s+(.+)$", markdown_text, flags=re.MULTILINE)
            if match:
                title = match.group(1).strip()
            else:
                title = "Регламент Star Building"

        safe_title = html.escape(title, quote=True)
        safe_author = html.escape(author_name, quote=True)
        generated_date = datetime.now().strftime("%d.%m.%Y %H:%M")

        body_content = self._escape_and_format_content(markdown_text)

        html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <style>
        :root {{
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #475569;
            --primary: #0284c7;
            --primary-dark: #0369a1;
            --border-color: #e2e8f0;
            --warning-bg: #fffbeb;
            --warning-border: #fde68a;
            --warning-text: #92400e;
            --clarify-bg: #eff6ff;
            --clarify-border: #bfdbfe;
            --clarify-text: #1e40af;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 32px 16px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
            padding: 40px;
            border: 1px solid var(--border-color);
        }}
        .header {{
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 24px;
            margin-bottom: 32px;
        }}
        .brand {{
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--primary);
            font-weight: 700;
            margin-bottom: 8px;
        }}
        .doc-title {{
            font-size: 26px;
            font-weight: 800;
            color: var(--text-main);
            line-height: 1.25;
            margin-bottom: 16px;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            background: #f1f5f9;
            padding: 16px;
            border-radius: 8px;
            font-size: 14px;
        }}
        .meta-item strong {{
            color: var(--text-muted);
            display: block;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 700;
            color: var(--primary-dark);
            margin-top: 36px;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }}
        .subsection-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-main);
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        p {{
            margin-bottom: 14px;
            color: var(--text-main);
        }}
        ul, ol {{
            margin-bottom: 16px;
            padding-left: 24px;
        }}
        li {{
            margin-bottom: 6px;
        }}
        .table-container {{
            overflow-x: auto;
            margin: 20px 0;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }}
        th {{
            background: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:nth-child(even) {{
            background: #fbfcfe;
        }}
        .callout-warning {{
            background: var(--warning-bg);
            border-left: 4px solid var(--warning-border);
            padding: 16px;
            border-radius: 4px;
            color: var(--warning-text);
            margin: 20px 0;
        }}
        .callout-clarify {{
            background: var(--clarify-bg);
            border-left: 4px solid var(--clarify-border);
            padding: 16px;
            border-radius: 4px;
            color: var(--clarify-text);
            margin: 20px 0;
        }}
        pre {{
            background: #1e293b;
            color: #f8fafc;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 16px 0;
            font-size: 13px;
        }}
        code {{
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }}
        .footer {{
            margin-top: 48px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            font-size: 12px;
            color: var(--text-muted);
            text-align: center;
        }}
        @media print {{
            body {{
                background: none;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                border: none;
                padding: 0;
                max-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">Группа компаний Star Building • Нормативная база</div>
            <div class="meta-grid">
                <div class="meta-item">
                    <strong>Автор / Инициатор</strong>
                    {safe_author}
                </div>
                <div class="meta-item">
                    <strong>Дата генерации</strong>
                    {generated_date}
                </div>
                <div class="meta-item">
                    <strong>Статус документа</strong>
                    Черновик (v0.1)
                </div>
            </div>
        </div>
        <div class="content">
            {body_content}
        </div>
        <div class="footer">
            Документ сформирован автоматически корпоративным агентом «Смотритель» (@ReglamentSB_bot)
        </div>
    </div>
</body>
</html>"""
        return html_doc


class PersistentArtifactStore:
    """
    HIGH-4: Долговечное атомарное хранилище артефактов на базе SQLite:
    - Сохраняется при перезапуске процесса;
    - Обеспечивает строгую изоляцию по user_id;
    - Ограниченный LRU-размер (max_users, по умолчанию 500);
    - Атомарные транзакции и WAL-режим;
    - Fail-closed режим при сбоях и повреждении базы.
    """

    def __init__(self, db_path: Optional[str | Path] = None, max_users: int = 500):
        self.max_users = max_users
        self._mem_conn: Optional[sqlite3.Connection] = None

        if db_path is None:
            env_db = os.environ.get("STAR_BUILDING_ARTIFACTS_DB_PATH")
            if env_db:
                self.db_path = str(Path(env_db).resolve())
            else:
                default_dir = Path(__file__).resolve().parent / "storage"
                default_dir.mkdir(parents=True, exist_ok=True)
                self.db_path = str(default_dir / "artifacts.db")
        else:
            self.db_path = str(db_path)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn

        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _create_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS completed_artifacts (
                user_id INTEGER PRIMARY KEY,
                author_name TEXT NOT NULL,
                regulation_text TEXT NOT NULL,
                html_content TEXT NOT NULL,
                filename TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                gdocs_url TEXT,
                gdocs_id TEXT,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_artifacts_updated
            ON completed_artifacts(updated_at DESC)
        """)
        conn.commit()

    def _init_db(self) -> None:
        try:
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = self._get_connection()
            self._create_table(conn)
            if self.db_path != ":memory:":
                conn.close()
        except Exception as e:
            logger.warning(f"Ошибка инициализации базы артефактов: {e}")

    def get(self, user_id: int) -> Optional[CompletedArtifact]:
        """Возвращает последний завершённый регламент пользователя. Fail-closed при ошибке."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, author_name, regulation_text, html_content,
                       filename, title, created_at, gdocs_url, gdocs_id
                FROM completed_artifacts
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CompletedArtifact(
                user_id=row["user_id"],
                author_name=row["author_name"],
                regulation_text=row["regulation_text"],
                html_content=row["html_content"],
                filename=row["filename"],
                title=row["title"],
                created_at=row["created_at"],
                gdocs_url=row["gdocs_url"],
                gdocs_id=row["gdocs_id"],
            )
        except Exception as e:
            logger.warning(f"Fail-closed: ошибка чтения артефакта пользователя {user_id}: {e}")
            return None
        finally:
            if conn and self.db_path != ":memory:":
                conn.close()

    def put(self, user_id: int, artifact: CompletedArtifact) -> None:
        """Сохраняет или обновляет артефакт пользователя с соблюдением лимита max_users."""
        conn = None
        try:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    INSERT INTO completed_artifacts (
                        user_id, author_name, regulation_text, html_content,
                        filename, title, created_at, gdocs_url, gdocs_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        author_name=excluded.author_name,
                        regulation_text=excluded.regulation_text,
                        html_content=excluded.html_content,
                        filename=excluded.filename,
                        title=excluded.title,
                        created_at=excluded.created_at,
                        gdocs_url=excluded.gdocs_url,
                        gdocs_id=excluded.gdocs_id,
                        updated_at=excluded.updated_at
                """, (
                    user_id,
                    artifact.author_name,
                    artifact.regulation_text,
                    artifact.html_content,
                    artifact.filename,
                    artifact.title,
                    artifact.created_at,
                    artifact.gdocs_url,
                    artifact.gdocs_id,
                    time.time(),
                ))

                # Ограничение размера хранилища (LRU-вытеснение старых записей)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM completed_artifacts")
                count = cursor.fetchone()[0]
                if count > self.max_users:
                    conn.execute("""
                        DELETE FROM completed_artifacts
                        WHERE user_id NOT IN (
                            SELECT user_id FROM completed_artifacts
                            ORDER BY updated_at DESC, rowid DESC
                            LIMIT ?
                        )
                    """, (self.max_users,))
        except Exception as e:
            logger.warning(f"Fail-closed: ошибка сохранения артефакта пользователя {user_id}: {e}")
        finally:
            if conn and self.db_path != ":memory:":
                conn.close()

    def update_gdocs_url(self, user_id: int, gdocs_url: str, gdocs_id: Optional[str] = None) -> None:
        """Атомарно обновляет Google Docs URL для артефакта пользователя."""
        conn = None
        try:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    UPDATE completed_artifacts
                    SET gdocs_url = ?, gdocs_id = ?, updated_at = ?
                    WHERE user_id = ?
                """, (gdocs_url, gdocs_id, time.time(), user_id))
        except Exception as e:
            logger.warning(f"Fail-closed: ошибка обновления gdocs_url: {e}")
        finally:
            if conn and self.db_path != ":memory:":
                conn.close()

    def __len__(self) -> int:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM completed_artifacts")
            return cursor.fetchone()[0]
        except Exception:
            return 0
        finally:
            if conn and self.db_path != ":memory:":
                conn.close()


# Алиас для обратной совместимости
ArtifactCache = PersistentArtifactStore


class GoogleDriveAdapter:
    """
    HIGH-3: Адаптер для экспорта HTML-документа в Google Docs (application/vnd.google-apps.document).
    Читает только безопасный проверенный путь к OAuth token-файлу.
    При отсутствии или сбое OAuth работает в режиме graceful failure.
    """

    def __init__(self, token_path: Optional[str] = None, allow_custom_dir: bool = False):
        self.token_path = token_path or os.environ.get(
            "STAR_BUILDING_GOOGLE_OAUTH_TOKEN_PATH",
            DEFAULT_GOOGLE_OAUTH_TOKEN_PATH,
        )
        self.allow_custom_dir = allow_custom_dir

    def is_configured(self) -> bool:
        """Проверяет наличие и строгую безопасность файла OAuth-токена."""
        if not self.token_path:
            return False
        valid, reason = OAuthTokenValidator.validate_token_file(
            self.token_path,
            allow_custom_dir=self.allow_custom_dir,
        )
        if not valid:
            logger.info(f"Google OAuth token не настроен или не прошел проверку безопасности: {reason}")
            return False
        return True

    def _upload_to_drive(self, html_content: str, title: str) -> Dict[str, Any]:
        """
        Реальный вызов Google Drive API.
        Загружает HTML с mimeType='application/vnd.google-apps.document'.
        """
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload

        creds = Credentials.from_authorized_user_file(self.token_path)

        # Безопасное обновление токена при истечении срока
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                OAuthTokenValidator.atomic_write_token_file(self.token_path, creds.to_json())
                logger.info("OAuth токен Google успешно обновлен и сохранен с правами 0600.")
            except Exception as e:
                logger.warning(f"Сбой обновления OAuth токена: {e.__class__.__name__}")
                raise RuntimeError("Сбой обновления OAuth токена")

        service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }
        media = MediaInMemoryUpload(
            html_content.encode("utf-8"),
            mimetype="text/html",
            resumable=True,
        )

        file_res = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
        ).execute()

        return file_res

    def export_html_to_google_doc(self, html_content: str, title: str) -> GoogleDocExportResult:
        """Экспорт HTML в Google Docs с безопасной валидацией URL."""
        if not self.is_configured():
            return GoogleDocExportResult(
                success=False,
                message="Google Docs недоступен: авторизация не настроена на сервере.",
                doc_url=None,
                doc_id=None,
            )

        try:
            res = self._upload_to_drive(html_content, title)
            doc_id = res.get("id")
            if not doc_id or not re.match(r"^[a-zA-Z0-9_-]+$", str(doc_id)):
                raise ValueError("Некорректный идентификатор файла от Google API")

            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
            logger.info(f"Документ успешно создан в Google Docs: {doc_id}")
            return GoogleDocExportResult(
                success=True,
                message="Документ успешно экспортирован в Google Docs.",
                doc_url=doc_url,
                doc_id=str(doc_id),
            )
        except Exception as e:
            logger.warning(f"Ошибка экспорта в Google Docs: {e.__class__.__name__}")
            return GoogleDocExportResult(
                success=False,
                message="Экспорт в Google Docs временно недоступен: сбой при обращении к сервису.",
                doc_url=None,
                doc_id=None,
            )


class ExportService:
    """
    HIGH-2: Единый сервис управления артефактами и идемпотентным экспортом регламентов:
    - Блокировки per-user для исключения дублирующих вызовов Drive API при параллельных запросах;
    - Переиспользование ранее созданного gdocs_url;
    - Сохранение артефактов в долговечное хранилище.
    """

    def __init__(
        self,
        store: Optional[PersistentArtifactStore] = None,
        renderer: Optional[HtmlRenderer] = None,
        sanitizer: Optional[FilenameSanitizer] = None,
        drive_adapter: Optional[GoogleDriveAdapter] = None,
        cache: Optional[PersistentArtifactStore] = None,
    ):
        # Поддержка именованного аргумента cache для совместимости
        if store is not None:
            self.store = store
        elif cache is not None:
            self.store = cache
        else:
            self.store = PersistentArtifactStore()

        self.renderer = renderer if renderer is not None else HtmlRenderer()
        self.sanitizer = sanitizer if sanitizer is not None else FilenameSanitizer()
        self.drive_adapter = drive_adapter if drive_adapter is not None else GoogleDriveAdapter()

        self._user_locks: Dict[int, threading.Lock] = defaultdict(threading.Lock)
        self._locks_lock = threading.Lock()

    @property
    def cache(self) -> PersistentArtifactStore:
        return self.store

    @cache.setter
    def cache(self, value: PersistentArtifactStore) -> None:
        self.store = value

    def _get_user_lock(self, user_id: int) -> threading.Lock:
        with self._locks_lock:
            return self._user_locks[user_id]

    def register_completed_regulation(
        self,
        user_id: int,
        author_name: str,
        regulation_text: str,
    ) -> Optional[CompletedArtifact]:
        """
        Проверяет полноту регламента, генерирует HTML, санитизирует имя файла
        и сохраняет в долговечное хранилище артефактов.
        """
        if not is_complete_regulation(regulation_text):
            return None

        # Извлекаем название
        match = re.search(r"^#\s+(?:РЕГЛАМЕНТ:\s*)?(.+)$", regulation_text, flags=re.MULTILINE)
        title = match.group(1).strip() if match else "Регламент"

        # Извлекаем код регламента, если есть
        code_match = re.search(r"Код(?:\s+документа)?:\s*([A-Za-z0-9а-яА-ЯёЁ_-]+)", regulation_text)
        file_prefix = code_match.group(1).strip() if code_match else f"reglament_{author_name}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_filename = f"{file_prefix}_{timestamp}"
        filename = self.sanitizer.sanitize(raw_filename, suffix=".html")

        html_content = self.renderer.render(
            markdown_text=regulation_text,
            author_name=author_name,
            title=title,
        )

        artifact = CompletedArtifact(
            user_id=user_id,
            author_name=author_name,
            regulation_text=regulation_text,
            html_content=html_content,
            filename=filename,
            title=title,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        with self._get_user_lock(user_id):
            self.store.put(user_id, artifact)
        return artifact

    def get_last_artifact(self, user_id: int) -> Optional[CompletedArtifact]:
        """Возвращает последний завершённый регламент пользователя из хранилища."""
        with self._get_user_lock(user_id):
            return self.store.get(user_id)

    def get_telegram_document_payload(self, artifact: CompletedArtifact) -> Dict[str, Any]:
        """Формирует payload для отправки документа в Telegram Bot API."""
        bio = io.BytesIO(artifact.html_content.encode("utf-8"))
        bio.name = artifact.filename
        bio.seek(0)
        return {
            "document": bio,
            "filename": artifact.filename,
            "caption": f"📄 **Регламент:** {artifact.title}\nФормат: автономный HTML (UTF-8)",
            "mime_type": "text/html",
        }

    def export_to_google_docs(self, artifact: CompletedArtifact) -> GoogleDocExportResult:
        """
        HIGH-2: Идемпотентный экспорт в Google Docs:
        - Если gdocs_url уже сформирован, немедленно возвращает сохранённый результат;
        - Блокировка per-user исключает параллельные вызовы API (20 concurrent -> 1 API call);
        - Сохраняет полученный gdocs_url в долговечное хранилище.
        """
        if artifact.gdocs_url:
            return GoogleDocExportResult(
                success=True,
                message="Документ уже экспортирован в Google Docs.",
                doc_url=artifact.gdocs_url,
                doc_id=artifact.gdocs_id,
            )

        with self._get_user_lock(artifact.user_id):
            # Double check после захвата блокировки
            if artifact.gdocs_url:
                return GoogleDocExportResult(
                    success=True,
                    message="Документ уже экспортирован в Google Docs.",
                    doc_url=artifact.gdocs_url,
                    doc_id=artifact.gdocs_id,
                )

            # Проверяем в БД (на случай параллельного запроса в другом потоке/процессе)
            stored = self.store.get(artifact.user_id)
            if stored and stored.gdocs_url:
                artifact.gdocs_url = stored.gdocs_url
                artifact.gdocs_id = stored.gdocs_id
                return GoogleDocExportResult(
                    success=True,
                    message="Документ уже экспортирован в Google Docs.",
                    doc_url=stored.gdocs_url,
                    doc_id=stored.gdocs_id,
                )

            result = self.drive_adapter.export_html_to_google_doc(
                html_content=artifact.html_content,
                title=artifact.title,
            )

            if result.success and result.doc_url:
                artifact.gdocs_url = result.doc_url
                artifact.gdocs_id = result.doc_id
                self.store.update_gdocs_url(artifact.user_id, result.doc_url, result.doc_id)

            return result
