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
    tenant_name: str
    oab_number: str = None
    oab_uf: str = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_name: str

@router.post("/register", response_model=TokenResponse)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado no sistema.")

    # Create new tenant
    tenant_slug = user_in.tenant_name.lower().replace(" ", "-")
    tenant = Tenant(name=user_in.tenant_name, slug=tenant_slug)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    # Create user
    user = User(
        tenant_id=tenant.id,
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role="admin",
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
        user_name=user.full_name
    )

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/login", response_model=TokenResponse)
async def login(login_in: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_in.email))
    user = result.scalars().first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")

    token = create_access_token(subject=user.id, tenant_id=user.tenant_id)
    return TokenResponse(
        access_token=token,
        tenant_id=user.tenant_id,
        user_name=user.full_name
    )
