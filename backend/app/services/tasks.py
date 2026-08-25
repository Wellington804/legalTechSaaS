import hashlib
import json
import time
import logging
from datetime import datetime, timezone
from app.core.celery_app import celery_app

logger = logging.getLogger("celery_tasks")

@celery_app.task(name="tasks.generate_audit_hash")
def generate_audit_hash_task(tenant_id: str, user_id: str, action: str, resource_type: str, details: dict):
    """
    Calcula o hash de auditoria em background para garantir imutabilidade sem travar o worker HTTP.
    """
    timestamp_str = datetime.now(timezone.utc).isoformat()
    payload = f"{tenant_id}:{user_id}:{action}:{resource_type}:{timestamp_str}:{json.dumps(details or {})}"
    sha256_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    logger.info(f"[Celery Audit] Log processado para Tenant {tenant_id} - Hash: {sha256_hash[:16]}...")
    return {
        "tenant_id": tenant_id,
        "action": action,
        "hash": f"sha256-{sha256_hash}",
        "processed_at": timestamp_str
    }

@celery_app.task(name="tasks.verify_signature_hash")
def verify_signature_hash_task(document_id: str, file_name: str, raw_content_snippet: str):
    """
    Simula validação criptográfica pesada de assinaturas digitais em background.
    """
    time.sleep(1) # Simula processamento pesado de I/O
    content_hash = hashlib.sha256(f"{document_id}:{file_name}:{raw_content_snippet}".encode()).hexdigest()
    return {
        "document_id": document_id,
        "file_name": file_name,
        "digital_signature": f"0x{content_hash[:32]}",
        "verified": True,
        "status": "VALID_DOCUMENT"
    }

@celery_app.task(name="tasks.poll_oab_tribunal_status")
def poll_oab_tribunal_status_task(candidate_cpf: str, seccional: str):
    """
    Simula a verificação assíncrona da situação cadastral do candidato na OAB/FGV.
    """
    time.sleep(2)
    return {
        "cpf": candidate_cpf,
        "seccional": seccional,
        "fgv_status": "APROVADO_39_EXAME",
        "certidao_emitida": True
    }
