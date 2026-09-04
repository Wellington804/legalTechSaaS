# Estúdio de Identidade Documental

Design validado em 02/09/2026 e implementado no Estúdio de Identidade Documental. Este documento preserva as decisões de produto e os limites da solução.

## Entendimento

- O advogado pode construir uma identidade em colaboração com a IA ou começar por referências em PDF, DOCX, PNG ou JPEG.
- Ao receber referências, o LexFlow pergunta se deve reproduzir, modernizar ou apenas usar o material como inspiração.
- A edição combina camadas fixas e validadas (papel, fundo, logo, cabeçalho, linhas, marca-d'água, rodapé e título) para preservar fidelidade entre navegador, Word e PDF. Não há CSS nem elementos arbitrários.
- Referências podem ser aplicadas como fundo fiel ou reconstruídas em camadas editáveis. O corpo jurídico continua nativo e editável no Word.
- Dados profissionais vêm do cadastro do advogado ou do escritório, com escolha do que exibir e ajustes específicos por identidade.
- A prévia no navegador reage imediatamente; um PDF real confirma o resultado antes da publicação.
- A IA funciona em um chat lateral contextual e apresenta diferenças antes de qualquer alteração ser aplicada.
- Uma identidade-base fornece cores, fontes e ativos comuns; variações controlam a composição de petições, contratos, procurações, notificações e correspondências.
- A IA nunca publica automaticamente. Publicações e exportações anteriores permanecem imutáveis.

## Premissas não funcionais

- Alterações devem aparecer na prévia em até 200 ms em um dispositivo comum.
- A geração de uma prévia PDF deve normalmente terminar em até 10 segundos.
- Nenhuma falha da IA, do upload ou do renderizador pode apagar o rascunho válido anterior.
- Identidades, referências, conversas e arquivos permanecem isolados por escritório e pelas permissões pessoais existentes.
- Arquivos só são enviados ao provedor de IA quando o usuário aciona uma análise, com indicação clara das referências incluídas.
- Os tokens aceitos permanecem limitados a fontes instaladas, cores legíveis, medidas seguras e componentes suportados pelo renderizador.
- O desenho deve funcionar no piloto atual e continuar tenant-scoped para adoção posterior por vários escritórios.
- Componentes e validações das variações documentais reutilizam a identidade-base; não devem existir cinco editores independentes.

## Experiência principal

### Galeria

A entrada do módulo mostra cartões com miniatura real, nome, escopo, estado do rascunho e versão publicada. As ações são `Editar`, `Duplicar`, `Visualizar` e `Arquivar`. Uma identidade utilizada em exportações não é apagada.

### Estúdio

No desktop, o estúdio possui três áreas:

```text
[ Estrutura e propriedades ] [ Documento visual ] [ Chat com a IA ]
```

O painel esquerdo organiza controles por partes reconhecíveis: modelo, capa e primeira página, cabeçalho, texto e títulos, rodapé, logotipo, marca-d'água, papel e margens. Medidas técnicas ficam em `Ajustes avançados`.

O centro apresenta o logotipo e a marca-d'água reais, permite alternar entre primeira página e páginas internas e trocar o tipo documental usado na demonstração. Conteúdo fictício é identificado como exemplo.

O painel direito contém a conversa, as referências autorizadas e as propostas pendentes. Selecionar uma parte do documento limita o contexto da IA àquela parte e aos dados permitidos.

No celular, as áreas tornam-se abas de tela inteira: `Editar`, `Visualizar` e `IA`. Salvar permanece acessível; zoom e troca de página não exigem gestos precisos. A folha conserva a cor escolhida, independentemente do tema do aplicativo.

## Identidade-base e variações

`BrandProfile` continua sendo a fonte da identidade-base. As variações armazenam apenas diferenças de composição por tipo documental:

```text
Identidade profissional
├── Petições
├── Contratos
├── Procurações
├── Notificações
└── Correspondências
```

Cores, fontes, ativos e regras comuns são herdados. Capa, cabeçalho da primeira página, rodapé e margens podem ser sobrescritos. Uma variação ausente usa o layout-base.

Campos como nome, OAB, endereço, e-mail e telefone são referências aos dados profissionais, não textos duplicados. A interface permite escolher o que exibir e criar uma substituição específica. Publicações e exportações preservam um snapshot dos valores efetivamente utilizados.

## Fluxo de referências e IA

1. O usuário escolhe começar do zero ou usar referências.
2. O servidor verifica formato, tamanho, malware e conteúdo ativo.
3. O PDF é renderizado no servidor e somente a página escolhida é enviada para análise visual. Cores, fontes, margens, cabeçalhos, rodapés e proporções são extraídos quando possível.
4. Cada resultado recebe o estado `Identificado`, `Estimado` ou `Não reconhecido`.
5. O usuário escolhe reproduzir, modernizar ou usar como inspiração.
6. No modo de reprodução, a IA cria a proposta, compara-a com uma prévia renderizada e executa uma segunda correção controlada.
7. O usuário escolhe uma direção, sobrepõe a referência para comparar e refina pelos controles estruturados.
8. A página inteira pode virar fundo fiel; uma área delimitada pode virar logo ou marca-d'água somente após confirmação humana.

A IA responde com patches validados, nunca com CSS, HTML ou mutação direta do perfil. A interface compara valor atual e proposto e oferece `Aplicar tudo`, `Escolher alterações` e `Descartar`. O backend rejeita campos desconhecidos, fontes não instaladas, ativos de outro perfil, cores sem contraste e medidas fora dos limites.

Arquivos binários ficam no Cloudflare R2; o banco mantém metadados, hash, análise, proprietário, escopo e chave privada do objeto. Registros de auditoria não incluem conteúdo sensível.

## Salvamento, publicação e exportação

Rascunhos usam salvamento automático com revisão otimista. O estado visível pode ser `Salvando`, `Rascunho salvo`, `Alterações não salvas` ou `Conflito de versão`. Uma edição concorrente nunca é sobrescrita silenciosamente.

Antes da publicação, o LexFlow verifica dados profissionais, contraste, resolução dos ativos, legibilidade da marca-d'água, limites de cabeçalho e rodapé, fontes disponíveis e geração do PDF real. Erros impedem a publicação; recomendações podem ser aceitas conscientemente.

A versão publicada contém identidade-base, variações, snapshots profissionais e hashes dos ativos. Documentos escolhem, nesta ordem:

1. Identidade pessoal publicada do responsável.
2. Variação correspondente ao tipo documental.
3. Identidade publicada do escritório.
4. Layout-base quando não houver variação.

A exportação mostra a identidade escolhida e permite troca explícita. PDF e Word usam a mesma estrutura validada. O histórico registra versão documental, identidade, variação, responsável e data sem reescrever artefatos anteriores.

## Falhas e casos-limite

- Falha da IA: mantém editor, referências e último rascunho; permite tentar novamente ou continuar manualmente.
- Falha do PDF: mantém rascunho e bloqueia publicação nova; exportações anteriores continuam acessíveis.
- Fonte ausente: bloqueia a configuração antes de publicar; não substitui silenciosamente.
- Referência inválida ou ativa: rejeita somente aquele arquivo e explica como corrigi-lo.
- Dados profissionais incompletos: destaca o campo e oferece atalho para corrigir o cadastro de origem.
- Conflito de edição: oferece comparar ou recarregar a revisão mais recente.
- Perfil já utilizado: permite arquivar, não apagar o histórico necessário às exportações.
- Resposta inválida da IA: descarta a proposta inteira sem modificar o rascunho.

## Segurança e privacidade

- RLS e verificações de autorização continuam obrigatórias em todas as consultas e mutações.
- Identidade pessoal é editável pelo titular; identidade do escritório segue as permissões administrativas existentes.
- URLs de ativos são privadas e temporárias; chaves do R2 e do provedor não chegam ao navegador.
- Uploads passam pelos mesmos limites, inspeções e quotas da Central de Arquivos.
- O acionamento da IA mostra quais referências serão processadas e registra o evento de forma auditável.
- A IA não inventa dados profissionais nem afirma exclusividade ou titularidade de logotipos gerados.
- Publicação e exportação são ações humanas explícitas.

## Validação

- Testes de contrato para todos os tokens e patches da IA.
- Testes de isolamento entre escritórios, perfis pessoais e identidades compartilhadas.
- Arquivos válidos, maliciosos, ativos, corrompidos e acima dos limites.
- Concorrência em duas sessões e preservação do último rascunho confirmado.
- Seleção automática de identidade e herança das variações.
- Snapshots de Word e PDF para capa, cabeçalho, rodapé, margens, quebras, marca-d'água e paginação.
- Fluxos reais em desktop e 375 px, teclado, leitor de tela e temas claro/escuro.
- Falhas controladas do provedor de IA, R2 e renderizador.

A liberação ocorre primeiro no piloto. Identidades atuais são lidas como identidade-base sem republicação automática; o novo estúdio substitui o editor anterior.

## Não objetivos deste ciclo

- Canvas arbitrário ou substituto do Canva/Figma; as camadas disponíveis são tipadas e limitadas ao timbrado.
- Instalação arbitrária de fontes ou execução de HTML/CSS enviado pelo usuário.
- Vetorização ou reconstrução pixel a pixel de documentos de terceiros. O modo de fundo fiel preserva a página rasterizada autorizada, sem transformar seus elementos em vetores editáveis.
- Assinatura digital, protocolo ou envio automático decorrente da publicação.
- Identificação infalível de fontes em imagens ou garantia de exclusividade de marca.

## Registro de decisões

| Decisão | Alternativas consideradas | Razão |
|---|---|---|
| Camadas fixas + fundo fiel | Canvas livre; somente formulário | Permite alta fidelidade sem HTML/CSS arbitrário e mantém o corpo do Word editável |
| Perguntar a intenção da referência | Reproduzir ou modernizar automaticamente | Evita presumir a intenção do advogado |
| Dados vinculados ao cadastro | Cópia única; preenchimento manual | Reduz repetição e inconsistências |
| Prévia instantânea e PDF real | PDF em toda alteração; PDF somente ao publicar | Equilíbrio entre desempenho e fidelidade |
| Chat lateral contextual | Questionário; fluxo misto | Colaboração contínua durante a edição |
| Identidade-base com variações | Modelo único; identidades independentes | Consistência sem engessar tipos documentais |
| Estúdio em três áreas | Assistente sequencial; editor dentro do documento | Mantém criação, visualização e IA no mesmo contexto |
| Propostas estruturadas | Alteração direta pela IA | Segurança, auditabilidade e revisão humana |
| R2 para binários | Manter referências no PostgreSQL | Evita crescimento desnecessário do banco |
