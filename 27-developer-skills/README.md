# 27-developer-skills: Навыки профиля разработчика

## Профиль

- Имя Hermes: `developer`
- Каталог: `~/.hermes/profiles/developer/`
- Состояние: создан и настроен
- Ограничение задачи: 100 итераций
- Сжатие контекста: до 50%

## Установленные навыки

| № | Навык | Репозиторий | Зафиксированная версия источника | Состояние |
|---:|---|---|---|---|
| 1 | `frontend-design` | `anthropics/skills` | `3b3fad96af16a10759d930941b4520ba0c40edae` | Доступен |
| 2 | `vercel-react-best-practices` | `vercel-labs/agent-skills` | `dd089a8c752c966dee8bf0f27cb625ba193ffd9e` | Доступен |
| 3 | `test-driven-development` | `obra/superpowers` | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` | Доступен |
| 4 | `systematic-debugging` | `obra/superpowers` | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` | Доступен |

## Проверка целостности основных файлов

| Навык | SHA-256 файла `SKILL.md` |
|---|---|
| `frontend-design` | `1608ea77fbb6fc30d13a97d12cfa8ebf31358d40f0dd97beed24829d6b3f45dd` |
| `vercel-react-best-practices` | `71ed7794962fa6e803ee83030517b5b93a9f70fbfeb431ec4535c5480a8d8355` |
| `test-driven-development` | `bf1b8216e523851a411e91d429a7c1c2a173e79d88957bc78e348218d50edd54` |
| `systematic-debugging` | `808fc5717aa88ad65efff312b11c186294d3e6ee301afb584e2f86599b137787` |

## Результаты проверки безопасности

- `frontend-design`: проверка Hermes — `SAFE`.
- `test-driven-development`: проверка Hermes — `SAFE`.
- `systematic-debugging`: проверка Hermes — `CAUTION` из-за диагностического примера `env | grep IDENTITY`; установлен с разрешенным ключом `--force` по прямому распоряжению пользователя выполнить установку без подтверждений.
- `vercel-react-best-practices`: встроенная проверка ошибочно отметила ссылку на сопровождающий `AGENTS.md` как изменение настроек агента. Файлы зафиксированной версии были отдельно проверены: команд удаления, повышения прав, загрузки внешних сценариев и доступа к секретам не найдено. Установлена точная копия каталога навыка из указанной версии репозитория.

## Когда применять

- `frontend-design` — при создании или переработке понятного и визуально цельного интерфейса.
- `vercel-react-best-practices` — при написании, проверке и ускорении проектов React или Next.js.
- `test-driven-development` — перед реализацией функции или исправлением ошибки, начиная с падающей проверки.
- `systematic-debugging` — при любой ошибке или неожиданном поведении, начиная с поиска первопричины.
