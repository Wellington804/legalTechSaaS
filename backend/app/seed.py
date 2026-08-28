import asyncio
import bcrypt
from app.core.database import AsyncSessionLocal, engine, Base
import app.models
from app.models.tenant import Tenant
from app.models.user import User
from app.models.dashboard import DashboardMetric, CriticalTask
from app.models.oab import OABFeeStructure

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

async def seed_database():
    print("[INFO] Inicializando criacao de tabelas e insercao de dados iniciais no Supabase...")
    
    # 1. Garantir que as tabelas existem no Supabase
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as session:
        # 2. Criar Tenant Inicial se não existir
        tenant_res = await session.execute(
            __import__("sqlalchemy").select(Tenant).where(Tenant.slug == "demo-law")
        )
        tenant = tenant_res.scalars().first()
        
        if not tenant:
            tenant = Tenant(
                name="Demo Law Advocacia Enterprise",
                slug="demo-law",
                cnpjs="12.345.678/0001-90",
                is_active=True
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            print(f"[OK] Tenant de testes criado: {tenant.name} (ID: {tenant.id})")
        else:
            print(f"[INFO] Tenant ja existe: {tenant.name}")
            
        # 3. Criar Usuários de Teste Pré-cadastrados (Demo Accounts)
        test_users = [
            {
                "full_name": "Dr. Wil Shaffer",
                "email": "super.admin@lexflow.law",
                "password": "lawyer123",
                "role": "super_admin",
                "oab_number": "00.001-MASTER",
                "oab_uf": "SP"
            },
            {
                "full_name": "Dra. Carolina Silva",
                "email": "carolina.silva@lexflow.law",
                "password": "lawyer123",
                "role": "socio",
                "oab_number": "12.345",
                "oab_uf": "DF"
            },
            {
                "full_name": "Dr. Alexandre Rossi",
                "email": "alexandre.rossi@lexflow.law",
                "password": "lawyer123",
                "role": "associado",
                "oab_number": "458.912",
                "oab_uf": "SP"
            },
            {
                "full_name": "Lucas Mendes",
                "email": "lucas.mendes@lexflow.law",
                "password": "lawyer123",
                "role": "estagiario",
                "oab_number": "99.111-E",
                "oab_uf": "DF"
            },
            {
                "full_name": "Mariana Costa",
                "email": "mariana.costa@lexflow.law",
                "password": "lawyer123",
                "role": "secretaria",
                "oab_number": "SEC-9082",
                "oab_uf": "SP"
            },
            {
                "full_name": "Dr. Alexandre Silva",
                "email": "admin@demolaw.com.br",
                "password": "admin123",
                "role": "admin",
                "oab_number": "123456",
                "oab_uf": "SP"
            }
        ]

        for u_data in test_users:
            user_res = await session.execute(
                __import__("sqlalchemy").select(User).where(User.email == u_data["email"])
            )
            user = user_res.scalars().first()
            
            if not user:
                hashed_pwd = hash_password(u_data["password"])
                user = User(
                    tenant_id=tenant.id,
                    full_name=u_data["full_name"],
                    email=u_data["email"],
                    hashed_password=hashed_pwd,
                    role=u_data["role"],
                    oab_number=u_data["oab_number"],
                    oab_uf=u_data["oab_uf"],
                    is_active=True
                )
                session.add(user)
                await session.commit()
                print(f"[OK] Usuario de testes criado: {u_data['email']} ({u_data['full_name']})")
            else:
                print(f"[INFO] Usuario ja existe: {u_data['email']}")

        # 4. Criar Métricas de Dashboard Iniciais
        metrics_res = await session.execute(
            __import__("sqlalchemy").select(DashboardMetric).where(DashboardMetric.tenant_id == tenant.id)
        )
        if not metrics_res.scalars().first():
            metric = DashboardMetric(
                tenant_id=tenant.id,
                period="Mes",
                processos="1,420",
                processos_change="+12.4%",
                conflitos="0 Conflitos",
                conflitos_change="100% Limpo",
                contratos="342 Assinados",
                contratos_change="+8.1%",
                faturamento=485000.00,
                faturamento_change="+18.2%"
            )
            session.add(metric)
            await session.commit()
            print("[OK] Metricas do Dashboard inseridas.")

        # 5. Criar Tarifas de OAB Exemplo
        oab_fee_res = await session.execute(
            __import__("sqlalchemy").select(OABFeeStructure).where(OABFeeStructure.seccional == "OAB/SP")
        )
        if not oab_fee_res.scalars().first():
            fee_sp = OABFeeStructure(
                seccional="OAB/SP",
                req_fee=265.00,
                card_fee=195.00,
                anuidade_full=997.00,
                jovem_advogado_discount_pct=50.0,
                sua_discount_pct=25.0
            )
            session.add(fee_sp)
            await session.commit()
            print("[OK] Tabela de Tarifas OAB/SP inserida.")

    print("\n[SUCCESS] Populacao do banco de dados no Supabase concluida com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed_database())
