"""Tenant-admin pricing provenance and TCO endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_tenant_write
from app.models.external_integrations import ProviderPriceItem, ProviderPriceVersion, ProviderUsageEvent
from app.models.user import User
from app.schemas.external_integrations import CostReport, CostScenario, PriceVersionCreate
from app.services.audit_service import AuditService
from app.services.provider_costs import cost_report, create_price_version
from app.services.workspace_service import ADMIN_ROLES, require_role


router = APIRouter()


@router.post("/provider-costs/prices", status_code=status.HTTP_201_CREATED)
async def create_provider_prices(
    body: PriceVersionCreate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, ADMIN_ROLES)
    version = await create_price_version(db, user, body)
    await AuditService.log_action(
        db, user.tenant_id, user.id, "PROVIDER_PRICE_VERSION_CREATED", "provider_price_versions", version.id,
        {"provider": version.provider, "version": version.version, "provenance_url": version.provenance_url},
        request.client.host if request.client else None,
    )
    await db.commit()
    return {"id": version.id, "provider": version.provider, "version": version.version, "quote_required": version.quote_required}


@router.get("/provider-costs/prices", response_model=dict)
async def list_provider_prices(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, ADMIN_ROLES)
    versions = (
        await db.scalars(
            select(ProviderPriceVersion)
            .where(ProviderPriceVersion.tenant_id == user.tenant_id)
            .order_by(ProviderPriceVersion.provider, ProviderPriceVersion.effective_on.desc(), ProviderPriceVersion.version.desc())
        )
    ).all()
    result = []
    for version in versions:
        items = (
            await db.scalars(
                select(ProviderPriceItem).where(
                    ProviderPriceItem.tenant_id == user.tenant_id,
                    ProviderPriceItem.price_version_id == version.id,
                ).order_by(ProviderPriceItem.metric)
            )
        ).all()
        result.append({
            "id": version.id, "provider": version.provider, "version": version.version,
            "currency": version.currency, "pricing_model": version.pricing_model,
            "monthly_base_amount": version.monthly_base_amount, "effective_on": version.effective_on,
            "observed_on": version.observed_on, "provenance_url": version.provenance_url,
            "quote_required": version.quote_required,
            "items": [{"metric": item.metric, "unit_price": item.unit_price, "included_units": item.included_units} for item in items],
        })
    return {"items": result}


@router.post("/provider-costs/report", response_model=CostReport)
async def provider_cost_report(body: CostScenario, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, ADMIN_ROLES)
    return await cost_report(db, user, body)


@router.get("/provider-costs/usage", response_model=dict)
async def provider_usage(
    user: CurrentUser,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    require_role(user, ADMIN_ROLES)
    end = date_to or datetime.now(timezone.utc)
    start = date_from or (end - timedelta(days=30))
    if start.tzinfo is None or end.tzinfo is None or start >= end or end - start > timedelta(days=366):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Período de uso inválido.")
    rows = await db.execute(
        select(ProviderUsageEvent.provider, ProviderUsageEvent.metric, func.sum(ProviderUsageEvent.units))
        .where(
            ProviderUsageEvent.tenant_id == user.tenant_id,
            ProviderUsageEvent.occurred_at >= start.astimezone(timezone.utc),
            ProviderUsageEvent.occurred_at < end.astimezone(timezone.utc),
        )
        .group_by(ProviderUsageEvent.provider, ProviderUsageEvent.metric)
        .order_by(ProviderUsageEvent.provider, ProviderUsageEvent.metric)
    )
    return {
        "date_from": start,
        "date_to": end,
        "items": [{"provider": provider, "metric": metric, "units": int(units)} for provider, metric, units in rows],
    }
