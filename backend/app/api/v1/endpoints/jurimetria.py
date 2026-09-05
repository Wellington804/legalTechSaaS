"""Tenant-safe descriptive analytics backed by the configured DataJud source."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import reserve_request
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, ensure_tenant_write_access
from app.core.redis_cache import cache_manager
from app.models.jurimetry import JurimetrySnapshot
from app.schemas.controladoria import SUPPORTED_DATAJUD_TRIBUNALS
from app.schemas.jurimetry import (
    MAX_PERIOD_DAYS,
    JurimetryAnalysisRequest,
    JurimetryAnalysisResponse,
    JurimetryOptions,
    JurimetrySnapshotList,
)
from app.services import jurimetry as jurimetry_service
from app.services.audit_service import AuditService
from app.services.controladoria_provider import JudicialProviderError, JudicialProviderRateLimited
from app.services.workspace_service import require_role


router = APIRouter()
ALLOWED_ROLES = {"admin", "partner", "lawyer"}


@router.get("/options", response_model=JurimetryOptions)
async def options(user: CurrentUser):
    require_role(user, ALLOWED_ROLES)
    return JurimetryOptions(
        provider_available=bool(settings.DATAJUD_ENABLED and settings.DATAJUD_API_KEY),
        source_name=jurimetry_service.SOURCE_NAME,
        source_documentation_url=jurimetry_service.SOURCE_DOCUMENTATION_URL,
        tribunals=sorted(SUPPORTED_DATAJUD_TRIBUNALS),
        sample_limits=[50, 100, 200],
        max_period_days=MAX_PERIOD_DAYS,
        supported_filters=["date_from", "date_to", "degree", "class_code", "subject_code", "court_unit_code"],
    )


async def _existing_snapshot(
    db: AsyncSession, tenant_id: str, request_id: str
) -> JurimetrySnapshot | None:
    return await db.scalar(
        select(JurimetrySnapshot).where(
            JurimetrySnapshot.tenant_id == tenant_id,
            JurimetrySnapshot.request_id == request_id,
        )
    )


def _idempotent_response(snapshot: JurimetrySnapshot, fingerprint: str) -> JurimetryAnalysisResponse:
    if snapshot.request_fingerprint != fingerprint:
        raise HTTPException(409, "Este identificador de requisição já foi usado com outros filtros.")
    return jurimetry_service.snapshot_response(snapshot)


async def _reserve_inflight_query(tenant_id: str, request_id: str) -> None:
    client = cache_manager.redis_client
    if not client:
        raise HTTPException(503, "Controle de consultas indisponível.")
    try:
        reserved = await client.set(f"legaltech:jurimetry:inflight:{tenant_id}:{request_id}", "1", ex=120, nx=True)
    except Exception as exc:
        raise HTTPException(503, "Controle de consultas indisponível.") from exc
    if not reserved:
        raise HTTPException(409, "Esta consulta já está em andamento. Aguarde o resultado antes de tentar novamente.")


@router.post("/analyses", response_model=JurimetryAnalysisResponse)
async def analyze(
    body: JurimetryAnalysisRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, ALLOWED_ROLES)
    tenant_id, user_id = user.tenant_id, user.id
    await ensure_tenant_write_access(db, tenant_id)
    fingerprint = jurimetry_service.request_fingerprint(body)
    request_id = str(body.request_id)
    if body.persist_snapshot:
        existing = await _existing_snapshot(db, tenant_id, request_id)
        if existing:
            return _idempotent_response(existing, fingerprint)
    if not settings.DATAJUD_ENABLED or not settings.DATAJUD_API_KEY:
        raise HTTPException(503, "DataJud não configurado. A análise não foi executada.")

    # Release the tenant-scoped database connection while waiting on the external provider.
    await db.rollback()
    await _reserve_inflight_query(tenant_id, request_id)
    await reserve_request(tenant_id, "datajud", 30, 3600)
    try:
        sample = await jurimetry_service.DataJudJurimetryProvider(settings.DATAJUD_API_KEY).query(body)
        response = jurimetry_service.analysis_response(body, sample)
    except JudicialProviderRateLimited as exc:
        raise HTTPException(429, "A fonte judicial limitou temporariamente as consultas. Tente mais tarde.") from exc
    except JudicialProviderError as exc:
        raise HTTPException(502, "Fonte judicial indisponível ou resposta inválida. Nenhuma análise foi salva.") from exc

    await _set_tenant_context(db, tenant_id)
    snapshot = None
    if body.persist_snapshot:
        snapshot = jurimetry_service.snapshot_from_response(
            response,
            tenant_id=tenant_id,
            user_id=user_id,
            fingerprint=fingerprint,
        )
        try:
            async with db.begin_nested():
                db.add(snapshot)
                await db.flush()
        except IntegrityError:
            await _set_tenant_context(db, tenant_id)
            existing = await _existing_snapshot(db, tenant_id, request_id)
            if not existing:
                raise
            return _idempotent_response(existing, fingerprint)
        response.snapshot_id = snapshot.id
        response.persisted = True

    await AuditService.log_action(
        db,
        tenant_id,
        user_id,
        "DATAJUD_JURIMETRY_QUERIED",
        "jurimetry_snapshots" if snapshot else "jurimetry_queries",
        snapshot.id if snapshot else request_id,
        {
            "tribunal": body.tribunal,
            "filters": body.filters.model_dump(mode="json", exclude_none=True),
            "sample_limit": body.sample_limit,
            "sample_size": response.sample_size,
            "total_matches": response.total_matches,
            "total_relation": response.total_relation,
            "persisted": bool(snapshot),
        },
    )
    await db.commit()
    return response


@router.get("/snapshots", response_model=JurimetrySnapshotList)
async def list_snapshots(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
):
    require_role(user, ALLOWED_ROLES)
    rows = (
        await db.scalars(
            select(JurimetrySnapshot)
            .where(JurimetrySnapshot.tenant_id == user.tenant_id)
            .order_by(JurimetrySnapshot.queried_at.desc())
            .limit(limit)
        )
    ).all()
    return JurimetrySnapshotList(items=[jurimetry_service.snapshot_response(row) for row in rows])


@router.get("/snapshots/{snapshot_id}", response_model=JurimetryAnalysisResponse)
async def get_snapshot(
    snapshot_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, ALLOWED_ROLES)
    snapshot = await db.scalar(
        select(JurimetrySnapshot).where(
            JurimetrySnapshot.tenant_id == user.tenant_id,
            JurimetrySnapshot.id == snapshot_id,
        )
    )
    if not snapshot:
        raise HTTPException(404, "Snapshot jurimétrico não encontrado.")
    return jurimetry_service.snapshot_response(snapshot)
