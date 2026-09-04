"""Approved document identity, never applied to original evidence files."""
import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.api.v1.endpoints.research import reserve_request
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, require_tenant_write
from app.models.branding import BrandAsset, BrandExport, BrandProfile, BrandVersion
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.branding import (
    AssetKind,
    BrandAssetExtract,
    BrandCreate,
    BrandDuplicate,
    BrandExportInput,
    BrandPreview,
    BrandRevision,
    BrandSettings,
    BrandSuggestion,
    BrandUpdate,
    BrandVariantSettings,
    DocumentType,
    FONT_FAMILIES,
)
from app.services.audit_service import AuditService
from app.services.brand_ai import ai_available, image_ai_available, suggest_brand
from app.services.brand_documents import crop_reference, isolate_layer_image, pdf_available, render_documents, render_reference_page, validate_reference
from app.services.document_kit import format_address
from app.services.workspace_service import ADMIN_ROLES, CASE_MANAGER_ROLES, MAX_UPLOAD_BYTES, ensure_document_storage_capacity, get_case, get_document, require_document_write, require_role
from app.services.document_storage import create_download_url, enabled as r2_enabled, put as put_object, read as read_object, scan as scan_object


router = APIRouter()
ASSET_FIELDS = {"logo_asset_id": "logo", "logo_dark_asset_id": "logo_dark", "logo_mono_asset_id": "logo_mono", "watermark_asset_id": "watermark", "background_asset_id": "background"}
VARIANT_FIELDS = set(BrandVariantSettings.model_fields)
PERSONAL_FIELDS = {"professional_name", "oab", "professional_email", "professional_phone", "professional_address"}
PROFESSIONAL_LABELS = {
    "professional_name": "Nome profissional",
    "oab": "OAB",
    "professional_email": "E-mail profissional",
    "professional_phone": "Telefone profissional",
    "professional_address": "Endereço profissional",
    "office_name": "Nome do escritório",
    "office_email": "E-mail do escritório",
    "office_phone": "Telefone do escritório",
    "office_address": "Endereço do escritório",
    "website": "Site",
}


def can_edit(profile: BrandProfile, user: User) -> bool:
    return user.role in CASE_MANAGER_ROLES and (
        profile.scope == "personal" and profile.owner_user_id == user.id
        or profile.scope == "office" and user.role in ADMIN_ROLES
    )


async def profile_for_editor(db: AsyncSession, user: User, profile_id: str, *, lock=False) -> BrandProfile:
    statement = select(BrandProfile).where(BrandProfile.tenant_id == user.tenant_id, BrandProfile.id == profile_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    profile = await db.scalar(statement)
    if not profile or profile.archived_at or not can_edit(profile, user):
        raise HTTPException(404, "Identidade não encontrada ou sem permissão de edição.")
    return profile


def check_revision(profile: BrandProfile, revision: int):
    if profile.revision != revision:
        raise HTTPException(409, "A identidade foi alterada em outra sessão. Recarregue antes de continuar.")


def normalized_variants(value: dict | None) -> dict:
    return {
        kind: BrandVariantSettings.model_validate(settings).model_dump(mode="json", exclude_none=True)
        for kind, settings in (value or {}).items()
        if kind != "general"
    }


def settings_for_document(settings: dict, variants: dict | None, document_type: DocumentType) -> dict:
    base = BrandSettings.model_validate(settings).model_dump(mode="json")
    if document_type == "general":
        return base
    override = BrandVariantSettings.model_validate((variants or {}).get(document_type, {})).model_dump(mode="json", exclude_none=True)
    return BrandSettings.model_validate({**base, **override}).model_dump(mode="json")


async def professional_values(
    db: AsyncSession,
    user: User,
    profile: BrandProfile,
    responsible_user_id: str | None = None,
) -> dict[str, str]:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    lawyer_id = profile.owner_user_id if profile.scope == "personal" else responsible_user_id or user.id
    lawyer = await db.scalar(select(User).where(User.tenant_id == user.tenant_id, User.id == lawyer_id, User.is_active.is_(True)))
    if not tenant or not lawyer:
        raise HTTPException(409, "Confira o advogado responsável e os dados do escritório antes de continuar.")
    oab = ""
    if lawyer.oab_number:
        oab = f"OAB/{lawyer.oab_uf} {lawyer.oab_number}" if lawyer.oab_uf else f"OAB {lawyer.oab_number}"
    values = {
        "professional_name": lawyer.professional_name or lawyer.full_name or "",
        "oab": oab,
        "professional_email": lawyer.professional_email or lawyer.email or "",
        "professional_phone": lawyer.professional_phone or "",
        "professional_address": format_address(lawyer.professional_address),
        "office_name": tenant.legal_name or tenant.name or "",
        "office_email": tenant.office_email or "",
        "office_phone": tenant.office_phone or "",
        "office_address": format_address(tenant.office_address),
        "website": tenant.website or "",
    }
    return {key: str(value).strip() for key, value in values.items()}


def professional_payload(values: dict[str, str]) -> dict:
    return {
        "fields": [
            {
                "key": key,
                "label": label,
                "value": values.get(key, ""),
                "source": "Perfil profissional" if key in PERSONAL_FIELDS else "Cadastro do escritório",
                "complete": bool(values.get(key)),
            }
            for key, label in PROFESSIONAL_LABELS.items()
        ]
    }


def materialize_professional_text(tokens: dict, values: dict[str, str]) -> tuple[dict, list[str]]:
    result = BrandSettings.model_validate(tokens).model_dump(mode="json")
    overrides = result.get("professional_overrides", {})
    missing = []

    def lines(area: str, custom: str) -> str:
        selected = result.get(f"{area}_fields", [])
        output = []
        for key in selected:
            value = str(overrides.get(key) or values.get(key) or "").strip()
            if not value:
                missing.append(key)
            else:
                output.append(value)
        if custom.strip():
            output.append(custom.strip())
        return "\n".join(output)

    result["header_text"] = lines("header", result.get("header_text", ""))
    result["footer_text"] = lines("footer", result.get("footer_text", ""))
    for layer in result.get("layout_layers", []):
        key = layer.get("binding")
        if not key:
            continue
        value = str(overrides.get(key) or values.get(key) or "").strip()
        if value:
            layer["text"] = value
        else:
            missing.append(key)
    return result, missing


def validate_professional_overrides(scope: str, tokens: dict):
    if scope == "office" and PERSONAL_FIELDS.intersection(tokens.get("professional_overrides", {})):
        raise HTTPException(422, "Na identidade do escritório, dados do advogado devem vir do responsável pelo processo.")


async def asset_content(asset: BrandAsset) -> bytes:
    if asset.object_key:
        try:
            return await asyncio.to_thread(read_object, asset.object_key)
        except Exception as exc:
            raise HTTPException(503, "Arquivo visual temporariamente indisponível.") from exc
    if asset.content is None:
        raise HTTPException(404, "Arquivo visual não encontrado.")
    return asset.content


async def brand_assets(db: AsyncSession, user: User, profile: BrandProfile, tokens: dict) -> dict[str, bytes]:
    result = {}
    for field, kind in ASSET_FIELDS.items():
        asset_id = tokens.get(field)
        if not asset_id:
            continue
        asset = await db.scalar(select(BrandAsset).where(BrandAsset.tenant_id == user.tenant_id, BrandAsset.profile_id == profile.id, BrandAsset.id == asset_id, BrandAsset.kind == kind))
        if not asset:
            raise HTTPException(422, "Imagem inexistente, de outro perfil ou de tipo incompatível.")
        result[asset.id] = await asset_content(asset)
    for layer in tokens.get("layout_layers", []):
        asset_id = layer.get("asset_id") if layer.get("kind") == "image" else None
        if not asset_id or asset_id in result:
            continue
        asset = await db.scalar(select(BrandAsset).where(
            BrandAsset.tenant_id == user.tenant_id, BrandAsset.profile_id == profile.id,
            BrandAsset.id == asset_id, BrandAsset.kind != "reference",
            BrandAsset.content_type.in_(("image/png", "image/jpeg")),
        ))
        if not asset:
            raise HTTPException(422, "Imagem de camada inexistente ou pertencente a outra identidade.")
        result[asset.id] = await asset_content(asset)
    return result


def profile_payload(profile: BrandProfile, user: User, tokens: dict | None = None, variants: dict | None = None) -> dict:
    settings_payload = BrandSettings.model_validate(tokens if tokens is not None else profile.settings).model_dump(mode="json")
    variants_payload = normalized_variants(variants if variants is not None else profile.variants)
    return {"id": profile.id, "name": profile.name, "scope": profile.scope, "owner_user_id": profile.owner_user_id,
            "revision": profile.revision, "settings": settings_payload,
            "variants": variants_payload, "archived_at": profile.archived_at,
            "published_version": profile.published_version, "can_edit": can_edit(profile, user)}


def asset_payload(asset: BrandAsset) -> dict:
    return {"id": asset.id, "filename": asset.filename, "kind": asset.kind, "content_type": asset.content_type,
            "analysis": asset.analysis,
            "size": asset.size, "sha256": asset.sha256, "created_at": asset.created_at,
            "stored_externally": bool(asset.object_key)}


def export_payload(export: BrandExport) -> dict:
    return {"id": export.id, "document_version": export.document_version, "profile_id": export.profile_id,
            "brand_version": export.brand_version, "document_type": export.document_type, "created_at": export.created_at,
            "sha256_pdf": export.sha256_pdf, "sha256_docx": export.sha256_docx}


async def audit(db: AsyncSession, user: User, action: str, resource_id: str, details: dict | None = None):
    await AuditService.log_action(db, user.tenant_id, user.id, action, "branding", resource_id, details or {})


async def published_profiles(db: AsyncSession, user: User, document):
    owner = user.id
    if document.case_id:
        owner = (await get_case(db, user, document.case_id)).responsible_user_id
    return (await db.execute(select(BrandProfile, BrandVersion).join(BrandVersion, and_(
        BrandVersion.tenant_id == BrandProfile.tenant_id, BrandVersion.profile_id == BrandProfile.id,
        BrandVersion.version == BrandProfile.published_version)).where(BrandProfile.tenant_id == user.tenant_id,
        BrandProfile.archived_at.is_(None),
        or_(BrandProfile.scope == "office", and_(BrandProfile.scope == "personal", BrandProfile.owner_user_id == owner)))
        .order_by((BrandProfile.scope == "personal").desc(), BrandVersion.created_at.desc()).limit(200))).all()


@router.get("/capabilities")
async def capabilities(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    enabled = ai_available()
    return {"fonts": FONT_FAMILIES, "pdf_available": pdf_available(), "ai_available": enabled,
            "image_ai_available": enabled and image_ai_available()}


@router.get("/profiles")
async def profiles(user: CurrentUser, document_id: str | None = Query(default=None, max_length=64), db: AsyncSession = Depends(get_db)):
    require_role(user, CASE_MANAGER_ROLES | {"paralegal"})
    if document_id:
        document = await get_document(db, user, document_id)
        return {"items": [profile_payload(p, user, v.settings, v.variants) for p, v in await published_profiles(db, user, document)]}
    records = (await db.scalars(select(BrandProfile).where(BrandProfile.tenant_id == user.tenant_id,
        BrandProfile.archived_at.is_(None), or_(BrandProfile.owner_user_id == user.id, BrandProfile.scope == "office"))
        .order_by(BrandProfile.updated_at.desc()).limit(200))).all()
    items = []
    for profile in records:
        if can_edit(profile, user):
            items.append(profile_payload(profile, user))
        elif profile.published_version:
            version = await db.scalar(select(BrandVersion).where(BrandVersion.tenant_id == user.tenant_id,
                BrandVersion.profile_id == profile.id, BrandVersion.version == profile.published_version))
            items.append(profile_payload(profile, user, version.settings, version.variants))
    return {"items": items}


@router.get("/profiles/{profile_id}/professional-data")
async def profile_professional_data(profile_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    profile = await profile_for_editor(db, user, profile_id)
    return professional_payload(await professional_values(db, user, profile))


@router.post("/profiles/{profile_id}/duplicate", status_code=201)
async def duplicate_profile(profile_id: str, body: BrandDuplicate, user: CurrentUser,
                            db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    source = await profile_for_editor(db, user, profile_id)
    check_revision(source, body.expected_revision)
    tokens = BrandSettings.model_validate(source.settings).model_dump(mode="json")
    for field in ASSET_FIELDS:
        tokens[field] = None
    tokens["layout_layers"] = [layer for layer in tokens.get("layout_layers", []) if layer.get("kind") != "image"]
    if tokens.get("layout_mode") == "composed" and not tokens["layout_layers"]:
        tokens["layout_mode"] = "reconstructed"
    duplicate = BrandProfile(
        tenant_id=user.tenant_id,
        name=body.name or f"Cópia de {source.name}"[:100],
        scope=source.scope,
        owner_user_id=user.id if source.scope == "personal" else None,
        settings=tokens,
        variants=normalized_variants(source.variants),
    )
    db.add(duplicate)
    await db.flush()
    await audit(db, user, "BRAND_PROFILE_DUPLICATED", duplicate.id, {"source_profile_id": source.id, "assets_copied": False})
    await db.commit()
    return profile_payload(duplicate, user)


@router.post("/profiles/{profile_id}/archive")
async def archive_profile(profile_id: str, body: BrandRevision, user: CurrentUser,
                          db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id, lock=True)
    check_revision(profile, body.expected_revision)
    profile.archived_at = datetime.now(timezone.utc)
    profile.revision += 1
    await audit(db, user, "BRAND_PROFILE_ARCHIVED", profile.id, {"published_version": profile.published_version})
    await db.commit()
    return profile_payload(profile, user)


@router.post("/profiles", status_code=201)
async def create_profile(body: BrandCreate, user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    require_role(user, ADMIN_ROLES if body.scope == "office" else CASE_MANAGER_ROLES)
    initial_settings = body.settings.model_dump()
    if any(initial_settings.get(field) for field in ASSET_FIELDS) or any(layer.get("asset_id") for layer in initial_settings.get("layout_layers", [])):
        raise HTTPException(422, "Crie o perfil antes de anexar suas imagens.")
    tokens = body.settings.model_dump(mode="json")
    validate_professional_overrides(body.scope, tokens)
    if not tokens["header_fields"] and not tokens["footer_fields"] and not tokens["header_text"] and not tokens["footer_text"]:
        tokens["header_fields"] = ["professional_name", "oab"]
        tokens["footer_fields"] = ["office_name", "professional_address", "professional_phone", "professional_email"]
    profile = BrandProfile(tenant_id=user.tenant_id, name=body.name, scope=body.scope,
        owner_user_id=user.id if body.scope == "personal" else None, settings=tokens, variants=normalized_variants(body.variants))
    db.add(profile)
    await db.flush()
    await audit(db, user, "BRAND_PROFILE_CREATED", profile.id, {"scope": body.scope})
    await db.commit()
    return profile_payload(profile, user)


@router.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, body: BrandUpdate, user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id, lock=True)
    check_revision(profile, body.expected_revision)
    tokens = body.settings.model_dump()
    validate_professional_overrides(profile.scope, tokens)
    await brand_assets(db, user, profile, tokens)
    profile.name, profile.settings, profile.variants = body.name, tokens, normalized_variants(body.variants)
    profile.revision += 1
    await audit(db, user, "BRAND_DRAFT_UPDATED", profile.id, {"revision": profile.revision})
    await db.commit()
    return profile_payload(profile, user)


@router.get("/profiles/{profile_id}/versions")
async def versions(profile_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    profile = await profile_for_editor(db, user, profile_id)
    records = (await db.scalars(select(BrandVersion).where(BrandVersion.tenant_id == user.tenant_id, BrandVersion.profile_id == profile.id)
        .order_by(BrandVersion.version.desc()).limit(200))).all()
    return {"items": [{"id": v.id, "version": v.version, "settings": BrandSettings.model_validate(v.settings).model_dump(mode="json"), "variants": normalized_variants(v.variants),
                       "created_at": v.created_at} for v in records]}


@router.post("/profiles/{profile_id}/publish")
async def publish(profile_id: str, body: BrandRevision, user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id, lock=True)
    check_revision(profile, body.expected_revision)
    tokens = BrandSettings.model_validate(profile.settings).model_dump(mode="json")
    validate_professional_overrides(profile.scope, tokens)
    variants = normalized_variants(profile.variants)
    professional = await professional_values(db, user, profile)
    rendered = []
    missing = []
    for document_type in ["general", *variants]:
        variant_tokens = settings_for_document(tokens, variants, document_type)
        materialized, variant_missing = materialize_professional_text(variant_tokens, professional)
        rendered.append((document_type, materialized))
        missing.extend(variant_missing)
    if missing:
        labels = ", ".join(PROFESSIONAL_LABELS[key] for key in dict.fromkeys(missing))
        raise HTTPException(422, f"Complete os dados profissionais selecionados antes de publicar: {labels}.")
    images = await brand_assets(db, user, profile, tokens)
    for document_type, rendered_tokens in rendered:
        await render(user, f"PRÉVIA DE PUBLICAÇÃO — {document_type.upper()} — NÃO PROTOCOLAR", "Validação técnica da identidade documental antes da publicação.", rendered_tokens, images)
    number = (profile.published_version or 0) + 1
    db.add(BrandVersion(tenant_id=user.tenant_id, profile_id=profile.id, version=number, settings=tokens,
        variants=variants, professional_snapshot=professional, created_by_user_id=user.id))
    await db.flush()
    profile.published_version = number
    profile.revision += 1
    await audit(db, user, "BRAND_PUBLISHED", profile.id, {"version": number})
    await db.commit()
    return profile_payload(profile, user)


@router.get("/profiles/{profile_id}/assets")
async def assets(profile_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    profile = await profile_for_editor(db, user, profile_id)
    records = (await db.scalars(select(BrandAsset).options(defer(BrandAsset.content)).where(BrandAsset.tenant_id == user.tenant_id, BrandAsset.profile_id == profile.id)
        .order_by(BrandAsset.created_at.desc()).limit(200))).all()
    return {"items": [asset_payload(a) for a in records]}


async def store_asset(db: AsyncSession, user: User, profile: BrandProfile, filename: str, content: bytes, kind: str,
                      *, reuse_existing: bool = False) -> BrandAsset:
    try:
        mime, normalized, analysis = await asyncio.to_thread(validate_reference, filename, content, kind)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    digest = hashlib.sha256(normalized).hexdigest()
    if reuse_existing:
        existing = await db.scalar(select(BrandAsset).where(
            BrandAsset.tenant_id == user.tenant_id, BrandAsset.profile_id == profile.id,
            BrandAsset.kind == kind, BrandAsset.sha256 == digest))
        if existing:
            return existing
    await ensure_document_storage_capacity(db, user.tenant_id, len(normalized))
    asset_id = str(uuid.uuid4())
    object_key = None
    stored_content = normalized
    if r2_enabled():
        try:
            await asyncio.to_thread(scan_object, normalized)
            object_key = f"branding/{user.tenant_id}/{profile.id}/{asset_id}"
            await asyncio.to_thread(put_object, object_key, normalized, mime, filename)
            stored_content = None
        except Exception as exc:
            raise HTTPException(503, "Não foi possível validar e armazenar o arquivo com segurança.") from exc
    asset = BrandAsset(id=asset_id, tenant_id=user.tenant_id, profile_id=profile.id, kind=kind, filename=filename,
        content_type=mime, content=stored_content, object_key=object_key, size=len(normalized), sha256=digest,
        analysis=analysis, created_by_user_id=user.id)
    db.add(asset)
    await db.flush()
    return asset


@router.post("/profiles/{profile_id}/assets", status_code=201)
async def upload_asset(profile_id: str, user: CurrentUser, kind: AssetKind = Form(...), file: UploadFile = File(...), db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id, lock=True)
    filename = file.filename or ""
    if not filename or PurePath(filename).name != filename or "\\" in filename or len(filename) > 255 or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, "Nome de arquivo inválido.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Referência deve ter no máximo 10 MB.")
    await reserve_request(user.tenant_id, "brand_import", 60, 3600)
    asset = await store_asset(db, user, profile, filename, content, kind)
    await audit(db, user, "BRAND_ASSET_IMPORTED", profile.id, {"asset_id": asset.id, "sha256": asset.sha256, "kind": kind})
    await db.commit()
    return asset_payload(asset)


def download(content: bytes, mime: str, filename: str, *, inline=False) -> Response:
    return Response(content, media_type=mime, headers={"Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/assets/{asset_id}/download")
async def download_asset(asset_id: str, user: CurrentUser, inline: bool = Query(default=False), db: AsyncSession = Depends(get_db)):
    asset = await db.scalar(select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.tenant_id == user.tenant_id))
    if not asset:
        raise HTTPException(404, "Imagem não encontrada.")
    await profile_for_editor(db, user, asset.profile_id)
    if inline and asset.content_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(422, "Somente imagens podem ser exibidas diretamente.")
    # Inline previews stay on the authenticated origin. Following a presigned R2
    # redirect from fetch() makes private editor images depend on bucket CORS.
    if asset.object_key and not inline:
        url = await asyncio.to_thread(create_download_url, asset.object_key, asset.filename, asset.content_type, inline=inline)
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})
    return download(await asset_content(asset), asset.content_type, asset.filename, inline=inline)


@router.get("/assets/{asset_id}/pages/{page}")
async def preview_asset_page(asset_id: str, page: int, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    asset = await db.scalar(select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.tenant_id == user.tenant_id))
    if not asset or asset.kind != "reference":
        raise HTTPException(404, "Referência não encontrada.")
    await profile_for_editor(db, user, asset.profile_id)
    try:
        rendered = await asyncio.to_thread(render_reference_page, await asset_content(asset), asset.content_type, page)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return download(rendered, "image/png", f"pagina-{page}.png", inline=True)


@router.post("/profiles/{profile_id}/assets/{asset_id}/extract", status_code=201)
async def extract_asset(profile_id: str, asset_id: str, body: BrandAssetExtract, user: CurrentUser,
                        db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id, lock=True)
    check_revision(profile, body.expected_revision)
    source = await db.scalar(select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.profile_id == profile.id,
                                                     BrandAsset.tenant_id == user.tenant_id, BrandAsset.kind == "reference"))
    if not source:
        raise HTTPException(404, "Referência não encontrada.")
    pages = source.analysis.get("identified", {}).get("pages") if isinstance(source.analysis, dict) else None
    if body.page != 1 and (source.content_type != "application/pdf" or not isinstance(pages, int) or body.page > pages):
        raise HTTPException(422, "A página escolhida não existe nesta referência.")
    await reserve_request(user.tenant_id, "brand_import", 60, 3600)
    try:
        image = await asyncio.to_thread(crop_reference, await asset_content(source), source.content_type, body.page,
                                        (body.x_percent, body.y_percent, body.width_percent, body.height_percent))
        if body.kind in {"logo", "watermark"}:
            image = await asyncio.to_thread(isolate_layer_image, image, faint_only=body.kind == "watermark")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    labels = {"logo": "logotipo", "watermark": "marca-dagua", "background": "papel-timbrado"}
    asset = await store_asset(db, user, profile, f"{labels[body.kind]}-pagina-{body.page}.png", image, body.kind, reuse_existing=True)
    await audit(db, user, "BRAND_REFERENCE_EXTRACTED", profile.id, {
        "source_asset_id": source.id, "asset_id": asset.id, "kind": body.kind, "page": body.page,
        "crop_percent": [body.x_percent, body.y_percent, body.width_percent, body.height_percent],
    })
    await db.commit()
    return asset_payload(asset)


@router.post("/profiles/{profile_id}/suggest")
async def suggest(profile_id: str, body: BrandSuggestion, user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id)
    check_revision(profile, body.expected_revision)
    if not body.consent:
        raise HTTPException(403, "Confirme o envio das referências ao assistente.")
    references = []
    reference_sources = []
    for asset_id in dict.fromkeys(body.reference_ids):
        asset = await db.scalar(select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.profile_id == profile.id, BrandAsset.tenant_id == user.tenant_id))
        if not asset:
            raise HTTPException(422, "Referência não pertence a este perfil.")
        page = body.reference_pages.get(asset_id)
        pages = asset.analysis.get("identified", {}).get("pages") if isinstance(asset.analysis, dict) else None
        if page is not None and (asset.content_type != "application/pdf" or not isinstance(pages, int) or page > pages):
            raise HTTPException(422, "A página escolhida não existe nesta referência.")
        content = await asset_content(asset)
        content_type = asset.content_type
        selected_page = page
        if asset.content_type == "application/pdf":
            selected_page = page or 1
            try:
                content = await asyncio.to_thread(render_reference_page, content, asset.content_type, selected_page)
                content_type = "image/png"
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from exc
        reference_sources.append({"asset": asset, "content": content, "content_type": content_type})
        references.append({"content_type": content_type, "content": content,
                           "analysis": asset.analysis, "page": selected_page})
    if not ai_available() or body.generate_logo and not image_ai_available():
        raise HTTPException(503, "IA não configurada.")
    await reserve_request(user.tenant_id, "ai", settings.AI_REQUESTS_PER_DAY, 86400)
    if body.reference_intent == "reproduce" and references:
        await reserve_request(user.tenant_id, "ai", settings.AI_REQUESTS_PER_DAY, 86400)
    if body.generate_logo:
        await reserve_request(user.tenant_id, "ai", settings.AI_REQUESTS_PER_DAY, 86400)
    tokens = settings_for_document(profile.settings, profile.variants, body.document_type)
    await audit(db, user, "BRAND_AI_REQUESTED", profile.id, {"reference_ids": body.reference_ids,
        "generate_logo": body.generate_logo, "reference_intent": body.reference_intent,
        "reference_pages": body.reference_pages,
        "document_type": body.document_type, "selected_element": body.selected_element})
    await db.commit()  # Do not retain database locks during the external request.
    proposal = await suggest_brand(tokens, body.brief, references, body.generate_logo,
        reference_intent=body.reference_intent, document_type=body.document_type,
        selected_element=body.selected_element, selected_layer_id=body.selected_layer_id)
    await _set_tenant_context(db, user.tenant_id)
    profile = await profile_for_editor(db, user, profile_id, lock=True)
    check_revision(profile, body.expected_revision)
    extractions = proposal.pop("asset_extractions", [])
    if extractions:
        await reserve_request(user.tenant_id, "brand_import", 60, 3600)
        layers = {layer.get("id"): layer for layer in proposal.get("settings", {}).get("layout_layers", [])}
        failed_layers = set()
        extracted_roles = set()
        for item in extractions:
            try:
                source = reference_sources[int(item["reference_index"]) - 1]
                layer = layers[item["layer_id"]]
                crop = item["crop"]
                image = await asyncio.to_thread(crop_reference, source["content"], source["content_type"], 1,
                    (crop["x_percent"], crop["y_percent"], crop["width_percent"], crop["height_percent"]))
                image = await asyncio.to_thread(isolate_layer_image, image, faint_only=item.get("role") == "watermark")
            except (IndexError, KeyError, TypeError, ValueError, RuntimeError):
                failed_layers.add(item.get("layer_id"))
                continue
            kind = "watermark" if item.get("role") == "watermark" else "logo"
            asset = await store_asset(db, user, profile, f"{kind}-ia-{item['layer_id']}.png", image, kind, reuse_existing=True)
            layer["asset_id"] = asset.id
            proposal["settings"][f"{kind}_asset_id"] = asset.id
            extracted_roles.add(kind)
            await audit(db, user, "BRAND_REFERENCE_EXTRACTED", profile.id, {
                "source_asset_id": source["asset"].id, "asset_id": asset.id, "kind": kind,
                "page": body.reference_pages.get(source["asset"].id, 1), "automatic": True,
                "crop_percent": [crop["x_percent"], crop["y_percent"], crop["width_percent"], crop["height_percent"]],
            })
        if failed_layers:
            proposal["settings"]["layout_layers"] = [
                layer for layer in proposal.get("settings", {}).get("layout_layers", []) if layer.get("id") not in failed_layers]
            proposal.setdefault("warnings", []).append(
                f"{len(failed_layers)} imagem(ns) não puderam ser recortadas; as demais camadas foram preservadas.")
        if proposal["settings"].get("layout_mode") == "composed" and not proposal["settings"].get("layout_layers"):
            proposal["settings"]["layout_mode"] = "reconstructed"
        if extracted_roles:
            labels = {"logo": "logotipo", "watermark": "marca-d'água"}
            proposal.setdefault("observations", []).append(
                "Imagens salvas no perfil: " + " e ".join(labels[role] for role in ("logo", "watermark") if role in extracted_roles) + ".")
    proposal["settings"] = BrandSettings.model_validate(proposal["settings"]).model_dump()
    await brand_assets(db, user, profile, proposal["settings"])
    logo = proposal.pop("logo_bytes", None)
    if logo:
        filename = "logo-ia.png" if logo.startswith(b"\x89PNG") else "logo-ia.jpg"
        asset = await store_asset(db, user, profile, filename, logo, "logo")
        proposal["logo_asset_id"] = asset.id
        proposal["settings"]["logo_asset_id"] = asset.id
        if proposal["settings"].get("layout_mode") == "composed" and not any(
            layer.get("role") == "logo" for layer in proposal["settings"].get("layout_layers", [])
        ):
            proposal["settings"]["layout_layers"].append({
                "id": f"generated-logo-{asset.id[:8]}", "kind": "image", "role": "logo", "label": "Símbolo criado pela IA",
                "x_percent": 40, "y_percent": 3, "width_percent": 20, "height_percent": 8,
                "rotation_deg": 0, "opacity": 1, "z_index": 20, "page_scope": "all", "color": "#17324D",
                "asset_id": asset.id, "text": "", "binding": None, "icon": "none",
                "font_family": "Liberation Sans", "font_size_pt": 8, "font_weight": "normal", "alignment": "center",
                "letter_spacing_pt": 0, "uppercase": False, "line_thickness_pt": 1,
            })
            proposal["settings"] = BrandSettings.model_validate(proposal["settings"]).model_dump(mode="json")
    await audit(db, user, "BRAND_AI_PROPOSED", profile.id, {"saved": False, "published": False,
        "detected_layers": len(proposal["settings"].get("layout_layers", [])), "extracted_images": len(extractions)})
    await db.commit()
    return proposal


async def render(user: User, title: str, content: str, tokens: dict, images: dict, content_format="plain"):
    if not pdf_available():
        raise HTTPException(503, "Conversão PDF indisponível. Configure o LibreOffice no servidor.")
    if not content.strip() or len(content) > 100_000:
        raise HTTPException(422, "Exportação requer texto autoral de até 100.000 caracteres.")
    await reserve_request(user.tenant_id, "brand_render", 60, 3600)
    try:
        return await asyncio.to_thread(render_documents, title, content, tokens, images, content_format)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, "Não foi possível renderizar o documento. Nenhum arquivo original foi alterado.") from exc


@router.post("/profiles/{profile_id}/preview")
async def preview(profile_id: str, body: BrandPreview, user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    profile = await profile_for_editor(db, user, profile_id)
    check_revision(profile, body.expected_revision)
    tokens = settings_for_document(profile.settings, profile.variants, body.document_type)
    professional = await professional_values(db, user, profile)
    rendered_tokens, missing = materialize_professional_text(tokens, professional)
    if missing:
        labels = ", ".join(PROFESSIONAL_LABELS[key] for key in dict.fromkeys(missing))
        raise HTTPException(422, f"Complete os dados profissionais selecionados para gerar a prévia: {labels}.")
    images = await brand_assets(db, user, profile, tokens)
    _, pdf = await render(user, "PRÉVIA ILUSTRATIVA — NÃO PROTOCOLAR", "Documento de exemplo para conferir a identidade visual.\n\nEsta prévia não contém orientação jurídica nem dados de clientes.\n\nConfira cabeçalho, tipografia, margens, marca d’água, rodapé e numeração antes de publicar.", rendered_tokens, images)
    return download(pdf, "application/pdf", "previa-identidade.pdf", inline=True)


@router.get("/documents/{document_id}/exports")
async def exports(document_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await get_document(db, user, document_id)
    rows = (await db.scalars(select(BrandExport).options(defer(BrandExport.docx), defer(BrandExport.pdf)).where(BrandExport.tenant_id == user.tenant_id, BrandExport.document_id == document_id)
        .order_by(BrandExport.created_at.desc()).limit(200))).all()
    return {"items": [export_payload(e) for e in rows]}


@router.post("/documents/{document_id}/exports", status_code=201)
async def create_export(document_id: str, body: BrandExportInput, user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    document = await get_document(db, user, document_id, for_update=True)
    require_document_write(user, document)
    if document.current_version != body.expected_version:
        raise HTTPException(409, "Documento alterado em outra sessão. Recarregue antes de exportar.")
    if document.kind == "evidence" or not (document.content_text or "").strip() or document.archived_at:
        raise HTTPException(422, "Somente documentos autorais ativos podem receber identidade. Anexos e provas são preservados.")
    candidates = await published_profiles(db, user, document)
    if body.profile_id:
        candidates = [(p, v) for p, v in candidates if p.id == body.profile_id]
    if not candidates:
        raise HTTPException(422, "Publique uma identidade do responsável pelo caso ou do escritório antes de exportar.")
    profile, version = candidates[0]
    document_type: DocumentType = body.document_type or document.document_type or "general"
    existing = await db.scalar(select(BrandExport).where(BrandExport.tenant_id == user.tenant_id, BrandExport.document_id == document.id,
        BrandExport.document_version == document.current_version, BrandExport.profile_id == profile.id,
        BrandExport.brand_version == version.version, BrandExport.document_type == document_type))
    if existing:
        return export_payload(existing)
    tokens = settings_for_document(version.settings, version.variants, document_type)
    responsible_user_id = user.id
    if document.case_id:
        responsible_user_id = (await get_case(db, user, document.case_id)).responsible_user_id
    current_professional = await professional_values(db, user, profile, responsible_user_id)
    if version.professional_snapshot:
        if profile.scope == "personal":
            professional = version.professional_snapshot
        else:
            professional = {**current_professional, **{key: value for key, value in version.professional_snapshot.items() if key not in PERSONAL_FIELDS}}
    else:
        professional = current_professional
    rendered_tokens, missing = materialize_professional_text(tokens, professional)
    if missing:
        labels = ", ".join(PROFESSIONAL_LABELS[key] for key in dict.fromkeys(missing))
        raise HTTPException(422, f"Complete os dados profissionais selecionados antes de exportar: {labels}.")
    images = await brand_assets(db, user, profile, tokens)
    docx, pdf = await render(user, document.title, document.content_text, rendered_tokens, images, document.content_format)
    await ensure_document_storage_capacity(db, user.tenant_id, len(docx) + len(pdf))
    export_id = str(uuid.uuid4())
    export = BrandExport(id=export_id, tenant_id=user.tenant_id, document_id=document.id, document_version=document.current_version,
        profile_id=profile.id, brand_version=version.version, document_type=document_type,
        brand_snapshot={"name": profile.name, "settings": version.settings, "variants": version.variants,
                        "applied_settings": rendered_tokens, "professional_data": professional},
        docx=docx, pdf=pdf, docx_size=len(docx), pdf_size=len(pdf), sha256_docx=hashlib.sha256(docx).hexdigest(), sha256_pdf=hashlib.sha256(pdf).hexdigest(), created_by_user_id=user.id)
    if r2_enabled():
        export.docx_object_key = f"exports/{user.tenant_id}/{export.id}/document.docx"
        export.pdf_object_key = f"exports/{user.tenant_id}/{export.id}/document.pdf"
        await asyncio.to_thread(put_object, export.docx_object_key, docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "documento.docx")
        await asyncio.to_thread(put_object, export.pdf_object_key, pdf, "application/pdf", "documento.pdf")
        export.docx = None
        export.pdf = None
    db.add(export)
    await db.flush()
    await audit(db, user, "BRAND_DOCUMENT_EXPORTED", export.id, {"document_id": document.id, "document_version": document.current_version,
        "brand_version": version.version, "document_type": document_type,
        "sha256_docx": export.sha256_docx, "sha256_pdf": export.sha256_pdf})
    await db.commit()
    return export_payload(export)


@router.get("/exports/{export_id}/download")
async def download_export(export_id: str, user: CurrentUser, format: Literal["pdf", "docx"] = "pdf", db: AsyncSession = Depends(get_db)):
    export = await db.scalar(select(BrandExport).where(BrandExport.tenant_id == user.tenant_id, BrandExport.id == export_id))
    if not export:
        raise HTTPException(404, "Exportação não encontrada.")
    await get_document(db, user, export.document_id)
    content, key, mime = (export.pdf, export.pdf_object_key, "application/pdf") if format == "pdf" else (export.docx, export.docx_object_key, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    filename = f"documento-v{export.document_version}-marca-v{export.brand_version}.{format}"
    if key:
        url = await asyncio.to_thread(create_download_url, key, filename, mime)
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})
    if content is None:
        raise HTTPException(404, "Arquivo da exportação não encontrado.")
    return download(content, mime, filename)
