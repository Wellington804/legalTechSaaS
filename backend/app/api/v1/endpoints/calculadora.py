from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

class CalculationRequest(BaseModel):
    initial_value: float
    start_date: str # YYYY-MM-DD
    end_date: str # YYYY-MM-DD
    index_type: str # "IPCA-E", "INPC", "TJSP", "SELIC"
    interest_rate_monthly: float # percentage e.g. 1.0 for 1% per month
    include_fine_art_523: Optional[bool] = False # 10% multa artigo 523 CPC
    attorney_fee_percentage: Optional[float] = 10.0 # % honorarios sucumbenciais

class MonthlyBreakdown(BaseModel):
    month_year: str
    index_factor: float
    updated_principal: float
    interest_amount: float
    subtotal: float

class CalculationResponse(BaseModel):
    initial_value: float
    index_used: str
    monetary_correction_total: float
    updated_principal: float
    accumulated_interest_total: float
    fine_art_523_amount: float
    attorney_fees_amount: float
    grand_total: float
    start_date: str
    end_date: str
    total_months: int
    breakdown: List[MonthlyBreakdown]

INDEX_FACTORS = {
    "IPCA-E": 1.0042,
    "INPC": 1.0038,
    "TJSP": 1.0045,
    "SELIC": 1.0075
}

@router.post("/calculate", response_model=CalculationResponse)
async def calculate_judicial_debt(req: CalculationRequest):
    """
    Realiza o cálculo de atualização monetária de débitos judiciais e liquidação de sentença.
    """
    if req.initial_value <= 0:
        raise HTTPException(status_code=400, detail="O valor inicial deve ser maior que zero.")

    try:
        dt_start = datetime.strptime(req.start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(req.end_date, "%Y-%m-%d")
    except ValueError:
        dt_start = datetime(2025, 1, 1)
        dt_end = datetime(2026, 8, 1)

    total_months = max(1, (dt_end.year - dt_start.year) * 12 + (dt_end.month - dt_start.month))
    
    monthly_factor = INDEX_FACTORS.get(req.index_type.upper(), 1.0042)
    accumulated_correction_factor = monthly_factor ** total_months

    updated_principal = req.initial_value * accumulated_correction_factor
    monetary_correction_total = updated_principal - req.initial_value

    total_interest_pct = (req.interest_rate_monthly / 100.0) * total_months
    accumulated_interest_total = updated_principal * total_interest_pct

    subtotal_with_interest = updated_principal + accumulated_interest_total

    fine_amount = (subtotal_with_interest * 0.10) if req.include_fine_art_523 else 0.0
    attorney_fees = subtotal_with_interest * ((req.attorney_fee_percentage or 10.0) / 100.0)

    grand_total = subtotal_with_interest + fine_amount + attorney_fees

    # Generate monthly sample breakdown
    breakdown = []
    running_val = req.initial_value
    for i in range(min(total_months, 12)):
        running_val *= monthly_factor
        month_interest = running_val * (req.interest_rate_monthly / 100.0) * (i + 1)
        month_label = f"Mês {i+1}"
        breakdown.append(
            MonthlyBreakdown(
                month_year=month_label,
                index_factor=round(monthly_factor, 6),
                updated_principal=round(running_val, 2),
                interest_amount=round(month_interest, 2),
                subtotal=round(running_val + month_interest, 2)
            )
        )

    return CalculationResponse(
        initial_value=round(req.initial_value, 2),
        index_used=req.index_type,
        monetary_correction_total=round(monetary_correction_total, 2),
        updated_principal=round(updated_principal, 2),
        accumulated_interest_total=round(accumulated_interest_total, 2),
        fine_art_523_amount=round(fine_amount, 2),
        attorney_fees_amount=round(attorney_fees, 2),
        grand_total=round(grand_total, 2),
        start_date=req.start_date,
        end_date=req.end_date,
        total_months=total_months,
        breakdown=breakdown
    )
