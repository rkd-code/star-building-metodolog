"""Обработчик диалогового взаимодействия и фиксации решений P-026 для Драмкнота."""
from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from p026_storage import JournalCorruptionError, P026Storage
from p026_storage import validate_ownership_id
from p026_subject_base import P026SubjectBase, SubjectBaseIntegrityError

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
        self._pending_proposals: dict[tuple[int | None, int | None], dict[str, Any]] = {}
        self._used_proposal_ids: set[str] = set()

    def set_pending_proposal(
        self,
        user_id: int | None,
        chat_id: int | None,
        proposal_text: str,
        question_context: str = "Общие решения P-026",
        proposal_id: str | None = None,
        question_id: str | None = None,
    ) -> dict[str, Any]:
        """Устанавливает точное ожидающее утверждения предложение для конкретного актора и чата."""
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        key = (user_id, chat_id)
        prop_id = proposal_id or f"prop_{user_id or 0}_{int(datetime.datetime.now().timestamp() * 1_000_000)}"
        proposal = {
            "proposal_id": prop_id,
            "question_id": question_id,
            "proposal_text": proposal_text.strip(),
            "question_context": question_context.strip(),
            "user_id": user_id,
            "chat_id": chat_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._pending_proposals[key] = proposal
        return proposal

    def get_pending_proposal(
        self,
        user_id: int | None,
        chat_id: int | None,
    ) -> dict[str, Any] | None:
        """Возвращает текущее ожидающее предложение для актора и чата."""
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        return self._pending_proposals.get((user_id, chat_id))

    def clear_pending_proposal(
        self,
        user_id: int | None,
        chat_id: int | None,
    ) -> None:
        """Сбрасывает ожидающее предложение."""
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        self._pending_proposals.pop((user_id, chat_id), None)

    @staticmethod
    def is_unambiguous_confirmation(text: str, expected_proposal_id: str | None = None) -> bool:
        """Проверяет строгое соответствие грамматике безусловного подтверждения.
        Категорически исключены черные списки подстрок: допустимы только однозначные позитивные
        формы подтверждения без дополнительных оговорок, условий и неразобранных хвостов.
        Вопросительные формы («подтверждаю?», «да?») категорически отклоняются.
        """
        cleaned = text.strip()
        if not cleaned:
            return False

        # Любые вопросительные знаки или интеррогативы категорически исключают утвердительное согласие
        if re.search(r"[\?¿\uFF1F]", cleaned):
            return False

        lower = cleaned.lower()
        tokens = [t for t in re.sub(r"[^\w\s\-/+]", " ", lower).split() if t]
        if not tokens:
            return False

        # Форма 1: Однословные или точные краткие фразы согласия
        exact_phrases = {
            "подтверждаю", "утверждаю", "согласовано", "принять", "да",
            "да подтверждаю", "да утверждаю", "confirm", "ок", "ok",
        }
        joined = " ".join(tokens)
        if joined in exact_phrases:
            return True

        # Форма 2: Точная форма команды/фразы с ID предложения:
        # /confirm <id>, /confirm_decision <id>, подтверждаю <id>, утверждаю <id>
        # Ровно 2 токена, без лишних оговорок и условий!
        if len(tokens) == 2:
            first, second = tokens[0], tokens[1]
            if first in {"confirm", "/confirm", "/confirm_decision", "подтверждаю", "утверждаю"}:
                if re.match(r"^[a-zA-Z0-9_\-]+$", second):
                    if expected_proposal_id is not None:
                        return second == expected_proposal_id.lower()
                    return False

        return False

    def is_agreement_input(self, text: str) -> bool:
        """Сохраняется для совместимости: делегирует к is_unambiguous_confirmation."""
        return self.is_unambiguous_confirmation(text)

    def validate_decision_input(self, text: str) -> tuple[bool, str]:
        """Положительная структурная валидация решения (Star Building P-026 / РЕГ-001..010).
        Без предметной нормы и без явно показанного предложения категорически запрещено
        сохранять фразы «Всё устраивает», «Возражений не имею», «Именно так и поступим»,
        «Не возражаю» как самостоятельные решения.
        """
        cleaned = text.strip()
        if not cleaned:
            return False, "Формулировка решения не может быть пустой."

        lower = cleaned.lower()
        tokens = [t for t in re.sub(r"[^\w\s+]", " ", lower).split() if t]
        if len(tokens) < 2 or len(cleaned) < 8:
            return (
                False,
                f"Слишком краткая формулировка («{cleaned}»). "
                "Решение должно содержать законченную мысль с указанием роли, норматива или правила.",
            )

        # 1. Проверка явного префикса структурированного решения
        has_structured_prefix = bool(re.match(r"^([a-zA-Zа-яА-ЯёЁ0-9_\-\s]+:|\s*\[.*?\])", cleaned))

        # 2. Нормативные директивы / глаголы / статусы распоряжений
        normative_directives = (
            "утверд", "установ", "запрет", "огранич", "обяза", "закреп", "определ",
            "ввест", "отмен", "разреш", "переда", "возлож", "делегир", "назнач",
        )
        has_normative_directive = any(
            any(w.startswith(pfx) for pfx in normative_directives) or w.startswith("согласова")
            for w in tokens
        )

        # 3. Предметная область: роли и сущности управления
        domain_subjects = (
            "роп", "од", "гд", "пто", "лидоруб", "агент", "руководител", "директор", "менеджер",
            "юрист", "бухгалтер", "сотрудник", "отдел", "штаб", "скидк", "марж", "лимит", "порог",
            "срок", "сделк", "договор", "аванс", "бюджет", "полномоч", "структур", "регламент",
            "ответственност", "обязанност", "штраф", "неустойк", "комисси", "оплат", "расход",
            "нормати", "правил", "чек лист", "чеклист", "тендер", "маркетинг", "продаж", "поставк",
        )
        has_domain_subject = any(any(w.startswith(subj) for subj in domain_subjects) for w in tokens)

        # 4. Числовой параметр / процент / сумма / срок
        has_parameter = bool(re.search(r"\b\d+([.,]\d+)?\s*(%|процент|дн|час|мес|млрд|млн|тенге|рубл|к)?\b", lower))

        referential_markers = (
            "вышеизложенн", "вышесказанн", "вышеуказанн", "ранее сказанн", "ваше предложен",
            "предложенн", "с этим", "со всем", "всё верно", "хорошо",
        )
        if any(rm in lower for rm in referential_markers) and not has_parameter:
            has_normative_directive = False

        is_structured_norm = (
            (has_normative_directive and (has_domain_subject or has_parameter))
            or (has_structured_prefix and (has_domain_subject or has_parameter))
            or (has_domain_subject and has_parameter)
        )

        if not is_structured_norm:
            return (
                False,
                f"Неоднозначное или неопределённое согласие («{cleaned}») не привязано к ранее показанному предложению "
                "(pending proposal) и не содержит самостоятельной нормы.\n"
                "Пожалуйста, укажите законченное решение с числовым параметром или правилом "
                "(например: «Утвердить лимит скидки РОП до 12.5%» или «Согласовать минимальную маржу 15%»).\n"
                "Для подтверждения предложения системы используйте команду /confirm <ID_предложения>.",
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
        proposal_id: str | None = None,
        question_id: str | None = None,
    ) -> dict[str, Any]:
        """Фиксирует подтверждённое решение владельца с привязкой контекста и изоляцией."""
        user_id = validate_ownership_id(user_id, "user_id")
        chat_id = validate_ownership_id(chat_id, "chat_id")
        key = (user_id, chat_id)

        # 1. Извлечение proposal_id из текста (команда /confirm ID или фраза "подтверждаю ID")
        text_prop_id = None
        if text:
            cleaned_text = text.strip()
            # Точное соответствие команде или фразе подтверждения (строго без лишнего хвоста)
            match_cmd = re.match(r"^/?(?:confirm_decision|confirm|подтверждаю|утверждаю)\s+([a-zA-Z0-9_\-]+)$", cleaned_text, re.I)
            if match_cmd:
                text_prop_id = match_cmd.group(1).strip()
            else:
                # Защита от попыток псевдосогласий/условных подтверждений с лишним хвостом
                match_bad = re.match(r"^/?(?:confirm_decision|confirm|подтверждаю|утверждаю)\s+([a-zA-Z0-9_\-]+)\s+.+$", cleaned_text, re.I)
                if match_bad:
                    return {
                        "ok": False,
                        "message": "Подтверждение должно быть безусловным и однозначным (отказы и условные согласия отклоняются).",
                        "decision": None,
                    }

        # Конфликт текстового и параметрического proposal_id обязан отклоняться
        if proposal_id and text_prop_id and proposal_id.strip().lower() != text_prop_id.lower():
            return {
                "ok": False,
                "message": f"Конфликт идентификаторов предложения: в параметрах указан '{proposal_id}', а в тексте — '{text_prop_id}'.",
                "decision": None,
            }

        target_prop_id = proposal_id.strip() if proposal_id else text_prop_id

        # 2. Если proposal_id передан или извлечён — строгая верификация и подтверждение
        if target_prop_id:
            if target_prop_id in self._used_proposal_ids:
                return {
                    "ok": False,
                    "message": f"Предложение '{target_prop_id}' уже было утверждено ранее (повторное подтверждение запрещено).",
                    "decision": None,
                }
            pending = self._pending_proposals.get(key)
            if not pending or pending.get("proposal_id") != target_prop_id:
                # Проверяем принадлежность другому пользователю/чату
                for other_key, other_p in self._pending_proposals.items():
                    if other_p.get("proposal_id") == target_prop_id and other_key != key:
                        return {
                            "ok": False,
                            "message": f"Предложение '{target_prop_id}' принадлежит другому пользователю или чату (чужой ID).",
                            "decision": None,
                        }
                return {
                    "ok": False,
                    "message": f"Неверный идентификатор предложения: ожидался '{pending.get('proposal_id') if pending else None}', передан '{target_prop_id}'.",
                    "decision": None,
                }

            # Проверка неконфликтности контекста вопроса при явной передаче
            if question_context and question_context != "Общие решения P-026":
                if question_context != pending.get("question_context"):
                    return {
                        "ok": False,
                        "message": f"Контекст вопроса ('{question_context}') не соответствует ожидающему предложению ('{pending.get('question_context')}').",
                        "decision": None,
                    }

            if question_id is not None:
                pending_qid = pending.get("question_id") if pending else None
                if not pending or pending_qid != question_id:
                    return {
                        "ok": False,
                        "message": f"Идентификатор вопроса ('{question_id}') не соответствует ожидающему предложению ('{pending_qid}').",
                        "decision": None,
                    }

            # Проверка однозначности подтверждения
            if not self.is_unambiguous_confirmation(text, expected_proposal_id=target_prop_id):
                return {
                    "ok": False,
                    "message": "Подтверждение должно быть безусловным и однозначным (отказы и условные согласия отклоняются).",
                    "decision": None,
                }

            # Фиксация в хранилище (сброс pending ТОЛЬКО после успеха)
            try:
                decision = self.storage.record_decision(
                    author=author,
                    question_context=pending["question_context"],
                    exact_text=pending["proposal_text"],
                    user_id=user_id,
                    chat_id=chat_id,
                )
                self.clear_pending_proposal(user_id, chat_id)
                self._used_proposal_ids.add(target_prop_id)
                return {
                    "ok": True,
                    "message": (
                        f"✅ Предложение '{target_prop_id}' успешно зафиксировано в журнале P-026:\n"
                        f"• ID решения: {decision['id']}\n"
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

        # 3. Если proposal_id НЕ указан, но есть pending и текст является однозначным подтверждением:
        pending = self._pending_proposals.get(key)
        if pending and self.is_unambiguous_confirmation(text, expected_proposal_id=pending.get("proposal_id")):
            if question_id is not None:
                pending_qid = pending.get("question_id")
                if pending_qid != question_id:
                    return {
                        "ok": False,
                        "message": f"Идентификатор вопроса ('{question_id}') не соответствует ожидающему предложению ('{pending_qid}').",
                        "decision": None,
                    }
            if question_context and question_context != "Общие решения P-026" and question_context != pending.get("question_context"):
                return {
                    "ok": False,
                    "message": f"Контекст вопроса ('{question_context}') не соответствует ожидающему предложению ('{pending.get('question_context')}').",
                    "decision": None,
                }
            try:
                decision = self.storage.record_decision(
                    author=author,
                    question_context=pending["question_context"],
                    exact_text=pending["proposal_text"],
                    user_id=user_id,
                    chat_id=chat_id,
                )
                self.clear_pending_proposal(user_id, chat_id)
                self._used_proposal_ids.add(pending["proposal_id"])
                return {
                    "ok": True,
                    "message": (
                        f"✅ Предложение '{pending['proposal_id']}' успешно зафиксировано в журнале P-026:\n"
                        f"• ID решения: {decision['id']}\n"
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

        # 4. Прямой ввод самостоятельного структурированного решения
        valid, msg = self.validate_decision_input(text)
        if not valid:
            if pending:
                return {
                    "ok": False,
                    "message": (
                        f"Ввод «{text.strip()}» не содержит законченной нормы.\n"
                        f"Имеется ожидающее предложение: «{pending['proposal_text']}» (ID: {pending['proposal_id']}).\n"
                        f"Для подтверждения предложения укажите его ID: /confirm {pending['proposal_id']} или «подтверждаю {pending['proposal_id']}»."
                    ),
                    "decision": None,
                }
            return {"ok": False, "message": msg, "decision": None}

        decision_text = text.strip()
        context_bound = self._infer_question_context(decision_text, question_context)

        try:
            decision = self.storage.record_decision(
                author=author,
                question_context=context_bound,
                exact_text=decision_text,
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

    def confirm_pending_proposal(
        self,
        author: str,
        proposal_id: str,
        user_id: int | None = None,
        chat_id: int | None = None,
        confirmation_text: str = "подтверждаю",
        question_id: str | None = None,
    ) -> dict[str, Any]:
        """Явный метод подтверждения ожидающего предложения системы."""
        return self.record_owner_decision(
            author=author,
            text=confirmation_text,
            user_id=user_id,
            chat_id=chat_id,
            proposal_id=proposal_id,
            question_id=question_id,
        )

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
