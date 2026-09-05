from datetime import datetime, timezone
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oab import OABEnrollment, OABEnrollmentChecklistItem
from app.schemas.oab import OABChecklistItemCreate, OABChecklistItemUpdate, OABEnrollmentCreate, OABEnrollmentUpdate


DIRECTORY_URL = "https://www.oab.org.br/seccional/se"
PROVISION_URL = "https://www.oab.org.br/leisnormas/legislacao/provimentos/178-2017"
SOURCE_VERSION = "oab-cf-directory-2026-09-05"
SOURCE_CHECKED_AT = datetime(2026, 9, 5, tzinfo=timezone.utc)
SOURCE_NOTICE = "Fonte externa: confirme dados, exigências e andamento diretamente com a Seccional. O LexFlow não consulta nem representa a OAB."

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}


class OABNotFoundError(Exception):
    pass


class OABRevisionConflictError(Exception):
    pass


class OABRequestConflictError(Exception):
    pass


def source_for_uf(uf: str) -> dict:
    return {
        "uf": uf,
        "state_name": STATE_NAMES[uf],
        "official_url": f"https://www.oab.org.br/seccional/{uf.lower()}",
        "directory_url": DIRECTORY_URL,
        "provision_url": PROVISION_URL,
        "source_version": SOURCE_VERSION,
        "source_checked_at": SOURCE_CHECKED_AT,
        "notice": SOURCE_NOTICE,
    }


def list_sources(query: str | None = None) -> list[dict]:
    normalized = unicodedata.normalize("NFKD", (query or "").strip().casefold()).encode("ascii", "ignore").decode()
    sources = [source_for_uf(uf) for uf in STATE_NAMES]
    if not normalized:
        return sources
    return [
        item for item in sources
        if normalized in item["uf"].casefold()
        or normalized in unicodedata.normalize("NFKD", item["state_name"].casefold()).encode("ascii", "ignore").decode()
    ]


class OABService:
    @staticmethod
    async def list_enrollments(db: AsyncSession, tenant_id: str, user_id: str) -> list[OABEnrollment]:
        return (
            await db.execute(
                select(OABEnrollment)
                .where(OABEnrollment.tenant_id == tenant_id, OABEnrollment.user_id == user_id)
                .order_by(OABEnrollment.updated_at.desc(), OABEnrollment.id)
            )
        ).scalars().all()

    @staticmethod
    async def get_enrollment(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str, *, for_update: bool = False) -> OABEnrollment:
        statement = select(OABEnrollment).where(
            OABEnrollment.id == enrollment_id,
            OABEnrollment.tenant_id == tenant_id,
            OABEnrollment.user_id == user_id,
        )
        enrollment = await db.scalar(statement.with_for_update() if for_update else statement)
        if not enrollment:
            raise OABNotFoundError
        return enrollment

    @staticmethod
    async def list_checklist(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str) -> list[OABEnrollmentChecklistItem]:
        return (
            await db.execute(
                select(OABEnrollmentChecklistItem)
                .where(
                    OABEnrollmentChecklistItem.tenant_id == tenant_id,
                    OABEnrollmentChecklistItem.user_id == user_id,
                    OABEnrollmentChecklistItem.enrollment_id == enrollment_id,
                )
                .order_by(OABEnrollmentChecklistItem.created_at, OABEnrollmentChecklistItem.id)
            )
        ).scalars().all()

    @staticmethod
    async def list_owner_checklist(db: AsyncSession, tenant_id: str, user_id: str) -> list[OABEnrollmentChecklistItem]:
        return (
            await db.execute(
                select(OABEnrollmentChecklistItem)
                .where(
                    OABEnrollmentChecklistItem.tenant_id == tenant_id,
                    OABEnrollmentChecklistItem.user_id == user_id,
                )
                .order_by(OABEnrollmentChecklistItem.created_at, OABEnrollmentChecklistItem.id)
            )
        ).scalars().all()

    @staticmethod
    async def create_enrollment(db: AsyncSession, tenant_id: str, user_id: str, payload: OABEnrollmentCreate) -> tuple[OABEnrollment, bool]:
        source = source_for_uf(payload.uf)
        request_id = str(payload.request_id)
        values = payload.model_dump(exclude={"request_id"})
        existing = await db.scalar(select(OABEnrollment).where(
            OABEnrollment.tenant_id == tenant_id,
            OABEnrollment.user_id == user_id,
            OABEnrollment.request_id == request_id,
        ))
        if existing:
            if all(getattr(existing, field) == value for field, value in values.items()):
                return existing, True
            raise OABRequestConflictError
        enrollment = OABEnrollment(
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            source_url=source["official_url"],
            source_version=source["source_version"],
            source_checked_at=source["source_checked_at"],
            **values,
        )
        try:
            async with db.begin_nested():
                db.add(enrollment)
                await db.flush()
        except IntegrityError:
            existing = await db.scalar(select(OABEnrollment).where(
                OABEnrollment.tenant_id == tenant_id,
                OABEnrollment.user_id == user_id,
                OABEnrollment.request_id == request_id,
            ))
            if existing and all(getattr(existing, field) == value for field, value in values.items()):
                return existing, True
            raise OABRequestConflictError from None
        return enrollment, False

    @staticmethod
    async def update_enrollment(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str, payload: OABEnrollmentUpdate) -> OABEnrollment:
        enrollment = await OABService.get_enrollment(db, tenant_id, user_id, enrollment_id, for_update=True)
        if enrollment.revision != payload.expected_revision:
            raise OABRevisionConflictError
        changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if "uf" in changes:
            source = source_for_uf(changes["uf"])
            changes.update(source_url=source["official_url"], source_version=source["source_version"], source_checked_at=source["source_checked_at"])
        for field, value in changes.items():
            setattr(enrollment, field, value)
        enrollment.revision += 1
        enrollment.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return enrollment

    @staticmethod
    async def add_checklist_item(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str, payload: OABChecklistItemCreate) -> tuple[OABEnrollmentChecklistItem, bool]:
        await OABService.get_enrollment(db, tenant_id, user_id, enrollment_id)
        request_id = str(payload.request_id)
        values = payload.model_dump(exclude={"request_id"})
        statement = select(OABEnrollmentChecklistItem).where(
            OABEnrollmentChecklistItem.tenant_id == tenant_id,
            OABEnrollmentChecklistItem.user_id == user_id,
            OABEnrollmentChecklistItem.enrollment_id == enrollment_id,
            OABEnrollmentChecklistItem.request_id == request_id,
        )
        existing = await db.scalar(statement)
        if existing:
            if all(getattr(existing, field) == value for field, value in values.items()):
                return existing, True
            raise OABRequestConflictError
        item = OABEnrollmentChecklistItem(tenant_id=tenant_id, user_id=user_id, enrollment_id=enrollment_id, request_id=request_id, **values)
        try:
            async with db.begin_nested():
                db.add(item)
                await db.flush()
        except IntegrityError:
            existing = await db.scalar(statement)
            if existing and all(getattr(existing, field) == value for field, value in values.items()):
                return existing, True
            raise OABRequestConflictError from None
        return item, False

    @staticmethod
    async def get_checklist_item(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str, item_id: str, *, for_update: bool = False) -> OABEnrollmentChecklistItem:
        statement = select(OABEnrollmentChecklistItem).where(
            OABEnrollmentChecklistItem.id == item_id,
            OABEnrollmentChecklistItem.enrollment_id == enrollment_id,
            OABEnrollmentChecklistItem.tenant_id == tenant_id,
            OABEnrollmentChecklistItem.user_id == user_id,
        )
        item = await db.scalar(statement.with_for_update() if for_update else statement)
        if not item:
            raise OABNotFoundError
        return item

    @staticmethod
    async def update_checklist_item(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str, item_id: str, payload: OABChecklistItemUpdate) -> OABEnrollmentChecklistItem:
        item = await OABService.get_checklist_item(db, tenant_id, user_id, enrollment_id, item_id, for_update=True)
        if item.revision != payload.expected_revision:
            raise OABRevisionConflictError
        for field, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
            setattr(item, field, value)
        item.revision += 1
        item.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return item

    @staticmethod
    async def delete_checklist_item(db: AsyncSession, tenant_id: str, user_id: str, enrollment_id: str, item_id: str, expected_revision: int) -> None:
        item = await OABService.get_checklist_item(db, tenant_id, user_id, enrollment_id, item_id, for_update=True)
        if item.revision != expected_revision:
            raise OABRevisionConflictError
        await db.delete(item)
