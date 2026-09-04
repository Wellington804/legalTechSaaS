"""Read-only comparison of every restored row, including bytea documents/branding.

Use after restore into a fresh legaltech_restore_* database while the source is
quiescent. URLs come from RESTORE_SOURCE_DATABASE_URL / RESTORE_TARGET_DATABASE_URL;
neither URLs, IDs nor content are printed. Administrator read privileges required.
"""
import asyncio
import hashlib
import os
import re

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


def validate_targets(source: str, target: str):
    source_url, target_url = make_url(source), make_url(target)
    if source_url.get_backend_name() != "postgresql" or target_url.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL required")
    if not re.fullmatch(r"legaltech_restore_[a-z0-9_]+", target_url.database or ""):
        raise ValueError("An isolated restore target is required")
    if (source_url.host, source_url.port, source_url.database) == (target_url.host, target_url.port, target_url.database):
        raise ValueError("Source and restore target must differ")


async def snapshot(url: str) -> dict:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            await connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            role = (await connection.execute(text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"))).scalar()
            if not role:
                raise ValueError("Use an administrator reader: an RLS-filtered snapshot is not a restore proof")
            tables = (await connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"))).scalars().all()
            result = {}
            for table in tables:
                if not re.fullmatch(r"[a-z_][a-z0-9_]*", table):
                    raise ValueError("Unexpected table identifier")
                digest, count = hashlib.sha256(), 0
                # Hash on the server; large document bytes never enter application logs/memory.
                rows = await connection.stream(text(f'SELECT encode(sha256(convert_to(row_to_json(t)::text,\'UTF8\')),\'hex\') AS fingerprint FROM public."{table}" t ORDER BY fingerprint'))
                async for row in rows:
                    digest.update(row.fingerprint.encode("ascii"))
                    count += 1
                result[table] = {"count": count, "sha256": digest.hexdigest()}
                binary_columns = {"workspace_document_versions": ["file_content"], "brand_assets": ["content"], "brand_exports": ["docx", "pdf"]}.get(table, [])
                if binary_columns:
                    sizes = " + ".join(f'COALESCE(octet_length("{column}"), 0)' for column in binary_columns)
                    result[table]["file_bytes"] = int((await connection.execute(text(f'SELECT COALESCE(sum({sizes}), 0) FROM public."{table}"'))).scalar())
            return result
    finally:
        await engine.dispose()


async def verify(source: str, target: str):
    validate_targets(source, target)
    first, restored = await asyncio.gather(snapshot(source), snapshot(target))
    if not first or first != restored:
        raise ValueError("Restored database contents differ from the source snapshot")
    document_rows = sum(first.get(table, {}).get("count", 0) for table in ("workspace_document_versions", "brand_assets", "brand_exports"))
    file_bytes = sum(item.get("file_bytes", 0) for item in first.values())
    if not document_rows or not file_bytes:
        raise ValueError("No file evidence: attach a fictitious document before the restore drill")
    return {"tables": len(first), "rows": sum(item["count"] for item in first.values()), "document_rows": document_rows, "file_bytes": file_bytes}


def main():
    try:
        result = asyncio.run(verify(os.environ["RESTORE_SOURCE_DATABASE_URL"], os.environ["RESTORE_TARGET_DATABASE_URL"]))
    except Exception:
        raise SystemExit("Restore verification FAILED. Check isolated target, read privileges, source quiescence and contents; no credentials/content were logged.") from None
    print(f"Restore verified: {result['tables']} tables, {result['rows']} rows, {result['document_rows']} document/version rows, {result['file_bytes']} file bytes; content matches.")


if __name__ == "__main__":
    main()
