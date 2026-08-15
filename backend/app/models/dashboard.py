import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, JSON
from app.core.database import Base

class DashboardMetric(Base):
    __tablename__ = "dashboard_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False, index=True) # Hoje, Semana, Mês, Ano
    processos = Column(String, nullable=False)
    processos_change = Column(String, nullable=False)
    conflitos = Column(String, nullable=False)
    conflitos_change = Column(String, nullable=False)
    contratos = Column(String, nullable=False)
    contratos_change = Column(String, nullable=False)
    faturamento = Column(Float, nullable=False)
    faturamento_change = Column(String, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CriticalTask(Base):
    __tablename__ = "critical_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    dept = Column(String, nullable=False)
    deadline = Column(String, nullable=False)
    priority = Column(String, nullable=False) # Alta, Média, Normal
    color = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
