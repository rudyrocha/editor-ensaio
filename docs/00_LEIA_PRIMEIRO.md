# Editor de Ensaios — documentação de referência

**Baseline auditada:** v3.1.3 (código do pacote de migração v3.1.2, com `ensaio.py`, `revisao_web.py`, `config.json` e `README.md` sobrepostos pelos arquivos da atualização v3.1.3). **Data da auditoria:** 2026-11-10.

## Escopo e evidências
Esta documentação é derivada da leitura estática dos fontes disponíveis nos pacotes emitidos nesta conversa e da árvore de diretórios enviada após a migração. Não houve acesso direto ao disco `D:` nem à gravação WAV do ensaio, ao catálogo CSV real ou à instância do editor em execução. Não houve execução Windows/FFmpeg nem teste ponta a ponta. Os testes incluídos são **uma proposta executável**, e devem rodar primeiro em cópia isolada do código, sem alterar dados do usuário.

A árvore enviada confirma o armazenamento dos dois WAV brutos de 2026-10-01, as 14 pastas de músicas `M0001`–`M0014`, a instalação em `_sistema/app`, o novo `.venv` Python 3.13, a revisão e o master de `261001`. A captura do editor mostrava 30 referências ativas, 15 músicas cadastradas e 22 segmentos detectados. Esses são dados de um momento específico, não uma garantia de estado atual.

## Conteúdo
- `01_ARQUITETURA.md`: componentes, limites, dependências, processamento.
- `02_FLUXOS_REGRAS.md`: regras funcionais e comportamento esperado.
- `03_MODELO_DE_DADOS.md`: arquivos persistentes, campos e evolução.
- `04_OPERACAO_MANUTENCAO.md`: instalação, backup, atualização e diagnóstico.
- `05_TESTES_REGRESSAO.md`: matriz e roteiro de homologação.
- `06_MELHORIAS_PRIORIZADAS.md`: riscos técnicos, prioridades e critérios de aceite.
- `07_CONTRATO_DE_COMPATIBILIDADE.md`: invariantes e política de versionamento.
- `../tests/test_regressao.py`: testes automatizados não destrutivos para funções puras/arquivo temporário.
- `../modelos/RELATORIO_DE_RELEASE.md`: checklist preenchível por versão.

## Como usar sem interferir no sistema
1. Salvar o conteúdo documental em `D:\OFFline\Videos\@ensaio\_sistema\docs`.
2. Não substituir **nenhum** arquivo da instalação v3.1.3 por este pacote.
3. Antes de cada mudança: tag Git, cópia de segurança dos dados, teste automatizado, teste ponta a ponta em sandbox e aceite explícito de novos comportamentos.
4. Atualizar a documentação e o relatório de release junto com cada versão.

## Classificação de afirmações
- **Confirmado no código:** existe uma rotina ou regra identificável no fonte v3.1.3.
- **Confirmado na árvore:** aparece na listagem disponibilizada pelo usuário.
- **Risco inferido:** falha plausível decorrente da implementação, ainda não reproduzida.
- **A validar:** requer execução em Windows/dados reais.