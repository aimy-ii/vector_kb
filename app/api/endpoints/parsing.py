"""Эндпоинты фонового парсинга."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.parsing import ParseJobAccepted, ParseJobStatus, ParseRequest
from app.services.parsing_service import jobs as jobs_service

parsing_router = APIRouter()


@parsing_router.post(
    path="/parse",
    summary="Запуск обновления данных в фоне",
    response_model=ParseJobAccepted,
    status_code=202,
)
async def post_parse(body: ParseRequest | None = None) -> ParseJobAccepted:
    """Ставит полный прогон пайплайна в фон; параллельно — не больше одной задачи."""
    request = body or ParseRequest()
    try:
        job = jobs_service.start_job(
            only=request.only,
            force=request.force,
            include_external=request.include_external,
        )
    except jobs_service.JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"detail": str(exc), "job_id": exc.job_id},
        ) from exc
    return ParseJobAccepted(job_id=job.job_id, status=job.status)


@parsing_router.get(
    path="/parse/{job_id}",
    summary="Статус задачи парсинга",
    response_model=ParseJobStatus,
)
async def get_parse_job(job_id: str) -> ParseJobStatus:
    """Возвращает состояние фоновой задачи по идентификатору."""
    job = jobs_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Задача «{job_id}» не найдена")
    return ParseJobStatus(
        job_id=job.job_id,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        step=job.step,
        cities_processed=job.cities_processed,
        error=job.error,
    )
