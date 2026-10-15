# Офлайн-план развертывания расширения P-026 для @Dramknote_bot (FN-014)

Данный документ представляет собой контролируемый офлайн-план точного развертывания и безопасного отката (exact deployment & safe rollback) расширения P-026 для стратегического штаба «Драмкнот» (компонент `37-strategy-bot`).
План подготовлен разработчиком Пондером Стиббонсом в строгом соответствии с политикой **NoMergeProdRestartCostsCredentialsACL**.

> ⛔ **ВНИМАНИЕ: СТРОГИЙ ЗАПРЕТ ПРИМЕНЕНИЯ БЕЗ СОГЛАСОВАНИЯ**
> Любые действия по живому развертыванию, обновлению файлов в рабочей среде, перезапуску сервиса или переключению версий выполняются **исключительно по отдельному прямому решению лорда Витинари**. Автоматическое или самовольное применение настоящего плана в ходе разработки и приёмки категорически запрещено.

---

## 1. Точный состав и инвентарь релиза (Exact Release Inventory)

Все компоненты релиза развертываются детерминированно из утвержденного снимка Git с фиксацией хэшей:

### Кодовая база компонента (37-strategy-bot):
1. `37-strategy-bot/p026_storage.py` — изолированное хранилище решений и версионных черновиков:
   - Полная предвалидация всех путей и их предков до вызовов `mkdir`/`open`/`write` (fail-closed);
   - Рекурсивная проверка отсутствия символических ссылок (`islink`, `is_symlink`) по всей цепочке предков до корня файловой системы;
   - Безопасное открытие lock-файлов с флагом `os.O_NOFOLLOW` и проверкой дескриптора;
   - Межпроцессные блокировки `fcntl.flock` с таймаутом и реентерабельностью;
   - Строгая изоляция акторов и чатов, поддержка отрицательных Telegram chat ID;
   - Запрет доступа к черновикам без подтверждённого владельца (unowned — fail-closed);
   - Микросекундный детерминированный формат ID решений (`dec_{n}_{timestamp_us}`);
   - Автоматический карантин пустых (0 байт) и структурно невалидных журналов решений без перезаписи;
   - Единая каноническая схема записей (`id`, `timestamp`, `author`, `user_id`, `chat_id`, `question_context`, `exact_text`, `status`), валидация ISO-8601 даты/времени, уникальности ID и допустимых статусов.
2. `37-strategy-bot/p026_handler.py` — обработчик диалога и экспорта:
   - Двухшаговый механизм фиксации решений через точное ожидающее предложение (`pending proposal`) с привязкой к `(user_id, chat_id)`;
   - Полный отказ от черных списков подстрок; отклонение любых неопределённых фраз согласия без привязки к активному предложению;
   - Валидация самостоятельных нормативных решений (наличие роли, параметра, числовой или процедурной нормы);
   - Runtime gate: обязательная верификация манифеста 30 источников перед генерацией статуса `/project` и экспортом черновиков (fail-closed отказ при повреждении);
   - Безопасный экспорт версионных черновиков с наложением изолированных решений актора.
3. `37-strategy-bot/p026_subject_base.py` — предметная база нормативных знаний P-026:
   - Неизменяемый нормативный манифест 30 канонических файлов с эталонными хэшами SHA-256 и размерами;
   - Метод `verify_all_sources()` со строгим контролем каждого файла;
   - Содержательное подключение всех 30 источников манифеста в модельный контекст с соблюдением нормативной иерархии (приоритет решений 107/109, ядро РЕГ-001..009, функционалы КД, РОП, МОП, паспорт P-026);
   - Безопасное текстовое извлечение HTML-документов без передачи в модель скриптов, стилей и base64;
   - Нормативные лимиты скидок v0.6 и ответы РОП 109.
4. `37-strategy-bot/strategy_bot.py` — стратегический сервис @Dramknote_bot:
   - Строгая chat boundary: отклонение любых сообщений и callbacks из групповых чатов до обращения к модели и истории;
   - Раздельная история диалогов по связке `(user_id, chat_id)`;
   - Runtime gate: отказ integrity gate останавливает модель и историю до любого вызова SDK / model API (`generate_content`) и до обновления пользовательской истории;
   - Бинарная отправка файлов документов через `reply_document`/`send_document` (I/O streaming).
5. `37-strategy-bot/systemd/star-building-strategy.service` — unit-файл службы systemd:
   - Изоляция песочницы: `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp=true`, `NoNewPrivileges=true`;
   - Единый прямой несимлинковый путь runtime: `ReadWritePaths=/home/roman/.local/share/star-building/dramknote-p026`, `StateDirectory=star-building/dramknote-p026`, `DRAMKNOTE_P026_STORAGE_DIR=/home/roman/.local/share/star-building/dramknote-p026`;
   - Подключение секретов исключительно через `EnvironmentFile=`.
6. `37-strategy-bot/README.md` — эксплуатационная документация с точным описанием границ изоляции и формата ID.
7. `37-strategy-bot/DEPLOYMENT_PLAN.md` — настоящий план точного развертывания и безопасного отката.

### Тестовый комплекс (100% PASS):
8. `37-strategy-bot/test_p026_storage.py` — unit-тесты хранилища (конкурентность, реентерабельность, карантин пустого и повреждённого журнала, actor/chat изоляция, отрицательные chat ID, каноническая нормализация алиасов, валидация ISO-8601);
9. `37-strategy-bot/test_p026_handler.py` — unit-тесты обработчика (двухшаговый pending proposal, отклонение вариаций согласий без подстрочных черных списков, runtime gate манифеста, изоляция экспорта);
10. `37-strategy-bot/test_p026_subject_base.py` — unit-тесты предметной базы (манифест 30 источников, содержательное чтение всех 30 файлов, правила скидок, очистка HTML от скриптов/base64);
11. `37-strategy-bot/test_p026_security.py` — security-тесты (symlink предков, lock-атаки, отсутствие side-effects до отказа, path traversal, неизменность SHA-256 источников, скан секретов);
12. `37-strategy-bot/test_p026_integration.py` — интеграционные тесты (блокировка групповых сообщений, fail-closed runtime gate промпта с 0 обращений к модели и без записи истории, бинарная отправка документов Telegram);
13. `37-strategy-bot/test_strategy_bot.py` — регрессионные тесты hardened-службы и тест-гард чистоты `$HOME/.local/share`;
14. `37-strategy-bot/test_strategy_healthcheck.py` — тесты диагностического модуля.

### Архитектурная документация и реестры:
15. `DATA_MODEL.md` — точное описание сущностей решений (us-timestamp, каноническая схема), версионных черновиков, fail-closed unowned правил и манифеста 30 источников;
16. `DECISIONS.md` — архитектурная фиксация решений ADR-028 (устранение findings R1–R7) и ADR-029 (устранение findings S1–S5);
17. `KNOWLEDGE_BASE.md` — актуализация регламентов коммерческого департамента P-026 и штаба @Dramknote_bot;
18. `PROJECT_MANIFEST.json` — машиночитаемый реестр репозитория;
19. `PROJECT_STRUCTURE.md` — структура репозитория;
20. `graphify-out/` — актуализированный граф связей базы знаний.

---

## 2. Предварительные условия и подготовка окружения (Pre-flight & Provisioning)

Перед развертыванием оператор обязан проверить выполнение следующих условий:

1. **Сервер:** рабочий хост Star Building (`/home/roman`).
2. **Пользователь:** `roman` (без запроса root/sudo).
3. **Виртуальное окружение Python:** `/srv/hermes-agent/venv/bin/python3` (версия Python >= 3.11).
4. **Конфигурация секретов:** файл `/home/roman/.config/star-building/strategy-bot.env` (права `0600`). Используется существующий авторизованный токен `@Dramknote_bot`. **Операции с секретами скриптами развертывания строго запрещены.** Токены не копируются, не перемещаются и не выводятся.
5. **Подготовка директории состояния (Provisioning):**
   ```bash
   # Создание структуры каталогов runtime state с безопасными правами доступа (0700)
   mkdir -p /home/roman/.local/share/star-building/dramknote-p026/decisions
   mkdir -p /home/roman/.local/share/star-building/dramknote-p026/drafts
   chmod 700 /home/roman/.local/share/star-building/dramknote-p026
   chmod 700 /home/roman/.local/share/star-building/dramknote-p026/decisions
   chmod 700 /home/roman/.local/share/star-building/dramknote-p026/drafts
   ```
6. **Единый несимлинковый путь состояния:**
   - Переменная окружения: `DRAMKNOTE_P026_STORAGE_DIR=/home/roman/.local/share/star-building/dramknote-p026`;
   - Песочница systemd: `ReadWritePaths=/home/roman/.local/share/star-building/dramknote-p026`;
   - Директива systemd: `StateDirectory=star-building/dramknote-p026`.
   - **СТРОГИЙ ЗАПРЕТ СИМВОЛИЧЕСКИХ ССЫЛОК:** Все операции хранения выполняются по прямому пути без создания symlink между `.local/state` и `.local/share`, так как хранилище `P026Storage` проверяет всех предков пути и блокирует работу fail-closed при наличии любых символических ссылок.
7. **Каталоги релизов и бэкапов:**
   ```bash
   mkdir -p /home/roman/srv/star-building-strategy/releases
   mkdir -p /home/roman/srv/star-building-strategy/backups
   ```

---

## 3. Пошаговая процедура точного развертывания (Exact Release Deployment)

Процедура выполняется **только** при наличии явного письменного решения лорда Витинари.

### Шаг 1. Верификация принятого коммита, дерева и архива
```bash
set -euo pipefail

TARGET_COMMIT="<ACCEPTED_COMMIT_SHA>"
EXPECTED_TREE="<EXPECTED_TREE_SHA>"
EXPECTED_ARCHIVE_SHA="<EXPECTED_ARCHIVE_SHA256>"

cd /home/roman/.worktrees/t_7b954f30
ACTUAL_COMMIT=$(git rev-parse HEAD)
ACTUAL_TREE=$(git rev-parse HEAD^{tree})

if [ "$ACTUAL_COMMIT" != "$TARGET_COMMIT" ]; then
    echo "ОШИБКА: Коммит не совпадает с принятым! Ожидался: $TARGET_COMMIT, получен: $ACTUAL_COMMIT"
    exit 1
fi

if [ "$ACTUAL_TREE" != "$EXPECTED_TREE" ]; then
    echo "ОШИБКА: Дерево не совпадает с принятым! Ожидалось: $EXPECTED_TREE, получено: $ACTUAL_TREE"
    exit 1
fi

# Генерация чистого архива принятого релиза и проверка SHA-256
TMP_ARCHIVE=$(mktemp /tmp/dramknote_release_XXXXXX.tar)
git archive --format=tar "$TARGET_COMMIT" > "$TMP_ARCHIVE"
ACTUAL_ARCHIVE_SHA=$(sha256sum "$TMP_ARCHIVE" | awk '{print $1}')

if [ "$ACTUAL_ARCHIVE_SHA" != "$EXPECTED_ARCHIVE_SHA" ]; then
    echo "ОШИБКА: SHA-256 архива релиза не совпадает!"
    echo "Ожидался: $EXPECTED_ARCHIVE_SHA"
    echo "Получен:   $ACTUAL_ARCHIVE_SHA"
    rm -f "$TMP_ARCHIVE"
    exit 1
fi
echo "Верификация точного снимка Git (commit, tree, archive SHA-256) успешно пройдена."
```

### Шаг 2. Фиксация и полный бэкап активного live-хэндла службы ДО любых изменений
```bash
set -euo pipefail

BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PINNED_BACKUP_DIR="/home/roman/srv/star-building-strategy/backups/pinned_live_${BACKUP_TIMESTAMP}"
mkdir -p "$PINNED_BACKUP_DIR"

# 1. Точное определение активных хэндлов работающей службы через systemd
LIVE_UNIT_PATH=$(systemctl --user show star-building-strategy.service -p FragmentPath --value 2>/dev/null || echo "")
LIVE_EXEC_START=$(systemctl --user show star-building-strategy.service -p ExecStart --value 2>/dev/null || echo "")
LIVE_WORK_DIR=$(systemctl --user show star-building-strategy.service -p WorkingDirectory --value 2>/dev/null || echo "")

if [ -z "$LIVE_UNIT_PATH" ] || [ ! -f "$LIVE_UNIT_PATH" ]; then
    echo "ОШИБКА: Активный unit-файл службы не найден в systemd!"
    exit 1
fi

if [ -z "$LIVE_WORK_DIR" ] || [ ! -d "$LIVE_WORK_DIR" ]; then
    echo "ОШИБКА: Рабочий каталог активной службы ($LIVE_WORK_DIR) не найден!"
    exit 1
fi

# 2. Сохранение активного unit-файла в бэкап с проверкой размера (> 0 байт)
cp -p "$LIVE_UNIT_PATH" "$PINNED_BACKUP_DIR/star-building-strategy.service"
if [ ! -s "$PINNED_BACKUP_DIR/star-building-strategy.service" ]; then
    echo "ОШИБКА: Сохранённый в бэкап unit-файл пуст!"
    exit 1
fi

# 3. Сохранение кода службы СТРОГО по положительному allowlist (без секретов/токенов)
mkdir -p "$PINNED_BACKUP_DIR/code"
python3 -c "
import hashlib, json, os, pathlib, shutil, sys

src_dir = pathlib.Path('$LIVE_WORK_DIR')
dst_code = pathlib.Path('$PINNED_BACKUP_DIR/code')

ALLOWED_EXTENSIONS = {'.py', '.md', '.txt', '.json', '.service'}
FORBIDDEN_PATTERNS = {'.env', 'token', 'secret', 'credential', '.pem', '.key'}

copied_files = {}
for p in src_dir.rglob('*'):
    if p.is_file():
        name_lower = p.name.lower()
        if any(bad in name_lower for bad in FORBIDDEN_PATTERNS):
            continue
        if p.suffix.lower() in ALLOWED_EXTENSIONS:
            rel = p.relative_to(src_dir)
            target = dst_code / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            copied_files[str(rel)] = hashlib.sha256(target.read_bytes()).hexdigest()

unit_bytes = (pathlib.Path('$PINNED_BACKUP_DIR') / 'star-building-strategy.service').read_bytes()
meta = {
    'timestamp': '$BACKUP_TIMESTAMP',
    'live_unit_path': '$LIVE_UNIT_PATH',
    'live_exec_start': '$LIVE_EXEC_START',
    'live_work_dir': '$LIVE_WORK_DIR',
    'unit_sha256': hashlib.sha256(unit_bytes).hexdigest(),
    'code_files_count': len(copied_files),
    'files': copied_files,
}
(pathlib.Path('$PINNED_BACKUP_DIR') / 'pinned_metadata.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False))
print(f'Pinned backup успешно сформирован ({len(copied_files)} файлов кода, 0 секретов).')
"

# 4. Сохранение снимка состояния runtime (decisions и drafts)
if [ -d /home/roman/.local/share/star-building/dramknote-p026 ]; then
    cp -a /home/roman/.local/share/star-building/dramknote-p026 "$PINNED_BACKUP_DIR/state"
fi

# ВАЖНО: Секретные файлы (strategy-bot.env) СТРОГО НЕ копируются в бэкап.
echo "Бэкап работающего релиза надёжно зафиксирован в: $PINNED_BACKUP_DIR"
```

### Шаг 3. Распаковка релиза в версионный каталог и чистый инвентарь файлов
```bash
set -euo pipefail

RELEASE_DIR="/home/roman/srv/star-building-strategy/releases/${TARGET_COMMIT}"

# Защита от смешивания: если каталог уже существовал, он очищается перед распаковкой
if [ -d "$RELEASE_DIR" ]; then
    rm -rf "$RELEASE_DIR"
fi
mkdir -p "$RELEASE_DIR"

# Распаковка верифицированного архива
tar -xf "$TMP_ARCHIVE" -C "$RELEASE_DIR"
rm -f "$TMP_ARCHIVE"

# Проверка инвентаря: сверка распакованных файлов компонента с манифестом коммита Git
python3 -c "
import subprocess, pathlib, sys
release_path = pathlib.Path('$RELEASE_DIR/37-strategy-bot')
git_cmd = ['git', 'ls-tree', '-r', '--name-only', '$TARGET_COMMIT', '37-strategy-bot']
git_files = set(subprocess.check_output(git_cmd, cwd='/home/roman/.worktrees/t_7b954f30').decode().splitlines())
disk_files = {str(p.relative_to('$RELEASE_DIR')) for p in release_path.rglob('*') if p.is_file()}

extra_files = disk_files - git_files
missing_files = git_files - disk_files

if extra_files or missing_files:
    print(f'ОШИБКА: Нарушен чистый инвентарь файлов релиза!')
    if extra_files: print(f'Лишние файлы: {extra_files}')
    if missing_files: print(f'Отсутствующие файлы: {missing_files}')
    sys.exit(1)

print(f'Инвентарь файлов релиза строго верифицирован ({len(disk_files)} файлов, 0 лишних, 0 пропущенных).')
"
```

### Шаг 4. Атомарное переключение службы на новый версионный релиз
```bash
set -euo pipefail

# Подготовка unit-файла systemd с указанием прямого версионного каталога релиза
# (Исключает пофайловое копирование rsync в работающую службу!)
TARGET_UNIT="/home/roman/.config/systemd/user/star-building-strategy.service"
mkdir -p /home/roman/.config/systemd/user

python3 -c "
import pathlib
src_unit = pathlib.Path('$RELEASE_DIR/37-strategy-bot/systemd/star-building-strategy.service').read_text()
# Направляем WorkingDirectory и ExecStart на изолированный версионный релиз
lines = []
for line in src_unit.splitlines():
    if line.startswith('WorkingDirectory='):
        lines.append('WorkingDirectory=$RELEASE_DIR/37-strategy-bot')
    elif line.startswith('ExecStart='):
        lines.append('ExecStart=/srv/hermes-agent/venv/bin/python3 $RELEASE_DIR/37-strategy-bot/strategy_bot.py')
    else:
        lines.append(line)

new_unit = '\n'.join(lines) + '\n'
# Атомарная запись через временный файл
tmp_path = pathlib.Path('${TARGET_UNIT}.tmp')
tmp_path.write_text(new_unit)
tmp_path.replace('${TARGET_UNIT}')
print('Unit-файл службы атомарно обновлён со ссылкой на релиз $TARGET_COMMIT')
"

# Применение конфигурации systemd
systemctl --user daemon-reload
```

### Шаг 5. Контролируемый перезапуск службы
```bash
systemctl --user restart star-building-strategy.service
```

### Шаг 6. Контроль готовности и статуса (Smoke Check)
```bash
# 1. Проверка активного статуса сервиса
systemctl --user is-active star-building-strategy.service

# 2. Проверка свежего системного журнала
journalctl --user -u star-building-strategy.service -n 50 --no-pager

# 3. Запуск встроенной офлайн-проверки работоспособности
/srv/hermes-agent/venv/bin/python3 "$RELEASE_DIR/37-strategy-bot/strategy_healthcheck.py"
```

---

## 4. Процедура безопасного отката (Safe Rollback Procedure)

В случае обнаружения любых непредвиденных дефектов, регрессий или сбоев процедура отката восстанавливает **фактический снимок работающего релиза из зафиксированного pinned-бэкапа**:
- Без вызова `git checkout` в корневом репозитории;
- С проверкой целостности бэкапа перед восстановлением;
- Без затрагивания секретов.

### Шаг 1. Остановка службы
```bash
systemctl --user stop star-building-strategy.service
```

### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа
```bash
set -euo pipefail

# 1. Строгая проверка наличия явно переданного идентификатора бэкапа
# Категорический запрет молчаливого fallback на «последний» бэкап (latest)!
if [ -z "${PINNED_BACKUP_DIR:-}" ]; then
    echo "КРИТИЧЕСКАЯ ОШИБКА: Идентификатор бэкапа PINNED_BACKUP_DIR не задан! Молчаливый fallback на latest запрещён." >&2
    exit 1
fi

if [ -z "$PINNED_BACKUP_DIR" ] || [ ! -d "$PINNED_BACKUP_DIR" ]; then
    echo "КРИТИЧЕСКАЯ ОШИБКА: Каталог pinned-бэкапа не найден! Откат заблокирован fail-closed." >&2
    exit 1
fi

# 2. Комплексная верификация бэкапа ДО ПЕРВОЙ МУТАЦИИ (fail-closed)
# Сверяются: обязательный манифест, хэши unit-файла, инвентарь файлов кода,
# хэши каждого разрешённого файла кода, pinned WorkingDirectory,
# запрет секретов/токенов в бэкапе.
# Любое несоответствие приводит к немедленному fail-closed отказу (exit 1) с 0 мутаций.
python3 -c "
import hashlib, json, os, pathlib, subprocess, sys

backup_dir = pathlib.Path(os.environ['PINNED_BACKUP_DIR'])
meta_path = backup_dir / 'pinned_metadata.json'

if not meta_path.is_file():
    print('КРИТИЧЕСКАЯ ОШИБКА: Обязательный манифест pinned_metadata.json отсутствует в бэкапе!', file=sys.stderr)
    sys.exit(1)

try:
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
except Exception as err:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Манифест pinned_metadata.json повреждён: {err}', file=sys.stderr)
    sys.exit(1)

required_fields = {'unit_sha256', 'code_files_count', 'live_work_dir'}
missing_fields = required_fields - set(meta.keys())
if missing_fields:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: В манифесте отсутствуют обязательные поля: {missing_fields}', file=sys.stderr)
    sys.exit(1)

unit_path = backup_dir / 'star-building-strategy.service'
if not unit_path.is_file() or unit_path.stat().st_size == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Unit-файл в бэкапе отсутствует или пуст!', file=sys.stderr)
    sys.exit(1)

actual_unit_sha = hashlib.sha256(unit_path.read_bytes()).hexdigest()
exp_unit_sha = str(meta.get('unit_sha256', ''))
if actual_unit_sha != exp_unit_sha:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Хэш unit-файла ({actual_unit_sha}) не совпадает с манифестом ({exp_unit_sha})!', file=sys.stderr)
    sys.exit(1)

code_dir = backup_dir / 'code'
if not code_dir.is_dir():
    print('КРИТИЧЕСКАЯ ОШИБКА: Каталог кода отсутствует в бэкапе!', file=sys.stderr)
    sys.exit(1)

code_files = [p for p in code_dir.rglob('*') if p.is_file()]
exp_count = meta.get('code_files_count', -1)
if len(code_files) != exp_count:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Число файлов кода ({len(code_files)}) не совпадает с манифестом ({exp_count})!', file=sys.stderr)
    sys.exit(1)

if 'files' in meta and isinstance(meta['files'], dict):
    for rel_str, exp_hash in meta['files'].items():
        fp = code_dir / rel_str
        if not fp.is_file():
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {rel_str} из манифеста отсутствует в бэкапе!', file=sys.stderr)
            sys.exit(1)
        if hashlib.sha256(fp.read_bytes()).hexdigest() != exp_hash:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Хэш файла {rel_str} повреждён!', file=sys.stderr)
            sys.exit(1)

FORBIDDEN_SECRET_PATTERNS = {'.env', 'token', 'secret', 'credential', '.pem', '.key'}
for p in backup_dir.rglob('*'):
    if p.is_file():
        name_lower = p.name.lower()
        if any(pat in name_lower for pat in FORBIDDEN_SECRET_PATTERNS):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: В бэкапе обнаружен недопустимый секретный файл: {p.name}', file=sys.stderr)
            sys.exit(1)

pinned_work_dir = meta['live_work_dir']
try:
    proc = subprocess.run(
        ['systemctl', '--user', 'show', 'star-building-strategy.service', '-p', 'WorkingDirectory', '--value'],
        capture_output=True, text=True, check=False
    )
    current_work_dir = proc.stdout.strip()
    if current_work_dir and current_work_dir != pinned_work_dir:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Pinned WorkingDirectory ({pinned_work_dir}) не совпадает со значением службы ({current_work_dir})!', file=sys.stderr)
        sys.exit(1)
except Exception:
    pass

print('Верификация бэкапа успешно пройдена: все хэши и инвентарь подтверждены fail-closed.')
"

# 3. Атомарное восстановление unit-файла службы
TARGET_UNIT_PATH="${HOME}/.config/systemd/user/star-building-strategy.service"
mkdir -p "${HOME}/.config/systemd/user"
cp -p "$PINNED_BACKUP_DIR/star-building-strategy.service" "$TARGET_UNIT_PATH"
systemctl --user daemon-reload

# 4. Восстановление рабочего каталога кода строго в подтверждённый pinned каталог
TARGET_WORK_DIR=$(python3 -c "import json, pathlib, os; print(json.loads((pathlib.Path(os.environ['PINNED_BACKUP_DIR']) / 'pinned_metadata.json').read_text())['live_work_dir'])")
if [ -n "$TARGET_WORK_DIR" ] && [ -d "$PINNED_BACKUP_DIR/code" ]; then
    mkdir -p "$TARGET_WORK_DIR"
    rsync -a --delete "$PINNED_BACKUP_DIR/code/" "$TARGET_WORK_DIR/"
fi
echo "Откат к проверенному снимку $PINNED_BACKUP_DIR успешно завершён."
```

### Шаг 3. Сохранность данных runtime
Существующий журнал решений и версионные черновики в `/home/roman/.local/share/star-building/dramknote-p026` сохраняются без удаления. При необходимости слияния или восстановления журнала решений используется архивный снимок `$PINNED_BACKUP_DIR/state/decisions/decisions.json`.

### Шаг 4. Запуск восстановленной службы и контроль
```bash
systemctl --user start star-building-strategy.service
systemctl --user is-active star-building-strategy.service
journalctl --user -u star-building-strategy.service -n 30 --no-pager
```

---

## 5. Политика ограничений безопасности

- **No Merge:** Ветка `work/dramknote-p026-handoff` не сливается в `main`/`master` в рамках данной задачи.
- **No Prod Restart:** В ходе разработки и приёмки перезапуск службы на боевом сервере запрещён.
- **No Costs:** Запрещены любые платные модельные вызовы или обращение к коммерческим внешним API.
- **No Credentials:** Запрещено чтение, запись, логирование, копирование или коммит секретов и токенов (`strategy-bot.env`).
- **No ACL Mutation:** Запрещено изменение прав доступа файловой системы live-контура.
- **No Deletion Live State:** Самовольное удаление файлов из боевого каталога хранения запрещено.
- **No Git Checkout on Rollback:** Откат выполняется строго из изолированного подтверждённого снимка бэкапа без изменения рабочего дерева Git.
