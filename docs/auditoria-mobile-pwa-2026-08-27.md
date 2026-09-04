# Mobile, PWA e notificações — 27/08/2026

## Escopo e diagnóstico

Pedido: verificar PWA/push e corrigir a experiência mobile de consulta durante diligências. Não houve implementação de um novo serviço de push, armazenamento offline ou aplicativo nativo.

| Capacidade | Estado encontrado |
| --- | --- |
| Web responsivo | Existente, com falhas de interação corrigidas nesta rodada. |
| PWA configurado | Ausente: sem manifesto/ícones de instalação; `frontend/public/sw.js` já estava removido. O layout cancela registros antigos e remove caches `legaltech`. |
| Web Push | Ausente: sem inscrição por dispositivo, PushManager, VAPID, listener de push ou canal de entrega no backend. |
| E-mail e WhatsApp | Infraestrutura de Resend/Evolution Go existente. Exige configuração/homologação; não equivale a push para o advogado nem comprova lembretes automáticos de prazos. |
| Consulta offline | Não implementada. Arquivos e APIs privados continuam sem novo cache persistente no dispositivo. |

Evidências: `frontend/src/app/layout.tsx`, `frontend/public`, `backend/app/models/notification.py` (canais email/whatsapp), `backend/app/services/notification_providers.py`.

## Correções realizadas

- Menu mobile com diálogo nativo: fundo inerte, nome acessível, fechamento por seleção, Escape e botão, com retorno de foco.
- Controles compartilhados maiores; inputs com 16 px em mobile sem bloquear zoom. Foco visível e espaço inferior para a busca flutuante/safe area.
- Cadastro, importação e editor recolhidos inicialmente no celular; permanecem acessíveis e abertos no desktop. Editar abre o formulário correspondente.
- Registros com ações abaixo dos dados em telas estreitas; quebra de nomes de arquivos, contatos e textos extensos. Removido o `overflow-x-hidden` que poderia mascarar cortes.
- Leitura de texto sem entrar no editor, preservando o arquivo anexado e o fluxo explícito de gravação.
- Busca com consulta direta de contato/documento usando os resultados autorizados do endpoint existente, inclusive registros fora da primeira página da listagem. Resultados antigos não aparecem enquanto a consulta muda.
- Busca com estados de carregamento/vazio, rótulos acessíveis, limite de consulta compatível com o backend e rolagem em viewport reduzida.
- Login com rolagem em telas baixas/teclado virtual e botão de mostrar senha com alvo de toque maior; formulário MFA pode quebrar linha.
- Seleção de área do caso exposta por `aria-pressed`; corrigida chave de renderização dos membros autorizados.

Não foram alteradas permissões, contratos de escrita, banco de dados, cobrança ou envio a provedores. Nenhuma dependência nova.

## Validação

- TypeScript, build de produção e 6 testes Node existentes.
- `frontend/tests/workspace-ui.cjs`: regressão de contratos da interface, gravação, navegação e onboarding de segurança com fixtures.
- `frontend/tests/mobile-ui.cjs`: 17 rotas em 320, 375, 390, 768 e 1440 px; formulário mobile, consulta, leitura, menu, foco, conteúdos longos e login em 320 × 320.
- Inspeção visual de capturas mobile; o teste de geometria verifica elementos visíveis, não apenas a largura do documento, para detectar conteúdo cortado.
- Fixtures interceptam as APIs; essa cobertura não comprova persistência no PostgreSQL, entrega em provedores ou comportamento em celulares físicos. Altura reduzida aproxima o teclado, não substitui Safari/Android reais. Não constitui certificação WCAG.

Execução contra o frontend Docker local (APIs interceptadas, sem chamar o backend):

```powershell
$env:WORKSPACE_UI_URL = 'http://localhost:3000'
$env:WORKSPACE_UI_API_URL = 'http://localhost:8000'
node tests/workspace-ui.cjs
node tests/mobile-ui.cjs
```

Executar em `frontend`. `PLAYWRIGHT_MODULE` permite apontar para uma instalação existente de Playwright; o fallback é o runtime local do Codex. Para um bundle com API na mesma origem, omitir `WORKSPACE_UI_API_URL`.

## Próximo incremento necessário para uso como aplicativo

1. Instalação: manifesto, ícones, identificação do aplicativo e orientação de instalação em domínio HTTPS. Manter limpeza de caches legados sem cancelar o novo worker indiscriminadamente.
2. Push: inscrição/revogação por usuário e dispositivo, consentimento explícito, chaves do servidor, fila e tratamento de inscrições expiradas. Validar eventos e destinatários antes de aproveitar a fila existente. Não mostrar dados de clientes/processos na tela bloqueada.
3. Disponibilidade: tela de indisponibilidade sem dados privados. Consulta offline de documentos exige decisão própria sobre seleção, proteção, expiração e limpeza no logout; não habilitar cache automático de toda a API.
4. Homologação: Android e iPhone físicos, instalação, renovação de sessão, downloads, câmera/arquivos, teclado, reconexão e push com o aplicativo fechado.

No iOS/iPadOS, o suporte Web Push para aplicativos adicionados à tela inicial existe a partir da versão 16.4 e requer autorização do usuário. Instalação não concede automaticamente permissão de notificações.

O Compose local é restrito ao computador e usa `localhost:8000` no navegador; não deve ser tratado como URL pronta para acessar pelo telefone. O Compose de produção já usa `/api/v1` na mesma origem, atrás de Caddy/HTTPS. Não foram expostas novas portas à rede nesta tarefa.

Referências oficiais: [instalação de PWAs — MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable), [Web Push no iOS/iPadOS — WebKit](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
