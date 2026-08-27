from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
URL = (ROOT / "index.html").as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL)

    assert page.title() == "Экзаменатор Star Building"
    assert page.locator("#question-data").count() == 1
    assert page.locator("#startView").is_visible()
    assert page.locator("text=Банк: 102 вопроса").is_visible()

    page.click("#ropMode")
    page.fill("#settingMinutes", "1")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#saveSettings")
    page.click("#employeeMode")

    page.fill("#employeeId", "test-sales-001")
    page.fill("#employeeName", "Тестовый сотрудник")
    page.select_option("#employeeRole", label="Менеджеры продаж")
    page.click("#startButton")
    assert page.locator("#examView").is_visible()
    assert page.locator("#timeMetric").is_visible()
    assert ":" in page.locator("#timeText").inner_text()
    assert page.locator(".option").count() == 4


    for index in range(102):
        page.locator(".option").first.click()
        page.click("#nextButton")
    assert page.locator("#resultView").is_visible()
    assert "Правильных ответов" in page.locator("#resultSummary").inner_text()

    page.click("#employeeMode")
    assert page.locator("#startButton").is_disabled()
    assert "текущий календарный месяц" in page.locator("#startMessage").inner_text()

    page.click("#ropMode")
    assert page.locator("#ropView").is_visible()
    assert page.locator("#resultsBody tr").count() == 1
    assert page.locator("#statAttempts").inner_text() == "1"


    print({"title": page.title(), "questions_completed": 102, "results_rows": 1, "page_errors": errors})
    assert not errors
    browser.close()
