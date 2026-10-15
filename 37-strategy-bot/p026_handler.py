"""Обработчик диалогового взаимодействия и фиксации решений P-026 для Драмкнота."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from p026_storage import JournalCorruptionError, P026Storage
from p026_subject_base import P026SubjectBase, SubjectBaseIntegrityError

AMBIGUOUS_TOKENS = {
    "да", "нет", "согласен", "согласна", "согласны", "согласенли", "соглашаюсь", "согласен(на)",
    "ок", "ok", "хорошо", "ага", "плюс", "+", "yes", "y",
    "подтверждаю", "подтвердил", "подтвердила", "подтверждено", "подтверждаем",
    "одобряю", "одобрено", "одобряем", "поддерживаю", "поддержано", "поддерживаем",
    "принято", "принимаю", "принимается", "ладно", "верно", "точно", "договорились", "понял", "поняла", "понятно",
    "все", "всё", "ясно", "сделаем", "добро", "так", "отлично", "го", "правильно", "именно",
    "я", "мы", "вы", "он", "она", "они",
    "с", "со", "этим", "это", "этом", "этой", "этого", "этому", "эти", "этих", "этими", "эта", "эту",
    "то", "тем", "том", "того", "тому", "та", "ту", "той", "те", "тех", "теми",
    "на", "в", "во", "по", "за", "к", "ко", "из", "у", "о", "об", "обо", "от", "для",
    "же", "ли", "бы", "уже", "полностью", "абсолютно", "целиком",
    "выше", "вышеизложенное", "вышеизложенного", "вышеизложенному", "вышеизложенным", "вышеизложенной",
    "вышесказанное", "вышесказанного", "вышеуказанное", "вышеуказанного", "написанное", "написанного",
    "предложенное", "предложенного", "предложение", "предложения", "вариант", "варианта",
    "пункт", "пункты", "пунктов", "пунктами", "пунктах",
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

SUBSTANTIVE_KEYWORDS = {
    "лимит", "скидк", "марж", "срок", "дн", "час", "процент", "%", "тенге", "рубл",
    "роп", "моп", "кд", "од", "гд", "пто", "лидоруб", "агент",
    "регламент", "правил", "норм", "стандарт", "сделк", "чек", "порог", "штраф", "преми",
    "утверд", "установ", "запрет", "зафиксир", "обяза", "назнач", "ввест", "депреми",
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

        Неоднозначные короткие и многословные согласия («да», «ок», «согласен», «да согласен»,
        «ок хорошо», «всё верно») отклоняются с требованием указать конкретную норму.
        """
        cleaned = text.strip().lower()
        cleaned_no_punct = re.sub(r"[^\w\s+]", " ", cleaned)
        tokens = [t for t in cleaned_no_punct.split() if t]

        if not tokens:
            return False, "Формулировка решения не может быть пустой."

        # Если все слова состоят исключительно из маркеров согласия/подтверждения
        if set(tokens).issubset(AMBIGUOUS_TOKENS):
            return (
                False,
                f"Неоднозначное согласие («{text.strip()}») не может быть зафиксировано как норма или решение. "
                "Пожалуйста, сформулируйте точное нормативное решение с указанием роли, норматива или правила "
                "(например: «Утвердить лимит скидки РОП до 12.5%» или «Согласовать минимальную маржу 15%»).",
            )

        has_agreement = any(term in cleaned for term in ("соглас", "подтвержд", "одобря", "поддержив", "принят"))
        has_substantive = any(k in cleaned for k in SUBSTANTIVE_KEYWORDS)
        if has_agreement and not has_substantive:
            return (
                False,
                f"Общее согласие («{text.strip()}») не содержит предметной нормы или параметра. "
                "Пожалуйста, сформулируйте точное нормативное решение с указанием роли, норматива или правила "
                "(например: «Утвердить лимит скидки РОП до 12.5%» или «Согласовать минимальную маржу 15%»).",
            )

        # Проверка на минимальную длину и смысловую нагрузку
        if len(tokens) < 2 and len(cleaned) < 10:
            return (
                False,
                f"Слишком краткая формулировка («{text.strip()}»). "
                "Решение должно содержать законченную мысль с указанием роли, норматива или правила.",
            )

        return True, "Формулировка корректна"

    def validate_file_instruction(self, file_content: str) -> tuple[bool, str]:
        """Файлы и вложенные документы расцениваются только как данные."""
        return (
            False,
            "Инструкции внутри пользовательских файлов рассматриваются исключительно как данные "
            "и не могут быть автоматически зафиксированы как решения или команды владельца.",
        )

    def _infer_question_context(self, text: str, explicit_context: str | None = None) -> str:
        """Привязывает решение к конкретному обсуждаемому предметному вопросу."""
        if explicit_context and explicit_context.strip() and explicit_context != "Общие решения P-026":
            return explicit_context.strip()

        # Разбор формата "Контекст: Решение" или "[Контекст] Решение"
        if ":" in text:
            prefix, _ = text.split(":", 1)
            if len(prefix.strip()) <= 60 and len(prefix.strip().split()) <= 6:
                return prefix.strip().strip("[]()")

        lower = text.lower()
        if "скидк" in lower or "лимит" in lower:
            return "Пределы скидок и полномочий"
        if "марж" in lower:
            return "Минимальная маржа и согласование ГД"
        if "стратегическ" in lower or "1 млрд" in lower or "порог" in lower:
            return "Порог стратегической сделки"
        if "роп" in lower or "время ответа" in lower or "пто" in lower or "прогноз" in lower:
            return "Нормативы и обязанности РОП"
        if "договор" in lower or "согласован" in lower:
            return "Маршрут согласования и подписания договоров"
        if "агент" in lower:
            return "Агентская схема"
        if "лидоруб" in lower:
            return "Контур Лидоруба"
        if "оргструктур" in lower or "подчинен" in lower or "од" in lower:
            return "Организационная структура КД"
        return "Управленческие нормативы P-026"

    def record_owner_decision(
        self,
        author: str,
        text: str,
        question_context: str = "Общие решения P-026",
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        """Фиксирует подтверждённое решение владельца с привязкой контекста и изоляцией."""
        valid, msg = self.validate_decision_input(text)
        if not valid:
            return {"ok": False, "message": msg, "decision": None}

        context_bound = self._infer_question_context(text, question_context)

        try:
            decision = self.storage.record_decision(
                author=author,
                question_context=context_bound,
                exact_text=text,
                user_id=user_id,
                chat_id=chat_id,
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
        except JournalCorruptionError as err:
            return {
                "ok": False,
                "message": f"⚠ Ошибка хранилища решений: {err}",
                "decision": None,
            }

    def handle_project_command(self, user_id: int | None = None, chat_id: int | None = None) -> str:
        """Формирует сводный статус проекта P-026 со строгой actor/chat изоляцией решений."""
        try:
            self.subject_base.verify_all_sources()
        except SubjectBaseIntegrityError:
            return ""

        status_text = self.subject_base.format_project_status()
        recent_decisions = self.storage.list_decisions(user_id=user_id, chat_id=chat_id)
        if recent_decisions:
            status_text += "\n\n📝 *Зафиксированные решения текущего пользователя:*"
            for dec in recent_decisions[-5:]:
                status_text += f"\n• [{dec['id']}] ({dec['question_context']}): {dec['exact_text']}"
        return status_text

    def export_draft(
        self,
        doc_type: str,
        author: str = "Руководитель",
        user_id: int | None = None,
        chat_id: int | None = None,
        custom_header: str | None = None,
    ) -> dict[str, Any]:
        """Экспортирует версионный рабочий черновик документа КД со строгой проверкой целостности."""
        normalized_type = doc_type.strip().lower()
        role_key = DOC_TYPE_MAP.get(normalized_type)
        if not role_key or role_key not in self.subject_base.DOCUMENT_VERSIONS:
            return {
                "ok": False,
                "error": f"Неизвестный тип документа: '{doc_type}'. Доступны: {list(DOC_TYPE_MAP.keys())}",
                "draft": None,
            }

        # Строгая fail-closed проверка целостности базы источников и исходного документа
        try:
            self.subject_base.verify_all_sources()
            content = self.subject_base.read_verified_document(role_key)
        except (FileNotFoundError, SubjectBaseIntegrityError, KeyError, PermissionError) as err:
            return {
                "ok": False,
                "error": f"Отказ экспорта: ошибка источника для '{role_key}': {err}",
                "draft": None,
            }

        # Строгая изоляция: добавляем ТОЛЬКО решения текущего пользователя и чата
        active_decisions = self.storage.list_decisions(
            user_id=user_id,
            chat_id=chat_id,
            status="active",
        )
        decisions_block = ""
        if active_decisions:
            decisions_block = "\n\n## Зафиксированные решения руководителя (P-026)\n"
            for dec in active_decisions:
                decisions_block += f"- [{dec['timestamp']}] ({dec['question_context']}): {dec['exact_text']}\n"

        full_draft_content = (custom_header or "") + content + decisions_block
        safe_doc_name = f"DRAFT_{role_key.replace(' ', '_')}"
        draft_info = self.storage.save_draft(
            doc_name=safe_doc_name,
            content=full_draft_content,
            author=author,
            user_id=user_id,
            chat_id=chat_id,
        )

        return {
            "ok": True,
            "role": role_key,
            "version": draft_info["version"],
            "draft": draft_info,
            "message": (
                f"Черновик {role_key} успешно экспортирован: {draft_info['filename']} "
                f"({draft_info['bytes']} байт). Исходные файлы защищены."
            ),
        }
