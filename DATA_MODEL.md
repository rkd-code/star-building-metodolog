# Модель данных проекта

## Канонические спецификации

Подробные схемы Кодификатора находятся в [`03-data-model/`](03-data-model/README.md):

- [`regulation.schema.json`](03-data-model/regulation.schema.json) — структура регламента;
- [`raci.schema.json`](03-data-model/raci.schema.json) — матрица ответственности;
- [`versioning.schema.json`](03-data-model/versioning.schema.json) — версии документов;
- [`relationship.schema.json`](03-data-model/relationship.schema.json) — связи документов.

Модель сервиса «Кворум» описана в [`29-employee-testing-service/DATA_MODEL.md`](29-employee-testing-service/DATA_MODEL.md).

## Модель контекста репозитория

`PROJECT_MANIFEST.json` содержит:

| Поле | Назначение |
|---|---|
| `schema_version` | Версия формата манифеста |
| `project` | Название проекта |
| `repository` | Основная ссылка GitHub |
| `github_slug` | Владелец и имя репозитория |
| `default_branch` | Ветка ссылок |
| `source_tree_hash` | Отпечаток всех версионируемых исходных файлов, кроме генерируемой документации |
| `documentation_files` | Обязательные документы |
| `files` | Полный список версионируемых файлов |

Каждая запись `files` содержит `path`, `name`, `area`, `description` и `github_url`.

## Правило синхронизации

Любое изменение сущностей, полей, связей или форматов должно одновременно обновлять этот файл и соответствующую профильную спецификацию. Генерируемый манифест пересобирается предкоммитным обработчиком.
