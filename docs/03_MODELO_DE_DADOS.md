# Modelo de dados e contrato de arquivos

## Estrutura persistente
```text
@ensaio/
  brutas/                    WAVs novos
  processadas/YYYY-MM-DD/    WAVs arquivados após sucesso
  output/                    MP4, WAV, capítulos, descrição e relatório final
  referencias/
    catalogo_musicas.csv     identidade/catálogo de músicas
    referencias.csv          metadados das execuções, hash, status
    audio/M0001/*.wav       referências reais
  old/                       legado/backup; fora do processo normal
  _sistema/
    app/                     executáveis, fontes, configuração, .venv
    assets/Logo.jpg          imagem do vídeo/editor
    dados/musicas.json       títulos exibidos para seleção
    dados/aprendizado/       registros de revisão e identificação
    revisao/                 análise atual e históricos
    trabalho/YYMMDD/        intermediários de geração
    logs/                    instalação/migração/execução, quando existentes
    docs/                    documentação proposta, ainda não instalada
```

## Arquivos-chave

### `manifesto.json`
Campos confirmados na criação: `app_version`, `data_codigo`, `criado_em`, `arquivos_brutos` (lista), `master`, `duracao_master`. A correção da versão 3.1.3 pode acrescentar `caminhos_reparados_em` e atualizar `app_version`. **Risco:** caminhos absolutos são frágeis ao mover o projeto.

### `segmentos.csv`
Codificação UTF-8 BOM, delimitador `;`, decimais com vírgula. Colunas exatas na v3.1.3:
`ordem`, `incluir`, `titulo`, `qualidade`, `usar_como_referencia`, `inicio_corte_original`, `fim_corte_original`, `ajuste_inicio`, `ajuste_fim`, `inicio_corte`, `fim_corte`, `duracao`, `inicio_bruto`, `fim_bruto`, `classificacao`, `observacao`, `titulo_sugerido`, `score_identificacao`, `segunda_opcao`, `score_segunda_opcao`, `identificacao_aplicada`.

Tipos: `incluir`, `usar_como_referencia`, `identificacao_aplicada` são serializados como `SIM`/`NAO`; tempos e scores como números decimais; `qualidade` utiliza os cinco valores da interface; `titulo_sugerido`, `segunda_opcao` são sugestões do reconhecedor.

### `musicas.json`
Estrutura atual: `{"musicas":["Título", ...]}`. Lista para a interface; pode diferir em tamanho do catálogo de referências (no levantamento havia 15 títulos de interface e 14 IDs no catálogo de áudio). Nomes são deduplicados por normalização de texto.

### Banco de referências
`referencias/catalogo_musicas.csv`: lista de IDs estáveis `M0001` etc. O código lê cabeçalho e preserva colunas como `musica_id` e `titulo_canonico`.
`referencias/referencias.csv`: cada referência contém `referencia_id`, `musica_id`, `titulo`, `data_ensaio`, `ordem`, `arquivo` (relativo à pasta de referências), `inicio_master`, `fim_master`, `duracao`, `sha256`, `ativa`, `criado_em`, `observacao`. Áudio fica em `audio/<musica_id>/*.wav`.

### Aprendizado
`ajustes_cortes.csv` e `ajustes_cortes.jsonl`: limites sugeridos/finais, correções, parâmetros de análise, inclusão e qualidade, apenas após sucesso.
`identificacoes.csv` e `identificacoes.jsonl`: sugestão, score, alternativa, título final, `resultado` (`correta`/`corrigida`), indicadores de inclusão, referência e qualidade. Arquivos podem não existir até haver primeira finalização bem-sucedida com sugestões.

### Histórico e temporários
`revisao/historico/`, `historico_interface/`, `historico_estrutura/`: backups parciais de etapas anteriores. `revisao/previews_web`, `previews`, `previews_inicio` armazenam MP3 regeneráveis. `trabalho/YYMMDD` pode ocupar muitos GB e é recriado na análise da mesma data.

## Compatibilidade de esquemas
- A leitura de CSV oferece alguns campos opcionais e suporte a decimais pt-BR/formatos legados; não significa que **qualquer** arquivo antigo seja válido.
- Nunca renomear colunas, alterar separador ou reordenar IDs de músicas sem migrador de esquema, fixture de amostra e regressão.
- Preferir caminhos relativos à raiz da configuração nos **próximos** esquemas, com versionamento e fallback, sem reescrever a v3.1.3 em uma mudança informal.