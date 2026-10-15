# Офлайн-план развертывания расширения P-026 для @Dramknote_bot (FN-014)

Данный документ представляет собой контролируемый офлайн-план развертывания расширения P-026 для стратегического бота «Драмкнот» (компонент `37-strategy-bot`).
План подготовлен разработчиком Пондером Стиббонсом в строгом соответствии с политикой **NoMergeProdRestartCostsCredentialsACL**.
Любые действия по живому развертыванию, смене конфигурации или перезапуску сервиса выполняются **исключительно по отдельному прямому решению лорда Витинари**.

---

## 1. Точный состав изменяемых файлов (Exact Files)

### Кодовая база компонента (37-strategy-bot):
1. `37-strategy-bot/p026_storage.py` — хранилище решений и версионных черновиков: межпроцессные блокировки `fcntl.flock` с таймаутом, реентерабельность, предотвращение дедлоков, микросекундная уникальность версий и ревизий, строгая fail-closed защита от symlink на всех уровнях, fsync;
2. `37-strategy-bot/p026_handler.py` — обработчик диалога: строгая actor/chat изоляция, отклонение неоднозначных согласий («согласен с этим», «ок принято», «всё верно»);
3. `37-strategy-bot/p026_subject_base.py` — предметная база знаний P-026: неизменяемый нормативный манифест 30 канонических источников (из передачи 108) с эталонными хэшами SHA-256, статусами и размерами, fail-closed проверка целостности при обращении, запрет генерации фиктивных шаблонов, правила скидок v0.6 и ответы РОП 109;
4. `37-strategy-bot/strategy_bot.py` — интеграция в штаб @Dramknote_bot: динамическая передача persistent решений конкретного актора в контролируемый модельный контекст (системный и пользовательский промпты), отправка реального версионного документа в Telegram через `reply_document`/`send_document` (бинарные байты), блокировка групповых чатов;
5. `37-strategy-bot/systemd/star-building-strategy.service` — кандидат unit-файла службы systemd: поддержка `ProtectHome=read-only`, `ReadWritePaths=/home/roman/.local/share/star-building/dramknote-p026`, `StateDirectory=star-building/dramknote-p026`, `DRAMKNOTE_P026_STORAGE_DIR`;
6. `37-strategy-bot/README.md` — очищенная документация компонента: удалены некорректные инструкции про создание новых ботов/токенов, зафиксирована архитектура единого сервиса @Dramknote_bot;
7. `37-strategy-bot/DEPLOYMENT_PLAN.md` — настоящий регламент развертывания и отката.

### Тестовый комплекс (изолированный 100% PASS suite):
8. `37-strategy-bot/test_p026_storage.py` — unit-тесты хранилища (конкурентная запись, реентерабельность блокировок, карантин поврежденного журнала, symlink fail-closed);
9. `37-strategy-bot/test_p026_handler.py` — unit-тесты обработчика (отклонение неоднозначных ответов, изоляция решений акторов, экспорт черновиков);
10. `37-strategy-bot/test_p026_subject_base.py` — unit-тесты предметной базы (манифест 30 источников, правила маржи/скидок, изоляция тестов);
11. `37-strategy-bot/test_p026_security.py` — security-тесты (матрица path traversal, symlink-атаки на родительские каталоги, неизменность SHA-256 источников, отсутствие секретов);
12. `37-strategy-bot/test_p026_integration.py` — интеграционные тесты бота (передача решений в промпт модели, отправка документа Telegram, запрет групповых чатов, изоляция сред через temporary directories);
13. `37-strategy-bot/test_strategy_bot.py` — регрессионные тесты hardened-службы и базовой функциональности;

### Системная документация и реестры:
14. `DATA_MODEL.md` — спецификация сущностей решений, черновиков, версионирования, манифеста 30 источников и actor isolation;
15. `DECISIONS.md` — актуализация ADR-028 с фиксацией устранения дефектов F1–F9;
16. `KNOWLEDGE_BASE.md` — актуализация раздела о штабе @Dramknote_bot и расширении P-026;
17. `PROJECT_MANIFEST.json` — обновленный машиночитаемый манифест репозитория;
18. `PROJECT_STRUCTURE.md` — обновленная структура репозитория;
19. `graphify-out/graph.json` — актуальный граф базы знаний проекта (1053 узла, 1395 ребер);
20. `graphify-out/graph.html` — автономная визуализация графа;
21. `graphify-out/GRAPH_REPORT.md` — отчет о связях и сообществах графа.

---

## 2. Предварительные условия для целевого контура (Pre-flight Requirements)

1. **Сервер:** рабочая станция / сервер Star Building (`/home/roman`).
2. **Служба systemd:** пользовательский сервис `star-building-strategy.service` под управлением пользователя `roman`.
3. **Хранилище runtime:** каталог `/home/roman/.local/share/star-building/dramknote-p026` с правами `0700` / `0755` владельца `roman:roman`.
4. **Конфигурация:** файл `/home/roman/.config/star-building/strategy-bot.env` (права `0600`). Новые токены не требуются; бот использует существующий токен `@Dramknote_bot`.
5. **Изоляция:** отсутствие необходимости изменения прав root/sudo или системных каталогов (`/etc`, `/var`).

---

## 3. Пошаговая процедура применения (только по решению владельца)

Шаги выполняются исключительно после официального согласования лордом Витинари:

### Шаг 1. Проверка контрольных сумм кандидата
```bash
cd /home/roman
git -C /home/roman/.worktrees/t_7b954f30 rev-parse HEAD
# Убедиться, что SHA коммита соответствует принятому ревизией коммиту
```

### Шаг 2. Обновление unit-файла службы systemd
```bash
cp /home/roman/.worktrees/t_7b954f30/37-strategy-bot/systemd/star-building-strategy.service ~/.config/systemd/user/star-building-strategy.service
systemctl --user daemon-reload
```

### Шаг 3. Перезапуск службы
```bash
systemctl --user restart star-building-strategy.service
```

### Шаг 4. Контроль готовности и статуса (Smoke Check)
```bash
systemctl --user status star-building-strategy.service
journalctl --user -u star-building-strategy.service -n 50 --no-pager
# Убедиться, что служба active (running), отсутствуют ошибки доступа к файлам и сбои авторизации
```

---

## 4. Процедура отката (Rollback Procedure)

В случае любых сбоев, регрессий или замечаний владельца:

### Шаг 1. Остановка обновленной службы
```bash
systemctl --user stop star-building-strategy.service
```

### Шаг 2. Восстановление исходного unit-файла
```bash
git checkout ddc5874c776f8e7d585a889a9866ff2bd516c6b1 -- 37-strategy-bot/systemd/star-building-strategy.service
cp 37-strategy-bot/systemd/star-building-strategy.service ~/.config/systemd/user/star-building-strategy.service
systemctl --user daemon-reload
```

### Шаг 3. Запуск стабильной версии службы
```bash
systemctl --user restart star-building-strategy.service
systemctl --user status star-building-strategy.service
```

### Шаг 4. Сохранение состояния хранилища runtime
Существующие пользовательские черновики и журнал решений в `~/.local/share/star-building/dramknote-p026` сохраняются без модификации и удаления. При необходимости создается резервная копия:
```bash
cp -r ~/.local/share/star-building/dramknote-p026 ~/.local/share/star-building/dramknote-p026.bak_$(date +%Y%m%d_%H%M%S)
```

---

## 5. Политика ограничений безопасности

- **No Merge:** Ветка `work/dramknote-p026-handoff` не сливается в `main`/`master` автоматически.
- **No Prod Restart:** В ходе выполнения задач разработки и приёмки перезапуск службы на боевом сервере запрещён.
- **No Costs:** Запрещены любые платные модельные вызовы или внешние коммерческие API.
- **No Credentials:** Запрещено чтение, модификация, логирование и коммит секретов и токенов.
- **No ACL Mutation:** Запрещено изменение прав доступа файловой системы live-контура.
- **No Deletion Live State:** Самовольное удаление файлов из боевого каталога хранения запрещено.
