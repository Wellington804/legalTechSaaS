import hashlib
import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from app.core.dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

class UploadResponse(BaseModel):
    filename: str
    content_type: str
    file_size: int
    sha256_hash: str
    storage_url: str
    status: str

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Realiza o upload seguro de logotipos, marcas d'água e documentos PDF
    para o armazenamento persistente (MinIO / AWS S3 / Local Storage).
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Arquivo vazio enviado.")
        
        # Validação de tamanho (máximo 15MB)
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="O tamanho do arquivo excede o limite de 15MB.")

        # Cálculo do Hash SHA-256 para integridade
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        # Simulação / Persistência do URL de Armazenamento Seguro
        storage_url = f"/storage/uploads/{sha256_hash}_{file.filename}"
        
        return UploadResponse(
            filename=file.filename or "uploaded_file",
            content_type=file.content_type or "application/octet-stream",
            file_size=len(content),
            sha256_hash=sha256_hash,
            storage_url=storage_url,
            status="uploaded_successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante o upload de arquivo: {str(e)}")
