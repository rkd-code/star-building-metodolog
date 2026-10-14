from collections import OrderedDict

MONTHS = ["Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

MONTHLY_OPERATING = OrderedDict([
    ("Сентябрь", 450_000),
    ("Октябрь", 650_000),
    ("Ноябрь", 850_000),
    ("Декабрь", 1_050_000),
])

CATEGORIES = [
    "Поисковая реклама",
    "Повторный показ и медийные тесты",
    "SEO и качественные внешние ссылки",
    "Экспертный контент и кейсы",
    "Видео и творческие материалы",
    "ABM, партнёры и экскурсии",
    "Аналитика и посадочные страницы",
    "ИИ и программные сервисы",
    "Отраслевые СМИ",
    "Резерв и эксперименты",
]

ALLOCATION = {
    "Сентябрь": OrderedDict(zip(CATEGORIES, [150_000, 20_000, 37_000, 45_000, 30_000, 50_000, 70_000, 25_000, 0, 23_000])),
    "Октябрь": OrderedDict(zip(CATEGORIES, [230_000, 40_000, 74_000, 55_000, 45_000, 70_000, 50_000, 30_000, 0, 56_000])),
    "Ноябрь": OrderedDict(zip(CATEGORIES, [280_000, 60_000, 74_000, 65_000, 55_000, 80_000, 40_000, 35_000, 120_000, 41_000])),
    "Декабрь": OrderedDict(zip(CATEGORIES, [360_000, 80_000, 100_000, 80_000, 70_000, 100_000, 40_000, 40_000, 150_000, 30_000])),
}

MANDATORY_INFRA = {
    "Сентябрь": 16_680,  # 7 100 хостинг + 9 580 домен starbuilding.kz
    "Октябрь": 18_380,   # 7 100 хостинг + 11 280 два домена Galenda
    "Ноябрь": 7_100,
    "Декабрь": 7_100,
}

ONE_TIME_CAPEX = {
    "Сентябрь": 180_000,  # телефон мобилографа, только после утверждения спецификации
    "Октябрь": 0,
    "Ноябрь": 0,
    "Декабрь": 0,
}

KPI_TARGETS = {
    "Сентябрь": {"inquiries": 15, "mql": 6, "sql": 2, "pipeline_tons": 80},
    "Октябрь": {"inquiries": 22, "mql": 9, "sql": 3, "pipeline_tons": 150},
    "Ноябрь": {"inquiries": 30, "mql": 12, "sql": 4, "pipeline_tons": 220},
    "Декабрь": {"inquiries": 38, "mql": 15, "sql": 5, "pipeline_tons": 300},
}


def totals():
    operating = sum(MONTHLY_OPERATING.values())
    infrastructure = sum(MANDATORY_INFRA.values())
    capex = sum(ONE_TIME_CAPEX.values())
    return {
        "operating_marketing": operating,
        "mandatory_infrastructure": infrastructure,
        "one_time_capex": capex,
        "grand_total": operating + infrastructure + capex,
    }


def monthly_total(month):
    return MONTHLY_OPERATING[month] + MANDATORY_INFRA[month] + ONE_TIME_CAPEX[month]
