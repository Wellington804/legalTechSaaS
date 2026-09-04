# Estúdio de Identidade Documental

Implementação atualizada em 02/09/2026. Acesso em `/dashboard/brand`; a escolha da identidade e da variação fica em **Documentos > Exportar PDF / Word**.

## Experiência

- A entrada é uma galeria de identidades pessoais e do escritório, com miniatura, situação do rascunho e versão publicada.
- O estúdio reúne propriedades estruturadas, documento em tempo real e assistente contextual. No celular, as mesmas áreas ficam nas abas `Editar`, `Visualizar` e `IA`.
- A identidade-base controla cores, fontes e imagens. Petições, contratos, procurações, notificações e correspondências podem sobrescrever margens, cabeçalho, rodapé e paginação.
- Nome, OAB, contatos e endereços vêm do cadastro profissional e do escritório. O usuário escolhe o que exibir e pode substituir um valor somente naquela identidade.
- O rascunho é salvo automaticamente com revisão otimista. Conflitos não sobrescrevem outra sessão.
- A publicação exige ação humana e geração válida do PDF para a identidade-base e todas as variações configuradas.

## Referências e IA

Referências aceitas: DOCX, PDF, PNG e JPEG, até 10 MiB. O servidor valida formato e conteúdo ativo; imagens são normalizadas. Quando o R2 está habilitado, novos binários passam por antivírus e ficam no bucket privado; o PostgreSQL conserva metadados, hash, análise e chave do objeto.

Antes de pedir uma sugestão, o usuário escolhe se a IA deve reproduzir, modernizar ou apenas se inspirar nas referências. Até três propostas recentes permanecem no chat para comparação. A IA só pode devolver tokens estruturados e validados; nunca altera dados profissionais, ativos, HTML/CSS, rascunho ou publicação diretamente. Aplicar uma proposta altera apenas o formulário e aciona o salvamento normal.

Sem provedor de IA, todo o editor manual, referências, prévia, publicação e exportação continuam disponíveis.

## Persistência e segurança

- Migration `20260902_0022`: variações documentais, snapshots profissionais, arquivamento, tipo documental e armazenamento externo de ativos.
- RLS e chaves compostas mantêm o isolamento por escritório. Identidade pessoal é editada pelo titular; identidade do escritório, por administrador ou sócio.
- Arquivar substitui exclusão. Versões publicadas e exportações anteriores continuam imutáveis.
- Cada exportação registra versão do documento, versão da identidade, tipo documental, snapshot aplicado e hashes SHA-256 do PDF e DOCX.
- URLs do R2 são privadas e temporárias; credenciais nunca chegam ao navegador.
- Campos, fontes, cores, medidas e IDs de ativos são validados no servidor. Cores de texto exigem contraste mínimo de 4,5:1 no papel branco.
- O PDF é o artefato visual de referência; o Word permanece editável e pode repaginar caso o dispositivo substitua fontes.

## Fluxo de uso

1. Complete os dados em **Conta e escritório**.
2. Crie ou abra uma identidade.
3. Ajuste a identidade geral e, se necessário, as variações documentais.
4. Anexe referências ou converse com a IA; revise cada diferença antes de aplicar.
5. Gere o PDF real, confirme os dados e publique uma versão.
6. No documento salvo, selecione `Exportar PDF / Word`, a identidade e a variação visual.

Seleção automática: identidade pessoal publicada do responsável pelo processo, depois identidade do escritório. Um documento sem processo usa a identidade do usuário atual ou do escritório. Provas, anexos originais e arquivos assinados nunca são reformatados.

## Configuração da VPS

O backend precisa de LibreOffice Writer e das fontes aprovadas já instaladas pela imagem. R2 é opcional no desenvolvimento e recomendado na VPS. A IA usa o provedor configurado no backend; nenhum segredo é cadastrado pelo advogado.

Após atualizar a imagem, execute `alembic upgrade head` antes de liberar tráfego. O head esperado é `20260902_0022`.

## Verificação desta entrega

- TypeScript e build de produção Next.js aprovados.
- 26 testes focados de Branding/IA/renderização aprovados; 1 teste de PDF multipágina ficou condicionado ao LibreOffice no ambiente do teste Python isolado.
- Testes Node de filtragem segura de referências e PDF privado aprovados.
- Migration aplicada no PostgreSQL local e confirmada em `20260902_0022`.
- Fluxo HTTP autenticado validado no ambiente Docker: criação, salvamento automático, dados profissionais, bloqueio por campo ausente e PDF real.
- Layout sem overflow verificado em 1440 px e 375 px. Provedor de IA real e Cloudflare R2 não foram homologados nesta execução; o ambiente local os informou como indisponíveis.
