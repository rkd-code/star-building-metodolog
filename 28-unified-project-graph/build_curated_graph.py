#!/usr/bin/env python3
"""Build deterministic project entities for the unified Graphify graph."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_FILE = "28-unified-project-graph/PROJECT_REGISTRY.md"

PROJECTS = [
    {
        "id": "p001",
        "label": "P-001 — Корпоративная система «Кодификатор» Star Building",
        "goal": "Стандартизировать регламенты, проверять противоречия и консультировать сотрудников.",
        "owner": "лорд Витинари; Star Building",
        "path": "/home/roman",
        "technologies": "Markdown, HTML, JSON Schema, Python, Telegram, Gemini, Faster Whisper, Git, Hermes, Graphify",
        "documents": "README.md; AGENTS.md; PROJECT_MAP.md; KNOWLEDGE_BASE.md; DECISIONS.md",
        "status": "активный монорепозиторий; часть интеграций остается прототипом",
        "next_step": "зарегистрировать проект во всех профилях Hermes и проверить сквозную задачу",
    },
    {
        "id": "p002",
        "label": "P-002 — Нормативная база Star Building",
        "goal": "Хранить рабочие и утвержденные регламенты и проверять новые документы накопительно.",
        "owner": "Star Building; операционный владелец — не указано",
        "path": "/home/roman/knowledge_base",
        "technologies": "Markdown, Excel, карточки документов, RACI, двухконтурное хранение",
        "documents": "KNOWLEDGE_BASE.md; knowledge_base/00_РЕЕСТР; 19-top-20-roadmap; 21-cross-audit",
        "status": "РЕГ-001..009 утверждены; РЕГ-010 на согласовании v0.1",
        "next_step": "закрыть коллизии, назначить владельца реестра и разработать РЕГ-011..030",
    },
    {
        "id": "p003",
        "label": "P-003 — «Смотритель»",
        "goal": "Принимать черновики, выполнять сверку и формировать регламенты по пяти разделам.",
        "owner": "Star Building; владелец процесса — не указано",
        "path": "/home/roman/17-two-bots-split/bot_1_codifier.py",
        "technologies": "Python, Telegram Bot API, Gemini, Faster Whisper, DOCX, PDF",
        "documents": "17-two-bots-split/README.md; AGENTS.md; 20-cross-check-engine/README.md",
        "status": "рабочий прототип; промышленная эксплуатация не подтверждена",
        "next_step": "настроить защищенную переменную, испытания, сервисный запуск и мониторинг",
    },
    {
        "id": "p004",
        "label": "P-004 — «Ом»",
        "goal": "Консультировать сотрудников по утвержденной базе и готовить только утвержденные формы.",
        "owner": "Star Building; владелец процесса — не указано",
        "path": "/home/roman/17-two-bots-split/bot_2_consultant.py",
        "technologies": "Python, Telegram Bot API, Gemini, Faster Whisper, DOCX, PDF",
        "documents": "17-two-bots-split/README.md; KNOWLEDGE_BASE.md; DECISIONS.md",
        "status": "рабочий прототип; разграничение доступа и мониторинг не подтверждены",
        "next_step": "настроить защищенную переменную, испытания, сервисный запуск и мониторинг",
    },
    {
        "id": "p005",
        "label": "P-005 — «Сверщик» и сквозной аудит",
        "goal": "Находить противоречия сроков, ролей, документов и функций.",
        "owner": "Star Building; ответственный методолог — не указано",
        "path": "/home/roman/20-cross-check-engine; /home/roman/21-cross-audit",
        "technologies": "Markdown, матрицы пересечений, ссылки РЕГ-XXX, экспертная проверка",
        "documents": "20-cross-check-engine/README.md; 21-cross-audit/audit_report.md",
        "status": "правила и отчет подготовлены; известные коллизии не закрыты",
        "next_step": "автоматизировать испытания и закрыть коллизии решениями рабочей группы",
    },
    {
        "id": "p006",
        "label": "P-006 — Интеграция Битрикс24",
        "goal": "Согласовывать и публиковать утвержденные регламенты через корпоративный контур.",
        "owner": "Star Building; владелец портала — не указано",
        "path": "/home/roman/15-bitrix24-integration",
        "technologies": "Битрикс24 REST API, вебхуки, задачи, бизнес-процессы, Wiki",
        "documents": "15-bitrix24-integration/README.md; 05-integrations/architecture_v2.md",
        "status": "архитектура описана; фактическое подключение отсутствует",
        "next_step": "указать портал, владельца, рабочую группу и безопасную авторизацию",
    },
    {
        "id": "p007",
        "label": "P-007 — Прием черновиков и Telegram-контур",
        "goal": "Принимать текст, голос, DOCX и заявки через три входных канала.",
        "owner": "сотрудники Star Building; владелец каналов — не указано",
        "path": "/home/roman/14-intake-tool; /home/roman/16-telegram-setup",
        "technologies": "HTML, Telegram, голосовая транскрибация, DOCX, файловый накопитель",
        "documents": "14-intake-tool/README.md; 16-telegram-setup/README.md",
        "status": "интерфейсы спроектированы; единая серверная обработка не подтверждена",
        "next_step": "назначить владельца и связать каналы единым идентификатором заявки",
    },
    {
        "id": "p008",
        "label": "P-008 — Маркетинговые помощники Star Building",
        "goal": "Анализировать рынок и боли клиентов и готовить проверяемые материалы.",
        "owner": "Руководитель маркетинга; Star Building",
        "path": "/home/roman/24-marketing-bots; /home/roman/25-marketing-bots-detailed",
        "technologies": "Excel, n8n или Dify, Crawl4AI или Firecrawl, Qdrant",
        "documents": "24-marketing-bots/top_20_marketing_bots.md; marketing_bots_star_building.xlsx",
        "status": "концепция и таблица готовы; учетные записи и интеграции не созданы",
        "next_step": "утвердить пилот, назначить проверяющего и подключить законные источники",
    },
    {
        "id": "p009",
        "label": "P-009 — Оркестрация Hermes и разработка",
        "goal": "Разделить постановку, разработку и независимую приемку задач.",
        "owner": "лорд Витинари",
        "path": "/home/roman/26-hermes-profiles; ~/.hermes/profiles/developer",
        "technologies": "Hermes Profiles, Projects, Kanban, Git worktree, GitHub SSH, Graphify",
        "documents": "26-hermes-profiles/README.md; TASK_CONTRACT.md; 27-developer-skills/README.md",
        "status": "developer создан; orchestrator не создан; реестры проектов пусты",
        "next_step": "создать orchestrator, зарегистрировать P-001 и проверить Kanban-задачу",
    },
    {
        "id": "p010",
        "label": "P-010 — Единый граф Graphify проектов и знаний",
        "goal": "Связать проекты, людей, репозиторий, документы, решения и следующие шаги.",
        "owner": "лорд Витинари",
        "path": "/home/roman/28-unified-project-graph; /home/roman/graphify-out",
        "technologies": "Graphify, JSON, Markdown, HTML, Git",
        "documents": "PROJECT_REGISTRY.md; RELATIONSHIPS.md; graph.json; GRAPH_REPORT.md",
        "status": "реестр сформирован; граф строится",
        "next_step": "проверить все сущности запросами и обновлять граф после изменений",
    },
]

PEOPLE = [
    ("human_h001", "H-001 — лорд Витинари", "владелец направления и заказчик"),
    ("human_h002", "H-002 — Star Building", "корпоративный заказчик"),
    ("human_h003", "H-003 — Генеральный директор", "утверждающее лицо; имя не указано"),
    ("human_h004", "H-004 — Руководитель маркетинга", "функциональный пользователь; имя не указано"),
    ("human_h005", "H-005 — рабочая группа согласования", "состав не указан"),
    ("human_h006", "H-006 — сотрудники Star Building", "пользователи корпоративных сервисов"),
]

DOCUMENTS = [
    ("doc_d001", "D-001 — AGENTS.md"),
    ("doc_d002", "D-002 — PROJECT_MAP.md"),
    ("doc_d003", "D-003 — KNOWLEDGE_BASE.md"),
    ("doc_d004", "D-004 — DECISIONS.md"),
    ("doc_d005", "D-005 — реестр регламентов"),
    ("doc_d006", "D-006 — отчет сквозного аудита"),
    ("doc_d007", "D-007 — архитектура маркетинговых помощников"),
    ("doc_d008", "D-008 — книга маркетинговых функций"),
    ("doc_d009", "D-009 — договор кодовой задачи"),
    ("doc_d010", "D-010 — единый реестр проектов"),
]

ADR_TITLES = [
    "Выбор Claude Project", "Пилотная база знаний", "Стандарт пяти разделов", "Запрет выдуманных ролей",
    "Маркировка неполных данных", "Интерактивные уточнения", "Сопряжение конфликтов", "Голосовой ввод",
    "Версионность документов", "Накопительная база", "Два контура согласования", "Два Telegram-вектора",
    "Ограничение выдачи форм", "Встроенный Сверщик", "Кодовые имена", "Маркетинговые контуры",
    "Исследователь ниши", "Два профиля Hermes", "Предел контекста и итераций", "Навыки разработчика",
]


def node(node_id: str, label: str, entity_type: str, description: str = "", **attrs):
    return {
        "id": node_id,
        "label": label,
        "type": entity_type,
        "description": description,
        "source_file": SOURCE_FILE,
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "verification": "verified",
        **attrs,
    }


def edge(source: str, target: str, relation: str):
    return {
        "source": source,
        "target": target,
        "relation": relation,
        "context": "28-unified-project-graph/RELATIONSHIPS.md",
        "source_file": "28-unified-project-graph/RELATIONSHIPS.md",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
    }


def build_extraction():
    nodes = []
    for project in PROJECTS:
        nodes.append(node(
            project["id"], project["label"], "Project", project["goal"],
            goal=project["goal"], owner=project["owner"], github="https://github.com/rkd-code/star-building-metodolog",
            working_path=project["path"], technologies=project["technologies"], documents=project["documents"],
            current_status=project["status"], next_step=project["next_step"],
        ))

    nodes.append(node(
        "repo_r001", "R-001 — rkd-code/star-building-metodolog", "Repository",
        "Единый активный GitHub-монорепозиторий Star Building.",
        github="https://github.com/rkd-code/star-building-metodolog", working_path="/home/roman", default_branch="main",
    ))
    nodes.extend(node(i, label, "PersonOrRole", desc) for i, label, desc in PEOPLE)
    nodes.extend(node(i, label, "Document") for i, label in DOCUMENTS)
    nodes.extend(node(f"adr_{i:03d}", f"ADR-{i:03d} — {title}", "Decision") for i, title in enumerate(ADR_TITLES, 1))

    edges = []
    for i in range(1, 11):
        edges.append(edge(f"p{i:03d}", "repo_r001", "stored_in"))
    for i in range(2, 9):
        edges.append(edge("p001", f"p{i:03d}", "contains"))
    edges.extend([
        edge("p009", "p001", "manages_changes"), edge("p010", "p001", "indexes"),
        edge("p007", "p003", "submits_drafts_to"), edge("p007", "p004", "submits_questions_to"),
        edge("p003", "p002", "uses_knowledge"), edge("p004", "p002", "reads_approved_knowledge"),
        edge("p003", "p005", "calls"), edge("p005", "p002", "audits"),
        edge("p003", "p006", "submits_for_approval"), edge("p006", "p002", "publishes_after_approval"),
        edge("p008", "p002", "uses_corporate_facts"), edge("p009", "p010", "uses_for_analysis"),
        edge("human_h001", "p001", "owns"), edge("human_h001", "p009", "commissions"),
        edge("human_h001", "p010", "commissions"), edge("human_h001", "repo_r001", "owns_account_for"),
        edge("human_h002", "p001", "commissions"), edge("human_h003", "p002", "approves"),
        edge("human_h004", "p008", "uses"), edge("human_h005", "p002", "coordinates"),
        edge("human_h006", "p003", "uses"), edge("human_h006", "p004", "uses"), edge("human_h006", "p007", "submits_to"),
        edge("doc_d001", "p001", "governs"), edge("doc_d002", "p001", "describes"),
        edge("doc_d003", "p002", "describes"), edge("doc_d004", "p001", "records_decisions_for"),
        edge("doc_d005", "p002", "registers"), edge("doc_d006", "p005", "produced_by"),
        edge("doc_d007", "p008", "describes"), edge("doc_d008", "p008", "details"),
        edge("doc_d009", "p009", "governs"), edge("doc_d010", "p010", "describes"),
    ])
    adr_projects = {1: 1, 3: 1, 8: 7, 10: 2, 11: 2, 13: 4, 14: 5, 15: 3, 16: 8, 17: 8, 18: 9, 19: 9, 20: 9}
    for adr_num, project_num in adr_projects.items():
        edges.append(edge(f"adr_{adr_num:03d}", f"p{project_num:03d}", "governs"))

    return {"nodes": nodes, "edges": edges, "hyperedges": [], "input_tokens": 0, "output_tokens": 0}


def main():
    out = ROOT / "curated_graph_source.json"
    out.write_text(json.dumps(build_extraction(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
