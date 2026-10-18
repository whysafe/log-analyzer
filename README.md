# Анализ логов nginx

Скрипт превращает `access.log` nginx или Apache (формат combined) в наглядный HTML-отчёт. Пригождается, когда сайт «тормозит» или кто-то перебирает `/wp-login.php`: сразу видно, кто и куда стучится.

## Возможности

- Сводные карточки: число запросов, уникальные IP, трафик, доля ошибок 4xx/5xx, доля ботов
- График запросов по часам в SVG прямо в отчёте
- Распределение по классам кодов ответа (2xx, 3xx, 4xx, 5xx)
- Топ-10 страниц и топ-10 активных IP
- Частые ошибки: код и путь
- Источники переходов (Referer)
- Читает обычные и сжатые `.gz` логи
- Фильтр по дате `--since`
- Нераспознанные строки пропускаются и считаются в отчёте
- Флаг `--demo` генерирует пример лога и строит по нему отчёт
- Работает без внешних зависимостей, только стандартная библиотека

## Стек

Python 3.10+ (стандартная библиотека: `re`, `gzip`, `html`, `collections`), pytest для тестов.

## Как запустить

```bash
python analyze.py /var/log/nginx/access.log -o report.html
python analyze.py access.log.2.gz --since 2026-10-01
python analyze.py --demo         # создаёт sample.log и report.html в текущей папке
```

| Аргумент | Что делает |
|---|---|
| `log` | путь к логу, можно `.gz` |
| `-o`, `--out` | файл отчёта, по умолчанию `report.html` |
| `--since ГГГГ-ММ-ДД` | учитывать записи начиная с этой даты |
| `--demo` | сгенерировать пример лога `sample.log` |

Тесты:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -v
```

Тесты запускаются в GitHub Actions (`.github/workflows/tests.yml`) на Python 3.11 и 3.12.

## Структура проекта

```
analyze.py             # разбор строк, подсчёт статистики, HTML и SVG, пример лога, CLI
tests/test_analyze.py  # тесты разбора строки, подсчётов и отчёта
requirements.txt       # pytest
```

## Как это устроено

- Строка лога разбирается одним регулярным выражением с именованными группами; Referer и User-Agent необязательны, поэтому подходит и формат common.
- Файл читается генератором построчно, `.gz` открывается через `gzip.open` в текстовом режиме с `errors="replace"`.
- Query-строка отрезается от пути, чтобы `/catalog?page=2` и `/catalog` считались одной страницей.
- Боты определяются по User-Agent регулярным выражением (bot, crawl, spider, yandex, bing, curl, python-requests, wget).
- Все значения из лога экранируются `html.escape` перед вставкой в отчёт, так что вредоносный путь в логе не выполнится в браузере.
- График строится как набор `<rect>` в SVG с подсказками `<title>`, без JavaScript.

## Идеи для развития

- Время ответа, если в формате лога есть `$request_time`
- Геолокация IP
- Сравнение двух периодов

## Лицензия

MIT © 2026 whysafe. Telegram: [@yawhysafe](https://t.me/yawhysafe) · Сайт: [whysafe.ru](https://whysafe.ru)
