import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("db_optimizations")

OPTIMIZATION_SQL = [
    # 1. HNSW Vector Indexing for pgvector
    """
    CREATE EXTENSION IF NOT EXISTS vector;
    """,
    """
    CREATE TABLE IF NOT EXISTS petition_templates (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        title VARCHAR NOT NULL,
        content TEXT NOT NULL,
        embedding vector(1536)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_petition_hnsw 
    ON petition_templates USING hnsw (embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64);
    """,
    # 2. Composite Multi-Tenant Indexes
    """
    CREATE INDEX IF NOT EXISTS idx_oab_apps_tenant_created 
    ON oab_applications (tenant_id, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_oab_apps_tenant_status 
    ON oab_applications (tenant_id, status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_tenant_created 
    ON audit_logs (tenant_id, created_at DESC);
    """,
    # 3. Enable Row Level Security (RLS) for Tenant Isolation
    """
    ALTER TABLE oab_applications ENABLE ROW LEVEL SECURITY;
    """,
    """
    ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
    """
]

async def apply_db_optimizations(engine: AsyncEngine):
    """
    Executa otimizações de banco de dados, índices HNSW e políticas de isolamento RLS.
    """
    async with engine.begin() as conn:
        for stmt in OPTIMIZATION_SQL:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"Otimização SQL ignorada ou não suportada no ambiente atual: {e}")
    logger.info("Otimizações de Banco de Dados, Índices HNSW e RLS processadas.")
