import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analyze as an  # noqa: E402

LINES = [
    '1.2.3.4 - - [10/Oct/2026:13:55:36 +0300] "GET /catalog?page=2 HTTP/1.1" 200 2326 "https://yandex.ru/" "Mozilla/5.0"',
    '1.2.3.4 - - [10/Oct/2026:13:56:01 +0300] "POST /api/order HTTP/1.1" 500 120 "-" "Mozilla/5.0"',
    '5.6.7.8 - - [10/Oct/2026:14:01:00 +0300] "GET /robots.txt HTTP/1.1" 404 0 "-" "YandexBot/3.0"',
    'это не строка лога',
]


def test_parse_line():
    h = an.parse_line(LINES[0])
    assert h.ip == "1.2.3.4" and h.path == "/catalog" and h.status == 200 and h.size == 2326


def test_analyze_counts():
    s = an.analyze(LINES)
    assert s["total"] == 3 and s["bad_lines"] == 1 and s["unique_ips"] == 2 and s["bots"] == 1
    assert s["statuses"][500] == 1 and s["statuses"][400] == 1
    assert s["top_errors"][0][1] == 1


def test_demo_report(tmp_path):
    log = an.demo_log(tmp_path / "a.log", n=500)
    s = an.analyze(an.read(log))
    html = an.render(s, "a.log")
    assert s["total"] == 500 and "<svg" in html and "/wp-login.php" in html


def test_bad_date_counts_as_unparsed():
    broken = [
        '1.2.3.4 - - [32/Oct/2026:13:55:36 +0300] "GET / HTTP/1.1" 200 10 "-" "Mozilla/5.0"',
        '1.2.3.4 - - [10/Foo/2026:13:55:36 +0300] "GET / HTTP/1.1" 200 10 "-" "Mozilla/5.0"',
        '1.2.3.4 - - [вчера] "GET / HTTP/1.1" 200 10 "-" "Mozilla/5.0"',
    ]
    assert all(an.parse_line(line) is None for line in broken)
    s = an.analyze(LINES + broken)
    assert s["total"] == 3 and s["bad_lines"] == 4
