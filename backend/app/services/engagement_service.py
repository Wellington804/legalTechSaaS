import hmac
from sqlalchemy import select, text
from app.core.security import decrypt_mfa_secret, hash_account_token
from app.models.engagement import CaseMessage, TenantChannel
from app.models.workspace import WorkspaceCase, WorkspaceClient


async def delivery_context(db, delivery):
    if not delivery.resource_ref.startswith("case-message:"):
        return None
    message_id = delivery.resource_ref.split(":", 1)[1]
    row = (await db.execute(select(CaseMessage, WorkspaceCase, WorkspaceClient).join(
        WorkspaceCase, (WorkspaceCase.id == CaseMessage.case_id) & (WorkspaceCase.tenant_id == CaseMessage.tenant_id)
    ).join(WorkspaceClient, (WorkspaceClient.id == CaseMessage.client_id) & (WorkspaceClient.tenant_id == CaseMessage.tenant_id)).where(
        CaseMessage.id == message_id, CaseMessage.tenant_id == delivery.tenant_id, CaseMessage.delivery_id == delivery.id,
        WorkspaceCase.client_id == CaseMessage.client_id,
    ))).first()
    if not row:
        raise ValueError("bound_message_missing")
    message, case, client = row
    channel = await db.scalar(select(TenantChannel).where(TenantChannel.tenant_id == delivery.tenant_id))
    if not channel or client.stage == "inactive" or case.archived_at:
        raise ValueError("bound_recipient_unavailable")
    if delivery.channel == "email":
        if not channel.email_enabled or client.email != delivery.recipient:
            raise ValueError("bound_recipient_changed")
        return {"text": message.body, "subject": "Mensagem do seu escritório"}
    if (not channel.whatsapp_enabled or channel.whatsapp_connection_state != "connected"
            or client.phone != delivery.recipient or not channel.evolution_instance_id_encrypted
            or not channel.evolution_instance_id_hash or not channel.evolution_api_key_encrypted):
        raise ValueError("bound_recipient_changed")
    return {"text": message.body, "evolution_instance_id": decrypt_mfa_secret(channel.evolution_instance_id_encrypted),
            "evolution_api_key": decrypt_mfa_secret(channel.evolution_api_key_encrypted)}


async def resolve_evolution_instance(db, instance_id, instance_token):
    # Narrow SECURITY DEFINER lookup; caller has not established a tenant yet.
    row = (await db.execute(text("SELECT * FROM public.tenant_channel_webhook_identity(:instance_hash)"),
                            {"instance_hash": hash_account_token(instance_id)})).first()
    if not row or not row[1]:
        return None
    try:
        valid = hmac.compare_digest(decrypt_mfa_secret(row[1]), instance_token)
    except RuntimeError:
        return None
    return row[0] if valid else None
