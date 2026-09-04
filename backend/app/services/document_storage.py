"""Private R2 document storage. Object keys never contain client-controlled names."""
import socket
import struct
from urllib.parse import quote

from app.core.config import settings


class DocumentStorageError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(settings.R2_ENABLED)


def _client():
    if not enabled():
        raise DocumentStorageError("Armazenamento de arquivos nao configurado.")
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        region_name="auto",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    )


def quarantine_key(tenant_id: str, upload_id: str) -> str:
    return f"quarantine/{tenant_id}/{upload_id}"


def object_key(tenant_id: str, document_id: str, version_id: str) -> str:
    return f"documents/{tenant_id}/{document_id}/{version_id}"


def create_upload_url(key: str, content_type: str, sha256_hex: str | None = None) -> dict:
    params = {"Bucket": settings.R2_BUCKET_NAME, "Key": key, "ContentType": content_type}
    headers = {"Content-Type": content_type}
    url = _client().generate_presigned_url("put_object", Params=params, ExpiresIn=300)
    return {"url": url, "headers": headers, "expires_in": 300}


def head(key: str) -> dict:
    return _client().head_object(Bucket=settings.R2_BUCKET_NAME, Key=key)


def read(key: str) -> bytes:
    body = _client().get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)["Body"]
    try:
        return body.read()
    finally:
        body.close()


def promote(source: str, destination: str, content_type: str, filename: str) -> None:
    _client().copy_object(
        Bucket=settings.R2_BUCKET_NAME,
        CopySource={"Bucket": settings.R2_BUCKET_NAME, "Key": source},
        Key=destination,
        ContentType=content_type,
        ContentDisposition=f"attachment; filename*=UTF-8''{quote(filename)}",
        MetadataDirective="REPLACE",
    )


def put(key: str, content: bytes, content_type: str, filename: str) -> None:
    _client().put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=content,
        ContentType=content_type,
        ContentDisposition=f"attachment; filename*=UTF-8''{quote(filename)}",
    )


def delete(key: str) -> None:
    _client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)


def create_download_url(key: str, filename: str, content_type: str, *, inline: bool = False) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
            "ResponseContentType": content_type,
            "ResponseContentDisposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(filename)}",
        },
        ExpiresIn=60,
    )


def check() -> None:
    _client().head_bucket(Bucket=settings.R2_BUCKET_NAME)
    try:
        with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=5) as sock:
            sock.sendall(b"PING\n")
            response = sock.recv(16)
    except OSError as exc:
        raise DocumentStorageError("Antivirus indisponivel.") from exc
    if b"PONG" not in response:
        raise DocumentStorageError("Antivirus nao respondeu ao health check.")


def scan(content: bytes) -> None:
    """Fail closed against clamd's bounded INSTREAM protocol."""
    try:
        with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=10) as sock:
            sock.settimeout(60)
            sock.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 1024 * 1024):
                chunk = content[offset:offset + 1024 * 1024]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            response = sock.recv(4096).decode("utf-8", "replace")
    except OSError as exc:
        raise DocumentStorageError("Antivirus indisponivel; arquivo mantido em quarentena.") from exc
    if "FOUND" in response:
        raise DocumentStorageError("Arquivo bloqueado pelo antivirus.")
    if "OK" not in response:
        raise DocumentStorageError("Antivirus nao confirmou o arquivo.")
