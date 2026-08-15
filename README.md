# LexFlow Enterprise - SaaS LegalTech & Hub OAB (Tier 1 Enterprise)

Sistema SaaS LegalTech de Alta Escalabilidade para Escritórios de Advocacia e Hub de Iniciação Profissional / Inscrição Originária OAB.

## Stack Tecnologica

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide React (Zero Emojis), Zustand, CSS personalizado.
- **Backend:** Python FastAPI (Assíncrono), SQLAlchemy 2.0 / SQLModel, Pydantic v2, PyJWT, Passlib (bcrypt).
- **Banco de Dados & Cache:** PostgreSQL 16 com extensão `pgvector` para buscas vetoriais/RAG, Redis 7.2.
- **Infraestrutura:** Docker & Docker Compose com orquestração completa.

---

## Modulos Implementados (Fase 1)

1. **Multi-Tenancy & Segurança (Módulo 1):** Isolamento nativo de dados com `tenant_id` em todas as tabelas, middleware de extração de tenant (`X-Tenant-ID`) e tokens JWT.
2. **Governança & Audit Logs (Módulo 11):** Rastreamento de ações com hashing imutável SHA-256 e captura de IP/User-Agent.
3. **Radar de Conflito de Interesses (Módulo 5):** Consulta ética com pontuação de risco.
4. **Hub de Emissão de Carteira OAB & Iniciação Profissional (Módulo 12):**
   - Checklist interativo dos 8 documentos obrigatórios (Certificado FGV, Diploma, Reservista, Certidões Negativas, Fotos 3x4).
   - Gerador de Declarações Oficiais de Idoneidade Moral e Não Incompatibilidade (Arts. 27 a 30 da Lei 8.906/94).
   - Calculadora de Anuidade Proporcional com descontos para Jovem Advogado (50%) e Sociedade Unipessoal (25%).
   - Guia de Registro de Sociedade Unipessoal de Advocacia (SUA) e Tabela Referencial de Honorários Mínimos da Seccional.

---

## Como Executar Localmente

### Via Docker Compose
```bash
# Na raiz do projeto legaltech-saas:
docker-compose up --build
```

### Execucao Direta (Dev Server)

#### Backend FastAPI:
```bash
cd backend
python -m venv venv
# No Windows PowerShell:
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend Next.js:
```bash
cd frontend
npm install
npm run dev
```

Acesse a interface no navegador: `http://localhost:3000/` ou `http://localhost:3000/oab-hub`
Documentação OpenAPI (Swagger): `http://localhost:8000/api/v1/docs`

---

## Diretrizes de Codigo & Estetica
- **Zero Emojis:** Todos os elementos visuais utilizam ícones vetoriais da biblioteca `lucide-react`.
- **Clean Architecture:** Camadas bem definidas no padrão `ponytail` (Core, Models, Schemas, Services, API Endpoints).
