# 📋 Registro de Mudanças do Projeto (CHANGELOG.md)
**LexFlow Enterprise - SaaS LegalTech & Hub OAB**

Este documento registra o histórico das principais alterações, novas funcionalidades, refatorações de código e correções implementadas no sistema, servindo como guia permanente para acompanhamento da evolução do projeto.

---

## 📅 Histórico de Mudanças Realizadas (Agosto/2026)

### 🟢 [Módulo 12] Caixa Flutuante das 27 UFs da OAB (`StateSelectorModal`)
- **Nova Funcionalidade**: Implementado modal flutuante em *dark glassmorphism* para seleção de qualquer uma das **27 Unidades Federativas (UFs)** do Brasil (AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI, RJ, RN, RS, RO, RR, SC, SP, SE, TO).
- **Busca em Tempo Real**: Campo de pesquisa inteligente por código de estado, nome do estado ou sigla (ex: *"São Paulo"*, *"OAB/MG"*, *"RJ"*, *"DF"*).
- **Abas por Região**: Filtros rápidos por Regiões do Brasil (*Todas*, *Sudeste*, *Sul*, *Nordeste*, *Centro-Oeste*, *Norte*).
- **Recálculo Financeiro Dinâmico**: Ao selecionar qualquer estado na caixa flutuante, a anuidade base, taxa de requerimento e carteira são recalculados instantaneamente no Zustand Store (`useOabStore.ts`).

---

### 🟢 [Módulo 12] Gerador de Boleto & Pix da Ordem (`PixPaymentModal`)
- **Nova Funcionalidade**: Modal de checkout e pagamento ativado pelo botão **"Gerar Boleto/Pix da Ordem"** na calculadora.
- **Aba Pix Instantâneo**: Exibição de **QR Code visual em padrão EMV Pix**, contador regressivo de expiração da chave (15 minutos), campo de chave **Pix Copia e Cola** e botão de cópia com notificação Toast.
- **Aba Boleto Bancário**: Exibição de linha digitável formatada da guia OAB, representação de código de barras e simulação de download de PDF da guia.
- **Discriminativo de Taxas & Descontos**: Exibição detalhada de taxas de requerimento, carteira, anuidade proporcional e abatimento dos programas **Jovem Advogado (50%)** e **Sociedade Unipessoal SUA (25%)**.
- **Simulação de Quitação**: Botão *"Simular Pagamento Confirmado no Pix"* que altera o estado do modal para exibições de recibo e comprovante de quitação imediata.

---

### 🟢 [Módulo 12] Tabela Ética Dinâmica & Reajuste Automático (`HonorariosTable` / Guia SUA)
- **Transformação Dinâmica**: Substituição da tabela HTML estática da página do Guia SUA (`/oab-hub/sua-guide`) pelo componente reativo `HonorariosTable`.
- **Seletor de Ano Referencial**: Suporte a alternância entre os anos **2024, 2025, 2026 e 2027** com aplicação de fatores inflacionários.
- **Reajuste Porcentual Automático (% ou IPCA)**: Botões de reajuste rápido (`0%`, `+5%`, `+10%`, `+15%`) e campo para aplicação de percentual em lote em todos os honorários da tabela.
- **Vínculo Regional por Seccional**: Aplicação de multiplicador dinâmico de acordo com a seccional ativa na store.
- **Edição Inline & Gerador de Proposta**: Ícone de edição em cada linha para personalizar o valor base e botão **"Copiar Proposta"** para gerar minutas comerciais prontas para clientes.

---

### 🟢 [Módulo 2] CRM & Inbox Unificada Totalmente Funcional (`/dashboard/crm`)
- **Nova Funcionalidade - Modal `NewLeadModal`**: Conectado o botão **"+ Novo Lead / Oportunidade"** a um formulário em *glassmorphic dark design* com cadastro de cliente, canal (WhatsApp, E-mail, Formulário, Recomendação, Telefone), assunto/serviço, valor estimado (R$), estágio no funil e observações.
- **Nova Funcionalidade - Modal `LeadDetailModal`**: Ao clicar em qualquer card do Kanban, abre-se o modal de detalhes com transição rápida de estágios (*Novos Leads ➔ Em Qualificação ➔ Proposta Enviada ➔ Contrato Fechado*), histórico de anotações editável e opção de exclusão.
- **Barra de Métricas do Pipeline (KPIs)**: Exibição em tempo real do **Total em Pipeline (R$)**, **Oportunidades Ativas**, **Ticket Médio de Proposta** e **Faturamento de Contratos Fechados**.
- **Barra de Filtros e Busca em Tempo Real**: Pesquisa por texto (nome do cliente ou assunto) e filtragem por origem/canal de prospecção.
- **Correção Linguística & Refatoração**: Correção do título da primeira coluna do Kanban (*"Novos Leed"* ➔ *"Novos Leads / Contato Inicial"*) e notificação Toast para todas as ações.

---

### 🟢 [Módulo 1] Dashboard Principal de Alto Desempenho & Governança (`/dashboard`)
- **Integração Real com Zustand Store**: O quadro de *Status da Inscrição OAB* agora lê dinamicamente a **Seccional Ativa** (com suporte à abertura direta da modal das 27 UFs) e calcula o **Percentual Exato do Checklist** (`X de Y validados (%)`).
- **Seletor de Período nos KPIs**: Adicionado filtro temporal (*Hoje*, *Semana*, *Mês*, *Ano*) recalculando dinamicamente os valores de *Processos Ativos*, *Conflitos Verificados*, *Contratos Assinados* e *Faturamento Projetado*.
- **Central de Ações Rápidas Executivas**: Atalhos diretos para *"Novo Lead CRM"*, *"Boleto/Pix OAB"*, *"Tabela Ética"* e *"Emitir Declaração"*.
- **Agenda de Prazos Críticos & Audit Logs LGPD**: Adicionados quadros de tarefas iminentes com tags de prioridade (*Alta*, *Média*, *Normal*) e log reativo da sessão do usuário com resumos de ações e hashes SHA-256.

---

### 🎨 [UI/UX & Arquitetura] Refatoração de Layouts & Resiliência Visual
- **Prevenção de Estouro de Tela (`overflow-x-hidden`)**: Atualizados os wrappers de layout principal (`OabHubLayout` e `DashboardLayout`) com regras de controle de esticamento horizontal, impedindo desalinhamento do cabeçalho e da barra lateral.
- **Grid Responsiva Simétrica (8 Itens)**: Ajustado o grid de atalhos rápidos de seccionais na calculadora para 7 estados + 1 botão gatilho **"+ 20 UFs"**, forming 2 linhas simétricas perfeitas de 4 colunas.
- **Estilização Dark em Dropdowns**: Aplicadas regras explícitas em tags `<select>` e `<option>` para evitar fundo branco padrão do navegador em modo escuro.

---

## 🔮 Registro de Mudanças Futuras (De Agora em Diante)

*Utilize o modelo padrão abaixo para registrar todas as novas funcionalidades, melhorias e correções:*

```markdown
### 🗓️ [DD/MM/AAAA] - [Título da Funcionalidade / Alteração]
- **Tipo**: `[Nova Funcionalidade]` | `[Melhoria / Refatoração]` | `[Correção de Bug]` | `[Arquitetura]`
- **Módulo Afetado**: ex: CRM, Conflitos, Petições, Hub OAB, Financial
- **Arquivos Modificados**:
  - `path/to/file.tsx`
- **Descrição da Alteração**:
  - Detalhamento do que foi alterado e seu impacto.
```

---

*LexFlow Enterprise SaaS — Documento Mantido pelo Assistente de IA e Equipe de Desenvolvimento.*
