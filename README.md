# Editor de Ensaios — versão 3.3.1

Editor local de áudio de ensaios com reconhecimento de músicas, segmentação/revisão humana, referências e publicação manual no YouTube.

**Documentação técnica:** [`docs/`](docs/). **Versão 3.3.1 (encerramento e instância única):** [`docs/14_ENCERRAMENTO_V3_3_1.md`](docs/14_ENCERRAMENTO_V3_3_1.md). Demais melhorias: [`docs/13_EDITOR_V3_3_0.md`](docs/13_EDITOR_V3_3_0.md).

## Atualização do aplicativo existente

1. **Code → Download ZIP**; extraia em pasta temporária fora de `_sistema`.
2. Clique no botão **Encerrar** dentro do Editor; fechar apenas a aba não encerra o servidor.
3. Execute `atualizar_editor_v3_3_1.bat` a partir da raiz extraída. Ele verifica se ainda existe algum processo do Editor e bloqueia a atualização nesse caso.
4. Abra o Editor pelo atalho e verifique a versão **3.3.1**.
5. Faça um ensaio de homologação antes de excluir os backups de código.

O atualizador preserva o ambiente virtual, os WAV originais, banco de referências, revisões, dados e intermediários existentes. As melhorias não dependem de repetir análise ou reconhecimento já feitos.

## Estrutura

- `app/`: código e scripts de execução local.
- `tests/`: testes automatizados (`python -m unittest discover -s tests -v`).
- `docs/`: arquitetura, regras, compatibilidade e evolução das versões.
- `processadas/` e `referencias/`: **não versionadas** no Git.

Saída de um ensaio novo: **MP4 e TXT de descrição**. Relatório técnico de segmentos permanece em `_sistema/dados/relatorios` para integração e referência.
