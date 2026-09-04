import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.workspace import create_document_record
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_tenant_write
from app.models.document_kit import DocumentKitReceipt
from app.models.user import User
from app.schemas.document_kit import DocumentKitCreate, DocumentKitPreview
from app.schemas.workspace import DocumentCreate, DocumentResponse
from app.services.document_kit import catalog, digest, document_context, preview
from app.services.workspace_service import get_case, get_document, lock_workspace_tenant, require_case_write


router = APIRouter()


@router.get("/templates")
async def templates(current_user: CurrentUser):
    return catalog()


@router.get("/context")
async def context(case_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await document_context(db, current_user, case_id)


@router.post("/preview")
async def preview_document(payload: DocumentKitPreview, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rendered, _ = await preview(db, current_user, payload)
    return rendered


@router.post("/documents", status_code=201)
async def create_document(payload: DocumentKitCreate, request: Request, current_user: CurrentUser,
                          db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    # The quota's existing tenant lock also serializes concurrent retries before receipt lookup.
    await lock_workspace_tenant(db, current_user.tenant_id)
    case = await get_case(db, current_user, payload.case_id)
    if current_user.role != "paralegal":
        require_case_write(current_user, case)
    request_hash = digest(payload.model_dump(mode="json", exclude={"request_id"}))
    receipt = await db.scalar(select(DocumentKitReceipt).where(
        DocumentKitReceipt.tenant_id == current_user.tenant_id,
        DocumentKitReceipt.user_id == current_user.id,
        DocumentKitReceipt.request_id == str(payload.request_id),
    ))
    if receipt:
        if not hmac.compare_digest(receipt.payload_hash, request_hash):
            raise HTTPException(409, "Esta solicitação já foi usada com outro conteúdo.")
        document = await get_document(db, current_user, receipt.document_id)
        return {"document": DocumentResponse.model_validate(document)}
    rendered, case = await preview(db, current_user, payload, lock=True)
    if payload.source.model_dump() != rendered["source"]:
        raise HTTPException(409, "Dados ou texto alterados desde a prévia. Gere uma nova prévia e confira novamente.")
    if rendered["missing_fields"]:
        raise HTTPException(422, "Preencha os campos indicados e confira o cadastro antes de salvar.")
    document_type = {
        "power_of_attorney": "power_of_attorney",
        "fee_agreement": "contract",
        "initial_petition": "petition",
        "defense": "petition",
        "intermediate_petition": "petition",
        "extrajudicial_notice": "notice",
        "collection_notice": "notice",
    }.get(payload.template_key, "general")
    document = await create_document_record(DocumentCreate(
        case_id=case.id, client_id=case.client_id, kind="note" if payload.template_key == "intake" else "document",
        document_type=document_type, title=rendered["title"], content_text=rendered["content_text"], content_format="plain",
    ), request, current_user, db, commit=False)
    db.add(DocumentKitReceipt(tenant_id=current_user.tenant_id, user_id=current_user.id,
                              request_id=str(payload.request_id), payload_hash=request_hash, document_id=document.id))
    await db.commit()
    return {"document": DocumentResponse.model_validate(document)}
