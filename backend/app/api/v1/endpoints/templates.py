from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter()

class TemplateItem(BaseModel):
    id: str
    title: str
    category: str
    description: str
    placeholders: List[str]
    content_template: str

class GenerateDocumentRequest(BaseModel):
    template_id: str
    variables: Dict[str, str]

class GenerateDocumentResponse(BaseModel):
    title: str
    rendered_content: str
    metadata: Dict[str, str]

TEMPLATES_DB: List[TemplateItem] = [
    TemplateItem(
        id="tpl_procuracao",
        title="Procuração Ad Judicia et Extra",
        category="Procurações",
        description="Outorga de poderes amplos para representação judicial em todas as instâncias.",
        placeholders=["outorgante_nome", "outorgante_cpf", "outorgante_rg", "outorgante_endereco", "foro_cidade"],
        content_template="""PROCURAÇÃO AD JUDICIA ET EXTRA

OUTORGANTE: {{outorgante_nome}}, brasileiro(a), portador(a) do CPF nº {{outorgante_cpf}} e RG nº {{outorgante_rg}}, residente e domiciliado(a) em {{outorgante_endereco}}.

OUTORGADOS: Rossi & Associados Advocacia, sociedade de advogados inscrita na OAB/SP sob o nº 45.890.

PODERES: Pelo presente instrumento particular de procuração, o(a) OUTORGANTE concede aos OUTORGADOS amplos poderes para o foro em geral, conferidos pelo artigo 105 do Código de Processo Civil, para representá-lo(a) judicial e extrajudicialmente perante a Comarca de {{foro_cidade}} e qualquer Juízo, Tribunal ou Órgão Público.

{{foro_cidade}}, 24 de Agosto de 2026.

_______________________________________
{{outorgante_nome}}
"""
    ),
    TemplateItem(
        id="tpl_honorarios",
        title="Contrato de Honorários Advocatícios Quota Litis",
        category="Contratos",
        description="Contrato de prestação de serviços jurídicos com cláusula de êxito e parcelamento.",
        placeholders=["contratante_nome", "contratante_cpf", "percentual_exito", "valor_entrada", "foro_cidade"],
        content_template="""CONTRATO DE PRESTAÇÃO DE SERVIÇOS JURÍDICOS E HONORÁRIOS ADVOCATÍCIOS

CONTRATANTE: {{contratante_nome}}, inscrito(a) no CPF nº {{contratante_cpf}}.
CONTRATADO: Rossi & Associados Advocacia.

CLÁUSULA PRIMEIRA - DO OBJETO: Prestação de serviços profissionais jurídicos no patrocínio dos interesses do CONTRATANTE.

CLÁUSULA SEGUNDA - DOS HONORÁRIOS:
a) Entrada inicial de R$ {{valor_entrada}}.
b) Honorários de Êxito: {{percentual_exito}}% (por cento) sobre o proveito econômico obtido ao final da demanda.

CLÁUSULA TERCEIRA - DO FORO: Fica eleito o foro da Comarca de {{foro_cidade}} para dirimir dúvidas deste contrato.

{{foro_cidade}}, 24 de Agosto de 2026.
"""
    ),
    TemplateItem(
        id="tpl_acordo",
        title="Termo de Acordo Extrajudicial",
        category="Acordos",
        description="Termo para quitação integral de obrigações com cláusula penal por descumprimento.",
        placeholders=["parte_a", "parte_b", "valor_acordo", "data_vencimento"],
        content_template="""TERMO DE ACORDO EXTRAJUDICIAL E QUITAÇÃO

REQUERENTE: {{parte_a}}
REQUERIDO: {{parte_b}}

Pelo presente instrumento, as partes transacionam a quitação da quantia líquida e certa de R$ {{valor_acordo}}, a ser paga impreterivelmente até {{data_vencimento}}.

Com o pagamento integral, as partes conferem mútua e irrevogável quitação.
"""
    )
]

@router.get("/", response_model=List[TemplateItem])
async def list_templates():
    """
    Retorna a lista de minutas e modelos de documentos jurídicos cadastrados no SaaS.
    """
    return TEMPLATES_DB

@router.post("/generate", response_model=GenerateDocumentResponse)
async def generate_document(req: GenerateDocumentRequest):
    """
    Gera o documento final preenchendo as variáveis dinâmicas do modelo.
    """
    tpl = next((t for t in TEMPLATES_DB if t.id == req.template_id), None)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template de documento não encontrado.")

    rendered = tpl.content_template
    for key, val in req.variables.items():
        placeholder = "{{" + key + "}}"
        rendered = rendered.replace(placeholder, str(val))

    return GenerateDocumentResponse(
        title=tpl.title,
        rendered_content=rendered,
        metadata={
            "category": tpl.category,
            "generated_at": "2026-08-24T15:50:00-03:00",
            "status": "Rascunho Pronto"
        }
    )
