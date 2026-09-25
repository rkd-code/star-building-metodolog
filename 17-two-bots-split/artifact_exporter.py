#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль экспорта регламентов: генерация автономного HTML и интеграция с Google Docs.
Реализует требования договора FN-013:
- Детерминированное распознавание намерений экспорта до вызова LLM;
- Построение защищённого автономного HTML (UTF-8) с экранированием XSS;
- Санитизация и ограничение длины имени файла;
- Ограниченный кэш последнего завершённого артефакта на пользователя;
- Адаптер Google Drive (HTML -> Google Docs) с безопасной обработкой OAuth;
- Подготовка Telegram document payload.
"""

import html
import io
import logging
import os
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("artifact_exporter")

DEFAULT_GOOGLE_OAUTH_TOKEN_PATH = "/home/roman/.config/star-building/google_oauth_token.json"


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


def is_complete_regulation(text: str) -> bool:
    """
    Проверяет, содержит ли текст все 5 стандартных разделов регламента Star Building:
    ## 1. Цель и ключевые результаты
    ## 2. Область применения и роли
    ## 3. Пошаговый алгоритм выполнения
    ## 4. Контроль и точки аудита
    ## 5. Документооборот, формы и шаблоны
    """
    if not text:
        return False

    # Требуется наличие всех 5 разделов
    required_sections = [
        "## 1.",
        "## 2.",
        "## 3.",
        "## 4.",
        "## 5.",
    ]
    return all(sec in text for sec in required_sections)


def detect_export_intent(text: str) -> bool:
    """
    Детерминированно определяет, является ли сообщение пользователя запросом на экспорт
    (выдачу файла, HTML, Google Docs, скачивание) до вызова языковой модели.
    """
    if not text:
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
    """Безопасная санитизация и ограничение длины имени файлов экспорта."""

    @staticmethod
    def sanitize(raw_name: str, default_prefix: str = "reglament", max_length: int = 64) -> str:
        if not raw_name:
            raw_name = ""

        # Удаляем пути и недопустимые символы
        cleaned = raw_name.replace("\\", "/").split("/")[-1]
        cleaned = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*#~`!@$%^&+=;]', '_', cleaned)
        cleaned = re.sub(r'[\s_]+', '_', cleaned).strip('._- ')

        # Разрешаем только кириллицу, латиницу, цифры, дефис и подчеркивание
        cleaned = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ_-]', '', cleaned)

        if not cleaned:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cleaned = f"{default_prefix}_{timestamp}"

        suffix = ".html"
        max_base_len = max(8, max_length - len(suffix))

        if len(cleaned) > max_base_len:
            cleaned = cleaned[:max_base_len].rstrip('._- ')

        return f"{cleaned}{suffix}"


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
                # Пропускаем разделитель заголовка таблицы (|---|---|)
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
                # Выделение жирным
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
            # Базовое форматирование жирного и курсива
            escaped_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped_text)
            escaped_text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped_text)

            # Выделение блока коллизий / предупреждений
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
            # Извлекаем название из первой строки # РЕГЛАМЕНТ: ...
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


class ArtifactCache:
    """Ограниченный LRU-кэш последних завершённых регламентов пользователей."""

    def __init__(self, max_users: int = 500):
        self.max_users = max_users
        self._cache: OrderedDict[int, CompletedArtifact] = OrderedDict()

    def get(self, user_id: int) -> Optional[CompletedArtifact]:
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
            return self._cache[user_id]
        return None

    def put(self, user_id: int, artifact: CompletedArtifact) -> None:
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
        self._cache[user_id] = artifact
        if len(self._cache) > self.max_users:
            self._cache.popitem(last=False)

    def __len__(self) -> int:
        return len(self._cache)


class GoogleDriveAdapter:
    """
    Адаптер для экспорта HTML-документа в Google Docs (application/vnd.google-apps.document).
    Читает только безопасный путь к OAuth token-файлу.
    При отсутствии или сбое OAuth работает в режиме graceful failure.
    """

    def __init__(self, token_path: Optional[str] = None):
        self.token_path = token_path or os.environ.get(
            "STAR_BUILDING_GOOGLE_OAUTH_TOKEN_PATH",
            DEFAULT_GOOGLE_OAUTH_TOKEN_PATH,
        )

    def is_configured(self) -> bool:
        """Проверяет наличие и доступность файла OAuth-токена."""
        if not self.token_path:
            return False
        try:
            p = Path(self.token_path)
            return p.is_file() and p.stat().st_size > 0
        except Exception:
            return False

    def _upload_to_drive(self, html_content: str, title: str) -> Dict[str, Any]:
        """
        Реальный вызов Google Drive API.
        Загружает HTML с mimeType='application/vnd.google-apps.document'.
        """
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload

        creds = Credentials.from_authorized_user_file(self.token_path)
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
            logger.info("Google OAuth token не настроен. Экспорт в Google Docs пропущен.")
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
            # Безопасное логирование без раскрытия секретов
            logger.warning(f"Ошибка экспорта в Google Docs: {e.__class__.__name__}")
            return GoogleDocExportResult(
                success=False,
                message="Экспорт в Google Docs временно недоступен: сбой при обращении к сервису.",
                doc_url=None,
                doc_id=None,
            )


class ExportService:
    """Единый сервис управления артефактами и экспортом регламентов."""

    def __init__(
        self,
        cache: Optional[ArtifactCache] = None,
        renderer: Optional[HtmlRenderer] = None,
        sanitizer: Optional[FilenameSanitizer] = None,
        drive_adapter: Optional[GoogleDriveAdapter] = None,
    ):
        self.cache = cache if cache is not None else ArtifactCache()
        self.renderer = renderer if renderer is not None else HtmlRenderer()
        self.sanitizer = sanitizer if sanitizer is not None else FilenameSanitizer()
        self.drive_adapter = drive_adapter if drive_adapter is not None else GoogleDriveAdapter()

    def register_completed_regulation(
        self,
        user_id: int,
        author_name: str,
        regulation_text: str,
    ) -> Optional[CompletedArtifact]:
        """
        Проверяет полноту регламента, генерирует HTML, санитизирует имя файла
        и сохраняет в кэш артефактов пользователя.
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
        filename = self.sanitizer.sanitize(raw_filename)

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

        self.cache.put(user_id, artifact)
        return artifact

    def get_last_artifact(self, user_id: int) -> Optional[CompletedArtifact]:
        """Возвращает последний завершённый регламент пользователя из кэша."""
        return self.cache.get(user_id)

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
        """Выполняет экспорт артефакта в Google Docs через адаптер."""
        result = self.drive_adapter.export_html_to_google_doc(
            html_content=artifact.html_content,
            title=artifact.title,
        )
        if result.success and result.doc_url:
            artifact.gdocs_url = result.doc_url
            artifact.gdocs_id = result.doc_id
        return result
