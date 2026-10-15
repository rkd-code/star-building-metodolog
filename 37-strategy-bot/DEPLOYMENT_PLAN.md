# Офлайн-план развертывания расширения P-026 для @Dramknote_bot (FN-014)

Данный документ представляет собой контролируемый офлайн-план точного развертывания и безопасного отката (deployment & rollback) расширения P-026 для стратегического штаба «Драмкнот» (компонент `37-strategy-bot`).
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
   - Автоматический карантин пустых (0 байт) и структурно невалидных журналов решений без перезаписи.
2. `37-strategy-bot/p026_handler.py` — обработчик диалога и экспорта:
   - Предметная валидация управленческих решений владельца;
   - Отклонение любых общих и неоднозначных согласий («да я согласен», «согласен с этим», «подтверждаю всё вышеизложенное», «ок принято»);
   - Runtime gate: обязательная верификация манифеста 30 источников перед генерацией статуса `/project` и экспортом черновиков (fail-closed отказ при повреждении);
   - Безопасный экспорт версионных черновиков с наложением изолированных решений актора.
3. `37-strategy-bot/p026_subject_base.py` — предметная база нормативных знаний P-026:
   - Неизменяемый нормативный манифест 30 канонических файлов с эталонными хэшами SHA-256 и размерами;
   - Метод `verify_all_sources()` со строгим контролем каждого файла;
   - Интеграция реальных подтверждённых выдержек и решений владельца из канонических файлов (каталоги 107, 109) в модельный контекст вместо статической заглушки;
   - Нормативные лимиты скидок v0.6 и ответы РОП 109.
4. `37-strategy-bot/strategy_bot.py` — стратегический сервис @Dramknote_bot:
   - Строгая chat boundary: отклонение любых сообщений и callbacks из групповых чатов до обращения к модели и истории;
   - Раздельная история диалогов по связке `(user_id, chat_id)`;
   - Runtime gate проверки целостности нормативного корпуса перед формированием системного промпта;
   - Бинарная отправка файлов документов через `reply_document`/`send_document` (I/O streaming).
5. `37-strategy-bot/systemd/star-building-strategy.service` — unit-файл службы systemd:
   - Изоляция песочницы: `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp=true`, `NoNewPrivileges=true`;
   - Согласованные пути runtime: `ReadWritePaths=/home/roman/.local/share/star-building/dramknote-p026`, `StateDirectory=star-building/dramknote-p026`, `DRAMKNOTE_P026_STORAGE_DIR=/home/roman/.local/share/star-building/dramknote-p026`;
   - Ссылка на развернутый релиз.
6. `37-strategy-bot/README.md` — эксплуатационная документация с точным описанием границ изоляции и формата ID.
7. `37-strategy-bot/DEPLOYMENT_PLAN.md` — настоящий план точного развертывания и безопасного отката.

### Тестовый комплекс (100% PASS, 70 тестов):
8. `37-strategy-bot/test_p026_storage.py` — unit-тесты хранилища (конкурентность, реентерабельность, карантин пустого и повреждённого журнала, actor/chat изоляция, отрицательные chat ID);
9. `37-strategy-bot/test_p026_handler.py` — unit-тесты обработчика (отклонение вариаций согласий, runtime gate манифеста, изоляция экспорта);
10. `37-strategy-bot/test_p026_subject_base.py` — unit-тесты предметной базы (манифест 30 источников, правила скидок, чтение проверенных файлов);
11. `37-strategy-bot/test_p026_security.py` — security-тесты (symlink предков, lock-атаки, отсутствие side-effects до отказа, path traversal, неизменность SHA-256 источников, скан секретов);
12. `37-strategy-bot/test_p026_integration.py` — интеграционные тесты (блокировка групповых сообщений, runtime gate промпта, реальное чтение источников, бинарная отправка документов Telegram);
13. `37-strategy-bot/test_strategy_bot.py` — регрессионные тесты hardened-службы и отрицательный тест-гард чистоты `$HOME/.local/share`;
14. `37-strategy-bot/test_strategy_healthcheck.py` — тесты диагностического модуля.

### Архитектурная документация и реестры:
15. `DATA_MODEL.md` — точное описание сущностей решений (us-timestamp), версионных черновиков, fail-closed unowned правил и манифеста 30 источников;
16. `DECISIONS.md` — архитектурная фиксация решений ADR-028 (устранение findings R1–R7);
17. `KNOWLEDGE_BASE.md` — актуализация регламентов коммерческого департамента P-026 и штаба @Dramknote_bot;
18. `PROJECT_MANIFEST.json` — обновлённый машиночитаемый реестр репозитория;
19. `PROJECT_STRUCTURE.md` — обновлённая структура репозитория;
20. `graphify-out/` — актуализированный граф связей базы знаний (1053 узла, 1395 рёбер).

---

## 2. Предварительные условия и подготовка окружения (Pre-flight & Provisioning)

Перед развертыванием оператор обязан проверить выполнение следующих условий:

1. **Сервер:** рабочий хост Star Building (`/home/roman`).
2. **Пользователь:** `roman` (без запроса root/sudo).
3. **Виртуальное окружение Python:** `/srv/hermes-agent/venv/bin/python3` (версия Python >= 3.11).
4. **Конфигурация:** файл `/home/roman/.config/star-building/strategy-bot.env` (права `0600`). Используется существующий авторизованный токен `@Dramknote_bot`. Новые токены не выпускаются.
5. **Подготовка директории состояния (Provisioning):**
   ```bash
   # Создание структуры каталогов runtime state с безопасными правами доступа (0700)
   mkdir -p /home/roman/.local/share/star-building/dramknote-p026/decisions
   mkdir -p /home/roman/.local/share/star-building/dramknote-p026/drafts
   chmod 700 /home/roman/.local/share/star-building/dramknote-p026
   chmod 700 /home/roman/.local/share/star-building/dramknote-p026/decisions
   chmod 700 /home/roman/.local/share/star-building/dramknote-p026/drafts
   ```
6. **Согласование путей (State Directory Harmonization):**
   - Переменная окружения: `DRAMKNOTE_P026_STORAGE_DIR=/home/roman/.local/share/star-building/dramknote-p026`;
   - Песочница systemd: `ReadWritePaths=/home/roman/.local/share/star-building/dramknote-p026`;
   - Директива systemd: `StateDirectory=star-building/dramknote-p026` гармонизирована через символическую связь или прямой путь к XDG shared storage.
7. **Каталог релизов:**
   ```bash
   mkdir -p /home/roman/srv/star-building-strategy/releases
   mkdir -p /home/roman/srv/star-building-strategy/backups
   ```

---

## 3. Пошаговая процедура точного развертывания (Exact Release Deployment)

Процедура выполняется **только** при наличии явного письменного решения лорда Витинари.

### Шаг 1. Верификация принятого коммита и архива
```bash
TARGET_COMMIT="<ACCEPTED_COMMIT_SHA>"
EXPECTED_TREE="<EXPECTED_TREE_SHA>"
EXPECTED_ARCHIVE_SHA="<EXPECTED_ARCHIVE_SHA256>"

cd /home/roman/.worktrees/t_7b954f30
ACTUAL_COMMIT=$(git rev-parse HEAD)
ACTUAL_TREE=$(git rev-parse HEAD^{tree})

if [ "$ACTUAL_COMMIT" != "$TARGET_COMMIT" ] || [ "$ACTUAL_TREE" != "$EXPECTED_TREE" ]; then
    echo "ОШИБКА: Несовпадение коммита или дерева кандидата!"
    exit 1
fi
```

### Шаг 2. Создание полного бэкапа работающего релиза ДО любых изменений
```bash
BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/roman/srv/star-building-strategy/backups/live_${BACKUP_TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

# 1. Бэкап активного unit-файла systemd
if [ -f ~/.config/systemd/user/star-building-strategy.service ]; then
    cp ~/.config/systemd/user/star-building-strategy.service "$BACKUP_DIR/star-building-strategy.service"
fi

# 2. Бэкап активного рабочего кода live-сервиса
if [ -d /home/roman/37-strategy-bot ]; then
    cp -a /home/roman/37-strategy-bot "$BACKUP_DIR/code"
fi

# 3. Бэкап конфигурации
if [ -f ~/.config/star-building/strategy-bot.env ]; then
    cp ~/.config/star-building/strategy-bot.env "$BACKUP_DIR/strategy-bot.env"
fi

# 4. Сохранение снимка состояния runtime (decisions и drafts)
if [ -d ~/.local/share/star-building/dramknote-p026 ]; then
    cp -a ~/.local/share/star-building/dramknote-p026 "$BACKUP_DIR/state"
fi

echo "Бэкап работающего релиза успешно сохранён в $BACKUP_DIR"
```

### Шаг 3. Развертывание кода кандидата в версионный каталог релиза
```bash
RELEASE_DIR="/home/roman/srv/star-building-strategy/releases/${TARGET_COMMIT}"
mkdir -p "$RELEASE_DIR"

# Экспорт чистого снимка компонента из принятого коммита
git archive --format=tar "$TARGET_COMMIT" 37-strategy-bot | tar -x -C "$RELEASE_DIR"

# Проверка контрольных сумм распакованных файлов
python3 -c "
import hashlib, pathlib
r = pathlib.Path('$RELEASE_DIR/37-strategy-bot')
print(f'Развернуто файлов: {len(list(r.rglob(\"*\")))}')
"

# Атомарное обновление рабочего каталога кода
# Копирование чистого верифицированного кода в рабочий путь сервиса
rsync -a --delete "$RELEASE_DIR/37-strategy-bot/" /home/roman/37-strategy-bot/
```

### Шаг 4. Установка проверенного unit-файла systemd
```bash
mkdir -p ~/.config/systemd/user
cp /home/roman/37-strategy-bot/systemd/star-building-strategy.service ~/.config/systemd/user/star-building-strategy.service
systemctl --user daemon-reload
```

### Шаг 5. Перезапуск службы
```bash
systemctl --user restart star-building-strategy.service
```

### Шаг 6. Контроль готовности и статуса (Post-Deployment Smoke Check)
```bash
# 1. Проверка статуса сервиса
systemctl --user is-active star-building-strategy.service

# 2. Проверка свежего журнала на отсутствие ошибок
journalctl --user -u star-building-strategy.service -n 50 --no-pager

# 3. Запуск встроенного healthcheck
/srv/hermes-agent/venv/bin/python3 /home/roman/37-strategy-bot/strategy_healthcheck.py
```

---

## 4. Процедура безопасного отката (Safe Rollback Procedure)

В случае обнаружения любых непредвиденных дефектов, регрессий или сбоев процедура отката восстанавливает **фактический снимок работающего релиза из бэкапа**, без вызова `git checkout` в корневом репозитории:

### Шаг 1. Остановка службы
```bash
systemctl --user stop star-building-strategy.service
```

### Шаг 2. Восстановление кода и unit-файла из live-бэкапа
```bash
# Идентификация последнего созданного бэкапа (или указание конкретного $BACKUP_DIR)
LATEST_BACKUP=$(ls -td /home/roman/srv/star-building-strategy/backups/live_* | head -n 1)

if [ ! -d "$LATEST_BACKUP" ]; then
    echo "КРИТИЧЕСКАЯ ОШИБКА: Каталог бэкапа $LATEST_BACKUP не найден!"
    exit 1
fi

echo "Восстановление состояния из бэкапа: $LATEST_BACKUP"

# 1. Восстановление unit-файла
if [ -f "$LATEST_BACKUP/star-building-strategy.service" ]; then
    cp "$LATEST_BACKUP/star-building-strategy.service" ~/.config/systemd/user/star-building-strategy.service
    systemctl --user daemon-reload
fi

# 2. Восстановление кода live-сервиса
if [ -d "$LATEST_BACKUP/code" ]; then
    rsync -a --delete "$LATEST_BACKUP/code/" /home/roman/37-strategy-bot/
fi

# 3. Восстановление конфигурации при необходимости
if [ -f "$LATEST_BACKUP/strategy-bot.env" ]; then
    cp "$LATEST_BACKUP/strategy-bot.env" ~/.config/star-building/strategy-bot.env
fi
```

### Шаг 3. Сохранность данных runtime
Существующий журнал решений и версионные черновики в `/home/roman/.local/share/star-building/dramknote-p026` сохраняются без удаления. При необходимости слияния или восстановления журнала решений используется файл `$LATEST_BACKUP/state/decisions/decisions.json`.

### Шаг 4. Запуск восстановленной службы и контроль
```bash
systemctl --user start star-building-strategy.service
systemctl --user status star-building-strategy.service
journalctl --user -u star-building-strategy.service -n 30 --no-pager
```

---

## 5. Политика ограничений безопасности

- **No Merge:** Ветка `work/dramknote-p026-handoff` не сливается в `main`/`master` в рамках данной задачи.
- **No Prod Restart:** В ходе разработки и приёмки перезапуск службы на боевом сервере запрещён.
- **No Costs:** Запрещены любые платные модельные вызовы или обращение к коммерческим внешним API.
- **No Credentials:** Запрещено чтение, запись, логирование или коммит секретов и токенов.
- **No ACL Mutation:** Запрещено изменение прав доступа файловой системы live-контура.
- **No Deletion Live State:** Самовольное удаление файлов из боевого каталога хранения запрещено.
