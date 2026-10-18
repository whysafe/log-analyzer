"""Разбор access.log nginx/Apache (формат combined) в наглядный HTML-отчёт.

    python analyze.py /var/log/nginx/access.log -o report.html
    python analyze.py access.log.gz --since 2026-10-01
    python analyze.py --demo            # сгенерировать пример лога и отчёт
"""
from __future__ import annotations

import argparse
import gzip
import html
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

LINE = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>[A-Z]+) (?P<path>\S+) [^"]*" '
    r'(?P<status>\d{3}) (?P<size>\d+|-)(?: "(?P<ref>[^"]*)" "(?P<ua>[^"]*)")?'
)
BOT = re.compile(r"bot|crawl|spider|slurp|yandex|bing|curl|python-requests|wget", re.I)


@dataclass
class Hit:
    ip: str
    time: datetime
    method: str
    path: str
    status: int
    size: int
    ref: str
    ua: str


def parse_line(line: str) -> Hit | None:
    m = LINE.match(line)
    if not m:
        return None
    try:
        time = datetime.strptime(m["time"], "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:  # битая дата: строку считаем нераспознанной, а не роняем весь разбор
        return None
    return Hit(m["ip"], time, m["method"], m["path"].split("?")[0],
               int(m["status"]), 0 if m["size"] == "-" else int(m["size"]), m["ref"] or "-", m["ua"] or "")


def read(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        yield from f


def analyze(lines, since: datetime | None = None) -> dict:
    hits, bad = [], 0
    for line in lines:
        h = parse_line(line)
        if h is None:
            bad += 1
        elif since is None or h.time >= since:
            hits.append(h)
    by_hour = Counter(h.time.strftime("%Y-%m-%d %H:00") for h in hits)
    statuses = Counter(h.status // 100 * 100 for h in hits)
    errors = Counter((h.status, h.path) for h in hits if h.status >= 400)
    slow_ips = defaultdict(int)
    for h in hits:
        slow_ips[h.ip] += 1
    bots = sum(1 for h in hits if BOT.search(h.ua))
    return {
        "total": len(hits), "bad_lines": bad, "unique_ips": len(slow_ips),
        "bytes": sum(h.size for h in hits), "bots": bots,
        "first": min((h.time for h in hits), default=None), "last": max((h.time for h in hits), default=None),
        "by_hour": sorted(by_hour.items()), "statuses": statuses,
        "top_paths": Counter(h.path for h in hits).most_common(10),
        "top_ips": Counter(slow_ips).most_common(10),
        "top_errors": errors.most_common(10),
        "top_refs": Counter(h.ref for h in hits if h.ref not in ("-", "")).most_common(8),
    }


def human_bytes(n: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} ТБ"


def bar_chart(data: list[tuple[str, int]], width=900, height=220) -> str:
    if not data:
        return "<p>Нет данных</p>"
    peak, bw = max(v for _, v in data), width / len(data)
    bars = "".join(f'<rect x="{i * bw:.1f}" y="{height - v / peak * (height - 20):.1f}" width="{max(bw - 1, 1):.1f}" height="{v / peak * (height - 20):.1f}" fill="#3b82f6"><title>{html.escape(k)}: {v}</title></rect>'
                   for i, (k, v) in enumerate(data))
    labels = "".join(f'<text x="{i * bw:.1f}" y="{height + 14}" font-size="10" fill="#666">{html.escape(k[5:13])}</text>'
                     for i, (k, _) in enumerate(data) if i % max(1, len(data) // 8) == 0)
    return f'<svg viewBox="0 0 {width} {height + 20}" style="width:100%">{bars}{labels}</svg>'


def table(rows, headers) -> str:
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{''.join(f'<th>{h}</th>' for h in headers)}</tr>{body or '<tr><td>—</td></tr>'}</table>"


def render(s: dict, source: str) -> str:
    st = s["statuses"]
    err_share = (st.get(400, 0) + st.get(500, 0)) / max(1, s["total"]) * 100
    period = f"{s['first']:%d.%m.%Y %H:%M} — {s['last']:%d.%m.%Y %H:%M}" if s["first"] else "—"
    cards = [("Запросов", f"{s['total']:,}".replace(",", " ")), ("Уникальных IP", s["unique_ips"]), ("Трафик", human_bytes(s["bytes"])),
             ("Ошибок 4xx/5xx", f"{err_share:.1f}%"), ("Боты", f"{s['bots'] / max(1, s['total']) * 100:.0f}%")]
    return f"""<!doctype html><html lang="ru"><meta charset="utf-8"><title>Отчёт по логам</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:30px auto;padding:0 20px;color:#1f2937}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}.card{{background:#f3f4f6;border-radius:10px;padding:12px}}
.card b{{display:block;font-size:24px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:5px 8px;border-bottom:1px solid #e5e7eb;text-align:left}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}h2{{margin-top:32px}}</style>
<h1>Отчёт по логам</h1><p>{html.escape(source)} · {period} · нераспознанных строк: {s['bad_lines']}</p>
<div class="cards">{''.join(f'<div class="card">{k}<b>{v}</b></div>' for k, v in cards)}</div>
<h2>Запросы по часам</h2>{bar_chart(s['by_hour'])}
<h2>Коды ответа</h2>{table(sorted(st.items()), ['Класс', 'Запросов'])}
<div class="two"><div><h2>Популярные страницы</h2>{table(s['top_paths'], ['Путь', 'Запросов'])}</div>
<div><h2>Активные IP</h2>{table(s['top_ips'], ['IP', 'Запросов'])}</div></div>
<div class="two"><div><h2>Частые ошибки</h2>{table([(f'{c} {p}', n) for (c, p), n in s['top_errors']], ['Ошибка', 'Раз'])}</div>
<div><h2>Источники переходов</h2>{table(s['top_refs'], ['Источник', 'Переходов'])}</div></div></html>"""


def demo_log(path: Path, n=6000, seed=3) -> Path:
    rnd = random.Random(seed)
    start = datetime(2026, 10, 5, tzinfo=datetime.now().astimezone().tzinfo)
    paths = ["/", "/catalog", "/catalog/shoes", "/product/123", "/cart", "/api/search", "/blog/how-to-choose", "/wp-login.php", "/favicon.ico"]
    uas = ["Mozilla/5.0 (Windows NT 10.0) Chrome/128", "Mozilla/5.0 (iPhone) Safari/604", "YandexBot/3.0", "Googlebot/2.1", "python-requests/2.31"]
    refs = ["-", "https://yandex.ru/", "https://www.google.com/", "https://t.me/", "https://vk.com/"]
    ips = [f"{rnd.randint(1, 223)}.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}" for _ in range(350)]
    with path.open("w") as f:
        for _ in range(n):
            t = start + timedelta(seconds=rnd.randint(0, 3 * 86400))
            p = rnd.choices(paths, weights=[30, 15, 10, 12, 6, 8, 5, 2, 4])[0]
            status = 404 if p == "/wp-login.php" else rnd.choices([200, 304, 404, 500], weights=[90, 6, 3, 1])[0]
            f.write(f'{rnd.choice(ips)} - - [{t:%d/%b/%Y:%H:%M:%S %z}] '
                    f'"GET {p} HTTP/1.1" {status} {rnd.randint(300, 90000)} "{rnd.choice(refs)}" "{rnd.choice(uas)}"\n')
        f.write("garbage line that is not a log\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="HTML-отчёт по access.log")
    ap.add_argument("log", nargs="?", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("report.html"))
    ap.add_argument("--since", help="учитывать записи с даты ГГГГ-ММ-ДД")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    if a.demo:
        a.log = demo_log(Path("sample.log"))
    if not a.log:
        ap.error("укажите файл лога или --demo")
    since = datetime.strptime(a.since, "%Y-%m-%d").astimezone() if a.since else None
    stats = analyze(read(a.log), since)
    a.out.write_text(render(stats, str(a.log)), encoding="utf-8")
    print(f"Запросов: {stats['total']}, IP: {stats['unique_ips']}, отчёт: {a.out}")


if __name__ == "__main__":
    main()
