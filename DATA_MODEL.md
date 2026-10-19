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
| `timestamp` | `str` | Время фиксации в стандарте ISO-8601 UTC (микросекундная точность `int(timestamp * 1_000_000)`) |
| `author` | `str` | ФИО или имя автора решения |
| `user_id` | `int \| null` | Числовой Telegram ID пользователя (actor isolation) |
| `chat_id` | `int \| null` | Числовой Telegram ID чата (chat isolation) |
| `question_context` | `str` | Конкретный предметный контекст вопроса (лимиты, маржа, нормативы) |
| `exact_text` | `str` | Точная формулировка решения руководителя |
| `status` | `str` | Статус решения (`active`, `superseded`, `archived`) |

Надёжность и транзакционность:
- Межпроцессная сериализация через `fcntl.flock(LOCK_EX)`;
- Атомарная запись через временный файл с `fsync` файла и родительского каталога;
- Каноническая схема и валидация: единый валидатор `validate_decision_record` на чтение и запись (`id`, `timestamp`, `author`, `user_id`, `chat_id`, `question_context`, `exact_text`, `status`); конфликтующие canonical/legacy алиасы отклоняются fail-closed; недопустимый `status` (например `INVALID`) отклоняется ДО записи на диск, предотвращая отравление журнала;
- Строгая типизация actor/chat: тип `bool` категорически исключён из допустимых `user_id`/`chat_id` (`validate_ownership_id`); значения `True`/`False` в журнале признаются повреждением; поддерживаются отрицательные chat ID Telegram;
- Строгая валидация формата: поле `timestamp` валидируется на полный формат ISO-8601 с датой, временем и явным часовым поясом (`validate_iso8601_timestamp`, date-only строки и naive timestamps отклоняются);
- Строгий режим fail-closed: при пустом файле (0 байт), синтаксическом или структурном повреждении JSON (невалидный timestamp, дубликаты ID, отсутствие обязательных полей, boolean ownership) создаётся карантинная копия `decisions_corrupted_{timestamp}.json.bak`, операция прерывается исключением `JournalCorruptionError` без немой перезаписи или потери данных.

### 1.1. Модель двухшагового подтверждения решений (`Pending Proposal`)
Изолированное отслеживание ожидающего подтверждения предложения руководителя перед фиксацией в журнале решений:
- Ключ изоляции: `(user_id, chat_id)`;
- Поля: `proposal_id` (уникальный ID предложения), `question_id`, `proposal_text` (точный формулируемый текст нормы), `question_context` (предметный контекст), `user_id`, `chat_id`, `created_at`;
- Поведение: подтверждение требует недвусмысленного безусловного ввода (`is_unambiguous_confirmation`) и привязки к `proposal_id`; пустые строки, точки (`...`), явный отказ («Не согласен») и условные фразы («Подтверждаю, но после уточнений») отклоняются;
- Защита от повторов и чужих ID: подтверждённый `proposal_id` заносится в `_used_proposal_ids` (повторное подтверждение запрещено); чужой ID отклоняется;
- Сохранность pending: предложение сбрасывается из pending ТОЛЬКО после успешной durable записи на диск в хранилище. При сбое хранилища предложение сохраняется.

### 2. Версионные черновики документов (`drafts/`)
Генерация и выдача рабочих версий документов коммерческого департамента с наложением актуальных решений руководителя без изменения оригиналов.

| Поле метаданных | Тип | Назначение |
|---|---|---|
| `doc_name` | `str` | Нормализованное безопасное имя документа |
| `version` | `int` | Монотонно возрастающий номер версии |
| `filename` | `str` | Имя файла вида `{safe_doc_name}_v{version}_{timestamp}_{unique}.md` |
| `path` | `Path` | Абсолютный путь в изолированном каталоге |
| `bytes` | `int` | Размер файла в байтах |
| `user_id` | `int \| null` | Идентификатор владельца черновика (строгая изоляция, unowned — fail-closed) |
| `chat_id` | `int \| null` | Идентификатор чата создания (поддерживаются отрицательные ID групп/супергрупп Telegram) |

Заголовок артефакта (Frontmatter):
`<!-- DRAFT ARTIFACT: {safe_name} | VERSION: v{version} | AUTHOR: {author} | USER_ID: {user_id} | CHAT_ID: {chat_id} | CREATED: {timestamp} -->`

### 3. Неизменяемый манифест предметных источников P-026 (база P026v1)
Жестко зафиксированный перечень из 40 канонических файлов нормативной базы P-026 (30 базовых источников + 10 источников дельты P026v1) с эталонными хэшами SHA-256, статусами и размерами.

| Роль / Документ | Версия | Итерация | Путь источника | Эталонный SHA-256 |
|---|---|---|---|---|
| Коммерческий директор (КД) | `v0.6` | 107 | `/home/roman/107-commercial-role-functions-cd-limits-04/01_COMMERCIAL_DIRECTOR_FUNCTIONAL_V0.6.md` | `cf7f3fb1098205a74a073a1b73ccb0ec6e2e09b60d1dd9ad3502ad2a582ec125` |
| Руководитель отдела продаж (РОП) | `v0.3` | 109 | `/home/roman/109-commercial-role-functions-rop-answers-02/02_HEAD_OF_SALES_FUNCTIONAL_V0.3.md` | `5f6e8f1ef70252992fdbc9f79f1dbd4d7bed995ee6e672da480a0cdfc0451667` |
| Старший менеджер по продажам | `v0.1` | 100 | `/home/roman/100-commercial-role-functions-senior-sales-01/03_SENIOR_SALES_FUNCTIONAL_V0.1.md` | `82b267726692cc6d57aaa68aa04a612828c5f592cfc79ff8f0613d657ba91966` |
| Менеджер по продажам (МОП) | `v0.1` | 101 | `/home/roman/101-commercial-role-functions-sales-01/04_SALES_MANAGER_FUNCTIONAL_V0.1.md` | `178f0d2a9956df116334f9b4735d56bb34059f381e7a841e7df15536c2ddcc96` |
| Лидоруб | `v0.1` | 106 | `/home/roman/106-commercial-role-functions-leadrub-01/05_LEAD_QUALIFIER_FUNCTIONAL_V0.1.md` | `24446f80a5b4ac870e82e79e26f101a11f6cc1cc49236ad783863f7a8e7b0d00` |
|| Оргструктура КД | `v0.1` | 102 | `/home/roman/102-commercial-department-org-regulation-01/REG_COMMERCIAL_ORG_V0.1.md` | `737861acea65400fb3f8f175eab909cf5e880705ad72d7a71bb44f0159c17560` |
||| Дельта P026v1: Стратегия | `раб.` | 35 | `35-commercial-marketing-strategy/STRATEGY.md` | `6317b14a596d286b15def6cafef26d84797fc7a784d709c3b04554b1dd72d6a1` |
||| Дельта P026v1: 110 Вопросы | `раб.` | 110 | `110-commercial-interviews-01/questions.json` | `4e4e162ec9034cdce7037ccc9213555ec7446f9ad73d231138b2674fef8011c1` |
||| Дельта P026v1: 111 Стандарт | `раб.` | 111 | `111-competitor-card-design-01/CARD_STANDARD_V0.1.md` | `beaa0c583212acaddad0218677d08fcaa9c5569cd33071bd42c76f93474b91b9` |
||| Дельта P026v1: 114 А-Профиль XLSX | `appr.` | 114 | `114-a-profile-executive-card-02/approved/A_Profile_Card_Leadership_v02.xlsx` | `9150ff7d01f7d2e67b1917301606dad9c1b978580afc4a77ea5aac01f6a4a564` |
||| Дельта P026v1: 114 А-Профиль PDF | `appr.` | 114 | `114-a-profile-executive-card-02/approved/A_Profile_Card_Leadership_v02.pdf` | `4f31d0fdfbce4677a52581ea18766476aacf4fcc19ed959822e9435ed804913f` |
||| Дельта P026v1: 115 Чек-лист XLSX | `раб.` | 115 | `115-competitor-presentation-checklist-01/CHECKLIST_StarBuilding_Competitors_Presentation_v01.xlsx` | `8703912cc60c01ed8eb45224a354b0ad456f0010b8df59fcea66623c3402897c` |
||| Дельта P026v1: 115 Запросы JSON | `раб.` | 115 | `115-competitor-presentation-checklist-01/CHECKLIST_ITEMS.json` | `ab5ac9f5d0170b3dd809304ad3604d0e528c702503ed1704a9b78a6d465fba24` |
|| Дельта P026v1: Акты и приёмки | `appr.` | 110/114/115 | `110/...`, `114/...`, `115/...` (ONLINE/FINAL_ACCEPTANCE.md) | Проверены по MANIFEST.json |

Правило валидации: чтение источников выполняется в режиме fail-closed; при отсутствии файла, наличии символических ссылок или расхождении хэша операции экспорта черновика, генерации контекста модели и команды `/project` прерываются с отказом целостности (`SubjectBaseIntegrityError`), генерация фиктивных шаблонов запрещена.

### 3.1. Манифест покрытия бинарных источников P026v1 (Coverage Manifest v1.0, `p026_coverage_manifest.json`)
Архитектурный инвариант Integrity связывает хэш исходных байтов с проверяемой содержательной полнотой фрагментов:
- **Инвариант:** hash/size исходного файла + поддерживаемый extraction + проверяемая содержательная полнота фрагментов.
- **Служебные заголовки:** строки `--- Лист: ... ---` и `--- Страница N ---` исключены из расчёта содержательного наполнения.
- **Отказ fail-closed:** при пустом содержании ячеек/страниц, несовпадении числа листов/страниц, перестановке или несовпадении хэша фрагмента выбрасывается `SubjectBaseIntegrityError` строго ДО вызова SDK (`0` SDK calls) и ДО мутации истории (`0` history writes).

| Источник | Формат | Число фрагментов | Политика допустимости пустых | Хэш исходного файла |
|---|---|---|---|---|
| `114-a-profile-executive-card-02/approved/A_Profile_Card_Leadership_v02.xlsx` (`SRC-35`) | XLSX | 7 листов | Запрещены (`allowed_empty: false`) | `9150ff7d01f7d2e67b1917301606dad9c1b978580afc4a77ea5aac01f6a4a564` |
| `114-a-profile-executive-card-02/approved/A_Profile_Card_Leadership_v02.pdf` (`SRC-36`) | PDF | 10 страниц | Запрещены (`allowed_empty: false`) | `4f31d0fdfbce4677a52581ea18766476aacf4fcc19ed959822e9435ed804913f` |
| `115-competitor-presentation-checklist-01/CHECKLIST_StarBuilding_Competitors_Presentation_v01.xlsx` (`SRC-38`) | XLSX | 6 листов | Запрещены (`allowed_empty: false`) | `8703912cc60c01ed8eb45224a354b0ad456f0010b8df59fcea66623c3402897c` |

Каждый фрагмент фиксирует `index`, `name`, `allowed_empty`, минимальный размер значащего содержимого и эталонный SHA-256 содержательного текста фрагмента. Дисковый артефакт `p026_coverage_manifest.json` и in-memory манифест валидируются взаимно методом `verify_coverage_manifest()`.

### 4. Границы изоляции среды исполнения и акторов
- Хранилище runtime state изолировано по пути `DRAMKNOTE_P026_STORAGE_DIR` или systemd `STATE_DIRECTORY` (`~/.local/share/star-building/dramknote-p026`).
- Черновики и решения пользователя/чата А недоступны пользователю/чату Б (actor & chat isolation); черновики без подтверждённого владельца имеют статус fail-closed.
- Все точки входа (команды выгрузки черновиков, фиксации решений, очистки истории, а также обычные диалоговые сообщения) заблокированы в групповых чатах (контур @Dramknote_bot доступен строго в личном диалоге).
- Полная защита от symlink-атак на всех уровнях предков до корня файловой системы и безопасное открытие lock-файлов с `O_NOFOLLOW`.
- Изоляция тестов: все тесты запускаются с временными директориями без загрязнения `$HOME/.local/share`.

### 5. Модель доверенной регистрации и версионного обмена знаниями (FN-015)

#### 5.1. Пакет разработки в `outbox/`
Изолированный пакет артефакта, создаваемый Драмкнотом в собственной директории `outbox/{package_id}/`:
- `manifest.json` — метаданные пакета;
- `{payload_filename}` — неизменяемый файл полезной нагрузки (`.md`, `.docx`, `.json`).

| Поле манифеста | Тип | Назначение |
|---|---|---|
| `id` | `str` | Безопасный идентификатор пакета (без path traversal) |
| `project` | `str` | Код проекта (по умолчанию `P-026`) |
| `author` | `str` | Автор разработки |
| `user_id` | `int \| null` | Числовой ID владельца (Telegram actor) |
| `chat_id` | `int \| null` | Числовой ID чата (Telegram chat) |
| `timestamp` | `str` | Время создания в строгом ISO-8601 UTC |
| `material_type` | `str` | Тип материала (`decision`, `draft`, `regulation`, `analytic`) |
| `version` | `int \| str` | Версия разработки |
| `parent_ref` | `str \| null` | Ссылка на предыдущую версию или родительский документ |
| `payload_filename` | `str` | Безопасное имя файла полезной нагрузки |
| `payload_sha256` | `str` | Контрольная сумма SHA-256 файла полезной нагрузки |
| `payload_size` | `int` | Точный размер полезной нагрузки в байтах |
| `status` | `str` | Статус разработки: `draft`, `confirmed_decision`, `verified_work_material`, `archived`, `superseded` |
| `audience` | `list[str]` | Разрешенные роли потребителей (`ponder`, `developer`, `dramknote`, `commercial_department`) |
| `metadata` | `dict` | Дополнительный контекст |

#### 5.2. Модель общего реестра разработок (`00_РЕЕСТР_РАЗРАБОТОК/registry.json`)
Единый реестр в рабочей базе знаний (`knowledge_base/01_В_РАБОТЕ/00_РЕЕСТР_РАЗРАБОТОК/`):
- Межпроцессная сериализация: `fcntl.flock(LOCK_EX)`;
- Атомарная запись с `fsync` файла и каталога;
- Поля записи дополняются `registered_path` (абсолютный путь к неизменяемому файлу в `01_В_РАБОТЕ/dramknote_developments/<project>/`) и `registered_at` (таймштамп регистрации UTC);
- Автоматическая регенерация представления в `REGISTRY.md`.

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
