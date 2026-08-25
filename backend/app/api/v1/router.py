from fastapi import APIRouter
from app.api.v1.endpoints import auth, oab, conflict, audit, search, crm, petitions, storage, jurimetria, financial, dashboard, portal, calculadora, templates

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticacao & Tenant"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Modulo 0 - Painel Executivo & Dashboard"])
api_router.include_router(oab.router, prefix="/oab", tags=["Modulo 12 - Hub OAB"])
api_router.include_router(conflict.router, prefix="/conflict", tags=["Modulo 5 - Conflito de Interesses"])
api_router.include_router(audit.router, prefix="/audit", tags=["Modulo 11 - Governanca & Audit Logs"])
api_router.include_router(search.router, prefix="/search", tags=["Modulo 9 - Busca Vetorial GED"])
api_router.include_router(crm.router, prefix="/crm", tags=["Modulo 2 - Omnichannel CRM"])
api_router.include_router(petitions.router, prefix="/petitions", tags=["Modulo 3 - Central de Peticoes"])
api_router.include_router(storage.router, prefix="/storage", tags=["Modulo 1 - Storage S3/MinIO"])
api_router.include_router(jurimetria.router, prefix="/jurimetria", tags=["Modulo 4 - Jurimetria de Magistrados"])
api_router.include_router(financial.router, prefix="/financial", tags=["Modulo 7 - Financeiro & Pix"])
api_router.include_router(portal.router, prefix="/portal", tags=["Modulo Publico - Portal do Cliente"])
api_router.include_router(calculadora.router, prefix="/calculadora", tags=["Modulo 8 - Calculadora Judicial"])
api_router.include_router(templates.router, prefix="/templates", tags=["Modulo 6 - Minutas e Contratos Inteligentes"])



