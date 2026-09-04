from fastapi import APIRouter, Depends
from app.api.v1.endpoints import account, audit, auth, branding, calendar_sync, controladoria, document_kit, engagement, integrations, notifications, operations, pilot, provider_costs, push, research, routines, workspace
from app.core.dependencies import require_privileged_mfa

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticacao & Tenant"])
api_router.include_router(account.router, prefix="/account", tags=["Conta & Assinatura"])
api_router.include_router(push.router, prefix="/push", tags=["Dispositivos & Web Push"])
api_router.include_router(pilot.router, prefix="/pilot", tags=["Piloto & Feedback"])
api_router.include_router(routines.router, prefix="/routines", tags=["Rotina & Diligencias"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(document_kit.router, prefix="/document-kit", tags=["Kit Documental"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(workspace.router, prefix="/workspace", tags=["Central do Advogado"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(controladoria.router, prefix="/controladoria", tags=["Controladoria judicial"], dependencies=[Depends(require_privileged_mfa)])
# Escavador authenticates callbacks with its dedicated Bearer token, not an office session.
api_router.include_router(controladoria.public_router, prefix="/controladoria", tags=["Webhooks judiciais"])
api_router.include_router(operations.router, prefix="/operations", tags=["Atendimento e operacao"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(branding.router, prefix="/branding", tags=["Identidade Documental"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(engagement.router, prefix="/engagement", tags=["Comunicacoes do Escritorio"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(research.router, prefix="/engagement", tags=["Pesquisa & Assistencia"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integracoes"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(calendar_sync.router, prefix="/integrations", tags=["Agenda externa"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(calendar_sync.public_router, prefix="/integrations", tags=["Webhooks de agenda"])
api_router.include_router(integrations.calendar_router, prefix="/calendar", tags=["Agenda externa"])
api_router.include_router(engagement.portal_router, prefix="/client-portal", tags=["Portal do Cliente"])
# Webhooks authenticate with provider credentials, not the office session.
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notificacoes Transacionais"])
api_router.include_router(operations.public_router, prefix="/operations", tags=["Atendimento publico e webhooks"])
api_router.include_router(provider_costs.router, prefix="/operations", tags=["Custos de provedores"], dependencies=[Depends(require_privileged_mfa)])
api_router.include_router(audit.router, prefix="/audit", tags=["Governanca & Audit Logs"], dependencies=[Depends(require_privileged_mfa)])

