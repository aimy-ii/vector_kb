"""Тесты сборки пакета и пайплайна: без сети."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.services.directory_service.store import directory_store
from app.services.parsing_service import package_data, pipeline

FIXTURE = Path(__file__).parent.parent / "fixtures" / "city_sample.txt"


def _full_city(slug: str, *, marker: str = "old") -> dict[str, Any]:
    """Минимальный полный JSON города для сборки пакета."""
    return {
        "meta": {"city": slug, "city_slug": slug, "version": 1},
        "branches": {"_source": "https://example.test", "items": []},
        "categories": {"items": []},
        "fleet": {"items": []},
        "theory_formats": {"items": []},
        "documents": {"items": []},
        "faq": {"items": [{"question": "q", "answer": marker}]},
        "installment": {},
        "contacts": {},
        "conflicts": [],
        "_review": [],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Пишет JSON с переносом строки в конце."""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_package_data_keeps_other_dst_files(tmp_path: Path) -> None:
    """Один город в исходном каталоге не удаляет остальные файлы целевого."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    _write_json(src / "omsk.json", _full_city("omsk", marker="new"))
    _write_json(dst / "omsk.json", _full_city("omsk", marker="old"))
    _write_json(dst / "perm.json", _full_city("perm", marker="keep"))
    _write_json(dst / "tara.json", _full_city("tara", marker="keep"))

    assert package_data.run(src_dir=src, dst_dir=dst) == 0

    assert (dst / "perm.json").exists()
    assert (dst / "tara.json").exists()
    assert (
        json.loads((dst / "perm.json").read_text(encoding="utf-8"))["faq"]["items"][0]["answer"]
        == "keep"
    )


def test_package_data_overwrites_present_city(tmp_path: Path) -> None:
    """Город из исходного каталога перезаписывается в целевом."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    _write_json(src / "omsk.json", _full_city("omsk", marker="fresh"))
    _write_json(dst / "omsk.json", _full_city("omsk", marker="stale"))

    assert package_data.run(src_dir=src, dst_dir=dst) == 0

    written = json.loads((dst / "omsk.json").read_text(encoding="utf-8"))
    assert written["faq"]["items"][0]["answer"] == "fresh"
    assert "conflicts" not in written


def test_package_data_prune_removes_only_unknown(tmp_path: Path) -> None:
    """prune=True удаляет только файлы вне исходника и вне списка городов."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    _write_json(src / "omsk.json", _full_city("omsk"))
    _write_json(dst / "omsk.json", _full_city("omsk"))
    _write_json(dst / "tara.json", _full_city("tara"))
    _write_json(dst / "ghost-city.json", _full_city("ghost-city"))

    assert package_data.run(src_dir=src, dst_dir=dst, prune=True) == 0

    assert (dst / "omsk.json").exists()
    assert (dst / "tara.json").exists()
    assert not (dst / "ghost-city.json").exists()


def test_package_data_empty_src_leaves_dst(tmp_path: Path) -> None:
    """Пустой исходный каталог возвращает 1 и не трогает целевой."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    _write_json(dst / "omsk.json", _full_city("omsk", marker="untouched"))

    assert package_data.run(src_dir=src, dst_dir=dst) == 1

    assert (dst / "omsk.json").exists()
    assert (
        json.loads((dst / "omsk.json").read_text(encoding="utf-8"))["faq"]["items"][0]["answer"]
        == "untouched"
    )


def test_pipeline_excludes_done_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """По умолчанию пайплайн не включает города с флагом done."""
    captured: dict[str, Any] = {}

    def fake_scrape(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("app.services.parsing_service.pipeline.scrape.run", fake_scrape)
    monkeypatch.setattr("app.services.parsing_service.pipeline.sections.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.finalize.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.index.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.package_data.run", lambda **_: 0)
    monkeypatch.setattr(
        "app.services.parsing_service.pipeline.directory_store.reload",
        lambda **_: 1,
    )

    directory_dir = tmp_path / "directory"
    directory_dir.mkdir()
    _write_json(directory_dir / "omsk.json", _full_city("omsk"))

    pipeline.run(
        directory_data_dir=directory_dir,
        out_dir=tmp_path / "out",
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "index.json",
    )
    assert captured.get("include_done") is False


def test_pipeline_include_done_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """include_done=True передаётся в шаг сбора."""
    captured: dict[str, Any] = {}

    def fake_scrape(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("app.services.parsing_service.pipeline.scrape.run", fake_scrape)
    monkeypatch.setattr("app.services.parsing_service.pipeline.sections.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.finalize.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.index.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.package_data.run", lambda **_: 0)
    monkeypatch.setattr(
        "app.services.parsing_service.pipeline.directory_store.reload",
        lambda **_: 1,
    )

    directory_dir = tmp_path / "directory"
    directory_dir.mkdir()
    _write_json(directory_dir / "omsk.json", _full_city("omsk"))

    pipeline.run(
        include_done=True,
        directory_data_dir=directory_dir,
        out_dir=tmp_path / "out",
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "index.json",
    )
    assert captured.get("include_done") is True


def test_pipeline_raises_if_cities_decrease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Пайплайн падает, если после сборки городов стало меньше."""
    directory_dir = tmp_path / "directory"
    directory_dir.mkdir()
    _write_json(directory_dir / "omsk.json", _full_city("omsk"))
    _write_json(directory_dir / "tara.json", _full_city("tara"))

    def shrink_package(**kwargs: Any) -> int:
        dst = kwargs["dst_dir"]
        next(dst.glob("*.json")).unlink()
        return 0

    monkeypatch.setattr("app.services.parsing_service.pipeline.scrape.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.sections.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.finalize.run", lambda **_: 0)
    monkeypatch.setattr("app.services.parsing_service.pipeline.index.run", lambda **_: 0)
    monkeypatch.setattr(
        "app.services.parsing_service.pipeline.package_data.run",
        shrink_package,
    )

    with pytest.raises(RuntimeError, match="стало меньше"):
        pipeline.run(
            directory_data_dir=directory_dir,
            out_dir=tmp_path / "out",
            raw_dir=tmp_path / "raw",
            index_path=tmp_path / "index.json",
        )


def test_pipeline_failure_keeps_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """При падении пайплайна данные в памяти остаются прежними."""
    snapshot = {"slug": "frozen", "meta": {"city_slug": "frozen"}}
    directory_store._cities = {"frozen": snapshot}
    before = directory_store.cities

    monkeypatch.setattr("app.services.parsing_service.pipeline.scrape.run", lambda **_: 1)

    with pytest.raises(RuntimeError, match="Сбор страниц"):
        pipeline.run(
            directory_data_dir=tmp_path / "directory",
            out_dir=tmp_path / "out",
            raw_dir=tmp_path / "raw",
            index_path=tmp_path / "index.json",
        )

    assert directory_store.cities is before
    assert directory_store.cities["frozen"] is snapshot
    directory_store.load()
