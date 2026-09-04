# Decisão: assinatura integrada e calendários externos

Data da observação pública: **2026-09-04**. Esta decisão não representa cotação comercial. Preços e limites precisam ser reconfirmados antes da contratação.

## Decisão

Manter Clicksign v3 como provedor já homologado e adicionar Autentique como segundo adaptador, selecionável por escritório. Não declarar um vencedor universal antes de homologar ambos com o volume e o método de autenticação do escritório.

Para calendário, oferecer OAuth server-side com Google Calendar e Microsoft Graph. No iOS, o evento chega ao app Calendário quando o usuário já usa a mesma conta Google ou Microsoft no aparelho; o LexFlow não solicita senha do iCloud e não guarda credenciais CalDAV. O feed `webcal` permanece como alternativa simples e somente leitura.

## Clicksign Widget Embedded/Premium x Autentique

| Critério | Clicksign | Autentique | Consequência para o LexFlow |
|---|---|---|---|
| API | API v3 existente e já integrada | API GraphQL v2 documentada | Adaptadores separados atrás do mesmo envelope persistido |
| Experiência incorporada | O Widget Embedded mantém a assinatura no domínio do cliente. O Widget Embedded Premium com ICP-Brasil é um upgrade dos planos Avançado, Custom e Enterprise, com habilitação e valor mensal sob consulta | O iframe oficial está na documentação Enterprise/Corporativo e usa token temporário de login de um **membro de organização filha** para incorporar páginas do painel. Não foi confirmada equivalência a um widget para signatário externo | Clicksign é a opção publicamente confirmada para a cerimônia ICP-Brasil dentro do domínio; custo e compatibilidade A1/A3 ainda exigem proposta e homologação. Não prometer equivalência do iframe Autentique |
| Certificado digital | O Widget Embedded Premium declara assinatura qualificada ICP-Brasil dentro do domínio cadastrado | `document.qualified` é documentado para assinatura qualificada, mas a jornada incorporada equivalente não foi confirmada | PFX, chave privada e PIN nunca entram no LexFlow; a cerimônia ocorre no provedor/browser/assinador local |
| Webhook | HMAC previsto no adaptador atual | `X-Autentique-Signature`: HMAC-SHA256 hexadecimal do corpo bruto | Verificar antes de desserializar e deduplicar por evento/corpo |
| PDF final | Baixado após evento final e preservado com SHA-256 | `files.signed`/`files.pades` após `document.finished` | Original não é sobrescrito; alteração posterior do mesmo artefato falha fechada |
| Preço aplicável à comparação | Plano Avançado e adicional mensal do Widget Embedded Premium: **cotação necessária**. Os planos self-service não são usados no TCO do widget ICP-Brasil | Profissional: R$ 99/mês ou R$ 999/ano. Corporativo: a partir de R$ 2.000/mês. API: criação R$ 0,06, e-mail R$ 0,013, WhatsApp R$ 0,12, SMS R$ 0,16, consulta R$ 0,001/documento e webhook R$ 0,0002 | Não embutir números no código. Registrar versão, data observada, fonte, base/compromisso e itens unitários por tenant |
| Preço do widget/white-label | **Cotação necessária** para Avançado + Widget Embedded Premium | **Cotação necessária** para iframe/white-label corporativo e qualquer requisito fora da tabela pública | Comparar proposta escrita, SLA, implantação, suporte, impostos e franquias |

Fontes oficiais consultadas:

- Clicksign, Widget Embedded com ICP-Brasil no próprio domínio: <https://ajuda.clicksign.com/widget-embedded-com-certificado-digital>
- Clicksign, disponibilidade e contratação do Widget Embedded: <https://ajuda.clicksign.com/article/694-widget-embedded>
- Clicksign, plano Avançado: <https://www.clicksign.com/plano-avancado>
- Autentique, visão geral da API: <https://docs.autentique.com.br/api/master.md>
- Autentique, criação de documento: <https://docs.autentique.com.br/api/mutations/criando-um-documento.md>
- Autentique, webhooks: <https://docs.autentique.com.br/api/integration-basics/webhooks.md>
- Autentique, planos e preços: <https://ajuda.autentique.com.br/pt-BR/articles/2973249-planos>
- Autentique, preços de API em BRL: <https://docs.autentique.com.br/api/2/precos-para-uso-via-api>
- Autentique, iframe Enterprise para membro de organização: <https://docs.autentique.com.br/api/corporate/mutations/integrando-com-iframe>

Há uma inconsistência entre páginas públicas da Autentique sobre a franquia gratuita (10 versus 20 documentos em materiais consultados). A franquia não deve entrar no cálculo até confirmação contratual.

## Como calcular TCO sem inventar preço

Cada escritório cadastra uma versão imutável de preço com URL de origem, data de vigência e data de observação. O relatório recebe volumes por métrica e aplica um dos modelos:

- `base_plus_usage`: mensalidade + itens excedentes;
- `commitment_floor`: maior valor entre compromisso mínimo e consumo calculado.

Eventos reais (`document_created`, `signature_request_email`, `document_query`, `webhook_received`) são persistidos com chave idempotente. O valor não é derivado de preço hard-coded. Campos como implantação, Widget Premium, White Label, biometria, certificado, suporte, retenção e SLA continuam como **cotação necessária**.

## Segurança da assinatura com token/certificado do advogado

É possível oferecer assinatura ICP-Brasil A1/A3 iniciada pelo LexFlow, mas não é aceitável receber ou custodiar o token USB, arquivo PFX, chave privada ou PIN no backend.

Fluxo seguro:

1. o LexFlow preserva e envia o hash/PDF exato ao provedor;
2. o advogado realiza a cerimônia no domínio/widget oficial do provedor, usando Web PKI, extensão ou assinador desktop quando A3 exigir acesso ao hardware;
3. o provedor confirma por webhook autenticado;
4. o LexFlow baixa o PDF final, valida tipo/tamanho, faz varredura, grava SHA-256 e o mantém imutável.

A Clicksign confirma publicamente a assinatura ICP-Brasil dentro do domínio com Widget Embedded Premium. Ainda assim, ela só pode ser ativada depois de contratar o plano elegível e o adicional, cadastrar o domínio e homologar a modalidade ICP-Brasil no navegador/SO alvo. Em iPhone/iPad, tokens USB A3 e middleware podem não ser suportados; assinatura remota ICP-Brasil em nuvem depende do certificado e do provedor do usuário. O iframe Autentique documentado não deve ser tratado como substituto comprovado dessa jornada.

## Calendário bidirecional

- OAuth Authorization Code com PKCE S256, `state` de uso único, callback autenticado e refresh token cifrado por usuário/tenant.
- Google: escopos `calendar.calendarlist.readonly` e `calendar.events.owned`, cursor `nextSyncToken`, recuperação de `410 Gone` e canal `events.watch` renovável.
- Microsoft: `offline_access User.Read Calendars.ReadWrite`, `calendarView/delta` com janela fixa e `@odata.deltaLink`, além de subscription com `clientState` renovável.
- Somente tarefas que o usuário selecionar explicitamente recebem vínculo externo. O delta da agenda escolhida é lido sob consentimento, mas eventos sem identificador previamente vinculado são descartados em memória e nunca viram tarefas nem são persistidos no LexFlow.
- `etag`/`If-Match`, hash local/remoto e tombstones evitam sobrescrita cega. Se os dois lados mudarem, ou se houver exclusão externa, cria-se conflito para decisão humana.
- Webhook apenas aciona reconciliação incremental; uma rotina periódica cobre notificações perdidas e renova subscriptions.

Fontes oficiais de calendário:

- Google OAuth web-server: <https://developers.google.com/identity/protocols/oauth2/web-server>
- Google sincronização incremental: <https://developers.google.com/workspace/calendar/api/guides/sync>
- Google push notifications: <https://developers.google.com/workspace/calendar/api/guides/push>
- Microsoft OAuth com PKCE: <https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow>
- Microsoft delta de eventos: <https://learn.microsoft.com/en-us/graph/delta-query-events>
- Microsoft subscriptions: <https://learn.microsoft.com/en-us/graph/api/resources/subscription>

## Portões antes de produção

1. Obter proposta escrita da Clicksign para plano Avançado + Widget Embedded Premium e confirmar custo/compatibilidade de certificado digital no fluxo desejado.
2. Confirmar com Autentique a tabela vigente, compromisso mínimo, limites, retenção, suporte e preço do iframe/white-label corporativo; resolver a divergência da franquia gratuita.
3. Homologar A1, A3 USB e certificado remoto nos navegadores/SOs realmente usados pelo escritório.
4. Testar webhook duplicado, fora de ordem e atrasado; download final; hash imutável; revogação de credencial; e isolamento entre tenants.
5. Verificar políticas/termos Google e Microsoft, tela de consentimento e URLs HTTPS públicas antes de ativar OAuth/webhooks.
