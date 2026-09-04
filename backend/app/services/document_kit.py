"""Generic drafting aids, not legally homologated instruments.

Scope checked on 2026-08-28 against CPC art.105 (no special powers inferred):
https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm
and OAB Code of Ethics art.48 (no fee, venue or payment terms inferred):
https://www.oab.org.br/leisnormas/legislacao/resolucoes/02-2015
The professional supplies the terms and must review suitability before use.
"""

import hashlib
import hmac
import json
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceClient
from app.schemas.document_kit import DocumentKitPreview
from app.schemas.workspace import safe_document_text
from app.services.workspace_service import get_case, require_case_write


VERSION = "2026-08-30.1"
WARNING = "RASCUNHO — revisão profissional necessária. Modelo genérico não homologado; confira dados, condições e adequação ao caso antes de utilizar."


def field(key: str, label: str, required: bool = True) -> dict:
    return {"key": key, "label": label, "required": required}


SIGNATURE_FIELDS = [
    field("client_qualification", "Qualificação complementar e endereço do cliente"),
    field("professional_address", "Endereço profissional completo do advogado responsável"),
    field("location", "Local de assinatura"),
    field("signed_on", "Data a constar no documento (AAAA-MM-DD)"),
]
TEMPLATES = {
    "intake": {
        "title": "Ficha de atendimento",
        "category": "internal",
        "description": "Registro interno com dados do cadastro e relato conferido pelo advogado.",
        "fields": [field("summary", "Relato e objetivo do atendimento"), field("received_documents", "Documentos recebidos", False), field("next_action", "Próxima ação combinada", False)],
    },
    "power_of_attorney": {
        "title": "Procuração",
        "category": "instrument",
        "description": "Rascunho para revisão. Os poderes devem ser escritos pelo advogado; nenhum poder especial é incluído automaticamente.",
        "fields": [*SIGNATURE_FIELDS, field("scope", "Objeto e limites da representação"), field("powers", "Poderes expressamente autorizados e conferidos com o cliente")],
    },
    "fee_agreement": {
        "title": "Contrato de honorários",
        "category": "instrument",
        "description": "Rascunho com condições informadas pelo advogado. Confira a tabela da seccional e a adequação das cláusulas; não há valores presumidos.",
        "fields": [*SIGNATURE_FIELDS, field("scope", "Objeto, atos abrangidos e limites do patrocínio"), field("fees", "Honorários ajustados e critérios de cálculo"), field("payment", "Forma e condições de pagamento"), field("settlement", "Condições em caso de acordo ou transação"), field("expenses", "Responsabilidade e prestação de contas das despesas"), field("termination", "Condições de encerramento da contratação")],
    },
    "initial_petition": {
        "title": "Petição inicial — estrutura genérica",
        "category": "petition",
        "description": "Organiza fatos, fundamentos e pedidos informados pelo advogado. Não inventa competência, rito, legislação, jurisprudência ou valor da causa.",
        "fields": [*SIGNATURE_FIELDS, field("addressing", "Endereçamento e competência conferidos pelo advogado"), field("facts", "Fatos relevantes em ordem cronológica"), field("legal_basis", "Fundamentos jurídicos e fontes conferidos"), field("requests", "Pedidos expressos e delimitados"), field("evidence", "Provas e documentos que sustentam os fatos", False), field("urgent_relief", "Tutela provisória pretendida e requisitos demonstrados", False), field("case_value", "Valor da causa e critério utilizado", False)],
    },
    "defense": {
        "title": "Contestação ou defesa — estrutura genérica",
        "category": "petition",
        "description": "Estrutura uma resposta processual a partir de alegações e documentos conferidos. Não presume preliminares, ônus, prazos ou teses.",
        "fields": [*SIGNATURE_FIELDS, field("addressing", "Endereçamento e identificação do processo"), field("claim_summary", "Síntese fiel das alegações da parte contrária"), field("preliminary_issues", "Questões preliminares expressamente identificadas", False), field("facts", "Versão dos fatos e pontos controvertidos"), field("legal_basis", "Fundamentos jurídicos e fontes conferidos"), field("requests", "Pedidos da defesa"), field("evidence", "Provas e documentos indicados", False)],
    },
    "intermediate_petition": {
        "title": "Manifestação ou petição intermediária",
        "category": "petition",
        "description": "Rascunho curto para manifestação em processo existente. O advogado informa o ato, o fundamento e a providência requerida.",
        "fields": [*SIGNATURE_FIELDS, field("addressing", "Endereçamento e identificação do processo"), field("procedural_context", "Ato, despacho ou evento ao qual se responde"), field("statement", "Manifestação objetiva"), field("legal_basis", "Fundamento e fontes conferidos", False), field("requests", "Providências expressamente requeridas"), field("attachments", "Documentos anexados", False)],
    },
    "extrajudicial_notice": {
        "title": "Notificação extrajudicial",
        "category": "notice",
        "description": "Comunicação formal baseada nos fatos e providências informados. Não presume recebimento, mora, prazo legal ou consequência automática.",
        "fields": [*SIGNATURE_FIELDS, field("recipient", "Nome, qualificação e endereço do destinatário"), field("facts", "Fatos que motivam a notificação"), field("demand", "Providência solicitada"), field("response_period", "Prazo informado pelo advogado e forma de contagem", False), field("consequences", "Consequências expressamente aprovadas para o não atendimento", False), field("delivery", "Forma de envio e comprovação pretendida", False)],
    },
    "collection_notice": {
        "title": "Notificação de cobrança",
        "category": "notice",
        "description": "Organiza uma cobrança extrajudicial com valores e vencimentos informados. Não calcula juros, correção, multa ou vencimento.",
        "fields": [*SIGNATURE_FIELDS, field("recipient", "Nome, qualificação e endereço do destinatário"), field("debt_origin", "Origem e documentos da obrigação"), field("amount", "Valor conferido e composição da cobrança"), field("due_dates", "Vencimentos conferidos"), field("payment", "Forma de pagamento ou negociação"), field("response_period", "Prazo informado pelo advogado", False), field("consequences", "Medidas futuras expressamente aprovadas", False)],
    },
}


def catalog() -> dict:
    return {"items": [{"key": key, **template, "version": VERSION, "review_required": True} for key, template in TEMPLATES.items()]}


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def format_address(address: dict | None) -> str:
    if not address:
        return ""
    first = ", ".join(filter(None, [address.get("street"), address.get("number")]))
    parts = [first, address.get("complement"), address.get("district")]
    city_state = "/".join(filter(None, [address.get("city"), address.get("state")]))
    parts.extend([city_state, address.get("postal_code")])
    return " - ".join(str(item).strip() for item in parts if item and str(item).strip())


def representative_details(client) -> str:
    if getattr(client, "has_legal_representative", None) is False:
        return ""
    name = getattr(client, "representative_name", None)
    if not name:
        return ""
    prefix = "representada por" if getattr(client, "person_type", "individual") == "company" else "com representante legal"
    parts = [f"{prefix} {name}"]
    if getattr(client, "representative_tax_id", None):
        parts.append(f"CPF/CNPJ {client.representative_tax_id}")
    if getattr(client, "representative_qualification", None):
        parts.append(f"qualificação {client.representative_qualification}")
    if getattr(client, "representative_email", None):
        parts.append(f"e-mail {client.representative_email}")
    if getattr(client, "representative_phone", None):
        parts.append(f"WhatsApp {client.representative_phone}")
    address = format_address(getattr(client, "representative_address", None))
    if address:
        parts.append(f"endereço {address}")
    return ", ".join(parts)


def client_qualification(client) -> str:
    parts = [getattr(client, "qualification", None), getattr(client, "occupation", None), format_address(getattr(client, "address", None))]
    representative = representative_details(client)
    if representative:
        parts.insert(1, representative)
    return ", ".join(part.strip() for part in parts if part and part.strip())


def render_preview(payload: DocumentKitPreview, *, case, client, lawyer, tenant) -> dict:
    template = TEMPLATES[payload.template_key]
    fields = template["fields"]
    if set(payload.values) - {item["key"] for item in fields}:
        raise HTTPException(422, "Campo não permitido para este modelo. Dados cadastrais devem ser alterados no cadastro de origem.")
    defaults = {
        "client_qualification": client_qualification(client),
        "professional_address": format_address(getattr(lawyer, "professional_address", None)) or format_address(getattr(tenant, "office_address", None)),
        "location": getattr(tenant, "signature_city", None) or (getattr(tenant, "office_address", None) or {}).get("city", ""),
    }
    values = {item["key"]: payload.values.get(item["key"], "") or defaults.get(item["key"], "") for item in fields}
    if values.get("signed_on"):
        try:
            parsed_date = date.fromisoformat(values["signed_on"])
            if parsed_date.isoformat() != values["signed_on"]:
                raise ValueError
            values["signed_on"] = parsed_date.strftime("%d/%m/%Y")
        except ValueError:
            raise HTTPException(422, "Informe a data no formato AAAA-MM-DD.")

    missing = []

    def value(key: str, label: str, raw: str | None, required: bool = True) -> str:
        if raw and raw.strip():
            return raw.strip()
        if required:
            missing.append({"key": key, "label": label})
            return f"[PREENCHER: {label}]"
        return "Não informado."

    name = value("client.name", "Nome no cadastro do cliente", client.name)
    category = template["category"]
    requires_legal_data = category != "internal"
    tax_id = value("client.tax_id", "CPF/CNPJ no cadastro do cliente", client.tax_id, requires_legal_data)
    lawyer_name = value("lawyer.full_name", "Nome do advogado responsável", getattr(lawyer, "professional_name", None) or lawyer.full_name)
    oab_number = value("lawyer.oab_number", "Número OAB no perfil do responsável", lawyer.oab_number, requires_legal_data)
    oab_uf = value("lawyer.oab_uf", "UF OAB no perfil do responsável", lawyer.oab_uf, requires_legal_data)
    filled = {item["key"]: value(item["key"], item["label"], values[item["key"]], item["required"]) for item in fields}
    lines = [template["title"].upper(), WARNING, "", f"Cliente: {name}", f"CPF/CNPJ: {tax_id}", f"Escritório: {tenant.name}", f"Advogado responsável: {lawyer_name}", f"OAB: {oab_number} / {oab_uf}", f"Caso de referência: {case.title}"]
    if case.number:
        lines.append(f"Número cadastrado: {case.number}")
    if case.court:
        lines.append(f"Órgão cadastrado: {case.court}")
    if payload.template_key == "intake":
        lines.extend([f"Contato cadastrado: {client.email or 'E-mail não informado'} | {client.phone or 'Telefone não informado'}", f"Qualificação do cliente: {client_qualification(client) or 'Não informada.'}", "", "Registro interno. Não substitui procuração ou contrato de prestação de serviços."])
    else:
        lines.extend(["", f"Qualificação complementar do cliente: {filled['client_qualification']}", f"Endereço profissional: {filled['professional_address']}"])
        if payload.template_key == "power_of_attorney":
            lines.extend(["", f"{name} constitui {lawyer_name} como procurador(a), nos limites e com os poderes expressamente descritos abaixo.", "O rascunho não acrescenta poderes especiais nem autorização para atos não descritos."])
        elif payload.template_key == "fee_agreement":
            lines.extend(["", f"{name} e {lawyer_name} registram as condições da contratação descritas abaixo, sujeitas à conferência e assinatura das partes."])
        elif category == "petition":
            lines.extend(["", "PEÇA PROCESSUAL EM RASCUNHO", "O texto abaixo apenas organiza informações fornecidas. Competência, procedimento, admissibilidade, fundamentos, pedidos e prazos exigem conferência profissional."])
        else:
            lines.extend(["", f"Por solicitação de {name}, apresenta-se a comunicação extrajudicial abaixo.", "A emissão deste rascunho não comprova envio, recebimento, constituição em mora ou vencimento de prazo."])
    for item in fields:
        if item["key"] not in {"client_qualification", "professional_address", "location", "signed_on"}:
            lines.extend(["", item["label"] + ":", filled[item["key"]]])
    if requires_legal_data:
        lines.extend(["", f"Local e data: {filled['location']}, {filled['signed_on']}", ""])
        if category == "petition":
            lines.append(f"Assinatura do advogado: ____________________  {lawyer_name} — OAB {oab_number}/{oab_uf}")
        else:
            representative_name = getattr(client, "representative_name", None) if getattr(client, "has_legal_representative", None) is not False else None
            signer_label = "representante legal" if representative_name else "cliente"
            signer_name = f"{representative_name} — representante legal de {name}" if representative_name else name
            lines.append(f"Assinatura do {signer_label}: ____________________  {signer_name}")
            if payload.template_key == "fee_agreement" or category == "notice":
                lines.append(f"Assinatura do advogado: ____________________  {lawyer_name}")
        lines.extend(["", "Conferência no sistema não equivale à assinatura das partes nem certifica a validade do instrumento."])
    content = "\n".join(lines)
    try:
        safe_document_text(content)
    except ValueError:
        raise HTTPException(422, "O cadastro contém marcação ativa não aceita em documentos. Confira os dados de origem.")
    source = {"case_revision": case.revision, "client_revision": client.revision, "template_version": VERSION}
    # Sign the full preview, not only names: changing terms after review requires a new preview.
    signed = {**source, "tenant_id": tenant.id, "lawyer_id": lawyer.id, "case_id": case.id, "client_id": client.id, "template_key": payload.template_key, "content": content}
    source["profile_fingerprint"] = hmac.new(settings.SECRET_KEY.encode(), digest(signed).encode(), hashlib.sha256).hexdigest()
    return {"title": f"{template['title']} — {case.title}"[:300], "content_text": content, "content_format": "plain", "missing_fields": missing, "source": source, "review_required": True}


async def preview(db: AsyncSession, user: User, payload: DocumentKitPreview, *, lock: bool = False) -> tuple[dict, object]:
    case = await get_case(db, user, payload.case_id, for_update=lock)
    if lock:
        # A prior permission read may already have placed this row in the identity map.
        await db.refresh(case)
    if user.role != "paralegal":
        require_case_write(user, case)
    if case.archived_at or case.status == "archived":
        raise HTTPException(409, "Reative o caso antes de preparar novos documentos.")
    client_query = select(WorkspaceClient).where(WorkspaceClient.tenant_id == user.tenant_id, WorkspaceClient.id == case.client_id)
    lawyer_query = select(User).where(User.tenant_id == user.tenant_id, User.id == case.responsible_user_id, User.is_active.is_(True))
    if lock:
        client_query = client_query.with_for_update()
        lawyer_query = lawyer_query.with_for_update()
    client = await db.scalar(client_query.execution_options(populate_existing=lock))
    lawyer = await db.scalar(lawyer_query.execution_options(populate_existing=lock))
    tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).execution_options(populate_existing=lock))
    if not client or client.archived_at or not lawyer or not tenant:
        raise HTTPException(409, "Confira o cliente e o responsável ativo do caso antes de preparar o documento.")
    return render_preview(payload, case=case, client=client, lawyer=lawyer, tenant=tenant), case


async def document_context(db: AsyncSession, user: User, case_id: str) -> dict:
    case = await get_case(db, user, case_id)
    client = await db.scalar(select(WorkspaceClient).where(WorkspaceClient.tenant_id == user.tenant_id, WorkspaceClient.id == case.client_id))
    lawyer = await db.scalar(select(User).where(User.tenant_id == user.tenant_id, User.id == case.responsible_user_id, User.is_active.is_(True)))
    tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if not client or not lawyer or not tenant:
        raise HTTPException(409, "Confira cliente, responsável e escritório antes de preparar o documento.")
    addresses = []
    if format_address(lawyer.professional_address):
        addresses.append({"id": "lawyer", "label": "Endereço profissional do advogado", "value": format_address(lawyer.professional_address)})
    if format_address(tenant.office_address):
        addresses.append({"id": "office", "label": "Endereço do escritório", "value": format_address(tenant.office_address)})
    return {
        "case": {"id": case.id, "title": case.title, "number": case.number},
        "client": {"id": client.id, "name": client.name, "tax_id": client.tax_id, "qualification": client_qualification(client)},
        "lawyer": {"id": lawyer.id, "name": lawyer.professional_name or lawyer.full_name, "oab": lawyer.oab_number, "oab_uf": lawyer.oab_uf},
        "addresses": addresses,
        "signature_city": tenant.signature_city or (tenant.office_address or {}).get("city"),
    }
