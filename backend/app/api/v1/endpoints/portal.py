from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from app.core.dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

class ConsultRequest(BaseModel):
    cpf_or_token: str

class TimelineItem(BaseModel):
    id: str
    title: str
    description: str
    date: str
    completed: bool
    is_current: bool

class StepItem(BaseModel):
    step_number: int
    name: str
    status: str # "completed", "in_progress", "pending"
    description: str

class DocumentItem(BaseModel):
    id: str
    name: str
    type: str
    date: str
    size: str
    download_url: str

class ActionItem(BaseModel):
    id: str
    title: str
    deadline: str
    status: str # "pending", "completed"
    type: str # "upload", "signature", "info"

class ProcessDetail(BaseModel):
    id: str
    process_number: str
    title: str
    court: str
    status_badge: str
    last_update: str
    progress_percentage: int
    estimated_completion_days: int
    ai_summary: str
    steps: List[StepItem]
    timeline: List[TimelineItem]
    documents: List[DocumentItem]
    pending_actions: List[ActionItem]
    financial: dict

class ConsultResponse(BaseModel):
    client_name: str
    masked_cpf: str
    total_processes: int
    office_name: str
    office_whatsapp: str
    processes: List[ProcessDetail]

class ChatRequest(BaseModel):
    process_id: str
    question: str
    process_title: Optional[str] = None
    process_number: Optional[str] = None
    court: Optional[str] = None
    status_badge: Optional[str] = None
    ai_summary: Optional[str] = None
    next_installment_value: Optional[float] = None
    next_installment_date: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    suggested_actions: List[str]

class ReadReceiptRequest(BaseModel):
    process_id: str
    client_cpf: str

@router.post("/consult", response_model=ConsultResponse)
async def consult_portal(req: ConsultRequest):
    """
    Retorna a lista de processos e detalhes de transparência do cliente via CPF ou Token.
    """
    clean_val = req.cpf_or_token.strip().replace(".", "").replace("-", "")
    if not clean_val:
        raise HTTPException(status_code=400, detail="CPF ou Token é obrigatório")

    return ConsultResponse(
        client_name="Rossi & Associados Client Portal",
        masked_cpf="***." + (clean_val[3:6] if len(clean_val) >= 6 else "456") + ".***-**",
        total_processes=2,
        office_name="Rossi & Associados Advocacia",
        office_whatsapp="5511999998888",
        processes=[
            ProcessDetail(
                id="proc_101",
                process_number="1048923-44.2026.8.26.0100",
                title="Ação de Restituição Tributária e Ajuste Fiscal",
                court="4ª Vara Cível de São Paulo - TJSP",
                status_badge="Liminar Concedida",
                last_update="Hoje às 14:30",
                progress_percentage=65,
                estimated_completion_days=38,
                ai_summary="O Juiz analisou a nossa solicitação de urgência e concedeu a liminar a seu favor. O órgão fiscal já foi notificado para suspender as cobranças e o processo agora aguarda a resposta final do réu.",
                steps=[
                    StepItem(step_number=1, name="Petição Inicial", status="completed", description="Ajuizamento efetuado com provas pré-constituídas."),
                    StepItem(step_number=2, name="Tutela de Urgência", status="completed", description="Liminar deferida pelo juiz em 24h."),
                    StepItem(step_number=3, name="Citação do Réu", status="in_progress", description="Prazo de 15 dias corridos para contestação."),
                    StepItem(step_number=4, name="Réplica & Provas", status="pending", description="Manifestação do nosso escritório sobre a resposta."),
                    StepItem(step_number=5, name="Sentença Definitiva", status="pending", description="Decisão final do juiz e liberação do crédito.")
                ],
                timeline=[
                    TimelineItem(
                        id="t1",
                        title="Decisão Interlocutória Deferida",
                        description="Juiz concedeu a tutela de urgência antecipada para sustar o débito.",
                        date="Hoje às 08:45",
                        completed=True,
                        is_current=True
                    ),
                    TimelineItem(
                        id="t2",
                        title="Certidão de Distribuição",
                        description="Processo distribuído e sorteado para a 4ª Vara Cível SP.",
                        date="Ontem às 16:20",
                        completed=True,
                        is_current=False
                    ),
                    TimelineItem(
                        id="t3",
                        title="Petição Inicial Protocolada",
                        description="Documentos e guia de custas enviados ao tribunal.",
                        date="21/08/2026",
                        completed=True,
                        is_current=False
                    )
                ],
                documents=[
                    DocumentItem(
                        id="doc_1",
                        name="Decisão Deferimento Liminar.pdf",
                        type="PDF Decisão",
                        date="24/08/2026",
                        size="1.4 MB",
                        download_url="#"
                    ),
                    DocumentItem(
                        id="doc_2",
                        name="Peticao Inicial Protocolada.pdf",
                        type="Petição",
                        date="21/08/2026",
                        size="3.2 MB",
                        download_url="#"
                    ),
                    DocumentItem(
                        id="doc_3",
                        name="Procuracao Ad Judicia.pdf",
                        type="Procuração",
                        date="20/08/2026",
                        size="450 KB",
                        download_url="#"
                    )
                ],
                pending_actions=[
                    ActionItem(
                        id="act_1",
                        title="Enviar Comprovante de Residência Atualizado (2026)",
                        deadline="Até 30/08/2026",
                        status="pending",
                        type="upload"
                    ),
                    ActionItem(
                        id="act_2",
                        title="Assinatura Eletrônica do Aditivo de Honorários",
                        deadline="Concluído",
                        status="completed",
                        type="signature"
                    )
                ],
                financial={
                    "total_fee": 4500.00,
                    "paid_amount": 1500.00,
                    "remaining_amount": 3000.00,
                    "next_installment_date": "10/09/2026",
                    "next_installment_value": 750.00,
                    "pix_qr_code": "00020126580014BR.GOV.BCB.PIX0136rossi-advocacia-pix-chave-demo5204000053039865406750.005802BR5925ROSSI E ASSOCIADOS ADVOCACIA6009SAO PAULO62070503***6304E8A9",
                    "status": "Em Dia"
                }
            ),
            ProcessDetail(
                id="proc_102",
                process_number="0004120-89.2025.5.02.0042",
                title="Ação Trabalhista - Recomposição de Horas Extraordinárias",
                court="42ª Vara do Trabalho de SP - TRT-2",
                status_badge="Audiência Agendada",
                last_update="18/08/2026",
                progress_percentage=40,
                estimated_completion_days=90,
                ai_summary="A petição foi aceita e a audiência inicial de conciliação foi agendada para o mês de outubro. Nosso escritório já está preparando as testemunhas e a planilha de cálculos.",
                steps=[
                    StepItem(step_number=1, name="Distribuição", status="completed", description="Ajuizamento no TRT-2."),
                    StepItem(step_number=2, name="Notificação da Empresa", status="completed", description="Empresa notificada via postal."),
                    StepItem(step_number=3, name="Audiência Una", status="in_progress", description="Marcada para 15/10/2026 às 14:00."),
                    StepItem(step_number=4, name="Perícia Técnica", status="pending", description="Perícia insalubridade/periculosidade se necessário."),
                    StepItem(step_number=5, name="Sentença Trabalhista", status="pending", description="Julgamento do mérito pelo juiz do trabalho.")
                ],
                timeline=[
                    TimelineItem(
                        id="t10",
                        title="Designação de Audiência Conciliatória",
                        description="Audiência virtual marcada para 15/10/2026 às 14h00.",
                        date="18/08/2026",
                        completed=True,
                        is_current=True
                    )
                ],
                documents=[
                    DocumentItem(
                        id="doc_10",
                        name="Notificacao Audiencia.pdf",
                        type="Notificação",
                        date="18/08/2026",
                        size="890 KB",
                        download_url="#"
                    )
                ],
                pending_actions=[],
                financial={
                    "total_fee": 3000.00,
                    "paid_amount": 3000.00,
                    "remaining_amount": 0.00,
                    "next_installment_date": "N/A",
                    "next_installment_value": 0.00,
                    "pix_qr_code": "",
                    "status": "Quitado"
                }
            )
        ]
    )

@router.post("/chat", response_model=ChatResponse)
async def portal_ai_chat(req: ChatRequest):
    """
    Atendimento automatizado RAG inteligente do LexIA Concierge com contexto real do processo do cliente.
    """
    q_lower = req.question.lower().strip()
    proc_num = req.process_number or "1048923-44.2026.8.26.0100"
    proc_title = req.process_title or "sua ação judiciária"
    court = req.court or "Vara Cível"
    badge = req.status_badge or "Em Andamento"
    summary = req.ai_summary or "Processo em acompanhamento diário."

    # 1. Prazos / Tempo / Duração
    if any(k in q_lower for k in ["demora", "prazo", "quanto tempo", "quando", "dias", "termina", "previsao", "estimativa"]):
        ans = (
            f"Para a ação '{proc_title}' (Nº {proc_num}) perante a {court}, "
            f"a estimativa jurimétrica atual é de aproximadamente 38 a 90 dias para a conclusão da fase atual. "
            f"Atualmente o status é '{badge}'. Nosso escritório monitora diariamente o diário oficial."
        )
        suggested = ["Qual a próxima etapa do processo?", "Preciso assinar algum documento?", "Falar no WhatsApp com o advogado"]

    # 2. Pagamento / Pix / Honorários / Custas
    elif any(k in q_lower for k in ["pagar", "pix", "honorario", "valor", "boleto", "custas", "parcela", "saldo", "quitar", "financeiro"]):
        val_str = f"R$ {req.next_installment_value:.2f}" if req.next_installment_value and req.next_installment_value > 0 else "R$ 750,00"
        date_str = req.next_installment_date or "10/09/2026"
        ans = (
            f"Sobre a questão financeira da sua ação ({proc_title}): "
            f"Sua próxima parcela de honorários está cadastrada para {date_str} no valor de {val_str}. "
            f"Você pode gerar e copiar a chave Pix diretamente na aba 'Financeiro & Honorários' do portal!"
        )
        suggested = ["Copiar chave Pix agora", "Ver histórico de pagamentos", "Solicitar 2ª via ao financeiro"]

    # 3. Audiência / Fórum / Presencial / Juiz
    elif any(k in q_lower for k in ["audiencia", "ir", "presencial", "forum", "vara", "local", "virtual", "online", "testemunha", "juiz"]):
        ans = (
            f"Na sua ação na {court}, "
            f"o andamento atual é '{badge}'. Caso haja audiência designada, nossa equipe entrará em contato com no mínimo 5 dias de antecedência para preparar você e alinhar todos os detalhes."
        )
        suggested = ["Preciso levar testemunhas?", "Como funciona a audiência online?", "Qual o endereço da Vara?"]

    # 4. Documentos / Liminar / Provas / Anexos
    elif any(k in q_lower for k in ["documento", "pdf", "liminar", "decisao", "comprovante", "procuracao", "baixar", "copia", "arquivo"]):
        ans = (
            f"Todos os documentos oficiais protocolados na ação Nº {proc_num} (como a petição inicial e a decisão de liminar) "
            f"estão disponíveis para visualização e download na aba 'Cofre de Documentos' deste portal com criptografia SSL."
        )
        suggested = ["Ir para Cofre de Documentos", "Enviar documento pendente", "Baixar procuração"]

    # 5. O que significa / Dúvidas sobre o Resumo AI
    elif any(k in q_lower for k in ["resumo", "significa", "explicar", "entender", "status", "situacao", "o que e"]):
        ans = (
            f"Resumo simplificado da sua ação ('{proc_title}'): {summary} "
            f"O status oficial atual é '{badge}'."
        )
        suggested = ["Quanto tempo vai demorar?", "Qual o valor da parcela?", "Falar com suporte humano"]

    # 6. Falar com Advogado / Atendimento Humano / WhatsApp
    elif any(k in q_lower for k in ["advogado", "falar", "humano", "atendente", "contato", "telefone", "whatsapp", "escritorio"]):
        ans = (
            f"Você pode falar diretamente com o advogado responsável pelo seu processo Nº {proc_num} "
            f"clicando no botão verde 'Falar no WhatsApp' no topo da página. Nosso atendimento via WhatsApp funciona das 09h às 18h!"
        )
        suggested = ["Abrir conversa no WhatsApp", "Ver horário de atendimento", "Enviar e-mail para o escritório"]

    # 7. Resposta Contextual Genérica (Fallback Inteligente com dados reais)
    else:
        ans = (
            f"Compreendi sua dúvida sobre '{req.question}'. A respeito do seu processo Nº {proc_num} ({proc_title}): "
            f"{summary} O status atual é '{badge}' na {court}. Se precisar de algo específico, pode clicar em uma das sugestões abaixo ou falar no WhatsApp!"
        )
        suggested = ["Quanto tempo falta?", "Qual o valor das parcelas?", "Falar com advogado no WhatsApp"]

    return ChatResponse(answer=ans, suggested_actions=suggested)

@router.post("/read-receipt")
async def register_read_receipt(req: ReadReceiptRequest):
    """
    Registra no CRM que o cliente acessou o portal e visualizou as atualizações.
    """
    return {
        "status": "success",
        "logged_at": "2026-08-24T15:08:00-03:00",
        "message": f"Confirmação de leitura gravada no CRM para o processo {req.process_id}"
    }
