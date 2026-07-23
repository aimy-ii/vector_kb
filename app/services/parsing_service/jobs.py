"""Реестр фоновых задач парсинга в памяти процесса."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.constants.parsing import PARSE_LOG_PREFIX, JobStatus
from app.services.parsing_service import pipeline

logger = logging.getLogger(__name__)


class JobConflictError(Exception):
    """Уже выполняется другая задача парсинга."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__("Уже выполняется задача парсинга")


@dataclass
class ParseJob:
    """Состояние одной фоновой задачи парсинга."""

    job_id: str
    status: JobStatus = JobStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    step: str | None = None
    cities_processed: int = 0
    error: str | None = None
    only: list[str] | None = None
    force: bool = False
    include_external: bool = False
    include_done: bool = False


_jobs: dict[str, ParseJob] = {}
_lock = threading.Lock()
_active_job_id: str | None = None


def get_job(job_id: str) -> ParseJob | None:
    """Возвращает задачу по идентификатору или None."""
    return _jobs.get(job_id)


def get_active_job_id() -> str | None:
    """Идентификатор текущей выполняющейся задачи, если есть."""
    return _active_job_id


def start_job(
    *,
    only: list[str] | None = None,
    force: bool = False,
    include_external: bool = False,
    include_done: bool = False,
) -> ParseJob:
    """
    Создаёт задачу и запускает пайплайн в отдельном потоке.

    Raises:
        JobConflictError: если предыдущая задача ещё идёт.
    """
    global _active_job_id

    with _lock:
        if _active_job_id is not None:
            active = _jobs.get(_active_job_id)
            if active is not None and active.status in (JobStatus.PENDING, JobStatus.RUNNING):
                raise JobConflictError(_active_job_id)

        job = ParseJob(
            job_id=uuid.uuid4().hex[:12],
            only=only,
            force=force,
            include_external=include_external,
            include_done=include_done,
        )
        _jobs[job.job_id] = job
        _active_job_id = job.job_id

    thread = threading.Thread(target=_run_job, args=(job.job_id,), daemon=True)
    thread.start()
    return job


def _run_job(job_id: str) -> None:
    """Выполняет пайплайн и обновляет состояние задачи."""
    global _active_job_id

    job = _jobs[job_id]
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    logger.info("%s Старт задачи job_id=%s", PARSE_LOG_PREFIX, job_id)

    try:
        pipeline.run(
            only=job.only,
            force=job.force,
            include_external=job.include_external,
            include_done=job.include_done,
            on_step=lambda step: setattr(job, "step", step),
            on_city_done=lambda count: setattr(job, "cities_processed", count),
        )
        job.status = JobStatus.DONE
        job.step = "done"
        logger.info("%s Задача завершена job_id=%s", PARSE_LOG_PREFIX, job_id)
    except Exception as exc:  # noqa: BLE001 — фиксируем ошибку в состоянии задачи
        job.status = JobStatus.FAILED
        job.error = str(exc)
        logger.exception("%s Задача упала job_id=%s: %s", PARSE_LOG_PREFIX, job_id, exc)
    finally:
        job.finished_at = datetime.now(UTC)
        with _lock:
            if _active_job_id == job_id:
                _active_job_id = None
