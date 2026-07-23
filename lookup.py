"""Поиск по справочнику: вводишь слаг — получаешь мету.

Запуск без аргументов открывает интерактивный режим:

    uv run python lookup.py

    слаг> perm
    слаг> perm_chernyshevskogo
    слаг> города
    слаг> филиалы perm

Разовый запрос одной командой:

    uv run python lookup.py perm_chernyshevskogo

Слаг города и слаг филиала различаются автоматически. Если слаг не найден,
предлагаются похожие, а не пустой ответ.
"""

from __future__ import annotations

import sys
from typing import Any

import directory

PROMPT = "слаг> "
HELP = (
    "Введи слаг города (perm) или филиала (perm_chernyshevskogo).\n"
    "  города           — список всех городов\n"
    "  филиалы <слаг>   — филиалы одного города\n"
    "  выход            — закончить"
)


def resolve(slug: str) -> tuple[str, dict[str, Any]] | None:
    """Определяет, чей это слаг, и достаёт мету.

    Аргументы:
        slug: слаг города или филиала.

    Возвращает:
        Пару («город» либо «филиал», мета) или None, если слаг неизвестен.
    """
    slug = slug.strip()
    if not slug:
        return None
    city = directory.get_city(slug)
    if city is not None:
        return "город", city
    branch = directory.get_branch(slug)
    if branch is not None:
        return "филиал", branch
    return None


def all_slugs() -> list[str]:
    """Собирает все существующие слаги — городов и филиалов."""
    slugs = []
    for city in directory.list_cities():
        slugs.append(city["слаг"])
        slugs.extend(b["слаг"] for b in directory.list_branches(city["слаг"]))
    return slugs


def suggest(slug: str, limit: int = 8) -> list[str]:
    """Подбирает похожие слаги для неверного ввода.

    Аргументы:
        slug: то, что ввёл человек.
        limit: сколько вариантов вернуть.

    Возвращает:
        Список слагов, содержащих введённый фрагмент.
    """
    needle = slug.strip().lower()
    if not needle:
        return []
    exact = [s for s in all_slugs() if s.startswith(needle)]
    partial = [s for s in all_slugs() if needle in s and s not in exact]
    return (exact + partial)[:limit]


def _line(label: str, value: Any) -> str:
    """Форматирует одну строку вывода, пропуская пустые значения."""
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return f"  {label}: {value}\n"


def render_city(meta: dict[str, Any]) -> str:
    """Собирает читаемый вывод по городу.

    Аргументы:
        meta: результат `directory.get_city`.

    Возвращает:
        Текст для терминала.
    """
    out = f"\n=== {meta['город']} ===\n"
    out += _line("филиалов", meta["филиалов"])
    out += _line("автодромов", meta["автодромов"])

    if meta["категории"]:
        out += "\n  Категории:\n"
        for item in meta["категории"]:
            parts = [item["категория"] or "?"]
            if item["срок обучения"]:
                parts.append(item["срок обучения"])
            if item["старт групп"]:
                parts.append(item["старт групп"])
            out += f"    • {' — '.join(parts)}\n"
            for entry in item["что входит"]:
                out += f"        {entry}\n"

    cars = meta["автомобили"]
    if cars["механика"] or cars["автомат"]:
        out += "\n  Автомобили:\n"
        out += _line("  механика", cars["механика"])
        out += _line("  автомат", cars["автомат"])
        out += _line("  возраст парка", cars["возраст парка"])

    if meta["документы"]:
        out += "\n  Документы:\n"
        for doc in meta["документы"]:
            out += f"    • {doc['что']} — {doc['когда']}\n"

    if meta["частые вопросы"]:
        out += f"\n  Частые вопросы: {len(meta['частые вопросы'])}\n"
        for pair in meta["частые вопросы"][:3]:
            out += f"    • {pair['вопрос']}\n"

    out += "\n"
    out += _line("телефон", meta["телефон"])
    out += _line("приём звонков", meta["приём звонков"])
    out += _line("мессенджеры", meta["мессенджеры"])
    return out


def render_branch(meta: dict[str, Any]) -> str:
    """Собирает читаемый вывод по филиалу.

    Аргументы:
        meta: результат `directory.get_branch`.

    Возвращает:
        Текст для терминала.
    """
    out = f"\n=== {meta['адрес']} ({meta['город']}) ===\n"
    out += _line("тип", meta["тип"])
    out += _line("статус", meta["статус"])
    out += _line("ориентир", meta["ориентир"])
    out += _line("район", meta["район"])
    out += _line("метро", meta["метро"])
    out += _line("часы работы", meta["часы работы"])
    out += _line("перерыв", meta["перерыв"])
    out += _line("телефон", meta["телефон"])
    out += _line("примечание", meta["примечание"])
    return out


def render_cities() -> str:
    """Собирает список всех городов со слагами."""
    out = "\n"
    for city in directory.list_cities():
        out += f"  {city['слаг']:22s} {city['город']:22s} филиалов {city['филиалов']}\n"
    return out


def render_branches(city_slug: str) -> str:
    """Собирает список филиалов города со слагами.

    Аргументы:
        city_slug: слаг города.

    Возвращает:
        Текст для терминала либо сообщение, что города нет.
    """
    branches = directory.list_branches(city_slug)
    if not branches:
        return f"\n  Города «{city_slug}» нет. Посмотри список: города\n"
    out = "\n"
    for branch in branches:
        landmark = f"  ({branch['ориентир']})" if branch["ориентир"] else ""
        out += f"  {branch['слаг']:38s} {branch['адрес']}{landmark}\n"
    return out


def handle(command: str) -> str:
    """Обрабатывает одну введённую строку.

    Аргументы:
        command: то, что ввёл человек.

    Возвращает:
        Текст ответа для терминала.
    """
    command = command.strip()
    if not command:
        return ""
    low = command.lower()

    if low in ("города", "cities"):
        return render_cities()
    if low.startswith(("филиалы", "branches")):
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            return "\n  Нужен слаг города: филиалы perm\n"
        return render_branches(parts[1].strip())
    if low in ("помощь", "help", "?"):
        return "\n" + HELP + "\n"

    found = resolve(command)
    if found is None:
        options = suggest(command)
        if options:
            return "\n  Не нашёл. Похожие:\n" + "".join(f"    {s}\n" for s in options)
        return "\n  Не нашёл и похожих нет. Список городов: города\n"

    kind, meta = found
    return render_city(meta) if kind == "город" else render_branch(meta)


def main(argv: list[str] | None = None) -> int:
    """Точка входа: разовый запрос или интерактивный режим.

    Аргументы:
        argv: аргументы командной строки; None — взять из sys.argv.

    Возвращает:
        Код возврата процесса.
    """
    argv = sys.argv[1:] if argv is None else argv

    if not directory.list_cities():
        print(f"Нет данных в {directory.data_dir()} — сначала собери справочник.")
        return 1

    if argv:
        print(handle(" ".join(argv)))
        return 0

    print(f"Справочник: {len(directory.list_cities())} городов. {HELP}")
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.strip().lower() in ("выход", "exit", "quit", "q"):
            return 0
        print(handle(line))


if __name__ == "__main__":
    raise SystemExit(main())
