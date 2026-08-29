# Структура проекта: Агент «Кодификатор» (Codifier Agent v1.0 MVP)

Отпечаток исходной структуры: `0990d2b69ccb94e085fd02a1ef4c7ad4ceff65ee2c1c86f32104bc3edc63f16f`

## .git-templates

| Файл | Назначение |
|---|---|
| [`.git-templates/hooks/pre-commit`](https://github.com/rkd-code/star-building-metodolog/blob/main/.git-templates/hooks/pre-commit) | Файл проекта: pre-commit. |

## .githooks

| Файл | Назначение |
|---|---|
| [`.githooks/pre-commit`](https://github.com/rkd-code/star-building-metodolog/blob/main/.githooks/pre-commit) | Файл проекта: pre-commit. |

## .github

| Файл | Назначение |
|---|---|
| [`.github/workflows/documentation-integrity.yml`](https://github.com/rkd-code/star-building-metodolog/blob/main/.github/workflows/documentation-integrity.yml) | name: Проверка актуальности документации on: push: pull_request: jobs: documentation: runs-on: ubuntu-latest steps: - uses: actions/checkout@v4 - name: Проверить обязательную документацию run: — if [ -f 34-agent-repository-documentation/ens |

## 01-report

| Файл | Назначение |
|---|---|
| [`01-report/01_input_draft.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/01-report/01_input_draft.md) | Пример входных данных (Сырой черновик от руководителя) |
| [`01-report/02_output_regulation.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/01-report/02_output_regulation.md) | РЕГЛАМЕНТ: Входной контроль и приемка строительных материалов и конструкций на объекте |
| [`01-report/03_fields_description.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/01-report/03_fields_description.md) | Описание полей и структуры выходного документа агента «Кодификатор» |
| [`01-report/04_assumptions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/01-report/04_assumptions.md) | Список допущений и ограничений (MVP v1.0) |
| [`01-report/report.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/01-report/report.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Прототип выдачи агента «Кодификатор» v1.0 (MVP)</title> <link rel="preconnect" href="https://fonts. |

## 02-tests

| Файл | Назначение |
|---|---|
| [`02-tests/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/02-tests/README.md) | 02-tests: Комплекс приёмочных сценариев (Acceptance Test Suite) |
| [`02-tests/test_01_happy_path.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/02-tests/test_01_happy_path.md) | TC-01: Приёмочный сценарий «Обычный случай» (Happy Path) |
| [`02-tests/test_02_edge_cases.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/02-tests/test_02_edge_cases.md) | TC-02: Приёмочные сценарии «Граничные ситуации» (Edge Cases) |
| [`02-tests/test_03_safe_stop.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/02-tests/test_03_safe_stop.md) | TC-03: Приёмочный сценарий «Безопасная остановка» (Safe Stop / Circuit Breaker) |
| [`02-tests/test_04_idempotency_and_explainability.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/02-tests/test_04_idempotency_and_explainability.md) | TC-04: Приёмочный сценарий «Детерминизм и Объяснимость» (Idempotency & Explainability) |
| [`02-tests/test_assumptions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/02-tests/test_assumptions.md) | test_assumptions.md: Спорные ожидания и допущения приемочных тестов |

## 03-data-model

| Файл | Назначение |
|---|---|
| [`03-data-model/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/README.md) | 03-data-model: Модель данных системы кодификации |
| [`03-data-model/assumptions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/assumptions.md) | Допущения по модели данных (MVP v1.0) |
| [`03-data-model/data_model.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/data_model.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Модель данных системы «Кодификатор»</title> <link rel="preconnect" href="https://fonts.googleapis.c |
| [`03-data-model/entities.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/entities.md) | Реестр сущностей информационной модели |
| [`03-data-model/examples.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/examples.md) | Примеры записей данных |
| [`03-data-model/input_and_decisions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/input_and_decisions.md) | Структуры входных данных, решений, правок и журнала действий |
| [`03-data-model/mindmap.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/mindmap.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Карта связей и сущностей системы «Кодификатор»</title> <link rel="preconnect" href="https://fonts.g |
| [`03-data-model/relationships_schema.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/03-data-model/relationships_schema.md) | Схема связей между сущностями информационной модели |

## 04-environment

| Файл | Назначение |
|---|---|
| [`04-environment/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/README.md) | 04-environment: Окружение агента на сервере Гермеса |
| [`04-environment/assumptions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/assumptions.md) | Допущения по инфраструктуре и окружению (MVP v1.0) |
| [`04-environment/backup_and_logging.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/backup_and_logging.md) | Регламент резервного копирования и журналирования |
| [`04-environment/config_template.yaml`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/config_template.yaml) | Шаблон конфигурации агента на сервере Гермеса (config_template.yaml) |
| [`04-environment/custom_instructions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/custom_instructions.md) | Системные инструкции: Универсальный агент Star Building (Кодификатор + Консультант) |
| [`04-environment/env_template.txt`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/env_template.txt) | Шаблон файла секретов (.env.template) |
| [`04-environment/launch_instructions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/launch_instructions.md) | Инструкция по подготовке и запуску окружения |
| [`04-environment/promt-kartochnik.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/promt-kartochnik.md) | Промпт «Карточник» (Извлечение карточки из полного текста регламента) |
| [`04-environment/promt-sverschik.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/promt-sverschik.md) | Промпт «Сверщик» (Поиск противоречий и сборка реестра связей) |
| [`04-environment/roles_and_permissions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/roles_and_permissions.md) | Роли пользователей и системные права доступа |
| [`04-environment/structure.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/04-environment/structure.md) | Структура серверного окружения на сервере Гермеса |

## 05-integrations

| Файл | Назначение |
|---|---|
| [`05-integrations/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/05-integrations/README.md) | 05-integrations: Архитектура внешних интеграций |
| [`05-integrations/assumptions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/05-integrations/assumptions.md) | Допущения по внешним интеграциям (MVP v1.0) |
| [`05-integrations/data_flow_map.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/05-integrations/data_flow_map.md) | Карта сквозного движения данных между системами |
| [`05-integrations/systems_catalog.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/05-integrations/systems_catalog.md) | Каталог внешних систем и интерфейсов интеграции |
| [`05-integrations/version_scope.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/05-integrations/version_scope.md) | Матрица разделения интеграций по версиям |

## 06-tools

| Файл | Назначение |
|---|---|
| [`06-tools/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/06-tools/README.md) | 06-tools: Сервер инструментов и протокол контекста модели |
| [`06-tools/assumptions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/06-tools/assumptions.md) | Допущения по инструментам и среде исполнения (MVP v1.0) |
| [`06-tools/mcp_server_manifest.json`](https://github.com/rkd-code/star-building-metodolog/blob/main/06-tools/mcp_server_manifest.json) | { "имя_сервера": "сервер-инструментов-кодификатор", "версия": "1.0.0", "описание": "Сервер инструментов протокола контекста модели для кодификации и проверки регламентов строительной компании Star Building", "группы_инструментов": [ { "груп |
| [`06-tools/tools_specification.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/06-tools/tools_specification.md) | Спецификация инструментов и команд сервера контекста модели |

## 07-concept

| Файл | Назначение |
|---|---|
| [`07-concept/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/07-concept/README.md) | 07-concept: Сводная концепция системы «Кодификатор» |
| [`07-concept/concept.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/07-concept/concept.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Актуальная концепция агента Star Building</title> <link rel="preconnect" href="https://fonts.google |

## 08-refinement

| Файл | Назначение |
|---|---|
| [`08-refinement/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/08-refinement/README.md) | 08-refinement: Утвержденные уточнения бизнес-логики |

## 09-roadmap

| Файл | Назначение |
|---|---|
| [`09-roadmap/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/09-roadmap/README.md) | 09-roadmap: Пошаговый поэтапный план разработки |
| [`09-roadmap/roadmap.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/09-roadmap/roadmap.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Дорожная карта внедрения Star Building</title> <link rel="preconnect" href="https://fonts.googleapi |

## 10-general-assistant

| Файл | Назначение |
|---|---|
| [`10-general-assistant/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/10-general-assistant/README.md) | 10-general-assistant: Универсальный корпоративный агент (Кодификатор + Консультант) |
| [`10-general-assistant/consultant_scenario.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/10-general-assistant/consultant_scenario.md) | Сквозной сценарий работы агента-консультанта |
| [`10-general-assistant/document_templates_catalog.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/10-general-assistant/document_templates_catalog.md) | Каталог шаблонов документов для автогенерации |
| [`10-general-assistant/updated_tz_v2.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/10-general-assistant/updated_tz_v2.md) | Обновленное Техническое Задание: Универсальный агент Star Building (v2.0) |

## 11-updated-artifacts

| Файл | Назначение |
|---|---|
| [`11-updated-artifacts/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/11-updated-artifacts/README.md) | 11-updated-artifacts: Обновленные презентационные материалы |

## 12-mindmap-update

| Файл | Назначение |
|---|---|
| [`12-mindmap-update/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/12-mindmap-update/README.md) | 12-mindmap-update: Актуализированный граф сущностей и связей |
| [`12-mindmap-update/mindmap.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/12-mindmap-update/mindmap.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Интерактивная карта сущностей Star Building</title> <style> :root { --bg: #070a13; --panel-bg: #0f1 |

## 14-intake-tool

| Файл | Назначение |
|---|---|
| [`14-intake-tool/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/14-intake-tool/README.md) | 14-intake-tool: Инструмент приема и первичной обработки черновиков |
| [`14-intake-tool/intake_form.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/14-intake-tool/intake_form.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Форма подачи черновика регламента — Star Building</title> <link rel="preconnect" href="https://font |

## 15-bitrix24-integration

| Файл | Назначение |
|---|---|
| [`15-bitrix24-integration/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/15-bitrix24-integration/README.md) | 15-bitrix24-integration: Архитектура интеграции с Битрикс24 |

## 16-telegram-setup

| Файл | Назначение |
|---|---|
| [`16-telegram-setup/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/16-telegram-setup/README.md) | 16-telegram-setup: Настройка и регламент Telegram-группы |
| [`16-telegram-setup/telegram_bot_service.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/16-telegram-setup/telegram_bot_service.py) | Telegram-бот «Star Building — Регламенты и Стандарты» Поддержка 2 веток: 1. Заявки и черновики регламентов (Кодификатор) 2. Вопросы и консультации (Консультант с автогенерацией документов) |
| [`16-telegram-setup/topic_1_instructions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/16-telegram-setup/topic_1_instructions.md) | Инструкция для Ветки 1: «Заявки и черновики регламентов» |
| [`16-telegram-setup/topic_2_instructions.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/16-telegram-setup/topic_2_instructions.md) | Инструкция для Ветки 2: «Вопросы и консультации» |

## 17-two-bots-split

| Файл | Назначение |
|---|---|
| [`17-two-bots-split/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/17-two-bots-split/README.md) | 17-two-bots-split: Разделение на 2 независимых бота |
| [`17-two-bots-split/bot_1_codifier.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/17-two-bots-split/bot_1_codifier.py) | Бот 1: «Кодификатор регламентов Star Building» (Версия v2.1 с модулем Сверщика) Функционал: 1. Автоматическая сверка нового черновика со ВСЕМИ действующими регламентами (РЕГ-001..010). 2. Выявление противоречий, пересечений сроков и ролей.  |
| [`17-two-bots-split/bot_2_consultant.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/17-two-bots-split/bot_2_consultant.py) | Бот 2: «Корпоративный консультант Star Building» (Надежная версия v2.0) Улучшения: 1. Память диалога (помнит исходный вопрос, когда пользователь отвечает «Да, сделай шаблон»). 2. Таймауты сети Telegram 60 сек. 3. Поддержка голосовых, фото и |

## 18-bot-behavior-refinement

| Файл | Назначение |
|---|---|
| [`18-bot-behavior-refinement/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/18-bot-behavior-refinement/README.md) | 18-bot-behavior-refinement: Регламент выдачи шаблонов документов |

## 19-top-20-roadmap

| Файл | Назначение |
|---|---|
| [`19-top-20-roadmap/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/19-top-20-roadmap/README.md) | 19-top-20-roadmap: План разработки ТОП-20 приоритетных регламентов |
| [`19-top-20-roadmap/top_20_regulations.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/19-top-20-roadmap/top_20_regulations.md) | ТОП-20 приоритетных регламентирующих документов Star Building |

## 20-cross-check-engine

| Файл | Назначение |
|---|---|
| [`20-cross-check-engine/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/20-cross-check-engine/README.md) | 20-cross-check-engine: Автоматическая сверка и поиск противоречий |

## 21-cross-audit

| Файл | Назначение |
|---|---|
| [`21-cross-audit/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/21-cross-audit/README.md) | 21-cross-audit: Результаты сквозного перекрестного аудита базы знаний |
| [`21-cross-audit/audit_report.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/21-cross-audit/audit_report.md) | АУДИТОРСКИЙ ОТЧЕТ И ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ |

## 22-actual-master-package

| Файл | Назначение |
|---|---|
| [`22-actual-master-package/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/22-actual-master-package/README.md) | 22-actual-master-package: Актуальный пакет концепции, дорожной карты и карты связей |
| [`22-actual-master-package/concept.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/22-actual-master-package/concept.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Актуальная концепция агента Star Building</title> <link rel="preconnect" href="https://fonts.google |
| [`22-actual-master-package/interactive_graph.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/22-actual-master-package/interactive_graph.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Интерактивная карта сущностей Star Building</title> <style> :root { --bg: #070a13; --panel-bg: #0f1 |
| [`22-actual-master-package/mindmap.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/22-actual-master-package/mindmap.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Интерактивная карта сущностей Star Building</title> <style> :root { --bg: #070a13; --panel-bg: #0f1 |
| [`22-actual-master-package/roadmap.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/22-actual-master-package/roadmap.html) | <!DOCTYPE html> <html lang="ru"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Дорожная карта внедрения Star Building</title> <link rel="preconnect" href="https://fonts.googleapi |

## 23-code-names

| Файл | Назначение |
|---|---|
| [`23-code-names/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/23-code-names/README.md) | 23-code-names: Внутренние имена ботов |

## 24-marketing-bots

| Файл | Назначение |
|---|---|
| [`24-marketing-bots/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/24-marketing-bots/README.md) | 24-marketing-bots: Концепция семейства маркетинговых помощников |
| [`24-marketing-bots/content_bots_detailed.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/24-marketing-bots/content_bots_detailed.md) | 10 содержательных ботов для Star Building |
| [`24-marketing-bots/sources_ledger.json`](https://github.com/rkd-code/star-building-metodolog/blob/main/24-marketing-bots/sources_ledger.json) | { "version": 1, "sources": [ { "id": 1, "url": "https://developers.facebook.com/docs/instagram-platform/content-publishing", "title": "Instagram Platform — Content Publishing", "accessed": "2026-08-20" }, { "id": 2, "url": "https://develope |
| [`24-marketing-bots/top_20_marketing_bots.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/24-marketing-bots/top_20_marketing_bots.md) | СЕМЕЙСТВО МАРКЕТИНГОВЫХ БОТОВ STAR BUILDING |

## 25-marketing-bots-detailed

| Файл | Назначение |
|---|---|
| [`25-marketing-bots-detailed/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/25-marketing-bots-detailed/README.md) | 25-marketing-bots-detailed: Подробная таблица маркетинговых помощников |
| [`25-marketing-bots-detailed/build_workbook.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/25-marketing-bots-detailed/build_workbook.py) | Краткий обзор |
| [`25-marketing-bots-detailed/marketing_bots_star_building.xlsx`](https://github.com/rkd-code/star-building-metodolog/blob/main/25-marketing-bots-detailed/marketing_bots_star_building.xlsx) | Книга Excel с проектными данными. |
| [`25-marketing-bots-detailed/sources_ledger.json`](https://github.com/rkd-code/star-building-metodolog/blob/main/25-marketing-bots-detailed/sources_ledger.json) | { "version": 1, "sources": [ { "id": 1, "url": "https://github.com/kushalsamani/social-media-ai-agent", "title": "Social Media AI Agent", "accessed": "2026-08-21" }, { "id": 2, "url": "https://github.com/BayramAnnakov/synthetic-market-resea |

## 26-hermes-profiles

| Файл | Назначение |
|---|---|
| [`26-hermes-profiles/PROJECT_CONTEXT_TEMPLATE.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/PROJECT_CONTEXT_TEMPLATE.md) | Шаблон контекста проекта для обоих профилей |
| [`26-hermes-profiles/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/README.md) | 26-hermes-profiles: Два независимых профиля Hermes |
| [`26-hermes-profiles/TASK_CONTRACT.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/TASK_CONTRACT.md) | Договор передачи кодовой задачи |
| [`26-hermes-profiles/developer/SOUL.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/developer/SOUL.md) | Профиль Hermes: Разработчик |
| [`26-hermes-profiles/orchestrator/SOUL.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/orchestrator/SOUL.md) | Профиль Hermes: Общий оркестратор |
| [`26-hermes-profiles/register_project.sh`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/register_project.sh) | #!/usr/bin/env bash set -euo pipefail if [[ $# -lt 3 —— $# -gt 4 ]]; then echo "Использование: $0 <код-проекта> <название> <путь> [исходная-ветка]" >&2 exit 1 fi SLUG="$1" NAME="$2" REPO="$(realpath "$3")" BASE_BRANCH="${4:-}" command -v he |
| [`26-hermes-profiles/setup_profiles.sh`](https://github.com/rkd-code/star-building-metodolog/blob/main/26-hermes-profiles/setup_profiles.sh) | Graphify устанавливает навык в активный профиль. Новые профили клонируют его. |

## 27-developer-skills

| Файл | Назначение |
|---|---|
| [`27-developer-skills/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/27-developer-skills/README.md) | 27-developer-skills: Навыки профиля разработчика |

## 28-unified-project-graph

| Файл | Назначение |
|---|---|
| [`28-unified-project-graph/PROJECT_REGISTRY.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/28-unified-project-graph/PROJECT_REGISTRY.md) | Единый реестр проектов и направлений |
| [`28-unified-project-graph/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/28-unified-project-graph/README.md) | 28-unified-project-graph: Единый граф проектов и знаний |
| [`28-unified-project-graph/RELATIONSHIPS.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/28-unified-project-graph/RELATIONSHIPS.md) | Связи единого графа проектов и знаний |
| [`28-unified-project-graph/build_curated_graph.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/28-unified-project-graph/build_curated_graph.py) | Build deterministic project entities for the unified Graphify graph. |
| [`28-unified-project-graph/curated_graph_source.json`](https://github.com/rkd-code/star-building-metodolog/blob/main/28-unified-project-graph/curated_graph_source.json) | { "nodes": [ { "id": "p001", "label": "P-001 — Корпоративная система «Кодификатор» Star Building", "type": "Project", "description": "Стандартизировать регламенты, проверять противоречия и консультировать сотрудников.", "source_file": "28-u |
| [`28-unified-project-graph/test_build_curated_graph.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/28-unified-project-graph/test_build_curated_graph.py) | import importlib.util import json import unittest from pathlib import Path ROOT = Path(__file__).resolve().parent MODULE_PATH = ROOT / "build_curated_graph.py" def load_module(): spec = importlib.util.spec_from_file_location("build_curated_ |

## 29-employee-testing-service

| Файл | Назначение |
|---|---|
| [`29-employee-testing-service/DATA_MODEL.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/DATA_MODEL.md) | Модель данных сервиса «Экзаменатор Star Building» |
| [`29-employee-testing-service/IMPORT_RULES.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/IMPORT_RULES.md) | Правила загрузки банка вопросов |
| [`29-employee-testing-service/POOL_001_IMPORT_REPORT.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/POOL_001_IMPORT_REPORT.md) | Отчет импорта первого пула вопросов |
| [`29-employee-testing-service/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/README.md) | 29-employee-testing-service: «Экзаменатор Star Building» |
| [`29-employee-testing-service/build_question_bank.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/build_question_bank.py) | Создает проверяемый Excel-шаблон банка вопросов. |
| [`29-employee-testing-service/import_pool_001.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/import_pool_001.py) | Импортирует первый пул вопросов из DOCX в банк Excel. |
| [`29-employee-testing-service/question_bank_pool_001.xlsx`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/question_bank_pool_001.xlsx) | Книга Excel с проектными данными. |
| [`29-employee-testing-service/question_bank_template.xlsx`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/question_bank_template.xlsx) | Книга Excel с проектными данными. |
| [`29-employee-testing-service/source_pool_001.docx`](https://github.com/rkd-code/star-building-metodolog/blob/main/29-employee-testing-service/source_pool_001.docx) | Документ Word. |

## 30-employee-testing-html

| Файл | Назначение |
|---|---|
| [`30-employee-testing-html/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/30-employee-testing-html/README.md) | 30-employee-testing-html: автономная платформа |
| [`30-employee-testing-html/build_platform.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/30-employee-testing-html/build_platform.py) | Собирает автономную HTML-платформу из Excel-банка. |
| [`30-employee-testing-html/index.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/30-employee-testing-html/index.html) | <!doctype html> <html lang="ru"> <head> <meta charset="utf-8"> <meta name="viewport" content="width=device-width,initial-scale=1"> <meta name="color-scheme" content="light"> <title>Экзаменатор Star Building</title> <style> :root{--ink:#1323 |
| [`30-employee-testing-html/test_browser.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/30-employee-testing-html/test_browser.py) | from pathlib import Path from playwright.sync_api import sync_playwright ROOT = Path(__file__).resolve().parent URL = (ROOT / "index.html").as_uri() with sync_playwright() as p: browser = p.chromium.launch(headless=True) page = browser.new_ |
| [`30-employee-testing-html/test_build_platform.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/30-employee-testing-html/test_build_platform.py) | import importlib.util import json import re import unittest from pathlib import Path ROOT = Path(__file__).resolve().parent MODULE_PATH = ROOT / "build_platform.py" BANK_PATH = ROOT.parent / "29-employee-testing-service" / "question_bank_po |

## 32-chat-history-archive

| Файл | Назначение |
|---|---|
| [`32-chat-history-archive/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/32-chat-history-archive/README.md) | Архив переписки Hermes |
| [`32-chat-history-archive/export_chat_history.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/32-chat-history-archive/export_chat_history.py) | Ежедневно выгружает переписку Hermes по профилям. |
| [`32-chat-history-archive/test_export_chat_history.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/32-chat-history-archive/test_export_chat_history.py) | import importlib.util import sqlite3 import tempfile import unittest from datetime import date from pathlib import Path MODULE_PATH = Path(__file__).with_name("export_chat_history.py") def load_module(): spec = importlib.util.spec_from_file |

## 33-vm-file-knowledge-graph

| Файл | Назначение |
|---|---|
| [`33-vm-file-knowledge-graph/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/33-vm-file-knowledge-graph/README.md) | 33 — Реестр файлов и граф знаний виртуальной машины |
| [`33-vm-file-knowledge-graph/build_inventory.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/33-vm-file-knowledge-graph/build_inventory.py) | Строит безопасный реестр рабочих файлов и граф их проектной принадлежности. |
| [`33-vm-file-knowledge-graph/test_build_inventory.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/33-vm-file-knowledge-graph/test_build_inventory.py) | import importlib.util import json import tempfile import unittest from pathlib import Path from openpyxl import load_workbook MODULE_PATH = Path(__file__).with_name("build_inventory.py") def load_module(): spec = importlib.util.spec_from_fi |

## 34-agent-repository-documentation

| Файл | Назначение |
|---|---|
| [`34-agent-repository-documentation/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/34-agent-repository-documentation/README.md) | 34 — Обязательная документация для всех агентов и репозиториев |
| [`34-agent-repository-documentation/ensure_repo_docs.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/34-agent-repository-documentation/ensure_repo_docs.py) | Создает и проверяет обязательную документацию любого Git-репозитория. |
| [`34-agent-repository-documentation/test_ensure_repo_docs.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/34-agent-repository-documentation/test_ensure_repo_docs.py) | import importlib.util import json import subprocess import tempfile import unittest from pathlib import Path MODULE_PATH = Path(__file__).with_name("ensure_repo_docs.py") def load_module(): spec = importlib.util.spec_from_file_location("ens |

## graphify-out

| Файл | Назначение |
|---|---|
| [`graphify-out/GRAPH_REPORT.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/graphify-out/GRAPH_REPORT.md) | Graph Report - roman (2026-08-29) |
| [`graphify-out/graph.html`](https://github.com/rkd-code/star-building-metodolog/blob/main/graphify-out/graph.html) | <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <title>graphify - graphify-out/graph.html</title> <script> /** * vis-network * https://visjs.github.io/vis-network/ * * A dynamic, browser-based visualization library. * * @vers |
| [`graphify-out/graph.json`](https://github.com/rkd-code/star-building-metodolog/blob/main/graphify-out/graph.json) | { "directed": false, "multigraph": false, "graph": { "hyperedges": [ { "id": "home_roman::home_roman::home_roman::home_roman::home_roman::marketing_automation_flow", "label": "Marketing Automation Flow", "nodes": [ "home_roman::home_roman:: |

## knowledge_base

| Файл | Назначение |
|---|---|
| [`knowledge_base/00_РЕЕСТР/reestr-reglamentov.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/00_%D0%A0%D0%95%D0%95%D0%A1%D0%A2%D0%A0/reestr-reglamentov.md) | РЕЕСТР РЕГЛАМЕНТОВ И МАТРИЦА ВЛАДЕНИЯ ПРОЦЕССАМИ |
| [`knowledge_base/00_РЕЕСТР/reestr-reglamentov.xlsx`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/00_%D0%A0%D0%95%D0%95%D0%A1%D0%A2%D0%A0/reestr-reglamentov.xlsx) | Книга Excel с проектными данными. |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-001_kodeks.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-001_kodeks.md) | --- СТРАНИЦА 1 --- СОДЕРЖАНИЕ /01 Общие положения 1 КОДЕКС группы компаний STAR BUILDING Караганда, 2024 --- СТРАНИЦА 2 --- /01 ОБЩИЕ ПОЛОЖЕНИЯ. . . . . . . . . . . . . . . . . . . . . . . . . . . . . 1 Введение . . . . . . . . . . . . . .  |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-002_orgstruktura.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-002_orgstruktura.md) | ЛИСТ: 01_Общая оргструктура |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-003_strategicheskaya_osnova.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-003_strategicheskaya_osnova.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ Дата выпуска: 25 марта 2025 года Дата последнего обновления: 12.06.2026 года В папку штатного сотрудника СТРАТЕГИЧЕСКАЯ ОСНОВА КОМПАНИИ Каждый сотрудник должен хорошо понимать, куда мы идем, какие |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-004_kak_napisat_reglament.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-004_kak_napisat_reglament.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ ОТ 26 ЯНВАРЯ 2026 Г. В папку всех руководителей КАК ПРАВИЛЬНО НАПИСАТЬ РЕГЛАМЕНТ В процессе работы, когда вы сталкиваетесь с разного рода неоптимальностями (в частности, во время проведения опросо |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-005_vidy_reglamentov.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-005_vidy_reglamentov.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ от 26 января 2026 года В папку штатного сотрудника В папки всех руководителей В папку ответственного за должностные папки ВИДЫ РЕГЛАМЕНТОВ И ИХ РОЛЬ В КОМПАНИИ Содержание: Преамбула Термины, опред |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-006_dogovornaya_rabota.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-006_dogovornaya_rabota.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ Дата выпуска: 22 июня 2026 года В папку сотрудника отдела продаж В папку ответственного за должностные папки ПРАВИЛА ВЕДЕНИЯ ДОГОВОРНОЙ РАБОТЫ Содержание Область применения 1.1 Настоящие Правила о |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-007_kadrovoe_deloproizvodstvo.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-007_kadrovoe_deloproizvodstvo.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ ОТ 16 МАРТА 2026 ГОДА В папки всех руководителей В папку штатного сотрудника В папку сотрудников отдела найма и адаптации персонала КАДРОВОЕ ДЕЛОПРОИЗВОДСТВО В целях упорядочения кадровых процедур |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-008_sistema_motivacii.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-008_sistema_motivacii.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО ПО УПРАВЛЕНИЮ КОМПАНИЕЙ ОТ ЯНВАРЯ 2026 ГОДА В папку штатного сотрудника ЕДИНАЯ СИСТЕМА МОТИВАЦИИ, ПООЩРЕНИЯ И ВЫСЛУГИ ЛЕТ Введение (Предпосылки и цели) В процессе работы мы столкнулись с тем, что правила начисления пр |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-009_toplivnye_karty.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-009_toplivnye_karty.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО ИСПОЛЬЗОВАНИЮ ТОПЛИВНОЙ КАРТЫ ОТ 30 МАРТА 2026 ГОДА В папку штатного сотрудника В папки всех руководителей В папку ответственного за должностные папки РЕГЛАМЕНТ ИСПОЛЬЗОВАНИЯ ТОПЛИВНЫХ КАРТ Обоснование необходимости р |
| [`knowledge_base/01_В_РАБОТЕ/full_REG-010_klientoorientirovannost.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%92_%D0%A0%D0%90%D0%91%D0%9E%D0%A2%D0%95/full_REG-010_klientoorientirovannost.md) | РЕГЛАМЕНТ: Стандарт клиентоориентированности и управления клиентским опытом |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-001_kodeks.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-001_kodeks.md) | КАРТОЧКА: РЕГ-001 Кодекс группы компаний Star Building |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-002_orgstruktura.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-002_orgstruktura.md) | КАРТОЧКА: РЕГ-002 Общая оргструктура и штатная модель компании |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-003_strategicheskaya_osnova.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-003_strategicheskaya_osnova.md) | КАРТОЧКА: РЕГ-003 Стратегическая основа компании |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-004_kak_napisat_reglament.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-004_kak_napisat_reglament.md) | КАРТОЧКА: РЕГ-004 Регламент «Как написать регламент» |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-005_vidy_reglamentov.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-005_vidy_reglamentov.md) | КАРТОЧКА: РЕГ-005 Виды регламентов и их роль в компании |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-006_dogovornaya_rabota.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-006_dogovornaya_rabota.md) | КАРТОЧКА: РЕГ-006 Правила ведения договорной работы |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-007_kadrovoe_deloproizvodstvo.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-007_kadrovoe_deloproizvodstvo.md) | КАРТОЧКА: РЕГ-007 Кадровое делопроизводство |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-008_sistema_motivacii.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-008_sistema_motivacii.md) | КАРТОЧКА: РЕГ-008 Единая система мотивации, поощрения и выслуги лет |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-009_toplivnye_karty.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-009_toplivnye_karty.md) | КАРТОЧКА: РЕГ-009 Порядок выдачи и использования топливных карт |
| [`knowledge_base/01_КАРТОЧКИ/card_REG-010_klientoorientirovannost.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/01_%D0%9A%D0%90%D0%A0%D0%A2%D0%9E%D0%A7%D0%9A%D0%98/card_REG-010_klientoorientirovannost.md) | КАРТОЧКА: РЕГ-010 Стандарт клиентоориентированности и клиентского опыта |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-001_kodeks.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-001_kodeks.md) | --- СТРАНИЦА 1 --- СОДЕРЖАНИЕ /01 Общие положения 1 КОДЕКС группы компаний STAR BUILDING Караганда, 2024 --- СТРАНИЦА 2 --- /01 ОБЩИЕ ПОЛОЖЕНИЯ. . . . . . . . . . . . . . . . . . . . . . . . . . . . . 1 Введение . . . . . . . . . . . . . .  |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-002_orgstruktura.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-002_orgstruktura.md) | ЛИСТ: 01_Общая оргструктура |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-003_strategicheskaya_osnova.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-003_strategicheskaya_osnova.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ Дата выпуска: 25 марта 2025 года Дата последнего обновления: 12.06.2026 года В папку штатного сотрудника СТРАТЕГИЧЕСКАЯ ОСНОВА КОМПАНИИ Каждый сотрудник должен хорошо понимать, куда мы идем, какие |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-004_kak_napisat_reglament.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-004_kak_napisat_reglament.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ ОТ 26 ЯНВАРЯ 2026 Г. В папку всех руководителей КАК ПРАВИЛЬНО НАПИСАТЬ РЕГЛАМЕНТ В процессе работы, когда вы сталкиваетесь с разного рода неоптимальностями (в частности, во время проведения опросо |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-005_vidy_reglamentov.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-005_vidy_reglamentov.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ от 26 января 2026 года В папку штатного сотрудника В папки всех руководителей В папку ответственного за должностные папки ВИДЫ РЕГЛАМЕНТОВ И ИХ РОЛЬ В КОМПАНИИ Содержание: Преамбула Термины, опред |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-006_dogovornaya_rabota.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-006_dogovornaya_rabota.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ Дата выпуска: 22 июня 2026 года В папку сотрудника отдела продаж В папку ответственного за должностные папки ПРАВИЛА ВЕДЕНИЯ ДОГОВОРНОЙ РАБОТЫ Содержание Область применения 1.1 Настоящие Правила о |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-007_kadrovoe_deloproizvodstvo.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-007_kadrovoe_deloproizvodstvo.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО УПРАВЛЕНИЮ КОМПАНИЕЙ ОТ 16 МАРТА 2026 ГОДА В папки всех руководителей В папку штатного сотрудника В папку сотрудников отдела найма и адаптации персонала КАДРОВОЕ ДЕЛОПРОИЗВОДСТВО В целях упорядочения кадровых процедур |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-008_sistema_motivacii.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-008_sistema_motivacii.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО ПО УПРАВЛЕНИЮ КОМПАНИЕЙ ОТ ЯНВАРЯ 2026 ГОДА В папку штатного сотрудника ЕДИНАЯ СИСТЕМА МОТИВАЦИИ, ПООЩРЕНИЯ И ВЫСЛУГИ ЛЕТ Введение (Предпосылки и цели) В процессе работы мы столкнулись с тем, что правила начисления пр |
| [`knowledge_base/02_УТВЕРЖДЕНО/full_REG-009_toplivnye_karty.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/02_%D0%A3%D0%A2%D0%92%D0%95%D0%A0%D0%96%D0%94%D0%95%D0%9D%D0%9E/full_REG-009_toplivnye_karty.md) | РЕГЛАМЕНТ ВЛАДЕЛЬЦА ПО ИСПОЛЬЗОВАНИЮ ТОПЛИВНОЙ КАРТЫ ОТ 30 МАРТА 2026 ГОДА В папку штатного сотрудника В папки всех руководителей В папку ответственного за должностные папки РЕГЛАМЕНТ ИСПОЛЬЗОВАНИЯ ТОПЛИВНЫХ КАРТ Обоснование необходимости р |
| [`knowledge_base/03_ПРИЕМ_ЧЕРНОВИКОВ/README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/knowledge_base/03_%D0%9F%D0%A0%D0%98%D0%95%D0%9C_%D0%A7%D0%95%D0%A0%D0%9D%D0%9E%D0%92%D0%98%D0%9A%D0%9E%D0%92/README.md) | 03_ПРИЕМ_ЧЕРНОВИКОВ: Входной накопитель черновиков |

## tools

| Файл | Назначение |
|---|---|
| [`tools/ensure_repo_docs.py`](https://github.com/rkd-code/star-building-metodolog/blob/main/tools/ensure_repo_docs.py) | Создает и проверяет обязательную документацию любого Git-репозитория. |

## Корень репозитория

| Файл | Назначение |
|---|---|
| [`.gitignore`](https://github.com/rkd-code/star-building-metodolog/blob/main/.gitignore) | Файл проекта: .gitignore. |
| [`.hermes.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/.hermes.md) | Контекст Hermes |
| [`AGENTS.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/AGENTS.md) | AGENTS.md: Спецификация агентов и правила поведения AI |
| [`CHANGELOG.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/CHANGELOG.md) | История изменений |
| [`DATA_MODEL.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/DATA_MODEL.md) | Модель данных проекта |
| [`DECISIONS.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/DECISIONS.md) | DECISIONS.md: Журнал архитектурных решений (ADR) и допущений |
| [`DOCS_INDEX.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/DOCS_INDEX.md) | Единая точка входа во всю документацию проекта. |
| [`DOCUMENTATION_STANDARD.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/DOCUMENTATION_STANDARD.md) | Обязательный стандарт документации репозитория |
| [`KNOWLEDGE_BASE.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/KNOWLEDGE_BASE.md) | KNOWLEDGE_BASE.md: Структура и реестр базы знаний Star Building |
| [`PROJECT_CONTEXT.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/PROJECT_CONTEXT.md) | Краткий обязательный контекст для начала работы агента. |
| [`PROJECT_MANIFEST.json`](https://github.com/rkd-code/star-building-metodolog/blob/main/PROJECT_MANIFEST.json) | Машиночитаемая структура репозитория и ссылки GitHub. |
| [`PROJECT_MAP.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/PROJECT_MAP.md) | PROJECT_MAP.md: Архитектурная карта проекта |
| [`PROJECT_STRUCTURE.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/PROJECT_STRUCTURE.md) | Автоматический указатель структуры и назначения файлов. |
| [`README.md`](https://github.com/rkd-code/star-building-metodolog/blob/main/README.md) | Агент «Кодификатор» (Codifier Agent v1.0 MVP) |
