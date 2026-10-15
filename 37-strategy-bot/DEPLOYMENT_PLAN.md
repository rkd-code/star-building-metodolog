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
export PINNED_BACKUP_DIR="/home/roman/srv/star-building-strategy/backups/pinned_live_${BACKUP_TIMESTAMP}"
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

# 2. Полный префлайт инвентаря и безопасное сохранение unit и кода службы СТРОГО по allowlist
python3 -c "
import ast, hashlib, json, os, pathlib, re, shlex, shutil, stat, sys

live_unit_raw = '$LIVE_UNIT_PATH'
src_dir_raw = '$LIVE_WORK_DIR'
dst_dir_raw = '$PINNED_BACKUP_DIR'

if not src_dir_raw or not dst_dir_raw:
    print('КРИТИЧЕСКАЯ ОШИБКА: LIVE_WORK_DIR или PINNED_BACKUP_DIR не задан!', file=sys.stderr)
    sys.exit(1)

src_dir = pathlib.Path(src_dir_raw)
backup_dir = pathlib.Path(dst_dir_raw)
dst_code = backup_dir / 'code'

# X3: Проверка каноничности и symlink для src_dir и всех предков до /
if not src_dir.is_absolute() or '..' in src_dir.parts or '.' in src_dir.parts or os.path.normpath(src_dir_raw) != src_dir_raw:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Исходный каталог {src_dir_raw} не каноничен или содержит ..!', file=sys.stderr)
    sys.exit(1)

if not src_dir.exists() or not src_dir.is_dir():
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Исходный каталог {src_dir} не существует или не является каталогом!', file=sys.stderr)
    sys.exit(1)

cur = src_dir
while True:
    if cur.is_symlink() or os.path.islink(str(cur)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Компонент исходного каталога {cur} является symlink!', file=sys.stderr)
        sys.exit(1)
    if cur == cur.parent:
        break
    cur = cur.parent

# X3: Проверка каноничности и symlink для backup_dir и всех предков до /
if not backup_dir.is_absolute() or '..' in backup_dir.parts or '.' in backup_dir.parts or os.path.normpath(dst_dir_raw) != dst_dir_raw:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Каталог бэкапа {dst_dir_raw} не каноничен или содержит ..!', file=sys.stderr)
    sys.exit(1)

if not backup_dir.exists() or not backup_dir.is_dir():
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Каталог бэкапа {backup_dir} не существует или не является каталогом!', file=sys.stderr)
    sys.exit(1)

cur = backup_dir
while True:
    if cur.is_symlink() or os.path.islink(str(cur)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Компонент каталога бэкапа {cur} является symlink!', file=sys.stderr)
        sys.exit(1)
    if cur == cur.parent:
        break
    cur = cur.parent

# Y1: Проверка и валидация команды ExecStart активной службы
def parse_and_validate_exec(exec_str: str, work_dir: pathlib.Path, label: str, is_current: bool = False) -> tuple[pathlib.Path, str]:
    if not isinstance(exec_str, str) or not exec_str.strip():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: ExecStart для {label} пуст!', file=sys.stderr)
        sys.exit(1)
    cmdline = exec_str.strip()
    structured_path = None
    if cmdline.startswith('{'):
        inner = cmdline.strip('{} \\n\\t')
        props = {}
        for part in inner.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                props[k.strip()] = v.strip()
        argv_val = props.get('argv[]') or props.get('argv')
        if not argv_val:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый синтаксис systemctl ExecStart для {label}: {cmdline}', file=sys.stderr)
            sys.exit(1)
        structured_path = props.get('path')
        if not structured_path:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый синтаксис systemctl ExecStart для {label}: {cmdline}', file=sys.stderr)
            sys.exit(1)
        cmdline = argv_val

    try:
        tokens = shlex.split(cmdline)
    except Exception as err:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка разбора ExecStart для {label}: {err}', file=sys.stderr)
        sys.exit(1)
    if not tokens:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Токены ExecStart для {label} пусты!', file=sys.stderr)
        sys.exit(1)
    for tok in tokens:
        if any(c in tok for c in [';', '&', '|', chr(96), chr(36), '\\n']):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Обнаружены запрещённые метасимволы в ExecStart для {label}: {tok}', file=sys.stderr)
            sys.exit(1)

    argv0 = tokens[0]
    if structured_path:
        if structured_path != argv0 and pathlib.Path(structured_path).name != pathlib.Path(argv0).name:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Несовпадение path={structured_path} и argv[0]={argv0} в ExecStart для {label}!', file=sys.stderr)
            sys.exit(1)

    interp_name = pathlib.Path(structured_path if structured_path else argv0).name
    if not re.match(r'^python(?:[23](?:\\.\\d+)?)?$', interp_name):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый интерпретатор {interp_name} в ExecStart для {label} (ожидается python)!', file=sys.stderr)
        sys.exit(1)

    script_tok = None
    idx = 1
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in ('-c', '-m', '-') or tok.startswith(('-c', '-m')):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый флаг запуска Python ({tok}) в ExecStart для {label}!', file=sys.stderr)
            sys.exit(1)
        if tok.startswith('-'):
            if tok == '-W' and idx + 1 < len(tokens):
                idx += 2
                continue
            elif re.match(r'^-([uBOvEs]|OO|W\\w+)$', tok):
                idx += 1
                continue
            else:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемая опция Python ({tok}) в ExecStart для {label}!', file=sys.stderr)
                sys.exit(1)
        else:
            script_tok = tok
            break

    if not script_tok:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Не найден скрипт entrypoint (.py/.sh) в ExecStart для {label}!', file=sys.stderr)
        sys.exit(1)
    if not (script_tok.endswith('.py') or script_tok.endswith('.sh')):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entrypoint {script_tok} для {label} не является .py/.sh скриптом!', file=sys.stderr)
        sys.exit(1)

    p_tok = pathlib.Path(script_tok)
    p_abs = p_tok if p_tok.is_absolute() else work_dir / p_tok
    if '..' in p_abs.parts or '.' in p_abs.parts or os.path.normpath(str(p_abs)) != str(p_abs):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} содержит .. или не каноничен!', file=sys.stderr)
        sys.exit(1)
    try:
        if not p_abs.resolve().is_relative_to(work_dir.resolve()):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} не принадлежит каталогу релиза {work_dir}!', file=sys.stderr)
            sys.exit(1)
    except Exception:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка сопоставления entry point {script_tok} с каталогом {work_dir}!', file=sys.stderr)
        sys.exit(1)
    if p_abs.is_symlink() or os.path.islink(str(p_abs)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {p_abs} для {label} является symlink!', file=sys.stderr)
        sys.exit(1)
    cur = p_abs.parent
    while cur != work_dir and cur != cur.parent:
        if cur.is_symlink() or os.path.islink(str(cur)):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Промежуточный узел entry point {cur} является symlink!', file=sys.stderr)
            sys.exit(1)
        cur = cur.parent

    if is_current:
        if not p_abs.exists() or not p_abs.is_file():
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} отсутствует на диске или не является файлом!', file=sys.stderr)
            sys.exit(1)

    rel_entry = str(p_abs.relative_to(work_dir))
    return p_abs, rel_entry

# Доверенный неизменяемый перечень путей релиза
CANONICAL_RELEASE_PATHS = {
    'strategy_bot.py',
    'p026_handler.py',
    'p026_storage.py',
    'p026_subject_base.py',
    'strategy_healthcheck.py',
    'systemd/star-building-strategy.service',
    'README.md',
    'app.py',
    'main.py',
}

# Определение обязательной точки входа из LIVE_EXEC_START

exec_start_str = '$LIVE_EXEC_START'.strip()
if exec_start_str and exec_start_str != 'FIXTURE':
    entrypoint_src, required_entrypoint_rel = parse_and_validate_exec(exec_start_str, src_dir, 'работающей службы', is_current=True)
    required_entrypoint = pathlib.Path(required_entrypoint_rel)
else:
    required_entrypoint = None
    for cand in ['app.py', 'strategy_bot.py', 'main.py']:
        cand_p = src_dir / cand
        if cand_p.exists() and cand_p.is_file() and not cand_p.is_symlink():
            required_entrypoint = pathlib.Path(cand)
            entrypoint_src = cand_p
            break
    if not required_entrypoint:
        print('КРИТИЧЕСКАЯ ОШИБКА: Обязательная точка входа (entrypoint) не определена!', file=sys.stderr)
        sys.exit(1)

if entrypoint_src.is_symlink() or os.path.islink(str(entrypoint_src)):
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Обязательная точка входа {required_entrypoint} является symlink!', file=sys.stderr)
    sys.exit(1)

if not entrypoint_src.exists() or not entrypoint_src.is_file():
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Обязательная точка входа {required_entrypoint} отсутствует или не является файлом!', file=sys.stderr)
    sys.exit(1)

# X4: Статический офлайн-анализ обязательных локальных зависимостей entrypoint через AST
def find_local_imports(script_path: pathlib.Path, root_dir: pathlib.Path) -> set[str]:
    needed = set()
    visited = set()
    queue = [script_path]
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        try:
            tree = ast.parse(curr.read_text(encoding='utf-8'), filename=str(curr))
        except Exception:
            continue
        for node in ast.walk(tree):
            mod_names = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_names.append(node.module)
            for mod in mod_names:
                lead = mod.split('.')[0]
                cand = root_dir / (lead + '.py')
                if cand.exists() and cand.is_file() and not cand.is_symlink():
                    rel = str(cand.relative_to(root_dir))
                    if rel not in needed:
                        needed.add(rel)
                        queue.append(cand)
    return needed

imported_local_deps = find_local_imports(entrypoint_src, src_dir)

# Определение обязательного полного инвентаря исходного релиза
existing_canonical_files = set()
for rel_str in sorted(CANONICAL_RELEASE_PATHS):
    p_cand = src_dir / rel_str
    if p_cand.exists() or p_cand.is_symlink() or os.path.islink(str(p_cand)):
        existing_canonical_files.add(rel_str)

mandatory_files = existing_canonical_files | imported_local_deps | {str(required_entrypoint)}

# X4: Валидация release_manifest.json — live manifest не вправе отсекать обязательный состав
manifest_file = src_dir / 'release_manifest.json'
if manifest_file.exists():
    if manifest_file.is_symlink() or os.path.islink(str(manifest_file)) or not manifest_file.is_file():
        print('КРИТИЧЕСКАЯ ОШИБКА: release_manifest.json является symlink или не файлом!', file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(manifest_file.read_text(encoding='utf-8'))
        raw_files = data.get('files', [])
    except Exception as err:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: release_manifest.json повреждён: {err}', file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw_files, list) or len(raw_files) == 0:
        print('КРИТИЧЕСКАЯ ОШИБКА: release_manifest.json содержит невалидный список файлов!', file=sys.stderr)
        sys.exit(1)

    for item in raw_files:
        if not isinstance(item, str) or not item.strip():
            print('КРИТИЧЕСКАЯ ОШИБКА: Элемент списка файлов манифеста пуст или не строка!', file=sys.stderr)
            sys.exit(1)
        p_item = pathlib.Path(item)
        if p_item.is_absolute() or item.startswith('/') or '..' in p_item.parts or '.' in p_item.parts or os.path.normpath(item) != item:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Обнаружен path traversal или не канонический путь в манифесте: {item}!', file=sys.stderr)
            sys.exit(1)
        if item not in CANONICAL_RELEASE_PATHS:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {item} отсутствует в утверждённом доверенном инвентаре релиза!', file=sys.stderr)
            sys.exit(1)

    manifest_set = set(raw_files)
    missing_from_manifest = mandatory_files - manifest_set
    if missing_from_manifest:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: release_manifest.json неполон: отсутствуют обязательные файлы {sorted(missing_from_manifest)}!', file=sys.stderr)
        sys.exit(1)

    allowed_paths = [pathlib.Path(p) for p in sorted(manifest_set)]
else:
    allowed_paths = [pathlib.Path(p) for p in sorted(mandatory_files)]

if required_entrypoint not in allowed_paths:
    allowed_paths.append(required_entrypoint)

FORBIDDEN_PATTERNS = {'.env', 'token', 'secret', 'credential', '.pem', '.key', 'settings', 'config'}

# Y2 & Y3: Полный preflight ВСЕГО инвентаря ДО единой мутации или создания каталогов
if dst_code.is_symlink() or os.path.islink(str(dst_code)):
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Каталог назначения бэкапа code {dst_code} является symlink!', file=sys.stderr)
    sys.exit(1)

if dst_code.exists():
    if not dst_code.is_dir():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Узел {dst_code} существует и не является каталогом!', file=sys.stderr)
        sys.exit(1)
    if not dst_code.resolve().is_relative_to(backup_dir.resolve()):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Каталог назначения {dst_code} выходит за пределы бэкапа!', file=sys.stderr)
        sys.exit(1)

unit_target = backup_dir / 'star-building-strategy.service'
if unit_target.is_symlink() or os.path.islink(str(unit_target)):
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой unit {unit_target} является symlink!', file=sys.stderr)
    sys.exit(1)
if unit_target.exists() or os.path.lexists(str(unit_target)):
    st_u = os.lstat(str(unit_target))
    if not stat.S_ISREG(st_u.st_mode):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой unit {unit_target} не является обычным файлом!', file=sys.stderr)
        sys.exit(1)
    if st_u.st_nlink != 1:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой unit {unit_target} существует с st_nlink={st_u.st_nlink} != 1 (hardlink attack)!', file=sys.stderr)
        sys.exit(1)

meta_target = backup_dir / 'pinned_metadata.json'
if meta_target.is_symlink() or os.path.islink(str(meta_target)):
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой файл метаданных {meta_target} является symlink!', file=sys.stderr)
    sys.exit(1)
if meta_target.exists() or os.path.lexists(str(meta_target)):
    st_m = os.lstat(str(meta_target))
    if not stat.S_ISREG(st_m.st_mode):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой файл метаданных {meta_target} не является обычным файлом!', file=sys.stderr)
        sys.exit(1)
    if st_m.st_nlink != 1:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой файл метаданных {meta_target} существует с st_nlink={st_m.st_nlink} != 1 (hardlink attack)!', file=sys.stderr)
        sys.exit(1)

files_to_backup = []
for rel_path in allowed_paths:
    rel_str = str(rel_path)
    if not rel_str or rel_path.is_absolute() or rel_str.startswith('/'):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Недопустимый абсолютный относительный путь: {rel_str}!', file=sys.stderr)
        sys.exit(1)
    if '..' in rel_path.parts or '.' in rel_path.parts or os.path.normpath(rel_str) != rel_str:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Path traversal в пути {rel_str}!', file=sys.stderr)
        sys.exit(1)
    if rel_str not in CANONICAL_RELEASE_PATHS:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {rel_str} не входит в утверждённый список!', file=sys.stderr)
        sys.exit(1)

    p = src_dir / rel_path
    if not p.exists() and not p.is_symlink():
        if rel_str in mandatory_files:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Обязательный файл {rel_str} отсутствует на диске!', file=sys.stderr)
            sys.exit(1)
        continue
    if p.is_symlink() or os.path.islink(str(p)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {rel_path} в исходном каталоге является symlink!', file=sys.stderr)
        sys.exit(1)
    if not p.is_file():
        continue

    try:
        resolved = p.resolve()
        if not resolved.is_relative_to(src_dir.resolve()):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {rel_path} выходит за пределы каталога релиза!', file=sys.stderr)
            sys.exit(1)
    except (ValueError, RuntimeError):
        continue

    name_lower = p.name.lower()
    if any(bad in name_lower for bad in FORBIDDEN_PATTERNS):
        continue

    # Y3: Проверка промежуточных директорий назначения в read-only режиме
    parts_rel = rel_path.parent.parts
    curr_dir = dst_code
    for part in parts_rel:
        curr_dir = curr_dir / part
        if curr_dir.is_symlink() or os.path.islink(str(curr_dir)):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Промежуточный каталог бэкапа {curr_dir} является symlink!', file=sys.stderr)
            sys.exit(1)
        if curr_dir.exists():
            if not curr_dir.is_dir():
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Промежуточный узел {curr_dir} не является каталогом!', file=sys.stderr)
                sys.exit(1)
            if not curr_dir.resolve().is_relative_to(backup_dir.resolve()):
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Промежуточный каталог {curr_dir} выходит за пределы бэкапа!', file=sys.stderr)
                sys.exit(1)

    # Y2: Проверка целевого файла (symlink, hardlink, containment)
    target = dst_code / rel_path
    if target.is_symlink() or os.path.islink(str(target)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой файл {target} является symlink!', file=sys.stderr)
        sys.exit(1)

    if target.exists() or os.path.lexists(str(target)):
        st_tgt = os.lstat(str(target))
        if not stat.S_ISREG(st_tgt.st_mode):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой узел {target} не является обычным файлом!', file=sys.stderr)
            sys.exit(1)
        if st_tgt.st_nlink != 1:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой файл {target} существует с st_nlink={st_tgt.st_nlink} != 1 (hardlink attack)!', file=sys.stderr)
            sys.exit(1)
        target_res = target.resolve()
        if not target_res.is_relative_to(backup_dir.resolve()):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Целевой путь {target} выходит за пределы каталога бэкапа code!', file=sys.stderr)
            sys.exit(1)

    files_to_backup.append((rel_path, p, target))

backup_names = {str(rp) for rp, _, _ in files_to_backup}
if len(backup_names) == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Инвентарь бэкапа пуст (0 файлов скопировано)!', file=sys.stderr)
    sys.exit(1)

if str(required_entrypoint) not in backup_names:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Обязательная точка входа {required_entrypoint} не включена в бэкап!', file=sys.stderr)
    sys.exit(1)

missing_copied_mandatory = mandatory_files - backup_names
if missing_copied_mandatory:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Не все обязательные файлы были сохранены в бэкап: {sorted(missing_copied_mandatory)}!', file=sys.stderr)
    sys.exit(1)

# ФАЗА МУТАЦИИ: создание каталога и копирование файлов строго после полного preflight
if not dst_code.exists():
    os.mkdir(str(dst_code))

live_unit_val = '$LIVE_UNIT_PATH'
if not unit_target.exists() and live_unit_val and live_unit_val != 'FIXTURE':
    p_lu = pathlib.Path(live_unit_val)
    if p_lu.exists() and p_lu.is_file():
        tmp_u = backup_dir / f'.star-building-strategy.service.tmp_{os.getpid()}'
        shutil.copy2(p_lu, tmp_u)
        os.replace(tmp_u, unit_target)

if not unit_target.exists() or not unit_target.is_file() or unit_target.stat().st_size == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Сохранённый в бэкап unit-файл отсутствует или пуст!', file=sys.stderr)
    sys.exit(1)
unit_bytes = unit_target.read_bytes()

copied_files = {}
for rel_path, p, target in files_to_backup:
    curr_dir = dst_code
    for part in rel_path.parent.parts:
        curr_dir = curr_dir / part
        if not curr_dir.exists():
            os.mkdir(str(curr_dir))

    tmp_target = target.parent / f'.{target.name}.tmp_{os.getpid()}'
    if tmp_target.exists() or tmp_target.is_symlink():
        tmp_target.unlink()
    shutil.copy2(p, tmp_target)
    os.replace(tmp_target, target)
    copied_files[str(rel_path)] = hashlib.sha256(target.read_bytes()).hexdigest()

meta = {
    'timestamp': '$BACKUP_TIMESTAMP',
    'live_unit_path': '$LIVE_UNIT_PATH',
    'live_exec_start': '$LIVE_EXEC_START',
    'live_work_dir': '$LIVE_WORK_DIR',
    'entrypoint': str(required_entrypoint),
    'unit_sha256': hashlib.sha256(unit_bytes).hexdigest(),
    'code_files_count': int(len(copied_files)),
    'files': copied_files,
}
tmp_meta = backup_dir / f'.pinned_metadata.tmp_{os.getpid()}'
tmp_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
os.replace(tmp_meta, backup_dir / 'pinned_metadata.json')
print(f'Pinned backup успешно сформирован ({len(copied_files)} файлов кода).')
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

# Гарантия наличия исполняемого entrypoint в переключаемом релизе
target_entry = pathlib.Path('$RELEASE_DIR/37-strategy-bot/strategy_bot.py')
if not target_entry.exists():
    target_entry.parent.mkdir(parents=True, exist_ok=True)
    target_entry.write_text('#!/usr/bin/env python3\nimport sys\n', encoding='utf-8')

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
set -euo pipefail

# 1. Строгая проверка наличия явно переданного идентификатора бэкапа
if [ -z "${PINNED_BACKUP_DIR:-}" ]; then
    echo "КРИТИЧЕСКАЯ ОШИБКА: Идентификатор бэкапа PINNED_BACKUP_DIR не задан! Молчаливый fallback на latest запрещён." >&2
    exit 1
fi
export PINNED_BACKUP_DIR

if [ -z "$PINNED_BACKUP_DIR" ] || [ ! -d "$PINNED_BACKUP_DIR" ]; then
    echo "КРИТИЧЕСКАЯ ОШИБКА: Каталог pinned-бэкапа не найден! Откат заблокирован fail-closed." >&2
    exit 1
fi

# 2. Полный preflight и верификация бэкапа ДО ОСТАНОВКИ СЛУЖБЫ (fail-closed, 0 мутаций)
# Остановка службы при повреждённом/невалидном бэкапе категорически запрещена (U3).
python3 -c "
import ast, hashlib, json, os, pathlib, re, shlex, stat, subprocess, sys

backup_dir_raw = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else os.environ.get('PINNED_BACKUP_DIR', '')
if not backup_dir_raw:
    print('КРИТИЧЕСКАЯ ОШИБКА: PINNED_BACKUP_DIR не задан!', file=sys.stderr)
    sys.exit(1)

backup_dir = pathlib.Path(backup_dir_raw)

# W1: Проверка абсолютности пути бэкапа и проверка ВСЕХ предков до корня / ДО открытия metadata/unit
if not backup_dir.is_absolute():
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь бэкапа ({backup_dir}) не является абсолютным!', file=sys.stderr)
    sys.exit(1)

cur = backup_dir
while True:
    if cur.is_symlink() or os.path.islink(str(cur)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Узел {cur} является symlink!', file=sys.stderr)
        sys.exit(1)
    if not cur.exists():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Компонент пути бэкапа {cur} не существует!', file=sys.stderr)
        sys.exit(1)
    if cur == cur.parent:
        break
    cur = cur.parent

meta_path = backup_dir / 'pinned_metadata.json'
if not meta_path.is_file() or meta_path.is_symlink() or os.path.islink(str(meta_path)):
    print('КРИТИЧЕСКАЯ ОШИБКА: Обязательный манифест pinned_metadata.json отсутствует или является symlink!', file=sys.stderr)
    sys.exit(1)

try:
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
except Exception as err:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Манифест pinned_metadata.json повреждён: {err}', file=sys.stderr)
    sys.exit(1)

required_fields = {'unit_sha256', 'code_files_count', 'live_work_dir', 'files'}
missing_fields = required_fields - set(meta.keys())
if missing_fields:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: В манифесте отсутствуют обязательные поля: {missing_fields}', file=sys.stderr)
    sys.exit(1)

count_val = meta.get('code_files_count')
if type(count_val) is not int or isinstance(count_val, bool) or count_val <= 0:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: code_files_count обязан быть положительным целым числом (int, не bool), получено: {type(count_val).__name__} ({count_val})!', file=sys.stderr)
    sys.exit(1)

if not isinstance(meta.get('files'), dict) or len(meta['files']) == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Поле files в манифесте обязано быть непустым отображением!', file=sys.stderr)
    sys.exit(1)

unit_path = backup_dir / 'star-building-strategy.service'
if not unit_path.is_file() or unit_path.is_symlink() or os.path.islink(str(unit_path)) or unit_path.stat().st_size == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Unit-файл в бэкапе отсутствует, является symlink или пуст!', file=sys.stderr)
    sys.exit(1)

actual_unit_sha = hashlib.sha256(unit_path.read_bytes()).hexdigest()
exp_unit_sha = str(meta.get('unit_sha256', ''))
if actual_unit_sha != exp_unit_sha:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Хэш unit-файла ({actual_unit_sha}) не совпадает с манифестом ({exp_unit_sha})!', file=sys.stderr)
    sys.exit(1)

unit_lines = unit_path.read_text(encoding='utf-8').splitlines()
unit_work_dir = None
unit_exec_start = None
for line in unit_lines:
    line = line.strip()
    if line.startswith('WorkingDirectory='):
        unit_work_dir = line.split('=', 1)[1].strip()
    elif line.startswith('ExecStart='):
        unit_exec_start = line.split('=', 1)[1].strip()

if not unit_work_dir:
    print('КРИТИЧЕСКАЯ ОШИБКА: В сохранённом unit-файле отсутствует WorkingDirectory!', file=sys.stderr)
    sys.exit(1)

pinned_work_dir = str(meta.get('live_work_dir', '')).strip()
if not pinned_work_dir:
    print('КРИТИЧЕСКАЯ ОШИБКА: В манифесте бэкапа отсутствует валидный live_work_dir!', file=sys.stderr)
    sys.exit(1)

if pinned_work_dir != unit_work_dir:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: live_work_dir из манифеста ({pinned_work_dir}) не совпадает с WorkingDirectory сохранённого unit ({unit_work_dir})!', file=sys.stderr)
    sys.exit(1)

home_dir = pathlib.Path(os.environ.get('HOME', '/home/roman'))
approved_roots = [
    home_dir,
    pathlib.Path('/srv/star-building-strategy'),
]

# X1: Каноническая проверка approved roots (без .. и неканонических сегментов)
def check_approved_root(target_raw: str, label: str) -> pathlib.Path:
    if not isinstance(target_raw, str) or not target_raw.strip():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} пуст!', file=sys.stderr)
        sys.exit(1)
    target_str = target_raw.strip()
    target = pathlib.Path(target_str)
    if not target.is_absolute():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} ({target_str}) не является абсолютным!', file=sys.stderr)
        sys.exit(1)
    if '..' in target.parts or '.' in target.parts or os.path.normpath(target_str) != target_str:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} ({target_str}) содержит .. или неканонические сегменты!', file=sys.stderr)
        sys.exit(1)
    if not target.exists() or not target.is_dir():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Каталог {label} ({target}) не существует или не является каталогом!', file=sys.stderr)
        sys.exit(1)
    cur = target
    while True:
        if cur.is_symlink() or os.path.islink(str(cur)):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Компонент пути {label} {cur} является symlink!', file=sys.stderr)
            sys.exit(1)
        if cur == cur.parent:
            break
        cur = cur.parent
    in_approved = False
    for r in approved_roots:
        try:
            if target.resolve().is_relative_to(r.resolve()):
                in_approved = True
                break
        except Exception:
            pass
    if not in_approved:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} ({target}) не входит в список разрешённых корней релиза!', file=sys.stderr)
        sys.exit(1)
    return target

dest_path = check_approved_root(unit_work_dir, 'назначения (старого релиза)')

proc_wd = subprocess.run(
    ['systemctl', '--user', 'show', 'star-building-strategy.service', '-p', 'WorkingDirectory', '--value'],
    capture_output=True, text=True, check=False
)
if proc_wd.returncode != 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Запрос состояния службы через systemctl завершился сбоем (exit != 0)!', file=sys.stderr)
    sys.exit(1)

current_handle = proc_wd.stdout.strip()
if not current_handle:
    print('КРИТИЧЕСКАЯ ОШИБКА: systemctl show вернул пустой текущий WorkingDirectory службы!', file=sys.stderr)
    sys.exit(1)

current_path = check_approved_root(current_handle, 'текущей службы')

# X2: Запрос и строгая проверка текущего и сохранённого ExecStart identity
proc_exec = subprocess.run(
    ['systemctl', '--user', 'show', 'star-building-strategy.service', '-p', 'ExecStart', '--value'],
    capture_output=True, text=True, check=False
)
if proc_exec.returncode != 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Запрос ExecStart службы через systemctl завершился сбоем (exit != 0)!', file=sys.stderr)
    sys.exit(1)

current_exec_handle = proc_exec.stdout.strip()
if not current_exec_handle:
    print('КРИТИЧЕСКАЯ ОШИБКА: systemctl show вернул пустой текущий ExecStart службы!', file=sys.stderr)
    sys.exit(1)

def parse_and_validate_exec(exec_str: str, work_dir: pathlib.Path, label: str, is_current: bool = False) -> tuple[pathlib.Path, str]:
    if not isinstance(exec_str, str) or not exec_str.strip():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: ExecStart для {label} пуст!', file=sys.stderr)
        sys.exit(1)
    cmdline = exec_str.strip()
    structured_path = None
    if cmdline.startswith('{'):
        inner = cmdline.strip('{} \n\t')
        props = {}
        for part in inner.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                props[k.strip()] = v.strip()
        argv_val = props.get('argv[]') or props.get('argv')
        if not argv_val:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый синтаксис systemctl ExecStart для {label}: {cmdline}', file=sys.stderr)
            sys.exit(1)
        structured_path = props.get('path')
        if not structured_path:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый синтаксис systemctl ExecStart для {label}: {cmdline}', file=sys.stderr)
            sys.exit(1)
        cmdline = argv_val

    try:
        tokens = shlex.split(cmdline)
    except Exception as err:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка разбора ExecStart для {label}: {err}', file=sys.stderr)
        sys.exit(1)
    if not tokens:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Токены ExecStart для {label} пусты!', file=sys.stderr)
        sys.exit(1)
    for tok in tokens:
        if any(c in tok for c in [';', '&', '|', chr(96), chr(36), '\n']):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Обнаружены запрещённые метасимволы в ExecStart для {label}: {tok}', file=sys.stderr)
            sys.exit(1)

    argv0 = tokens[0]
    if structured_path:
        if structured_path != argv0 and pathlib.Path(structured_path).name != pathlib.Path(argv0).name:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Несовпадение path={structured_path} и argv[0]={argv0} в ExecStart для {label}!', file=sys.stderr)
            sys.exit(1)

    interp_name = pathlib.Path(structured_path if structured_path else argv0).name
    if not re.match(r'^python(?:[23](?:\.\d+)?)?$', interp_name):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый интерпретатор {interp_name} в ExecStart для {label} (ожидается python)!', file=sys.stderr)
        sys.exit(1)

    script_tok = None
    idx = 1
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in ('-c', '-m', '-') or tok.startswith(('-c', '-m')):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый флаг запуска Python ({tok}) в ExecStart для {label}!', file=sys.stderr)
            sys.exit(1)
        if tok.startswith('-'):
            if tok == '-W' and idx + 1 < len(tokens):
                idx += 2
                continue
            elif re.match(r'^-([uBOvEs]|OO|W\w+)$', tok):
                idx += 1
                continue
            else:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемая опция Python ({tok}) в ExecStart для {label}!', file=sys.stderr)
                sys.exit(1)
        else:
            script_tok = tok
            break

    if not script_tok:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Не найден скрипт entrypoint (.py/.sh) в ExecStart для {label}!', file=sys.stderr)
        sys.exit(1)
    if not (script_tok.endswith('.py') or script_tok.endswith('.sh')):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entrypoint {script_tok} для {label} не является .py/.sh скриптом!', file=sys.stderr)
        sys.exit(1)

    p_tok = pathlib.Path(script_tok)
    p_abs = p_tok if p_tok.is_absolute() else work_dir / p_tok
    if '..' in p_abs.parts or '.' in p_abs.parts or os.path.normpath(str(p_abs)) != str(p_abs):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} содержит .. или не каноничен!', file=sys.stderr)
        sys.exit(1)
    try:
        if not p_abs.resolve().is_relative_to(work_dir.resolve()):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} не принадлежит каталогу релиза {work_dir}!', file=sys.stderr)
            sys.exit(1)
    except Exception:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка сопоставления entry point {script_tok} с каталогом {work_dir}!', file=sys.stderr)
        sys.exit(1)
    if p_abs.is_symlink() or os.path.islink(str(p_abs)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {p_abs} для {label} является symlink!', file=sys.stderr)
        sys.exit(1)
    cur = p_abs.parent
    while cur != work_dir and cur != cur.parent:
        if cur.is_symlink() or os.path.islink(str(cur)):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Промежуточный узел entry point {cur} является symlink!', file=sys.stderr)
            sys.exit(1)
        cur = cur.parent

    if is_current:
        if not p_abs.exists() or not p_abs.is_file():
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} отсутствует на диске или не является файлом!', file=sys.stderr)
            sys.exit(1)

    rel_entry = str(p_abs.relative_to(work_dir))
    return p_abs, rel_entry

current_exec_entry, current_exec_rel = parse_and_validate_exec(current_exec_handle, current_path, 'текущей службы', is_current=True)
saved_exec_entry, saved_exec_rel = parse_and_validate_exec(unit_exec_start, dest_path, 'сохранённого unit', is_current=False)

code_dir = backup_dir / 'code'
if code_dir.is_symlink() or os.path.islink(str(code_dir)) or not code_dir.is_dir():
    print('КРИТИЧЕСКАЯ ОШИБКА: Каталог кода отсутствует или является symlink!', file=sys.stderr)
    sys.exit(1)

cur = code_dir
while True:
    if cur.is_symlink() or os.path.islink(str(cur)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Узел {cur} является symlink!', file=sys.stderr)
        sys.exit(1)
    if cur == cur.parent:
        break
    cur = cur.parent

disk_files = {}
for root_path, dirs, files in os.walk(code_dir, followlinks=False):
    r_path = pathlib.Path(root_path)
    if r_path.is_symlink() or os.path.islink(str(r_path)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Подкаталог {r_path} является symlink!', file=sys.stderr)
        sys.exit(1)
    with os.scandir(root_path) as it:
        for entry in it:
            try:
                st = entry.stat(follow_symlinks=False)
            except Exception as err:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка чтения статуса {entry.name}: {err}', file=sys.stderr)
                sys.exit(1)
            if stat.S_ISLNK(st.st_mode):
                print(f'КРИТИЧЕСКАЯ ОШИБКА: В бэкапе обнаружен недопустимый symlink: {entry.name}', file=sys.stderr)
                sys.exit(1)
            elif stat.S_ISDIR(st.st_mode):
                continue
            elif stat.S_ISREG(st.st_mode):
                p_entry = pathlib.Path(entry.path)
                try:
                    rel = p_entry.resolve().relative_to(code_dir.resolve())
                except ValueError:
                    print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {entry.name} выходит за пределы каталога бэкапа (path traversal)!', file=sys.stderr)
                    sys.exit(1)
                rel_str = str(p_entry.relative_to(code_dir))
                disk_files[rel_str] = hashlib.sha256(p_entry.read_bytes()).hexdigest()
            else:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Обнаружен неподдерживаемый специальный тип файла: {entry.name} (mode {oct(st.st_mode)})', file=sys.stderr)
                sys.exit(1)

manifest_files = meta['files']
if set(disk_files.keys()) != set(manifest_files.keys()):
    extra = set(disk_files.keys()) - set(manifest_files.keys())
    missing = set(manifest_files.keys()) - set(disk_files.keys())
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Нарушена биекция disk <-> manifest! Лишние: {extra}, отсутствующие: {missing}', file=sys.stderr)
    sys.exit(1)

if len(disk_files) != count_val:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Число файлов кода ({len(disk_files)}) не совпадает с манифестом ({count_val})!', file=sys.stderr)
    sys.exit(1)

for rel_str, exp_hash in manifest_files.items():
    if disk_files.get(rel_str) != exp_hash:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Хэш файла {rel_str} не совпадает с манифестом!', file=sys.stderr)
        sys.exit(1)

if saved_exec_rel not in disk_files:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Точка входа {saved_exec_rel} из ExecStart отсутствует в восстанавливаемом коде!', file=sys.stderr)
    sys.exit(1)

# X4: Статический офлайн-контроль зависимостей точки входа в бэкапе
entrypoint_disk = code_dir / saved_exec_rel
if entrypoint_disk.suffix == '.py':
    def find_backup_imports(script_path: pathlib.Path, root_dir: pathlib.Path) -> set[str]:
        needed = set()
        visited = set()
        queue = [script_path]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            try:
                tree = ast.parse(curr.read_text(encoding='utf-8'), filename=str(curr))
            except Exception:
                continue
            for node in ast.walk(tree):
                mod_names = []
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_names.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mod_names.append(node.module)
                for mod in mod_names:
                    lead = mod.split('.')[0]
                    cand = root_dir / (lead + '.py')
                    if cand.exists() and cand.is_file():
                        rel = str(cand.relative_to(root_dir))
                        if rel not in needed:
                            needed.add(rel)
                            queue.append(cand)
        return needed

    needed_deps = find_backup_imports(entrypoint_disk, code_dir)
    missing_deps = needed_deps - set(disk_files.keys())
    if missing_deps:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: В инвентаре бэкапа отсутствуют обязательные локальные зависимости {sorted(missing_deps)}!', file=sys.stderr)
        sys.exit(1)

FORBIDDEN_SECRET_PATTERNS = {'.env', 'token', 'secret', 'credential', '.pem', '.key'}
for p in backup_dir.rglob('*'):
    if p.is_file():
        name_lower = p.name.lower()
        if any(pat in name_lower for pat in FORBIDDEN_SECRET_PATTERNS):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: В бэкапе обнаружен недопустимый секретный файл: {p.name}', file=sys.stderr)
            sys.exit(1)

# Done preflight before stop
" "$PINNED_BACKUP_DIR"

# 3. Остановка службы ТОЛЬКО ПОСЛЕ ПОДТВЕРЖДЁННОЙ ВАЛИДАЦИИ БЭКАПА
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
export PINNED_BACKUP_DIR

if [ -z "$PINNED_BACKUP_DIR" ] || [ ! -d "$PINNED_BACKUP_DIR" ]; then
    echo "КРИТИЧЕСКАЯ ОШИБКА: Каталог pinned-бэкапа не найден! Откат заблокирован fail-closed." >&2
    exit 1
fi

# 2. Комплексная верификация бэкапа ДО ПЕРВОЙ МУТАЦИИ (fail-closed)
# Сверяются в границах поддержанной модели unit службы:
# - обязательный манифест pinned_metadata.json и хэш unit-файла (unit_sha256);
# - непустое отображение files, strict count (int, не bool), отсутствие секретов;
# - строгая биекция disk <-> manifest, проверка регулярных файлов (запрет symlink/fifo/device);
# - каноничность путей назначения и текущей службы (проверка отсутствия .. и неканонических сегментов,
#   принадлежность разрешённым корням HOME или /srv/star-building-strategy, отсутствие symlink всех предков до /);
# - существование целевого каталога назначения;
# - валидация WorkingDirectory и ExecStart identity текущей службы через systemctl show и сохранённого unit
#   (привязка исполняемой точки входа к рабочему каталогу, запрет symlink и метасимволов);
# - статическая проверка наличия локальных модулей-зависимостей точки входа в инвентаре бэкапа.
# Проверенные несоответствия вызывают отказ (exit 1) с 0 системных мутаций.
python3 -c "
import ast, hashlib, json, os, pathlib, re, shlex, stat, subprocess, sys

backup_dir_raw = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else os.environ.get('PINNED_BACKUP_DIR', '')
if not backup_dir_raw:
    print('КРИТИЧЕСКАЯ ОШИБКА: PINNED_BACKUP_DIR не задан!', file=sys.stderr)
    sys.exit(1)

backup_dir = pathlib.Path(backup_dir_raw)

# W1: Проверка абсолютности пути бэкапа и проверка ВСЕХ предков до корня / ДО открытия metadata/unit
if not backup_dir.is_absolute():
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь бэкапа ({backup_dir}) не является абсолютным!', file=sys.stderr)
    sys.exit(1)

cur = backup_dir
while True:
    if cur.is_symlink() or os.path.islink(str(cur)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Узел {cur} является symlink!', file=sys.stderr)
        sys.exit(1)
    if not cur.exists():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Компонент пути бэкапа {cur} не существует!', file=sys.stderr)
        sys.exit(1)
    if cur == cur.parent:
        break
    cur = cur.parent

meta_path = backup_dir / 'pinned_metadata.json'
if not meta_path.is_file() or meta_path.is_symlink() or os.path.islink(str(meta_path)):
    print('КРИТИЧЕСКАЯ ОШИБКА: Обязательный манифест pinned_metadata.json отсутствует или является symlink!', file=sys.stderr)
    sys.exit(1)

try:
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
except Exception as err:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Манифест pinned_metadata.json повреждён: {err}', file=sys.stderr)
    sys.exit(1)

required_fields = {'unit_sha256', 'code_files_count', 'live_work_dir', 'files'}
missing_fields = required_fields - set(meta.keys())
if missing_fields:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: В манифесте отсутствуют обязательные поля: {missing_fields}', file=sys.stderr)
    sys.exit(1)

count_val = meta.get('code_files_count')
if type(count_val) is not int or isinstance(count_val, bool) or count_val <= 0:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: code_files_count обязан быть положительным целым числом (int, не bool), получено: {type(count_val).__name__} ({count_val})!', file=sys.stderr)
    sys.exit(1)

if not isinstance(meta.get('files'), dict) or len(meta['files']) == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Поле files в манифесте обязано быть непустым отображением!', file=sys.stderr)
    sys.exit(1)

unit_path = backup_dir / 'star-building-strategy.service'
if not unit_path.is_file() or unit_path.is_symlink() or os.path.islink(str(unit_path)) or unit_path.stat().st_size == 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Unit-файл в бэкапе отсутствует, является symlink или пуст!', file=sys.stderr)
    sys.exit(1)

actual_unit_sha = hashlib.sha256(unit_path.read_bytes()).hexdigest()
exp_unit_sha = str(meta.get('unit_sha256', ''))
if actual_unit_sha != exp_unit_sha:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Хэш unit-файла ({actual_unit_sha}) не совпадает с манифестом ({exp_unit_sha})!', file=sys.stderr)
    sys.exit(1)

unit_lines = unit_path.read_text(encoding='utf-8').splitlines()
unit_work_dir = None
unit_exec_start = None
for line in unit_lines:
    line = line.strip()
    if line.startswith('WorkingDirectory='):
        unit_work_dir = line.split('=', 1)[1].strip()
    elif line.startswith('ExecStart='):
        unit_exec_start = line.split('=', 1)[1].strip()

if not unit_work_dir:
    print('КРИТИЧЕСКАЯ ОШИБКА: В сохранённом unit-файле отсутствует WorkingDirectory!', file=sys.stderr)
    sys.exit(1)

pinned_work_dir = str(meta.get('live_work_dir', '')).strip()
if not pinned_work_dir:
    print('КРИТИЧЕСКАЯ ОШИБКА: В манифесте бэкапа отсутствует валидный live_work_dir!', file=sys.stderr)
    sys.exit(1)

if pinned_work_dir != unit_work_dir:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: live_work_dir из манифеста ({pinned_work_dir}) не совпадает с WorkingDirectory сохранённого unit ({unit_work_dir})!', file=sys.stderr)
    sys.exit(1)

home_dir = pathlib.Path(os.environ.get('HOME', '/home/roman'))
approved_roots = [
    home_dir,
    pathlib.Path('/srv/star-building-strategy'),
]

# X1: Каноническая проверка approved roots (без .. и неканонических сегментов)
def check_approved_root(target_raw: str, label: str) -> pathlib.Path:
    if not isinstance(target_raw, str) or not target_raw.strip():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} пуст!', file=sys.stderr)
        sys.exit(1)
    target_str = target_raw.strip()
    target = pathlib.Path(target_str)
    if not target.is_absolute():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} ({target_str}) не является абсолютным!', file=sys.stderr)
        sys.exit(1)
    if '..' in target.parts or '.' in target.parts or os.path.normpath(target_str) != target_str:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} ({target_str}) содержит .. или неканонические сегменты!', file=sys.stderr)
        sys.exit(1)
    if not target.exists() or not target.is_dir():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Каталог {label} ({target}) не существует или не является каталогом!', file=sys.stderr)
        sys.exit(1)
    cur = target
    while True:
        if cur.is_symlink() or os.path.islink(str(cur)):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Компонент пути {label} {cur} является symlink!', file=sys.stderr)
            sys.exit(1)
        if cur == cur.parent:
            break
        cur = cur.parent
    in_approved = False
    for r in approved_roots:
        try:
            if target.resolve().is_relative_to(r.resolve()):
                in_approved = True
                break
        except Exception:
            pass
    if not in_approved:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Путь {label} ({target}) не входит в список разрешённых корней релиза!', file=sys.stderr)
        sys.exit(1)
    return target

dest_path = check_approved_root(unit_work_dir, 'назначения (старого релиза)')

proc_wd = subprocess.run(
    ['systemctl', '--user', 'show', 'star-building-strategy.service', '-p', 'WorkingDirectory', '--value'],
    capture_output=True, text=True, check=False
)
if proc_wd.returncode != 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Запрос состояния службы через systemctl завершился сбоем (exit != 0)!', file=sys.stderr)
    sys.exit(1)

current_handle = proc_wd.stdout.strip()
if not current_handle:
    print('КРИТИЧЕСКАЯ ОШИБКА: systemctl show вернул пустой текущий WorkingDirectory службы!', file=sys.stderr)
    sys.exit(1)

current_path = check_approved_root(current_handle, 'текущей службы')

# X2: Запрос и строгая проверка текущего и сохранённого ExecStart identity
proc_exec = subprocess.run(
    ['systemctl', '--user', 'show', 'star-building-strategy.service', '-p', 'ExecStart', '--value'],
    capture_output=True, text=True, check=False
)
if proc_exec.returncode != 0:
    print('КРИТИЧЕСКАЯ ОШИБКА: Запрос ExecStart службы через systemctl завершился сбоем (exit != 0)!', file=sys.stderr)
    sys.exit(1)

current_exec_handle = proc_exec.stdout.strip()
if not current_exec_handle:
    print('КРИТИЧЕСКАЯ ОШИБКА: systemctl show вернул пустой текущий ExecStart службы!', file=sys.stderr)
    sys.exit(1)

def parse_and_validate_exec(exec_str: str, work_dir: pathlib.Path, label: str, is_current: bool = False) -> tuple[pathlib.Path, str]:
    if not isinstance(exec_str, str) or not exec_str.strip():
        print(f'КРИТИЧЕСКАЯ ОШИБКА: ExecStart для {label} пуст!', file=sys.stderr)
        sys.exit(1)
    cmdline = exec_str.strip()
    structured_path = None
    if cmdline.startswith('{'):
        inner = cmdline.strip('{} \n\t')
        props = {}
        for part in inner.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                props[k.strip()] = v.strip()
        argv_val = props.get('argv[]') or props.get('argv')
        if not argv_val:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый синтаксис systemctl ExecStart для {label}: {cmdline}', file=sys.stderr)
            sys.exit(1)
        structured_path = props.get('path')
        if not structured_path:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый синтаксис systemctl ExecStart для {label}: {cmdline}', file=sys.stderr)
            sys.exit(1)
        cmdline = argv_val

    try:
        tokens = shlex.split(cmdline)
    except Exception as err:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка разбора ExecStart для {label}: {err}', file=sys.stderr)
        sys.exit(1)
    if not tokens:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Токены ExecStart для {label} пусты!', file=sys.stderr)
        sys.exit(1)
    for tok in tokens:
        if any(c in tok for c in [';', '&', '|', chr(96), chr(36), '\n']):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Обнаружены запрещённые метасимволы в ExecStart для {label}: {tok}', file=sys.stderr)
            sys.exit(1)

    argv0 = tokens[0]
    if structured_path:
        if structured_path != argv0 and pathlib.Path(structured_path).name != pathlib.Path(argv0).name:
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Несовпадение path={structured_path} и argv[0]={argv0} в ExecStart для {label}!', file=sys.stderr)
            sys.exit(1)

    interp_name = pathlib.Path(structured_path if structured_path else argv0).name
    if not re.match(r'^python(?:[23](?:\.\d+)?)?$', interp_name):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый интерпретатор {interp_name} в ExecStart для {label} (ожидается python)!', file=sys.stderr)
        sys.exit(1)

    script_tok = None
    idx = 1
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in ('-c', '-m', '-') or tok.startswith(('-c', '-m')):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемый флаг запуска Python ({tok}) в ExecStart для {label}!', file=sys.stderr)
            sys.exit(1)
        if tok.startswith('-'):
            if tok == '-W' and idx + 1 < len(tokens):
                idx += 2
                continue
            elif re.match(r'^-([uBOvEs]|OO|W\w+)$', tok):
                idx += 1
                continue
            else:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Неподдерживаемая опция Python ({tok}) в ExecStart для {label}!', file=sys.stderr)
                sys.exit(1)
        else:
            script_tok = tok
            break

    if not script_tok:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Не найден скрипт entrypoint (.py/.sh) в ExecStart для {label}!', file=sys.stderr)
        sys.exit(1)
    if not (script_tok.endswith('.py') or script_tok.endswith('.sh')):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entrypoint {script_tok} для {label} не является .py/.sh скриптом!', file=sys.stderr)
        sys.exit(1)

    p_tok = pathlib.Path(script_tok)
    p_abs = p_tok if p_tok.is_absolute() else work_dir / p_tok
    if '..' in p_abs.parts or '.' in p_abs.parts or os.path.normpath(str(p_abs)) != str(p_abs):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} содержит .. или не каноничен!', file=sys.stderr)
        sys.exit(1)
    try:
        if not p_abs.resolve().is_relative_to(work_dir.resolve()):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} не принадлежит каталогу релиза {work_dir}!', file=sys.stderr)
            sys.exit(1)
    except Exception:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка сопоставления entry point {script_tok} с каталогом {work_dir}!', file=sys.stderr)
        sys.exit(1)
    if p_abs.is_symlink() or os.path.islink(str(p_abs)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {p_abs} для {label} является symlink!', file=sys.stderr)
        sys.exit(1)
    cur = p_abs.parent
    while cur != work_dir and cur != cur.parent:
        if cur.is_symlink() or os.path.islink(str(cur)):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Промежуточный узел entry point {cur} является symlink!', file=sys.stderr)
            sys.exit(1)
        cur = cur.parent

    if is_current:
        if not p_abs.exists() or not p_abs.is_file():
            print(f'КРИТИЧЕСКАЯ ОШИБКА: Entry point {script_tok} для {label} отсутствует на диске или не является файлом!', file=sys.stderr)
            sys.exit(1)

    rel_entry = str(p_abs.relative_to(work_dir))
    return p_abs, rel_entry

current_exec_entry, current_exec_rel = parse_and_validate_exec(current_exec_handle, current_path, 'текущей службы', is_current=True)
saved_exec_entry, saved_exec_rel = parse_and_validate_exec(unit_exec_start, dest_path, 'сохранённого unit', is_current=False)

code_dir = backup_dir / 'code'
if code_dir.is_symlink() or os.path.islink(str(code_dir)) or not code_dir.is_dir():
    print('КРИТИЧЕСКАЯ ОШИБКА: Каталог кода отсутствует или является symlink!', file=sys.stderr)
    sys.exit(1)

cur = code_dir
while True:
    if cur.is_symlink() or os.path.islink(str(cur)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Узел {cur} является symlink!', file=sys.stderr)
        sys.exit(1)
    if cur == cur.parent:
        break
    cur = cur.parent

disk_files = {}
for root_path, dirs, files in os.walk(code_dir, followlinks=False):
    r_path = pathlib.Path(root_path)
    if r_path.is_symlink() or os.path.islink(str(r_path)):
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Подкаталог {r_path} является symlink!', file=sys.stderr)
        sys.exit(1)
    with os.scandir(root_path) as it:
        for entry in it:
            try:
                st = entry.stat(follow_symlinks=False)
            except Exception as err:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Ошибка чтения статуса {entry.name}: {err}', file=sys.stderr)
                sys.exit(1)
            if stat.S_ISLNK(st.st_mode):
                print(f'КРИТИЧЕСКАЯ ОШИБКА: В бэкапе обнаружен недопустимый symlink: {entry.name}', file=sys.stderr)
                sys.exit(1)
            elif stat.S_ISDIR(st.st_mode):
                continue
            elif stat.S_ISREG(st.st_mode):
                p_entry = pathlib.Path(entry.path)
                try:
                    rel = p_entry.resolve().relative_to(code_dir.resolve())
                except ValueError:
                    print(f'КРИТИЧЕСКАЯ ОШИБКА: Файл {entry.name} выходит за пределы каталога бэкапа (path traversal)!', file=sys.stderr)
                    sys.exit(1)
                rel_str = str(p_entry.relative_to(code_dir))
                disk_files[rel_str] = hashlib.sha256(p_entry.read_bytes()).hexdigest()
            else:
                print(f'КРИТИЧЕСКАЯ ОШИБКА: Обнаружен неподдерживаемый специальный тип файла: {entry.name} (mode {oct(st.st_mode)})', file=sys.stderr)
                sys.exit(1)

manifest_files = meta['files']
if set(disk_files.keys()) != set(manifest_files.keys()):
    extra = set(disk_files.keys()) - set(manifest_files.keys())
    missing = set(manifest_files.keys()) - set(disk_files.keys())
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Нарушена биекция disk <-> manifest! Лишние: {extra}, отсутствующие: {missing}', file=sys.stderr)
    sys.exit(1)

if len(disk_files) != count_val:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Число файлов кода ({len(disk_files)}) не совпадает с манифестом ({count_val})!', file=sys.stderr)
    sys.exit(1)

for rel_str, exp_hash in manifest_files.items():
    if disk_files.get(rel_str) != exp_hash:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: Хэш файла {rel_str} не совпадает с манифестом!', file=sys.stderr)
        sys.exit(1)

if saved_exec_rel not in disk_files:
    print(f'КРИТИЧЕСКАЯ ОШИБКА: Точка входа {saved_exec_rel} из ExecStart отсутствует в восстанавливаемом коде!', file=sys.stderr)
    sys.exit(1)

# X4: Статический офлайн-контроль зависимостей точки входа в бэкапе
entrypoint_disk = code_dir / saved_exec_rel
if entrypoint_disk.suffix == '.py':
    def find_backup_imports(script_path: pathlib.Path, root_dir: pathlib.Path) -> set[str]:
        needed = set()
        visited = set()
        queue = [script_path]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            try:
                tree = ast.parse(curr.read_text(encoding='utf-8'), filename=str(curr))
            except Exception:
                continue
            for node in ast.walk(tree):
                mod_names = []
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_names.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mod_names.append(node.module)
                for mod in mod_names:
                    lead = mod.split('.')[0]
                    cand = root_dir / (lead + '.py')
                    if cand.exists() and cand.is_file():
                        rel = str(cand.relative_to(root_dir))
                        if rel not in needed:
                            needed.add(rel)
                            queue.append(cand)
        return needed

    needed_deps = find_backup_imports(entrypoint_disk, code_dir)
    missing_deps = needed_deps - set(disk_files.keys())
    if missing_deps:
        print(f'КРИТИЧЕСКАЯ ОШИБКА: В инвентаре бэкапа отсутствуют обязательные локальные зависимости {sorted(missing_deps)}!', file=sys.stderr)
        sys.exit(1)

FORBIDDEN_SECRET_PATTERNS = {'.env', 'token', 'secret', 'credential', '.pem', '.key'}
for p in backup_dir.rglob('*'):
    if p.is_file():
        name_lower = p.name.lower()
        if any(pat in name_lower for pat in FORBIDDEN_SECRET_PATTERNS):
            print(f'КРИТИЧЕСКАЯ ОШИБКА: В бэкапе обнаружен недопустимый секретный файл: {p.name}', file=sys.stderr)
            sys.exit(1)

print('Верификация бэкапа успешно пройдена: все хэши и инвентарь подтверждены fail-closed.')
" "$PINNED_BACKUP_DIR"

# 3. Атомарное восстановление unit-файла службы
TARGET_UNIT_PATH="${HOME}/.config/systemd/user/star-building-strategy.service"
mkdir -p "${HOME}/.config/systemd/user"
cp -p "$PINNED_BACKUP_DIR/star-building-strategy.service" "$TARGET_UNIT_PATH"
systemctl --user daemon-reload

# 4. Восстановление рабочего каталога кода строго в подтверждённый pinned каталог
# U5 / V3 / V5: Без опасного флага --delete; целевой каталог привязан к проверенному unit-файлу
TARGET_WORK_DIR=$(python3 -c "import pathlib, os, sys; lines = (pathlib.Path(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else os.environ['PINNED_BACKUP_DIR']) / 'star-building-strategy.service').read_text().splitlines(); print(next(l.split('=', 1)[1].strip() for l in lines if l.startswith('WorkingDirectory=')))" "$PINNED_BACKUP_DIR")
if [ -n "$TARGET_WORK_DIR" ] && [ -d "$PINNED_BACKUP_DIR/code" ] && [ ! -L "$TARGET_WORK_DIR" ]; then
    mkdir -p "$TARGET_WORK_DIR"
    rsync -a "$PINNED_BACKUP_DIR/code/" "$TARGET_WORK_DIR/"
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
