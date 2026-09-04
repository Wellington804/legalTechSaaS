import hashlib
import io
import zipfile
from pathlib import PurePath
from typing import Iterable

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import Select, and_, exists, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.tenant import Tenant
from app.models.branding import BrandAsset, BrandExport
from app.models.workspace import (
    WorkspaceCase,
    WorkspaceCaseAccess,
    WorkspaceClient,
    WorkspaceDocument,
    WorkspaceDocumentVersion,
    WorkspaceDocumentUpload,
    WorkspaceTask,
)


MAX_LIST_LIMIT = 200
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_UPLOAD_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
FINANCE_ROLES = {"admin", "partner"}
CASE_MANAGER_ROLES = {"admin", "partner", "lawyer"}
ADMIN_ROLES = {"admin", "partner"}


def bounded_limit(value: int) -> int:
    return min(max(value, 1), MAX_LIST_LIMIT)


def reset_document_review(document: WorkspaceDocument) -> None:
    """A new version always returns to draft; prior review entries stay immutable."""
    document.review_status = "draft"
    document.review_version = None
    document.reviewed_by_user_id = None
    document.reviewed_at = None


def require_role(user: User, allowed: Iterable[str]) -> None:
    if user.role not in set(allowed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")


def case_access_clause(user: User, case_table=WorkspaceCase):
    if user.role in ADMIN_ROLES:
        return true()
    return or_(
        case_table.restricted.is_(False),
        case_table.responsible_user_id == user.id,
        exists(
            select(WorkspaceCaseAccess.id).where(
                WorkspaceCaseAccess.tenant_id == user.tenant_id,
                WorkspaceCaseAccess.case_id == case_table.id,
                WorkspaceCaseAccess.user_id == user.id,
            )
        ),
    )


def authorized_case_query(user: User) -> Select:
    return select(WorkspaceCase).where(
        WorkspaceCase.tenant_id == user.tenant_id,
        case_access_clause(user),
    )


async def get_case(
    db: AsyncSession,
    user: User,
    case_id: str,
    *,
    for_update: bool = False,
) -> WorkspaceCase:
    statement = authorized_case_query(user).where(WorkspaceCase.id == case_id)
    if for_update:
        statement = statement.with_for_update()
    case = await db.scalar(statement)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caso nao encontrado.")
    return case


async def get_case_for_user(db: AsyncSession, tenant_id: str, user: User, case_id: str) -> WorkspaceCase:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caso nao encontrado.")
    return await get_case(db, user, case_id)


async def get_client(db: AsyncSession, user: User, client_id: str) -> WorkspaceClient:
    client = await db.scalar(
        select(WorkspaceClient).where(
            WorkspaceClient.id == client_id,
            WorkspaceClient.tenant_id == user.tenant_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado.")
    return client


async def get_document(
    db: AsyncSession,
    user: User,
    document_id: str,
    *,
    for_update: bool = False,
    refresh: bool = False,
) -> WorkspaceDocument:
    statement = select(WorkspaceDocument).where(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.tenant_id == user.tenant_id,
    ).execution_options(populate_existing=refresh)
    if for_update:
        statement = statement.with_for_update()
    document = await db.scalar(statement)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento nao encontrado.")
    if document.case_id:
        await get_case(db, user, document.case_id)
    return document


async def get_task(db: AsyncSession, user: User, task_id: str, *, for_update: bool = False) -> WorkspaceTask:
    statement = select(WorkspaceTask).where(
        WorkspaceTask.id == task_id,
        WorkspaceTask.tenant_id == user.tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    task = await db.scalar(statement)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarefa nao encontrada.")
    if task.case_id:
        await get_case(db, user, task.case_id)
    return task


async def active_tenant_user(db: AsyncSession, tenant_id: str, user_id: str) -> User:
    member = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Usuario do escritorio nao encontrado.")
    return member


async def lock_workspace_tenant(db: AsyncSession, tenant_id: str) -> Tenant:
    tenant = await db.scalar(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True)).with_for_update()
    )
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Escritorio nao encontrado.")
    return tenant


def document_version_bytes(content_text: str | None, file_content: bytes | None = None) -> int:
    return len((content_text or "").encode("utf-8")) + len(file_content or b"")


async def document_storage_used(db: AsyncSession, tenant_id: str) -> int:
    used_bytes = await db.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(
                        func.octet_length(WorkspaceDocumentVersion.file_content),
                        WorkspaceDocumentVersion.file_size,
                        0,
                    )
                    + func.coalesce(func.octet_length(WorkspaceDocumentVersion.content_text), 0)
                ),
                0,
            )
        ).where(WorkspaceDocumentVersion.tenant_id == tenant_id)
    )
    asset_bytes = await db.scalar(select(func.coalesce(func.sum(func.octet_length(BrandAsset.content)), 0)).where(BrandAsset.tenant_id == tenant_id))
    export_bytes = await db.scalar(select(func.coalesce(func.sum(
        func.coalesce(func.octet_length(BrandExport.pdf), BrandExport.pdf_size, 0)
        + func.coalesce(func.octet_length(BrandExport.docx), BrandExport.docx_size, 0)
    ), 0)).where(BrandExport.tenant_id == tenant_id))
    reserved_bytes = await db.scalar(
        select(func.coalesce(func.sum(WorkspaceDocumentUpload.expected_size), 0)).where(
            WorkspaceDocumentUpload.tenant_id == tenant_id,
            WorkspaceDocumentUpload.status.in_({"created", "uploaded", "processing"}),
            WorkspaceDocumentUpload.expires_at > func.now(),
        )
    )
    return int(used_bytes or 0) + int(asset_bytes or 0) + int(export_bytes or 0) + int(reserved_bytes or 0)


async def ensure_document_storage_capacity(db: AsyncSession, tenant_id: str, additional_bytes: int) -> None:
    if additional_bytes < 0:
        raise ValueError("additional_bytes must not be negative")
    tenant = await lock_workspace_tenant(db, tenant_id)
    if await document_storage_used(db, tenant_id) + additional_bytes > tenant.quota_storage_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="A quota de armazenamento do escritorio foi atingida.",
        )


def require_case_write(user: User, case: WorkspaceCase) -> None:
    require_role(user, CASE_MANAGER_ROLES)
    if user.role == "lawyer" and case.responsible_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Somente o responsavel pode alterar este caso.")


def require_document_write(user: User, document: WorkspaceDocument) -> None:
    if document.kind == "template":
        require_role(user, CASE_MANAGER_ROLES)
    elif user.role not in CASE_MANAGER_ROLES | {"paralegal"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")


def require_task_write(user: User, task: WorkspaceTask | None = None) -> None:
    if user.role not in CASE_MANAGER_ROLES | {"paralegal"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")
    if task and user.role == "paralegal" and task.assigned_user_id not in {None, user.id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tarefa atribuida a outro usuario.")


def require_finance_role(user: User) -> None:
    require_role(user, FINANCE_ROLES)


async def read_validated_upload(file: UploadFile) -> tuple[str, str, bytes, str]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nome do arquivo e obrigatorio.")
    filename = PurePath(file.filename).name
    if filename != file.filename or len(filename) > 255 or "\x00" in filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nome de arquivo invalido.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Arquivo vazio.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo excede 25 MB.")
    return validate_upload_bytes(filename, content)


def validate_upload_bytes(filename: str, content: bytes) -> tuple[str, str, bytes, str]:
    safe_name = PurePath(filename).name
    if safe_name != filename or not safe_name or len(safe_name) > 255 or "\x00" in safe_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nome de arquivo invalido.")
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo vazio ou maior que 25 MB.")
    suffix = PurePath(safe_name).suffix.casefold()
    content_type = ALLOWED_UPLOAD_TYPES.get(suffix)
    if not content_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use PDF, DOCX, XLSX, TXT, JPG ou PNG.")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PDF invalido.")
    if suffix in {".docx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                required = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
                entries = archive.infolist()
                if "[Content_Types].xml" not in archive.namelist() or required not in archive.namelist():
                    raise ValueError
                if len(entries) > 2_000 or sum(item.file_size for item in entries) > 50 * 1024 * 1024:
                    raise ValueError
                if any(item.compress_size and item.file_size / item.compress_size > 200 for item in entries):
                    raise ValueError
        except (ValueError, zipfile.BadZipFile):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Arquivo Office invalido ou inseguro.")
    if suffix == ".txt":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="TXT deve usar UTF-8.")
        if "<script" in text.casefold() or "<html" in text.casefold():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="HTML ativo nao e aceito.")
    if suffix in {".jpg", ".jpeg", ".png"}:
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS or image.format not in {"JPEG", "PNG"}:
                    raise ValueError
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Imagem invalida ou extensa demais.")
    return safe_name, content_type, content, hashlib.sha256(content).hexdigest()


def document_scope(user: User) -> Select:
    access = case_access_clause(user)
    return (
        select(WorkspaceDocument)
        .outerjoin(
            WorkspaceCase,
            and_(
                WorkspaceCase.id == WorkspaceDocument.case_id,
                WorkspaceCase.tenant_id == WorkspaceDocument.tenant_id,
            ),
        )
        .where(
            WorkspaceDocument.tenant_id == user.tenant_id,
            or_(WorkspaceDocument.case_id.is_(None), access),
        )
    )
