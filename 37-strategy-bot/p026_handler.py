"""Обработчик диалогового взаимодействия и фиксации решений P-026 для Драмкнота."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from p026_storage import P026Storage
from p026_subject_base import P026SubjectBase

AMBIGUOUS_REPLIES = {
    "да", "согласен", "ок", "ок.", "ок!", "хорошо", "ага", "плюс", "+", "yes", "y",
    "подтверждаю", "принято", "ладно", "верно", "точно", "договорились", "понял",
}

DOC_TYPE_MAP = {
    "kd": "КД",
    "кд": "КД",
    "rop": "РОП",
    "роп": "РОП",
    "senior": "Старший МОП",
    "старший": "Старший МОП",
    "sales": "МОП",
    "моп": "МОП",
    "leadrub": "Лидоруб",
    "лидоруб": "Лидоруб",
    "org": "Оргструктура КД",
    "орг": "Оргструктура КД",
}


class P026Handler:
    def __init__(
        self,
        storage: P026Storage | None = None,
        subject_base: P026SubjectBase | None = None,
    ) -> None:
        self.storage = storage or P026Storage()
        self.subject_base = subject_base or P026SubjectBase()

    def validate_decision_input(self, text: str) -> tuple[bool, str]:
        """Проверяет валидность формулировки решения.

        Неоднозначные короткие ответы («да», «ок», «согласен») не принимаются
        без явной, развёрнутой формулировки.
        """
        cleaned = text.strip().lower()
        cleaned_no_punct = re.sub(r"[^\w\s+]", "", cleaned)

        if cleaned in AMBIGUOUS_REPLIES or cleaned_no_punct in AMBIGUOUS_REPLIES:
            return (
                False,
                f"Неоднозначный ответ («{text.strip()}») не может быть зафиксирован как норма или решение. "
                "Пожалуйста, сформулируйте точное решение развёрнуто (например: «Утвердить лимит скидки РОП до 12.5%»).",
            )

        words = text.strip().split()
        if len(words) < 2 and len(text.strip()) < 10:
            return (
                False,
                f"Слишком краткая формулировка («{text.strip()}»). "
                "Решение должно содержать законченную мысль с указанием роли, норматива или правила.",
            )

        return True, "Формулировка корректна"

    def validate_file_instruction(self, file_content: str) -> tuple[bool, str]:
        """Файлы и вложенные документы расцениваются только как данные.

        Инструкции внутри них не фиксируются как решения или системные команды.
        """
        return (
            False,
            "Инструкции внутри пользовательских файлов рассматриваются исключительно как данные "
            "и не могут быть автоматически зафиксированы как решения или команды владельца.",
        )

    def record_owner_decision(
        self,
        author: str,
        text: str,
        question_context: str = "Общие решения P-026",
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Фиксирует подтверждённое решение владельца."""
        valid, msg = self.validate_decision_input(text)
        if not valid:
            return {"ok": False, "message": msg, "decision": None}

        decision = self.storage.record_decision(
            author=author,
            question_context=question_context,
            exact_text=text,
            user_id=user_id,
        )
        return {
            "ok": True,
            "message": (
                f"✅ Решение успешно зафиксировано в изолированном журнале P-026:\n"
                f"• ID: {decision['id']}\n"
                f"• Автор: {decision['author']}\n"
                f"• Контекст: {decision['question_context']}\n"
                f"• Текст: «{decision['exact_text']}»"
            ),
            "decision": decision,
        }

    def handle_project_command(self, user_id: int | None = None) -> str:
        """Формирует сводный статус проекта P-026 с учётом зафиксированных решений."""
        status_text = self.subject_base.format_project_status()
        recent_decisions = self.storage.list_decisions(user_id=user_id)
        if recent_decisions:
            status_text += "\n\n📝 *Зафиксированные решения текущего пользователя:*"
            for dec in recent_decisions[-5:]:
                status_text += f"\n• [{dec['id']}] {dec['exact_text']}"
        return status_text

    def export_draft(
        self,
        doc_type: str,
        author: str = "Руководитель",
        custom_header: str | None = None,
    ) -> dict[str, Any]:
        """Экспортирует версионный рабочий черновик документа КД без изменения оригиналов."""
        normalized_type = doc_type.strip().lower()
        role_key = DOC_TYPE_MAP.get(normalized_type)
        if not role_key or role_key not in self.subject_base.DOCUMENT_VERSIONS:
            return {
                "ok": False,
                "error": f"Неизвестный тип документа: '{doc_type}'. Доступны: {list(DOC_TYPE_MAP.keys())}",
            }

        doc_meta = self.subject_base.DOCUMENT_VERSIONS[role_key]
        source_path = Path(doc_meta["path"])
        if not source_path.is_file():
            # Если исходный файл отсутствует на локальном диске, создаём базовый шаблон
            content = f"# {doc_meta['title']}\n\nБазовая версия {doc_meta['version']}.\n"
        else:
            content = source_path.read_text(encoding="utf-8")

        # Добавляем актуальные решения из хранилища
        active_decisions = self.storage.list_decisions(status="active")
        decisions_block = ""
        if active_decisions:
            decisions_block = "\n\n## Зафиксированные решения владельца (P-026)\n"
            for dec in active_decisions:
                decisions_block += f"- [{dec['timestamp']}] ({dec['author']}): {dec['exact_text']}\n"

        full_draft_content = (custom_header or "") + content + decisions_block
        safe_doc_name = f"DRAFT_{role_key.replace(' ', '_')}"
        draft_info = self.storage.save_draft(
            doc_name=safe_doc_name,
            content=full_draft_content,
            author=author,
        )

        return {
            "ok": True,
            "role": role_key,
            "version": draft_info["version"],
            "draft": draft_info,
            "message": f"Черновик {role_key} успешно экспортирован: {draft_info['filename']} ({draft_info['bytes']} байт). Исходные файлы не затронуты.",
        }
