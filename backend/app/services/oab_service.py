import hashlib
import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.oab import OABApplication, OABChecklist, OABFeeStructure, OABDeclaration
from app.schemas.oab import FeeSimulationRequest, FeeSimulationResponse

DEFAULT_OAB_CHECKLIST_ITEMS = [
    {"code": "CERTIFICADO_FGV", "title": "Certificado de Aprovação no Exame de Ordem (FGV/OAB)"},
    {"code": "DIPLOMA", "title": "Diploma ou Certidão de Graduação/Colação de Grau com Histórico Escolar"},
    {"code": "RG_CPF", "title": "Documento de Identidade Oficial (RG) e CPF"},
    {"code": "TITULO_ELEITOR", "title": "Título de Eleitor e Certidão de Quitação Eleitoral"},
    {"code": "RESERVISTA", "title": "Certificado de Reservista ou Dispensa de Incorporação (masculino)"},
    {"code": "RESIDENCIA", "title": "Comprovante de Residência Atualizado"},
    {"code": "CERTIDOES_NEGATIVAS", "title": "Certidões Negativas Criminal/Cível (Justiça Estadual, Federal e Eleitoral)"},
    {"code": "FOTOS_3X4", "title": "Duas Fotos 3x4 Oficiais (fundo branco, traje formal)"}
]

class OABService:

    @staticmethod
    async def create_application(db: AsyncSession, tenant_id: str, user_id: str, data: dict) -> OABApplication:
        app = OABApplication(
            tenant_id=tenant_id,
            user_id=user_id,
            seccional=data["seccional"],
            candidate_name=data["candidate_name"],
            cpf=data["cpf"],
            rg=data["rg"],
            fgv_exam_number=data.get("fgv_exam_number"),
            protocol_number=f"PROT-OAB-{uuid.uuid4().hex[:8].upper()}"
        )
        db.add(app)
        await db.commit()
        await db.refresh(app)

        # Initialize default checklist items
        for item in DEFAULT_OAB_CHECKLIST_ITEMS:
            chk = OABChecklist(
                application_id=app.id,
                item_code=item["code"],
                title=item["title"],
                is_completed=False
            )
            db.add(chk)
        await db.commit()
        return app

    @staticmethod
    def calculate_fees(req: FeeSimulationRequest) -> FeeSimulationResponse:
        # Standard OAB Fee structure defaults
        anuidade_anual = 950.00
        req_fee = 250.00
        card_fee = 180.00

        # Pro-rata for remaining months of the year
        months_remaining = max(1, 13 - req.month_of_registration)
        anuidade_proporcional = round((anuidade_anual / 12.0) * months_remaining, 2)

        desconto_jovem = 0.0
        if req.is_jovem_advogado:
            desconto_jovem = round(anuidade_proporcional * 0.50, 2)

        desconto_sua = 0.0
        if req.register_sua:
            desconto_sua = round(anuidade_proporcional * 0.25, 2)

        anuidade_final = max(0.0, anuidade_proporcional - desconto_jovem - desconto_sua)
        total_estimado = round(req_fee + card_fee + anuidade_final, 2)

        return FeeSimulationResponse(
            seccional=req.seccional,
            req_fee=req_fee,
            card_fee=card_fee,
            anuidade_bruta=anuidade_anual,
            anuidade_proporcional=anuidade_proporcional,
            desconto_jovem_advogado=desconto_jovem,
            desconto_sua=desconto_sua,
            total_estimado=total_estimado
        )

    @staticmethod
    def generate_declaration_text(decl_type: str, candidate_name: str, cpf: str, rg: str, address: str, civil_status: str) -> str:
        if decl_type == "IDONEIDADE_MORAL":
            return (
                f"DECLARAÇÃO DE IDONEIDADE MORAL\n\n"
                f"Eu, {candidate_name.upper()}, estado civil {civil_status}, portador(a) do RG nº {rg} "
                f"e inscrito(a) no CPF/MF sob o nº {cpf}, residente e domiciliado(a) no endereço {address}, "
                f"DECLARO, sob as penas da lei e para os fins previstos no artigo 8º, inciso VI, da Lei nº 8.906/1994 "
                f"(Estatuto da Advocacia e da OAB), gozar de ilibada idoneidade moral, não respondendo a processo penal "
                f"ou qualquer procedimento incompatível com o exercício da advocacia."
            )
        else:
            return (
                f"DECLARAÇÃO DE NÃO INCOMPATIBILIDADE E IMPEDIMENTO\n\n"
                f"Eu, {candidate_name.upper()}, estado civil {civil_status}, portador(a) do RG nº {rg} "
                f"e inscrito(a) no CPF/MF sob o nº {cpf}, residente e domiciliado(a) no endereço {address}, "
                f"DECLARO, sob as penas da lei, nos termos dos artigos 27 a 30 da Lei nº 8.906/1994, "
                f"que NÃO EXERÇO cargo ou função incompatível com a atividade de advocacia, nem me encontro em "
                f"situação de impedimento legal para o exercício da profissão de Advogado(a)."
            )
