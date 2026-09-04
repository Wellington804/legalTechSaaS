"""Generate VAPID once, atomically preserving unrelated .env fields. Never print secrets."""
import argparse
import base64
import io
import os
from pathlib import Path
import re
import tempfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from dotenv import dotenv_values


def generate_pair() -> tuple[str, str]:
    private = ec.generate_private_key(ec.SECP256R1())
    encode = lambda data: base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
    return (encode(private.private_numbers().private_value.to_bytes(32, "big")),
            encode(private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))


def configure(path: Path, subject: str, *, enable: bool = False) -> bool:
    if not re.fullmatch(r"(?:mailto:[^\s@]+@[^\s@]+\.[^\s@]+|https://[^\s]+)", subject) or any(c in subject for c in "\r\n'\"#"):
        raise ValueError("Informe um contato mailto: ou HTTPS valido.")
    if path.is_symlink():
        raise ValueError("O arquivo de destino nao pode ser um link simbolico.")
    original = path.read_bytes() if path.exists() else b""
    content = original.decode("utf-8-sig")
    values = dotenv_values(stream=io.StringIO(content), interpolate=False)
    private_name, public_name = "WEB_PUSH_VAPID_PRIVATE_KEY", "WEB_PUSH_VAPID_PUBLIC_KEY"
    if bool(values.get(private_name)) != bool(values.get(public_name)):
        raise ValueError("Par VAPID incompleto; nenhuma chave existente foi alterada.")
    updates = {}
    if not values.get(private_name):
        private, public = generate_pair()
        updates.update({private_name: private, public_name: public})
    if not values.get("WEB_PUSH_VAPID_SUBJECT"):
        updates["WEB_PUSH_VAPID_SUBJECT"] = subject
    if enable or not values.get("WEB_PUSH_ENABLED"):
        updates["WEB_PUSH_ENABLED"] = "true" if enable else "false"
    for key, value in updates.items():
        pattern = rf"(?m)^[ \t]*(?:export[ \t]+)?{key}[ \t]*=[^\r\n]*"
        if len(re.findall(pattern, content)) > 1:
            raise ValueError("Campo VAPID duplicado; nenhuma alteracao aplicada.")
        if re.search(pattern, content):
            content = re.sub(pattern, f"{key}={value}", content)
        else:
            content += ("" if not content or content.endswith("\n") else "\n") + f"{key}={value}\n"
    if content.encode("utf-8") == original:
        return False
    descriptor, temporary = tempfile.mkstemp(prefix=".push-env-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content.encode("utf-8"))
            output.flush()
            os.fsync(output.fileno())
        if (path.read_bytes() if path.exists() else b"") != original:
            raise ValueError("O arquivo mudou durante a operacao; tente novamente.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()
    try:
        changed = configure(args.env_file.absolute(), args.subject, enable=args.enable)
    except (ValueError, OSError, UnicodeError):
        parser.exit(1, "Nao foi possivel configurar VAPID. Verifique destino, contato e par existente; nenhum segredo foi exibido.\n")
    print("Configuracao VAPID atualizada; chaves privadas nao exibidas." if changed else "Configuracao VAPID preservada.")


if __name__ == "__main__":
    main()
