# LexFlow — contexto do produto

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Público principal confirmado pelo responsável pelo produto: **advogados**.
- Advogados alternam trabalho no escritório com diligências e períodos sem computador. O celular deve facilitar consulta e registro rápido, sem tornar o desktop obrigatório para os fluxos essenciais.
- O primeiro piloto foi definido para um advogado recém-aprovado na OAB. Esse recorte de validação não limita o público comercial a iniciantes.
- Porte de escritório, especialidade jurídica e experiência profissional prioritários permanecem em aberto; não assumir foco exclusivo em autônomos, pequenos escritórios ou grandes bancas.

## Product Purpose

Ser uma **Central do Advogado**: reunir a gestão do escritório, a consulta aos casos, as próximas providências e a produção documental no mesmo contexto de trabalho.

Sucesso significa o advogado conseguir localizar informações confiáveis, identificar o que precisa fazer e registrar seu trabalho sem perder dados nem depender de controles paralelos desnecessários. Não há metas quantitativas ou resultados comerciais comprovados a declarar.

## Positioning

A direção confirmada combina gestão jurídica e uma central de consulta e trabalho para o advogado. A identidade documental pessoal ou do escritório acompanha os documentos gerados pelo sistema, com assistência opcional de IA e aprovação humana.

Esse é o mecanismo de produto desejado, não uma alegação de exclusividade no mercado. Diferenciação comercial, planos e preços ainda não foram definidos.

## Operating Context

- Fluxo de referência: cliente → caso/atendimento → próxima ação → documento → honorário/despesa → comunicação. Preservar os vínculos e permissões entre essas etapas.
- No escritório: acompanhamento da carteira, agenda, documentos, financeiro e equipe. Em diligências: consulta do caso, compromisso, local e contato, seguida do registro de resultado e próxima providência.
- Identidade documental: importar referências ou configurar uma identidade, receber proposta opcional de IA, revisar, salvar rascunho, conferir a prévia e publicar. A identidade do documento é distinta da marca comercial LexFlow.
- Piloto fechado com dados fictícios e acompanhamento semanal antes de ampliar uso ou admitir dados reais. Um piloto não equivale à homologação de produção.
- Destino de hospedagem definido pelo responsável: VPS, domínio próprio e Cloudflare para DNS. Evolution Go para WhatsApp, Resend para e-mail e Sentry para erros são condições do plano, sujeitas à configuração e validação reais.

## Capabilities and Constraints

- A implementação existente é web responsiva com PWA e Web Push. Isso não a torna um aplicativo nativo nem comprova entrega de notificações em um celular físico.
- O núcleo reúne clientes, casos e permissões, agenda/tarefas, diligências, checklists, lembretes, documentos e versões, identidade documental, honorários/despesas, comunicações/portal, equipe, conta e feedback do piloto. Usar os contratos e dados persistidos existentes; não substituir funcionalidades reais por demonstrações.
- O CRM registra oportunidades persistentes por escritório em `/dashboard/crm`, com etapa, responsável, próxima ação e vínculos opcionais com cliente, processo e atendimento. Ele não substitui comunicação, cobrança ou automação comercial externa.
- `/dashboard/oab` organiza o acompanhamento pessoal da inscrição, oferece busca e links oficiais para as 27 Seccionais e guarda somente situações e itens informados pelo usuário. Não protocola pedidos, consulta processos administrativos nem confirma exigências perante a OAB.
- `/dashboard/jurimetria` consulta amostras limitadas da API Pública do DataJud e apresenta apenas distribuições descritivas e cobertura dos campos, com snapshots opcionais. A fonte pode estar indisponível, incompleta ou desatualizada; não usar a amostra como previsão de êxito, duração ou decisão judicial.
- `/dashboard/audit/ai-quality` permite importar casos de avaliação, registrar revisão independente e executar testes com casos aprovados. Essa avaliação depende do provedor configurado e não transforma uma resposta da IA em conteúdo juridicamente aprovado.
- Contas e dados são separados por escritório, com permissões por usuário/caso. Revisão, confirmação, concorrência, auditoria e limites de armazenamento fazem parte do comportamento a preservar em mudanças de interface.
- A IA é assistiva e depende de integração habilitada. Propostas exigem revisão; gerar não significa salvar, publicar, enviar ou protocolar. Não inventar fatos, poderes, condições contratuais ou datas legais.
- Branding suporta referências privadas e identidades pessoais/do escritório. Exportações Word/PDF usam versões publicadas; mudanças posteriores não reescrevem arquivos antigos. Provas, anexos originais e documentos assinados não devem ser reformatados.
- Datas de tarefas e lembretes são conferidas pelo advogado. Push não substitui acompanhamento da agenda; aceitação pelo provedor não comprova recebimento pelo usuário.
- Não guardar documentos jurídicos em cache offline persistente por padrão. Rascunhos protegidos permanecem somente em memória da conta, sem salvamento automático; fechar/recarregar pode descartá-los. Não prometer trabalho jurídico completo sem conexão.
- Assinatura eletrônica externa, cobrança automática do SaaS, protocolo ou consulta automatizada na OAB/FGV, cálculo judicial e jurimetria preditiva não devem ser apresentados como entregues sem implementação e evidência próprias.
- Publicação na VPS, entrega de provedores, alertas, recuperação de backup e experiência em aparelho físico precisam de validação no ambiente real. Testes locais e fixtures de interface não comprovam esses requisitos externos.

## Brand Commitments

- Nome confirmado pelo responsável: **LexFlow**.
- “Central do Advogado” descreve a direção funcional do produto.
- Há referências legadas a “LegalFlow” e “LegalTech” no código e metadados. São nomenclatura preexistente, não alternativas ao nome confirmado. Este registro não autoriza renomear identificadores técnicos ou redesenhar a interface.
- A identidade visual de cada advogado/escritório deve ser respeitada nos documentos; não deve ser confundida com a identidade do próprio SaaS.
- Idioma atual da aplicação: português do Brasil. Nenhuma nova paleta, tipografia, personalidade visual ou promessa comercial foi aprovada neste init.

## Evidence on Hand

- `README.md`: núcleo, limites e execução do projeto existente.
- `docs/piloto-fechado.md`: fluxo do piloto, evidências locais e requisitos externos de liberação.
- `docs/central-branding.md`: identidade documental, revisão, publicação, exportação e restrições.
- `docs/pwa-web-push.md`: instalação, notificações e limites de validação.
- `docs/operacao-vps.md`: operação e configuração de produção.
- `frontend/src/lib/navigation.ts`, `frontend/src/components/workspace/` e `backend/app/api/v1/endpoints/`: rotas, telas e contratos reais a consultar antes de modificar um fluxo.
- As evidências de teste têm escopo e data próprios; consultar o registro correspondente antes de alegar validade atual. Não há autorização para inventar depoimentos, clientes, certificações, licenças, preços ou resultados de produtividade.

## Product Principles

1. Privacidade e separação entre escritórios/casos são requisitos do produto, não detalhes opcionais da interface.
2. Facilitar a próxima ação real, inclusive durante diligências pelo celular.
3. Manter o advogado no controle de revisão, publicação e uso profissional de documentos e IA.
4. Preservar trabalho e histórico; distinguir rascunho, salvo, publicado, enviado e recebido, sem ocultar falhas ou conflitos.
5. Mostrar capacidades e limitações com honestidade, sem apresentar protótipos ou integrações pendentes como operações concluídas.

## Accessibility & Inclusion

- O uso pelo celular é um requisito explícito: controles operáveis por toque, textos legíveis e acesso facilitado às funções, sem bloquear o zoom.
- Preservar navegação por teclado, foco visível, rótulos e estados compreensíveis existentes. Não depender apenas de cor para comunicar ações ou erros.
- Necessidades assistivas específicas e uma meta formal de conformidade ainda não foram definidas. Não declarar certificação ou conformidade integral sem auditoria correspondente.
