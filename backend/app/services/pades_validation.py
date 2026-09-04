"""Fail-closed PAdES integrity validation through Poppler's ``pdfsig``.

``pdfsig`` validates the CMS signature and the signed byte ranges.  Its local
certificate store is not, by itself, authoritative for ICP-Brasil revocation,
so certificate trust is reported separately from cryptographic integrity.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


PDFSIG_TIMEOUT_SECONDS = 25
MAX_PDFSIG_OUTPUT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PadesSignature:
    index: int
    signer_common_name: str | None
    signer_distinguished_name: str | None
    signing_time: str | None
    signature_type: str | None
    signature_validation: str | None
    certificate_validation: str | None
    covers_entire_file: bool


@dataclass(frozen=True)
class PadesValidationResult:
    status: Literal["valid_integrity", "invalid", "unavailable"]
    certificate_trust: Literal["trusted", "unverified", "invalid", "unavailable"]
    signatures: tuple[PadesSignature, ...]
    reason: str

    @property
    def integrity_valid(self) -> bool:
        return self.status == "valid_integrity"

    def report_json(self) -> str:
        return json.dumps(
            {
                "validator": "pdfsig",
                "status": self.status,
                "certificate_trust": self.certificate_trust,
                "reason": self.reason,
                "signatures": [asdict(signature) for signature in self.signatures],
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )


def _field(lines: list[str], label: str) -> str | None:
    prefix = label.casefold() + ":"
    for line in lines:
        candidate = line.strip().removeprefix("-").strip()
        if candidate.casefold().startswith(prefix):
            value = candidate[len(prefix) :].strip()
            return value[:1000] or None
    return None


def _covers_entire_file(lines: list[str], pdf_size: int) -> bool:
    normalized = {line.strip().removeprefix("-").strip().casefold() for line in lines}
    if "not total document signed" in normalized:
        return False
    if "total document signed" in normalized:
        return True
    ranges = _field(lines, "Signed Ranges")
    if not ranges:
        return False
    numbers = [int(value) for value in re.findall(r"\d+", ranges)]
    return bool(numbers and numbers[-1] == pdf_size)


def _parse_pdfsig(output: str, pdf_size: int) -> tuple[PadesSignature, ...]:
    sections: list[tuple[int, list[str]]] = []
    current: tuple[int, list[str]] | None = None
    for line in output.splitlines():
        match = re.match(r"^Signature\s+#(\d+):\s*$", line.strip(), re.IGNORECASE)
        if match:
            current = (int(match.group(1)), [])
            sections.append(current)
        elif current is not None:
            current[1].append(line)
    return tuple(
        PadesSignature(
            index=index,
            signer_common_name=_field(lines, "Signer Certificate Common Name"),
            signer_distinguished_name=_field(lines, "Signer full Distinguished Name"),
            signing_time=_field(lines, "Signing Time"),
            signature_type=_field(lines, "Signature Type"),
            signature_validation=_field(lines, "Signature Validation"),
            certificate_validation=_field(lines, "Certificate Validation"),
            covers_entire_file=_covers_entire_file(lines, pdf_size),
        )
        for index, lines in sections
    )


def validate_pades_pdf(pdf: bytes) -> PadesValidationResult:
    """Validate every embedded signature and require the last one to cover EOF."""
    if not pdf.startswith(b"%PDF-"):
        return PadesValidationResult("invalid", "invalid", (), "not_pdf")
    environment = os.environ.copy()
    environment.update({"LANG": "C", "LC_ALL": "C"})
    try:
        with tempfile.TemporaryDirectory(prefix="lexflow-pades-") as directory:
            source = Path(directory) / "signed.pdf"
            report = Path(directory) / "pdfsig.txt"
            source.write_bytes(pdf)
            with report.open("wb") as output:
                process = subprocess.run(
                    ["pdfsig", str(source)],
                    cwd=directory,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=PDFSIG_TIMEOUT_SECONDS,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            if report.stat().st_size > MAX_PDFSIG_OUTPUT_BYTES:
                return PadesValidationResult("unavailable", "unavailable", (), "validator_output_limit")
            combined = report.read_bytes()
    except (OSError, subprocess.TimeoutExpired):
        return PadesValidationResult("unavailable", "unavailable", (), "validator_unavailable")
    output = combined.decode("utf-8", errors="replace")
    signatures = _parse_pdfsig(output, len(pdf))
    validations = [(signature.signature_validation or "").casefold() for signature in signatures]
    all_valid = bool(signatures) and all(
        "signature is valid" in value and "invalid" not in value for value in validations
    )
    fully_covered = bool(signatures and signatures[-1].covers_entire_file)
    if process.returncode != 0 or not all_valid or not fully_covered:
        reason = "no_signature" if not signatures else "invalid_signature" if not all_valid else "unsigned_increment"
        return PadesValidationResult("invalid", "invalid", signatures, reason)
    certificate_values = [(signature.certificate_validation or "").casefold() for signature in signatures]
    trusted = bool(certificate_values) and all("certificate is trusted" in value for value in certificate_values)
    return PadesValidationResult(
        "valid_integrity",
        "trusted" if trusted else "unverified",
        signatures,
        "integrity_valid_trust_local_only" if trusted else "integrity_valid_trust_unverified",
    )
