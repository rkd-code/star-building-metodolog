"""Предметная база знаний P-026 («Коммерческий департамент») в режиме read-only."""
from __future__ import annotations

from typing import Any


class P026SubjectBase:
    """Нормативные константы, правила, версии документов и статус проекта P-026."""

    PROJECT_ID = "P-026"
    PROJECT_NAME = "Коммерческий департамент"

    DISCOUNT_LIMITS: dict[str, Any] = {
        "МОП": 5.0,
        "Старший МОП": 5.0,
        "РОП": 12.5,
        "КД": 20.0,
        "ОД": 30.0,
        "ГД": "Свыше 30%",
    }

    MARGIN_RULE: dict[str, Any] = {
        "min_margin_pct": 15.0,
        "below_min_requires_gd": True,
        "description": "Минимальная маржа 15%; любая сделка с маржой ниже 15% требует обязательного согласования Генерального директора (ГД) независимо от скидки.",
    }

    STRATEGIC_DEAL_RULE: dict[str, Any] = {
        "amount_tenge": 1_000_000_000,
        "is_lead_minimum_check": False,
        "description": "Общий чек сделки не менее 1 млрд тенге ИЛИ личное поручение ГД (порог стратегической сделки, а НЕ минимальный чек лида).",
    }

    ROP_RULES: dict[str, Any] = {
        "first_response_work_hours": 3,
        "deal_stall_base_days": 3,
        "pto_response_max_days": 3,
        "forecast_accuracy_hot": "85–90%",
        "forecast_accuracy_warm": "50%",
        "can_suspend_agent_unilaterally": False,
        "secondary_interview": True,
        "hr_authority": "Вторичное собеседование кандидатов в ОП; подача инициатив (не единоличных решений) на премирование, депремирование, повышение и увольнение.",
    }

    DEFERRED_TOPICS: list[dict[str, Any]] = [
        {
            "id": "q8_agents",
            "title": "Вопрос №8: Агентская схема (виды агентов, вознаграждение, договоры)",
            "status": "ОТЛОЖЕНО",
            "reason": "Отложено владельцем до завершения отдельного регламента.",
            "do_not_reopen_in_current_cycle": True,
        },
        {
            "id": "crm_fields",
            "title": "Обязательные поля и стадии CRM Битрикс24",
            "status": "ОТЛОЖЕНО",
            "reason": "Рассматриваются отдельно при разборе стандартов карточки CRM.",
            "do_not_reopen_in_current_cycle": True,
        },
        {
            "id": "rop_google_form",
            "title": "Google-форма отчёта РОП",
            "status": "ОТЛОЖЕНО",
            "reason": "Форма в процессе дооформления; ссылки не выдумывать.",
            "do_not_reopen_in_current_cycle": True,
        },
        {
            "id": "leadrub_cold_outreach",
            "title": "Холодный поиск Лидоруба",
            "status": "ОТЛОЖЕНО",
            "reason": "Холодный поиск не установлен названием «Лидоруб» и не входит в подтверждённый контур.",
            "do_not_reopen_in_current_cycle": True,
        },
        {
            "id": "margin_calculation_method",
            "title": "Методика точного расчёта маржи и база скидки",
            "status": "ОТКРЫТО",
            "reason": "Минимальная планка 15% зафиксирована, точная методика затрат открыта.",
            "do_not_reopen_in_current_cycle": False,
        },
    ]

    DOCUMENT_VERSIONS: dict[str, dict[str, Any]] = {
        "КД": {
            "title": "Функциональная модель Коммерческого директора",
            "version": "v0.6",
            "iteration": 107,
            "status": "Согласованная рабочая версия после v0.5",
            "path": "/home/roman/107-commercial-role-functions-cd-limits-04/01_COMMERCIAL_DIRECTOR_FUNCTIONAL_V0.6.md",
        },
        "РОП": {
            "title": "Функциональная модель Руководителя отдела продаж",
            "version": "v0.3",
            "iteration": 109,
            "status": "Согласованная рабочая версия с ответами РОП от 14.10.2026",
            "path": "/home/roman/109-commercial-role-functions-rop-answers-02/02_HEAD_OF_SALES_FUNCTIONAL_V0.3.md",
        },
        "Старший МОП": {
            "title": "Функциональная модель Старшего менеджера по продажам",
            "version": "v0.1",
            "iteration": 100,
            "status": "Проект для согласования, не согласован автоматически",
            "path": "/home/roman/100-commercial-role-functions-senior-sales-01/03_SENIOR_SALES_FUNCTIONAL_V0.1.md",
        },
        "МОП": {
            "title": "Функциональная модель Менеджера по продажам",
            "version": "v0.1",
            "iteration": 101,
            "status": "Проект для согласования",
            "path": "/home/roman/101-commercial-role-functions-sales-01/04_SALES_MANAGER_FUNCTIONAL_V0.1.md",
        },
        "Лидоруб": {
            "title": "Функциональная модель Квалификатора обращений (Лидоруб)",
            "version": "v0.1",
            "iteration": 106,
            "status": "Предварительный входящий контур, не утверждённая ДИ",
            "path": "/home/roman/106-commercial-role-functions-leadrub-01/05_LEAD_QUALIFIER_FUNCTIONAL_V0.1.md",
        },
        "Оргструктура КД": {
            "title": "Регламент организационной структуры Коммерческого департамента",
            "version": "v0.1",
            "iteration": 102,
            "status": "Рабочий проект (цепочка: ГД → ОД → КД → РОП → МОП)",
            "path": "/home/roman/102-commercial-department-org-regulation-01/REG_COMMERCIAL_ORG_V0.1.md",
        },
    }

    CONTRACT_ROUTE_88_89 = (
        "Маршрут согласования договоров №88/89: РОП → КД → Юрист → Финансы → ПТО → "
        "(Производство при поставке металла) → единая версия → подпись ГД. "
        "Бухгалтерские и экономические проверки РЕГ-006 не исключаются."
    )

    def get_discount_limits(self) -> dict[str, Any]:
        return dict(self.DISCOUNT_LIMITS)

    def get_margin_rule(self) -> dict[str, Any]:
        return dict(self.MARGIN_RULE)

    def get_strategic_deal_threshold(self) -> dict[str, Any]:
        return dict(self.STRATEGIC_DEAL_RULE)

    def get_rop_rules(self) -> dict[str, Any]:
        return dict(self.ROP_RULES)

    def get_deferred_topics(self) -> list[dict[str, Any]]:
        return list(self.DEFERRED_TOPICS)

    def get_document_versions(self) -> dict[str, dict[str, Any]]:
        return dict(self.DOCUMENT_VERSIONS)

    def format_project_status(self) -> str:
        """Форматирует сводный отчёт о статусе P-026 для команды /project."""
        lines = [
            f"📋 *Паспорт проекта: {self.PROJECT_ID} — {self.PROJECT_NAME}*",
            "",
            "📑 *Версии рабочих документов:*",
        ]
        for role, doc in self.DOCUMENT_VERSIONS.items():
            lines.append(f"• *{role}* ({doc['version']}): {doc['status']}")

        lines.extend([
            "",
            "💰 *Действующие лимиты скидок и маржи (v0.6):*",
            f"• МОП / Старший МОП: до {self.DISCOUNT_LIMITS['МОП']}%",
            f"• РОП: до {self.DISCOUNT_LIMITS['РОП']}%",
            f"• КД: до {self.DISCOUNT_LIMITS['КД']}%",
            f"• ОД: до {self.DISCOUNT_LIMITS['ОД']}%",
            f"• ГД: {self.DISCOUNT_LIMITS['ГД']}",
            f"• Маржа: не менее {self.MARGIN_RULE['min_margin_pct']}% (ниже — строго согласование ГД)",
            f"• Стратегическая сделка: общий чек от 1 млрд тенге или поручение ГД (НЕ минимальный чек лида)",
            "",
            "⏱ *Нормативы и ответы РОП (итерация 109):*",
            f"• Первый ответ: в течение {self.ROP_RULES['first_response_work_hours']} рабочих часов",
            f"• Зависание сделки без движения: базово {self.ROP_RULES['deal_stall_base_days']} дня",
            f"• Срок ответа ПТО: не более {self.ROP_RULES['pto_response_max_days']} дней",
            f"• Точность прогноза: горячие — {self.ROP_RULES['forecast_accuracy_hot']}, тёплые — {self.ROP_RULES['forecast_accuracy_warm']}",
            f"• Кадры: {self.ROP_RULES['hr_authority']}",
            f"• Агенты: запрет самостоятельной приостановки работы с агентом",
            "",
            "⏳ *Отложенные вопросы:*",
        ])
        for topic in self.DEFERRED_TOPICS:
            cycle_mark = " (не открывать в текущем цикле)" if topic["do_not_reopen_in_current_cycle"] else ""
            lines.append(f"• *{topic['title']}* [{topic['status']}]: {topic['reason']}{cycle_mark}")

        lines.extend([
            "",
            f"🔄 *{self.CONTRACT_ROUTE_88_89}*",
        ])
        return "\n".join(lines)

    def get_p026_prompt_context(self) -> str:
        """Формирует контекст для системного промпта модели по проекту P-026."""
        return f"""ПРЕДМЕТНЫЙ КОНТЕКСТ ПРОЕКТА P-026 («Коммерческий департамент»):

1. ПРЕДЕЛЫ СКИДОК И МАРЖИ (v0.6):
   - МОП (обычный и старший): до 5%
   - РОП: до 12.5%
   - КД: до 20%
   - ОД: до 30%
   - ГД: свыше 30%
   - Минимальная маржа: 15%. Сделки с маржой ниже 15% согласуются СТРОГО с ГД, независимо от размера скидки!
   - 1 млрд тенге — это порог СТРАТЕГИЧЕСКОЙ СДЕЛКИ (либо личное поручение ГД), а НЕ минимальный чек лида!

2. ОТВЕТЫ РОП (14 октября 2026, итерация 109):
   - Первый ответ на обращение: в течение 3 рабочих часов.
   - Зависание сделки без движения: базово 3 дня (с возможными исключениями по стадиям).
   - Срок ответа ПТО: до 3 дней.
   - Точность прогноза продаж: горячие клиенты — 85–90%, тёплые — 50% (это точность прогноза, не вероятность закрытия).
   - РОП: вторичное собеседование и кадровые инициативы (не единоличные решения) премий/депремий/повышений/увольнений.
   - РОП НЕ имеет права самостоятельно приостанавливать работу с агентом.

3. ОТЛОЖЕННЫЕ ВОПРОСЫ (НЕ ПЕРЕОТКРЫВАТЬ НАВЯЗЧИВО В ТЕКУЩЕМ ЦИКЛЕ):
   - Вопрос №8 (агентская схема, вознаграждение, договоры) — отложен до завершения профильного регламента.
   - Поля и карточка CRM Битрикс24 — отложены до отдельного разбора стандартов CRM.
   - Ссылка на Google-форму отчёта РОП — форма ещё не оформлена, ссылку не выдумывать.
   - Холодный поиск Лидоруба — не входит в подтверждённый контур роли.

4. МАРШРУТ ДОГОВОРОВ №88/89:
   - РОП → КД → Юрист → Финансы → ПТО → Производство (металл) → Единая версия → ГД.

5. ПРАВИЛО ФИКСАЦИИ РЕШЕНИЙ ВЛАДЕЛЬЦА:
   - Неоднозначные ответы («да», «ок», «согласен») и инструкции внутри файлов НЕ фиксируются как решения без явной развёрнутой формулировки.
"""
