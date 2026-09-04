# Design aprovado — Painel Diário do LexFlow

Status: aprovado para planejamento em 01/09/2026. Este documento não autoriza alegações de homologação ou produção.

## Entendimento confirmado

- O produto é o LexFlow, priorizando advogados autônomos e pequenos escritórios.
- O próximo ciclo deve entregar diferenciação percebida e reduzir risco técnico no mesmo fluxo.
- O Painel Diário será a porta de entrada para casos, documentos, comunicações e financeiro.
- O advogado deve entender as prioridades e iniciar a próxima ação em até 30 segundos.
- Casos sem próxima ação devem ser sinalizados e corrigidos por cadastro explícito, nunca por automação silenciosa.
- O painel executará somente ações rápidas e reversíveis; operações profundas permanecem nos módulos especializados.
- Nenhuma integração externa nova faz parte deste ciclo.

## Requisitos não funcionais

- Escala: até 100 escritórios, normalmente com até 5 usuários e dezenas de milhares de registros por tenant.
- Desempenho: conteúdo útil em até 2 segundos e mutações em até 500 ms, ambos no p95.
- Segurança: isolamento por tenant e caso, autorização por papel, auditoria e nenhum cache jurídico offline persistente.
- Confiabilidade: 99,5% mensal, sem confirmação falsa, operações idempotentes, RPO de 1 hora e RTO de 4 horas.
- Manutenção: uma pessoa ou equipe pequena, preservando o monólito modular.
- Acessibilidade: fluxo completo operável por teclado e toque, inclusive em viewport de 375 px, sem depender somente de cor.

## Premissas

- PostgreSQL e os contratos persistidos existentes são a fonte de verdade.
- APIs, permissões, auditoria e controle de concorrência existentes devem ser reutilizados.
- O painel não duplicará regras pertencentes aos módulos especializados.
- IA não determinará prioridades neste ciclo.
- Documentos, mensagens e movimentações financeiras continuarão exigindo seus fluxos próprios.
- O checkout contém alterações não consolidadas que devem ser preservadas durante qualquer implementação futura.
- Metas de disponibilidade, RPO e RTO dependem de homologação operacional; não podem ser comprovadas apenas pelo código do painel.

## Evidência do estado atual

- `frontend/src/app/dashboard/page.tsx` já consome `/workspace/summary`, `/workspace/analytics`, `/workspace/activity` e `/workspace/tasks`.
- `backend/app/api/v1/endpoints/workspace.py` já aplica autorização às tarefas e suporta criação e atualização auditadas.
- Atualizações de tarefas já exigem `expected_revision`, permitindo tratar concorrência sem sobrescrever silenciosamente.
- O resumo atual carrega coleções de tarefas e casos para produzir alguns totais em memória.
- A primeira tela depende de várias requisições antes de consolidar seu contexto.
- `backend/app/api/v1/endpoints/dashboard.py` e `frontend/src/lib/dashboardService.ts` conservam métricas simuladas legadas, sem consumidor identificado na interface atual.

## Alternativas consideradas

### 1. Evoluir a visão diária no módulo `workspace` — aceita

Ampliar o contrato existente, ordenar e agregar no PostgreSQL e reutilizar as mutações de tarefas. Entrega consistência e desempenho sem criar infraestrutura.

### 2. Compor tudo no frontend — rejeitada

Tem menor custo inicial, mas espalha regras de prioridade pelo navegador, aumenta requisições e pode combinar respostas de instantes diferentes.

### 3. Criar projeção operacional materializada — rejeitada

Oferece alta extensibilidade, mas exige eventos, reconciliação, monitoramento e operação incompatíveis com a escala e a equipe definidas.

## Arquitetura aprovada

O design permanece dentro do monólito modular. Não serão criados microserviço, fila, tabela de projeção ou dependência nova.

`GET /workspace/summary` será estendido de forma compatível para entregar:

- totais de atrasados, hoje, próximos e casos sem ação;
- fila operacional limitada e ordenada pelo banco;
- sinais persistidos de documentos, comunicações e financeiro;
- contexto mínimo de caso e cliente;
- ações permitidas e token de revisão quando aplicável;
- `generated_at` e fuso horário efetivamente usado.

O conteúdo essencial dependerá somente dessa resposta. Analytics, atividade recente e assistente serão secundários e não bloquearão a primeira ação.

Os cálculos atuais sobre coleções completas serão substituídos por agregações SQL, consultas limitadas e `NOT EXISTS`. Índices novos só serão admitidos quando `EXPLAIN ANALYZE` demonstrar necessidade.

As ações rápidas reutilizarão:

- `POST /workspace/tasks` para cadastrar a próxima ação;
- `PUT /workspace/tasks/{id}` para concluir ou reagendar;
- `expected_revision` para concorrência;
- autorização e auditoria existentes.

O dashboard legado com métricas simuladas e seu fallback local deverão ser removidos após a checagem final de referências no runtime. Não haverá substituição fictícia se o backend falhar.

## Contrato conceitual da fila

Cada item de atenção terá somente os campos necessários à decisão e navegação:

- `kind`: origem persistida do item;
- `severity`: agrupamento visual e de ordenação;
- `title`: descrição curta, sem corpo documental;
- data relevante e fuso aplicável;
- `case_id` e contexto mínimo permitido;
- destino para o módulo responsável;
- ações permitidas;
- `revision`, quando o item puder ser alterado.

A fila inicial será limitada a 20 itens. Paginação ou expansão só será adicionada se o uso real demonstrar necessidade; o painel não substituirá a agenda completa.

## Ordenação determinística

1. Compromissos vencidos.
2. Prazos e audiências de hoje, destacando datas ainda não revisadas.
3. Demais tarefas de hoje.
4. Publicações ainda não reconhecidas.
5. Comunicações com entrega `failed` ou `unknown`.
6. Processos ativos sem tarefa pendente.
7. Próximas tarefas, em ordem cronológica.

Empates devem usar data relevante e identificador estável para que a ordem não oscile entre carregamentos.

## Limites semânticos dos dados

- Documentos não têm estado jurídico persistido como “aguardando revisão”. O painel pode sinalizar falhas de upload, armazenamento ou processamento, mas não inventará atraso documental.
- Lançamentos financeiros não têm vencimento persistido. O painel pode mostrar lançamentos em rascunho para revisão, somente a papéis financeiros, mas não os chamará de cobrança vencida.
- Estados jurídicos adicionais exigirão validação do piloto e um design próprio antes de ampliar o modelo.

Todas as consultas aplicarão tenant, acesso ao caso, papel financeiro e exclusão de registros arquivados ou cancelados. Itens visíveis sem permissão de escrita não oferecerão ações rápidas.

## Interface aprovada

O Painel Diário terá três níveis:

1. **Agora:** um item principal, com contexto do caso e uma ação inequívoca.
2. **Hoje e atenção:** lista compacta, agrupada por gravidade.
3. **Planejamento:** processos sem próxima ação e próximos compromissos.

Documentos, comunicações e financeiro aparecerão como sinais contextuais com navegação ao módulo responsável. Analytics, atividade recente e IA permanecerão abaixo do fluxo operacional.

Ações rápidas:

- concluir;
- reagendar;
- cadastrar próxima ação;
- abrir o contexto correto.

No celular, a interface será uma coluna única. O desktop poderá exibir mais contexto, mas não possuirá ações exclusivas.

## Fluxo de mutação e erros

Nenhum item desaparecerá de forma otimista. A interface aguardará a resposta persistida e então atualizará o resumo.

- `409`: informar concorrência e carregar a versão atual.
- `401`: preservar a tela e solicitar nova autenticação.
- `403`: informar falta de permissão sem revelar dados adicionais.
- `422`: manter o formulário e destacar o campo inválido.
- falha de rede ou `5xx`: manter o item e permitir nova tentativa segura.
- resposta parcial: mostrar conteúdo disponível e identificar a seção indisponível.

Botões permanecerão ocupados durante a requisição para evitar repetição acidental. Confirmações só serão exibidas depois do commit no servidor.

## Estratégia de validação

### Backend

- ordenação por gravidade, data e desempate;
- limites de “hoje” no fuso do escritório;
- isolamento de tenant e acesso restrito por caso em PostgreSQL;
- ocultação financeira por papel;
- criação, conclusão, reagendamento, auditoria e conflito por revisão;
- ausência de fallback e métricas simuladas.

### Frontend

- carregamento, vazio, resposta parcial e erro;
- ações rápidas sem remoção otimista;
- preservação do formulário após `409`, `422` e falha de rede;
- teclado, foco, anúncio de resultado e viewport de 375 px;
- jornada com backend real em desktop e celular.

### Desempenho e observabilidade

O teste de desempenho usará PostgreSQL descartável com dezenas de milhares de registros no mesmo tenant e outro tenant para detectar vazamento. Serão medidos o p95 do resumo e das mutações.

A observabilidade registrará duração, código HTTP e quantidade de itens por categoria. Não registrará títulos, conteúdo jurídico, destinatários ou valores. Erros continuarão no Sentry existente.

RPO, RTO e disponibilidade serão gates do ambiente real, comprovados por monitoramento, backup e restauração, não inferidos dos testes locais.

## Registro de decisões

| Decisão | Alternativas | Motivo |
| --- | --- | --- |
| Público inicial: autônomos e pequenos escritórios | Escritórios médios, departamentos jurídicos, público genérico | Permite validar o fluxo completo com menor complexidade organizacional. |
| Diferencial e risco técnico no mesmo ciclo | Estabilizar tudo antes ou lançar feature antes | Evita ampliar uma base frágil sem adiar valor percebido. |
| Painel Diário como centro | Caso, cliente ou assistente como centro | Corresponde ao objetivo de orientar o trabalho em até 30 segundos. |
| Próxima ação explícita | Regra automática ou sugestão de IA | Mantém o advogado no controle e oferece rastreabilidade. |
| Ações rápidas limitadas | Somente navegação ou operação completa no painel | Reduz troca de contexto sem duplicar módulos especializados. |
| Evoluir `workspace` | Composição frontend ou projeção materializada | Melhor equilíbrio entre consistência, desempenho e manutenção. |
| Prioridade determinística | IA ou heurística opaca | Evita recomendações jurídicas não verificáveis. |
| Sem integração externa nova | Expandir provedores | Concentra o ciclo na consolidação dos dados existentes. |
| Sem confirmação otimista | Remoção imediata do item | Impede falso sucesso em operações profissionais. |
| Metas operacionais como gates | Inferi-las do código | Disponibilidade e recuperação exigem evidência do ambiente real. |

## Riscos reconhecidos

- O resumo pode se tornar um endpoint excessivamente amplo; a resposta deve permanecer limitada ao trabalho diário, não a relatórios completos.
- Regras de prioridade podem não refletir todas as rotinas jurídicas; o piloto deverá observar reordenações frequentes e itens ignorados.
- Estados atuais de documentos e financeiro são insuficientes para prazos de negócio; o painel deve comunicar essa limitação.
- Consultas agregadas podem exigir índices adicionais, mas adicioná-los sem medição aumentaria custo de escrita e manutenção.
- O checkout atual é amplo e não consolidado; qualquer implementação deverá separar mudanças do painel das alterações preexistentes.

## Critérios de aceite do design

- O advogado identifica e inicia uma prioridade em até 30 segundos.
- O conteúdo essencial vem de uma única visão persistida e autorizada.
- Nenhuma métrica simulada aparece quando há falha.
- Concluir, reagendar e criar próxima ação preservam auditoria, permissão e concorrência.
- Tenant, acesso ao caso e papel financeiro são respeitados em todos os itens.
- O fluxo essencial funciona a 375 px e por teclado.
- Metas de p95 são medidas com volume representativo.
- Nenhuma integração, serviço ou dependência nova é necessária.
