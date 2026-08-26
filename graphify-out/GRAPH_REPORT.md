# Graph Report - roman  (2026-08-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 186 nodes · 190 edges · 52 communities (17 shown, 35 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.86)
- Token cost: semantic extraction 108,860 input · 5,046 output · estimated Gemini cost $0.0696; community labeling 1,693 input · 587 output

## Graph Freshness
- Built from commit: `ae785489`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Implementation Roadmap and Regulations
- AI Agent Prompts and Logic
- Telegram Bot Service Core
- Codifier Bot Implementation
- Consultant Bot Implementation
- System Integration and Features
- Graph Validation Tests
- Contract and Bitrix24 Workflow
- Corporate Governance and HR
- Graph Construction Scripts
- Regulation Conflict Checking
- Marketing Assistant Framework
- Workspace and HR Policies
- Document Type Definitions
- RACI and Agent Standards
- Hermes Profile Management
- Regulation Processing Pipeline
- Org Structure and Marketing
- Marketing Bot Family
- Project Registration Script
- Profile Setup Script
- Regulation Publication Process
- Process Card Extraction
- Strategic Foundation Policy
- Technical Specifications
- Telegram Group Organization
- Bot Behavior Guidelines
- Priority Regulation List
- Unified System Concept
- Bot Role Personas
- Marketing Content Automation
- Project Registry Management
- Unified Graph Registry
- Hex Computing System
- Claude Project Deployment
- Two-Circuit Storage Model
- Sverchik Collision Module
- Fuel Card Regulation
- Instruction Templates
- Official Orders
- Executive Directives
- Customer Service Standards
- Personnel Records
- Star Building Core Architecture
- Knowledge Base Pilot
- Role Definition Standards
- Data Integrity Labeling
- Interactive User Clarifications
- Conflict Resolution Logic
- Document Version Control
- Telegram Vector Architecture

## God Nodes (most connected - your core abstractions)
1. `P-001 — Корпоративная система «Кодификатор» Star Building` - 18 edges
2. `P-002 — Нормативная база Star Building` - 13 edges
3. `R-001 — rkd-code/star-building-metodolog` - 11 edges
4. `P-008 — Маркетинговые помощники Star Building` - 10 edges
5. `P-009 — Оркестрация Hermes и разработка` - 8 edges
6. `P-003 — «Смотритель»` - 8 edges
7. `handle_message()` - 7 edges
8. `handle_message()` - 7 edges
9. `handle_message()` - 7 edges
10. `Основной агент «Кодификатор»` - 6 edges

## Surprising Connections (you probably didn't know these)
- `@ReglamentSB_bot (Watchman)` --calls--> `REG-004: How to Write a Regulation`  [INFERRED]
  23-code-names/README.md → knowledge_base/01_КАРТОЧКИ/card_REG-004_kak_napisat_reglament.md
- `Intake Tool Design` --references--> `@ReglamentSB_bot (Watchman)`  [INFERRED]
  14-intake-tool/README.md → 23-code-names/README.md
- `Уильям де Ворд (William de Worde)` --implements--> `P-008 — Маркетинговые помощники Star Building`  [INFERRED]
  25-marketing-bots-detailed/README.md → 28-unified-project-graph/PROJECT_REGISTRY.md
- `Основной агент «Кодификатор»` --implements--> `5-Section Regulation Schema`  [EXTRACTED]
  AGENTS.md → 03-data-model/README.md
- `Основной агент «Кодификатор»` --references--> `REG-002: Communications Regulation`  [EXTRACTED]
  AGENTS.md → KNOWLEDGE_BASE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Marketing Automation Flow** — home_roman::bot_hex, home_roman::bot_william_de_worde, home_roman-2::p008 [EXTRACTED 0.90]
- **Система управления Star Building** — home_roman::knowledge_base_02_utverzhdeno_full_reg_001_kodeks, home_roman::knowledge_base_02_utverzhdeno_full_reg_002_orgstruktura, home_roman::knowledge_base_01_v_rabote_full_reg_003_strategicheskaya_osnova, home_roman::knowledge_base_01_v_rabote_full_reg_005_vidy_reglamentov [EXTRACTED 0.95]
- **Star Building Normative Base** — home_roman::reg001_kodeks, home_roman::reg002_orgstructure, home_roman-2::p001 [EXTRACTED 0.95]
- **Codifier Agent Family** — home_roman::agents_md_kartochnik, home_roman::agents_md_sverschik, home_roman::agents_md_codifier [EXTRACTED 1.00]
- **Core Knowledge Base (The 'Golden Standard')** — home_roman::07_concept_concept_reg_001, home_roman::07_concept_concept_reg_002, home_roman::07_concept_concept_reg_003 [EXTRACTED 1.00]
- **Core Knowledge Base** — home_roman::knowledge_base_reg_001, home_roman::knowledge_base_reg_002, home_roman::knowledge_base_reg_003 [EXTRACTED 1.00]
- **Core Knowledge Base (REG-001..003)** — home_roman::reg_001_kodeks, home_roman::reg_002_orgstruktura [EXTRACTED 1.00]
- **Dual-Circuit AI Assistant Architecture** — home_roman::bot_codifier, home_roman::bot_consultant, home_roman::module_svershchik, home_roman::10_general_assistant_readme [EXTRACTED 1.00]
- **Hermes Agent System** — home_roman::profile_orchestrator, home_roman::profile_developer, home_roman-2::p009 [EXTRACTED 1.00]
- **Иерархия регламентирующей документации** — home_roman::knowledge_base_02_утверждено_full_reg_005_vidy_reglamentov_rgv, home_roman::knowledge_base_02_утверждено_full_reg_005_vidy_reglamentov_rgp, home_roman::knowledge_base_02_утверждено_full_reg_005_vidy_reglamentov_prikaz, home_roman::knowledge_base_02_утверждено_full_reg_005_vidy_reglamentov_rasporyazhenie, home_roman::knowledge_base_02_утверждено_full_reg_005_vidy_reglamentov_instrukciya [EXTRACTED 1.00]
- **Codification Logic Flow** — home_roman::knowledge_base_smotritel, home_roman::04_environment_promt_sverschik, home_roman::04_environment_promt_kartochnik [INFERRED 0.85]
- **Automated Verification Flow** — home_roman::06_tools_tools_specification_проверить_конфликты_с_ядром, home_roman::20_cross_check_engine_cross_check_logic, home_roman::21_cross_audit_audit_report_sla_conflict [INFERRED 0.85]
- **Процесс управления персоналом** — home_roman::knowledge_base_01_v_rabote_full_reg_007_kadrovoe_deloproizvodstvo, home_roman::knowledge_base_01_v_rabote_full_reg_008_sistema_motivacii, home_roman::knowledge_base_02_utverzhdeno_full_reg_002_orgstruktura [INFERRED 0.85]
- **Кадровые и мотивационные процессы** — home_roman::knowledge_base_02_утверждено_full_reg_007_kadrovoe_deloproizvodstvo_reglament, home_roman::knowledge_base_02_утверждено_full_reg_008_sistema_motivacii_reglament [INFERRED 0.90]

## Communities (52 total, 35 thin omitted)

### Community 0 - "Implementation Roadmap and Regulations"
Cohesion: 0.17
Nodes (12): Roadmap: Star Building Implementation, Document Templates Catalog, General Assistant Concept, Intake Tool Design, @ReglamentSB_bot (Watchman), @star_building_help_bot (Om), Master Registry of Regulations, Svershchik (Collision Checker) (+4 more)

### Community 1 - "AI Agent Prompts and Logic"
Cohesion: 0.22
Nodes (11): TC-01: Happy Path Test, Prompt: Sverchik (Auditor), Основной агент «Кодификатор», Промпт «Карточник», Промпт «Сверщик», 5-Section Regulation Schema, Bot: Om (Consultant), REG-001: Code of Conduct (+3 more)

### Community 2 - "Telegram Bot Service Core"
Cohesion: 0.36
Nodes (7): handle_message(), handle_start(), main(), process_user_request(), DEFAULT_TYPE, Update, transcribe_audio()

### Community 3 - "Codifier Bot Implementation"
Cohesion: 0.36
Nodes (7): handle_message(), handle_start(), main(), process_draft_request(), DEFAULT_TYPE, Update, transcribe_audio()

### Community 4 - "Consultant Bot Implementation"
Cohesion: 0.36
Nodes (7): handle_message(), handle_start(), main(), process_consultant_request(), DEFAULT_TYPE, Update, transcribe_audio()

### Community 5 - "System Integration and Features"
Cohesion: 0.29
Nodes (7): Dual-Circuit Architecture, Voice Input Support, Consultant Scenario Flow, Bitrix24 Integration, @ReglamentSB_bot (Смотритель), @star_building_help_bot (Ом), Cross-Check Engine

### Community 7 - "Contract and Bitrix24 Workflow"
Cohesion: 0.33
Nodes (6): Битрикс24, РЕГ-004 Как правильно написать регламент, РЕГ-005 Виды регламентов и их роль в компании, РЕГ-006 Правила ведения договорной работы, Инициатор договора, Правила ведения договорной работы

### Community 8 - "Corporate Governance and HR"
Cohesion: 0.40
Nodes (6): РЕГ-003 Стратегическая основа компании, РЕГ-007 Кадровое делопроизводство, РЕГ-008 Единая система мотивации, поощрения и выслуги лет, РЕГ-010 Стандарт клиентоориентированности и управления клиентским опытом, РЕГ-001 Кодекс группы компаний Star Building, РЕГ-002 Общая оргструктура и штатная модель

### Community 9 - "Graph Construction Scripts"
Cohesion: 0.70
Nodes (4): build_extraction(), edge(), main(), node()

### Community 10 - "Regulation Conflict Checking"
Cohesion: 0.50
Nodes (4): проверить_конфликты_с_ядром, читать_базовый_регламент, РЕГ-001: Кодекс Star Building, SLA Conflict (REG-010 vs REG-006)

### Community 11 - "Marketing Assistant Framework"
Cohesion: 0.22
Nodes (9): ADR-016 — Маркетинговые контуры, ADR-017 — Исследователь ниши, D-007 — архитектура маркетинговых помощников, D-008 — книга маркетинговых функций, H-004 — Руководитель маркетинга, P-008 — Маркетинговые помощники Star Building, 25-marketing-bots-detailed: Подробная таблица маркетинговых помощников, Уильям де Ворд (William de Worde) (+1 more)

### Community 12 - "Workspace and HR Policies"
Cohesion: 0.50
Nodes (4): Google Workspace, Кадровое делопроизводство, Единая система мотивации, поощрения и выслуги лет, Регламент использования топливных карт

### Community 13 - "Document Type Definitions"
Cohesion: 0.50
Nodes (4): Письмо-решение (ПР), Регламентирующая документация (РДК), Регламент производства (РГП), Регламент владельца по управлению компанией (РГВ)

### Community 14 - "RACI and Agent Standards"
Cohesion: 0.67
Nodes (3): RACI Matrix Standard, Entity: Regulation, System Prompt: Universal Agent

### Community 15 - "Hermes Profile Management"
Cohesion: 1.00
Nodes (3): 26-hermes-profiles: Два независимых профиля Hermes, Hermes Profile: Developer, Hermes Profile: Orchestrator

### Community 45 - "Star Building Core Architecture"
Cohesion: 0.09
Nodes (35): ADR-001 — Выбор Claude Project, ADR-003 — Стандарт пяти разделов, ADR-008 — Голосовой ввод, ADR-010 — Накопительная база, ADR-011 — Два контура согласования, ADR-013 — Ограничение выдачи форм, ADR-014 — Встроенный Сверщик, ADR-015 — Кодовые имена (+27 more)

## Knowledge Gaps
- **94 isolated node(s):** `register_project.sh script`, `setup_profiles.sh script`, `Промпт «Карточник»`, `Промпт «Сверщик»`, `5-Section Regulation Schema` (+89 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **35 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `P-001 — Корпоративная система «Кодификатор» Star Building` connect `Star Building Core Architecture` to `Marketing Assistant Framework`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `P-008 — Маркетинговые помощники Star Building` connect `Marketing Assistant Framework` to `Star Building Core Architecture`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `P-002 — Нормативная база Star Building` connect `Star Building Core Architecture` to `Marketing Assistant Framework`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **What connects `register_project.sh script`, `setup_profiles.sh script`, `Промпт «Карточник»` to the rest of the system?**
  _94 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Star Building Core Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.09411764705882353 - nodes in this community are weakly interconnected._