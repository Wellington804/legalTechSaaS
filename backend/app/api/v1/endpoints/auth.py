from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter()

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: Optional[str] = "lawyer" # admin, socio, associado, estagiario, secretaria
    tenant_name: Optional[str] = "Demo Law Advocacia Enterprise"
    oab_number: Optional[str] = None
    oab_uf: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    user_name: str
    email: str
    role: str
    oab_number: Optional[str] = None
    oab_uf: Optional[str] = None

@router.post("/register", response_model=TokenResponse)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado no sistema.")

    # Get or create tenant
    tenant_name = user_in.tenant_name or "Demo Law Advocacia Enterprise"
    tenant_slug = tenant_name.lower().replace(" ", "-")
    
    tenant_res = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = tenant_res.scalars().first()
    
    if not tenant:
        tenant = Tenant(name=tenant_name, slug=tenant_slug)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

    # Create user
    user = User(
        tenant_id=tenant.id,
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role or "lawyer",
        oab_number=user_in.oab_number,
        oab_uf=user_in.oab_uf
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=user.id, tenant_id=tenant.id)
    return TokenResponse(
        access_token=token,
        tenant_id=tenant.id,
        user_id=user.id,
        user_name=user.full_name,
        email=user.email,
        role=user.role,
        oab_number=user.oab_number,
        oab_uf=user.oab_uf
    )

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/login", response_model=TokenResponse)
async def login(login_in: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_in.email))
    user = result.scalars().first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    token = create_access_token(subject=user.id, tenant_id=user.tenant_id)
    return TokenResponse(
        access_token=token,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_name=user.full_name,
        email=user.email,
        role=user.role,
        oab_number=user.oab_number,
        oab_uf=user.oab_uf
    )

