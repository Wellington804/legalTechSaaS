"""Versioned provider pricing and deterministic TCO calculations."""

import hashlib
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_integrations import ProviderPriceItem, ProviderPriceVersion, ProviderUsageEvent
from app.models.user import User
from app.schemas.external_integrations import CostLine, CostReport, CostScenario, PriceVersionCreate


SIX = Decimal("0.000001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(SIX, rounding=ROUND_HALF_UP)


async def create_price_version(db: AsyncSession, user: User, body: PriceVersionCreate) -> ProviderPriceVersion:
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:scope))"),
            {"scope": f"provider-price:{user.tenant_id}:{body.provider}:{body.effective_on.isoformat()}"},
        )
    latest = await db.scalar(
        select(func.max(ProviderPriceVersion.version)).where(
            ProviderPriceVersion.tenant_id == user.tenant_id,
            ProviderPriceVersion.provider == body.provider,
            ProviderPriceVersion.effective_on == body.effective_on,
        )
    )
    version = ProviderPriceVersion(
        tenant_id=user.tenant_id,
        provider=body.provider,
        version=int(latest or 0) + 1,
        currency=body.currency,
        pricing_model=body.pricing_model,
        monthly_base_amount=body.monthly_base_amount,
        effective_on=body.effective_on,
        observed_on=body.observed_on,
        provenance_url=body.provenance_url,
        quote_required=body.quote_required,
        notes=body.notes,
        created_by_user_id=user.id,
    )
    db.add(version)
    await db.flush()
    db.add_all(
        ProviderPriceItem(
            tenant_id=user.tenant_id,
            price_version_id=version.id,
            metric=item.metric,
            unit_price=item.unit_price,
            included_units=item.included_units,
        )
        for item in body.items
    )
    await db.flush()
    return version


async def cost_report(db: AsyncSession, user: User, scenario: CostScenario) -> CostReport:
    version = await db.scalar(
        select(ProviderPriceVersion).where(
            ProviderPriceVersion.tenant_id == user.tenant_id,
            ProviderPriceVersion.id == scenario.price_version_id,
            ProviderPriceVersion.provider == scenario.provider,
        )
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tabela de preços não encontrada.")
    items = (
        await db.scalars(
            select(ProviderPriceItem).where(
                ProviderPriceItem.tenant_id == user.tenant_id,
                ProviderPriceItem.price_version_id == version.id,
            )
        )
    ).all()
    by_metric = {item.metric: item for item in items}
    unknown = set(scenario.volumes) - set(by_metric)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Preço não configurado para: {', '.join(sorted(unknown))}.",
        )
    lines = []
    usage = Decimal("0")
    for metric, units in sorted(scenario.volumes.items()):
        item = by_metric[metric]
        billable = max(0, units - item.included_units)
        amount = _money(Decimal(item.unit_price) * billable)
        usage += amount
        lines.append(
            CostLine(
                metric=metric,
                units=units,
                billable_units=billable,
                unit_price=_money(Decimal(item.unit_price)),
                amount=amount,
            )
        )
    base = _money(Decimal(version.monthly_base_amount))
    usage = _money(usage)
    total = max(base, usage) if version.pricing_model == "commitment_floor" else base + usage
    return CostReport(
        provider=version.provider,
        currency=version.currency,
        pricing_model=version.pricing_model,
        monthly_base_amount=base,
        usage_amount=usage,
        total_amount=_money(total),
        quote_required=version.quote_required,
        observed_on=version.observed_on,
        provenance_url=version.provenance_url,
        lines=lines,
    )


async def record_provider_usage(
    db: AsyncSession,
    *,
    tenant_id: str,
    provider: str,
    metric: str,
    idempotency_key: str,
    envelope_id: str | None = None,
    units: int = 1,
) -> bool:
    key_hash = hashlib.sha256(f"{tenant_id}:{provider}:{metric}:{idempotency_key}".encode()).hexdigest()
    event = ProviderUsageEvent(
        tenant_id=tenant_id,
        provider=provider,
        envelope_id=envelope_id,
        metric=metric,
        units=units,
        idempotency_hash=key_hash,
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
        return True
    except IntegrityError:
        return False
