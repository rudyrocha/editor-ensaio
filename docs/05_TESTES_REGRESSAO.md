# Testes de regressão e homologação

## Níveis
- **Unitários:** funções sem FFmpeg, arquivos em diretórios temporários.
- **Integração:** uso de FFmpeg e áudio sintético temporário em raiz isolada.
- **Interface:** navegador real (Chrome/Edge) com timeline, salvar, divisão/união e status.
- **Ponta a ponta:** ensaio pequeno com vídeos, arquivos e eventual movimentação de brutos **em cópia de teste**.

## Matriz de cenários indispensáveis

| ID | Cenário | Resultado esperado | Status inicial |
|---|---|---|---|
| T01 | CSV de revisão, UTF-8 BOM e decimal vírgula | Lê, grava e relê sem perda | Automatizado neste pacote |
| T02 | Capítulos, qualidade e tempo | Formato e duração corretos | Automatizado neste pacote |
| T03 | Observações na descrição | Capítulos contínuos; seção separada | Automatizado neste pacote |
| T04 | Manifesto pré-migração | Corrige master/brutos preservados | Automatizado neste pacote |
| T05 | Validação de sobreposição | Recusa faixas selecionadas conflitantes | Automatizado neste pacote |
| T06 | Hash repetido de referência com título divergente | Impede alteração silenciosa do cadastro | Integração pendente |
| T07 | Dividir e unir | Persistência de limites/título/qualidade/observação | Teste de UI pendente |
| T08 | Timeline, seek, início e últimos 10s | Busca livre/sem +20s ou -20s e pausa exclusividade | Teste de UI pendente |
| T09 | Reconhecimento e correção | Sugestão correta não sobrepõe humano; feedback é registrado | Integração pendente |
| T10 | Finalização com referência aprovada | Saídas válidas e incorporação uma única vez | Ponta a ponta pendente |
| T11 | Falha simulada após WAV/MP4 | Brutos e referência não ficam em estado inconsistente | Pendente; risco identificado |
| T12 | Reabrir revisão antiga e após reinicialização | Nenhum ajuste perdido | Integração pendente |
| T13 | Análise com master preexistente | Solicita confirmação ou mantém backup recuperável | Pendente; risco identificado |
| T14 | Atualização de versão | App instalado, `.venv` e dados preservados | Integração Windows pendente |
| T15 | Dois botões/operações simultâneas | Estado não corrompido | Integração pendente |

## Execução da suíte incluída
Na cópia do código-fonte v3.1.3 (sem qualquer WAV real), usar:
```powershell
cd C:\caminho\para\copia_do_projeto
py -3.13 -m unittest discover -s tests -p 'test_*.py' -v
```
O pacote fornece os testes e a documentação, **não instala nem modifica a v3.1.3**. Eles detectam o `ensaio.py` com `ENSAIO_SOURCE_DIR`; alternativamente coloque a pasta `tests/` ao lado de `ensaio.py` na cópia de testes. Os testes não dependem de FFmpeg.

## Critério mínimo por release
Todos os testes unitários aprovados; integração com arquivos temporários aprovada; checklist manual completo; backup/rollback testados; nenhuma alteração no banco real; relatório de release assinado com versão e resultado. Novas funcionalidades entram com testes novos antes de substituir a implementação.