"""Скачивание городских страниц и приведение их к плоскому тексту.

Сохраняем и HTML, и текст: если разбор какого-то поля окажется неверным, его можно
починить и перезапустить только этап парсинга, не дёргая сайт повторно.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
from selectolax.parser import HTMLParser

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Теги, содержимое которых в текст не попадает.
DROP_TAGS = ("script", "style", "noscript", "svg", "iframe")


def html_to_text(html: str) -> str:
    """Превращает HTML в плоский текст, сохраняя порядок блоков.

    Аргументы:
        html: исходная разметка страницы.

    Возвращает:
        Текст, где каждый значимый узел на своей строке, без пустых строк подряд.
    """
    tree = HTMLParser(html)
    for tag in DROP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    body = tree.body or tree.root
    if body is None:
        return ""
    raw = body.text(separator="\n", strip=True)
    lines = [line.strip() for line in raw.split("\n")]
    return "\n".join(line for line in lines if line)


def collect_links(html: str) -> list[tuple[str, str]]:
    """Собирает ссылки страницы парами (текст, href).

    Нужны для лицензии, страницы документов и мессенджеров — их адреса в тексте не видны.

    Аргументы:
        html: исходная разметка страницы.

    Возвращает:
        Список пар (видимый текст ссылки, значение href).
    """
    tree = HTMLParser(html)
    links: list[tuple[str, str]] = []
    for node in tree.css("a"):
        href = node.attributes.get("href")
        if not href:
            continue
        links.append((node.text(strip=True), href))
    return links


def fetch(url: str, *, timeout: float = 30.0, retries: int = 3, pause: float = 1.5) -> str:
    """Скачивает страницу с повторами при сетевых ошибках.

    Аргументы:
        url: адрес страницы.
        timeout: таймаут одного запроса в секундах.
        retries: сколько раз повторить при ошибке.
        pause: пауза между повторами в секундах, растёт линейно.

    Возвращает:
        HTML страницы.

    Исключения:
        httpx.HTTPError: если все попытки исчерпаны.
    """
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = httpx.get(
                url,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"},
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:  # noqa: PERF203
            last = exc
            if attempt < retries:
                time.sleep(pause * attempt)
    raise last if last else RuntimeError("не удалось скачать страницу")


def fetch_to_disk(slug: str, url: str, raw_dir: Path, *, force: bool = False) -> tuple[str, str]:
    """Скачивает страницу города и кладёт HTML и текст на диск.

    Аргументы:
        slug: идентификатор города, он же имя файла.
        url: адрес городской страницы.
        raw_dir: каталог для сырых файлов.
        force: перекачивать, даже если файл уже есть.

    Возвращает:
        Пару (html, text).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    html_path = raw_dir / f"{slug}.html"
    text_path = raw_dir / f"{slug}.txt"

    if html_path.exists() and not force:
        html = html_path.read_text(encoding="utf-8")
    else:
        html = fetch(url)
        html_path.write_text(html, encoding="utf-8")

    text = html_to_text(html)
    text_path.write_text(text, encoding="utf-8")
    return html, text
