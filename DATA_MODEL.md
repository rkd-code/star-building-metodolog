# Модель данных проекта

## Канонические спецификации

Подробные схемы Кодификатора находятся в [`03-data-model/`](03-data-model/README.md):

- [`regulation.schema.json`](03-data-model/regulation.schema.json) — структура регламента;
- [`raci.schema.json`](03-data-model/raci.schema.json) — матрица ответственности;
- [`versioning.schema.json`](03-data-model/versioning.schema.json) — версии документов;
- [`relationship.schema.json`](03-data-model/relationship.schema.json) — связи документов.

Модель сервиса «Кворум» описана в [`29-employee-testing-service/DATA_MODEL.md`](29-employee-testing-service/DATA_MODEL.md).

## Модель данных компонента 37-strategy-bot (Драмкнот / P-026)

### 1. Журнал решений владельца (`decisions.json`)
Изолированное долговременное хранение подтверждённых управленческих решений руководителя в рамках проекта P-026.

| Поле | Тип | Назначение |
|---|---|---|
| `id` | `str` | Уникальный идентификатор решения вида `dec_{номер}_{timestamp_микросекунды}` |
| `timestamp` | `str` | Время фиксации в стандарте ISO-8601 UTC |
| `author` | `str` | ФИО или имя автора решения |
| `user_id` | `int \| null` | Числовой Telegram ID пользователя (actor isolation) |
| `chat_id` | `int \| null` | Числовой Telegram ID чата (chat isolation) |
| `question_context` | `str` | Конкретный предметный контекст вопроса (лимиты, маржа, нормативы) |
| `exact_text` | `str` | Точная формулировка решения руководителя |
| `status` | `str` | Статус решения (`active`, `superseded`, `archived`) |

Надёжность и транзакционность:
- Межпроцессная сериализация через `fcntl.flock(LOCK_EX)`;
- Атомарная запись через временный файл с `fsync` файла и родительского каталога;
- Строгий режим fail-closed: при повреждении синтаксиса JSON создаётся карантинная копия `decisions_corrupted_{timestamp}.json.bak`, операция прерывается исключением `JournalCorruptionError` без немой перезаписи.

### 2. Версионные черновики документов (`drafts/`)
Генерация и выдача рабочих версий документов коммерческого департамента с наложением актуальных решений руководителя без изменения оригиналов.

| Поле метаданных | Тип | Назначение |
|---|---|---|
| `doc_name` | `str` | Нормализованное безопасное имя документа |
| `version` | `int` | Монотонно возрастающий номер версии |
| `filename` | `str` | Имя файла вида `{safe_doc_name}_v{version}_{timestamp}_{unique}.md` |
| `path` | `Path` | Абсолютный путь в изолированном каталоге |
| `bytes` | `int` | Размер файла в байтах |
| `user_id` | `int \| null` | Идентификатор владельца черновика |
| `chat_id` | `int \| null` | Идентификатор чата создания |

Заголовок артефакта (Frontmatter):
`<!-- DRAFT ARTIFACT: {safe_name} | VERSION: v{version} | AUTHOR: {author} | USER_ID: {user_id} | CHAT_ID: {chat_id} | CREATED: {timestamp} -->`

### 3. Неизменяемый манифест предметных источников P-026
Жестко зафиксированный перечень из 30 канонических файлов нормативной базы P-026 (из передачи 108) с эталонными хэшами SHA-256, статусами и размерами.

| Роль / Документ | Версия | Итерация | Путь источника | Эталонный SHA-256 |
|---|---|---|---|---|
| Коммерческий директор (КД) | `v0.6` | 107 | `/home/roman/107-commercial-role-functions-cd-limits-04/01_COMMERCIAL_DIRECTOR_FUNCTIONAL_V0.6.md` | `cf7f3fb1098205a74a073a1b73ccb0ec6e2e09b60d1dd9ad3502ad2a582ec125` |
| Руководитель отдела продаж (РОП) | `v0.3` | 109 | `/home/roman/109-commercial-role-functions-rop-answers-02/02_HEAD_OF_SALES_FUNCTIONAL_V0.3.md` | `5f6e8f1ef70252992fdbc9f79f1dbd4d7bed995ee6e672da480a0cdfc0451667` |
| Старший менеджер по продажам | `v0.1` | 100 | `/home/roman/100-commercial-role-functions-senior-sales-01/03_SENIOR_SALES_FUNCTIONAL_V0.1.md` | `82b267726692cc6d57aaa68aa04a612828c5f592cfc79ff8f0613d657ba91966` |
| Менеджер по продажам (МОП) | `v0.1` | 101 | `/home/roman/101-commercial-role-functions-sales-01/04_SALES_MANAGER_FUNCTIONAL_V0.1.md` | `178f0d2a9956df116334f9b4735d56bb34059f381e7a841e7df15536c2ddcc96` |
| Лидоруб | `v0.1` | 106 | `/home/roman/106-commercial-role-functions-leadrub-01/05_LEAD_QUALIFIER_FUNCTIONAL_V0.1.md` | `24446f80a5b4ac870e82e79e26f101a11f6cc1cc49236ad783863f7a8e7b0d00` |
| Оргструктура КД | `v0.1` | 102 | `/home/roman/102-commercial-department-org-regulation-01/REG_COMMERCIAL_ORG_V0.1.md` | `737861acea65400fb3f8f175eab909cf5e880705ad72d7a71bb44f0159c17560` |

Правило валидации: чтение источников выполняется в режиме fail-closed; при отсутствии файла, наличии символических ссылок или расхождении хэша операция экспорта прерывается с ошибкой целостности, генерация фиктивных шаблонов запрещена.

### 4. Границы изоляции среды исполнения и акторов
- Хранилище runtime state изолировано по пути `DRAMKNOTE_P026_STORAGE_DIR` или systemd `STATE_DIRECTORY` (`~/.local/share/star-building/dramknote-p026`).
- Черновики и решения пользователя/чата А недоступны пользователю/чату Б.
- Команды выгрузки черновиков и фиксации решений заблокированы в групповых чатах.

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
