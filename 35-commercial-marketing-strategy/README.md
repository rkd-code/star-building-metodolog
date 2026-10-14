# 35 — Единая стратегия коммерческого отдела и маркетинга

Рабочий пакет стратегии ТОО «Стар Билдинг» и Grand Construction до конца 2026 года с векторами на 2027 год.

## Состав

- `STRATEGY.md` — единый рабочий документ.
- `PRESENTATION_THESES.md` — тезисы для доклада Генеральному директору.
- `strategy_graph.json` — машинный граф стратегии.
- `strategy_graph.html` — автономная интерактивная визуализация графа.
- `strategy_mindmap.html` — автономная интеллект-карта.
- `strategy_mindmap.excalidraw` — редактируемая карта Excalidraw.
- `star_building_strategy.docx` — рабочая версия для импорта в Google Документы.
- `star_building_strategy_presentation.pptx` — презентация руководству.
- `build_artifacts.py` — воспроизводимая сборка артефактов.
- `test_artifacts.py` — проверки полноты и целостности.

## Статус

Рабочая версия для принятия управленческих решений. Производственные нормативы и помесячные планы уточняются после десятидневного аудита мощности и распределения портфеля 600 тонн по производственным слотам.

## Сборка

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python build_artifacts.py
.venv/bin/python -m unittest -v test_artifacts.py
```
