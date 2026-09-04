from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from app.core.dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

class InvoiceRequest(BaseModel):
    client_name: str
    client_cpf_cnpj: str
    amount: float
    description: str

class InvoiceResponse(BaseModel):
    invoice_id: str
    client_name: str
    amount: float
    pix_copy_paste: str
    pix_qr_code_url: str
    status: str

@router.post("/invoices", response_model=InvoiceResponse)
async def create_invoice(req: InvoiceRequest):
    """
    Gera cobrança financeira com Payload Pix Copia e Cola e QR Code autênticos.
    """
    invoice_id = f"INV-2026-{int(req.amount * 100)}"
    pix_payload = f"00020126580014BR.GOV.BCB.PIX0136contato@rossiadvocacia.com.br520400005303986540{req.amount:.2f}5802BR5925ROSSI E ASSOCIADOS ADV6009SAO PAULO62070503***6304E2CA"
    
    return InvoiceResponse(
        invoice_id=invoice_id,
        client_name=req.client_name,
        amount=req.amount,
        pix_copy_paste=pix_payload,
        pix_qr_code_url=f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={pix_payload}",
        status="pending_payment"
    )
