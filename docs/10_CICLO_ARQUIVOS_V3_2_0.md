# v3.2.0 — Gerenciamento de arquivos por ensaio

## Objetivo

Eliminar o crescimento da antiga `_sistema/trabalho` sem excluir os WAVs originais antes de decisão humana. O acervo definitivo continua no YouTube, publicado manualmente pelo usuário; o editor **não confirma o upload**.

## Pastas

| Local | Natureza | Retenção |
|---|---|---|
| `brutas/*.wav` | Originais ainda pendentes | Até finalização validada e opção de mover |
| `processadas/AAAA-MM-DD/*.wav` | Originais após processar | Exclusão **manual** depois de conferir o YouTube |
| `processadas/AAAA-MM-DD/temporarios/*` | Derivados (normalizados, master, partes finais, áudio intermediário) | Automática **somente após** validação e incorporação de referências |
| `output/*` | MP4/WAV/descrição/capítulos/CSV | Exclusão manual após conferência da publicação |
| `referencias/*` | Trechos de referência e índices | Permanente; nunca excluir automaticamente |
| `_sistema/revisao/*` | Revisão ativa e prévias MP3 | Persistente (arquivos menores), sem alterações nesta versão |

## Garantias implementadas

1. Toda análise de ensaio grava intermediários em `processadas/AAAA-MM-DD/temporarios/`.
2. O programa recusa sobrescrever automaticamente uma pasta temporária não vazia. Isso evita destruir uma revisão em andamento; caso um ensaio falhe durante a análise, a resolução é explícita.
3. Finalização só limpa temporários **depois de**: criar WAV/MP4 e auxiliares, validar duração, incorporar referências marcadas, mover originais quando solicitado.
4. Finalização com erro mantém temporários e brutos; erro ao limpar temporários após sucesso é apenas registrado, preservando o vídeo.
5. Operação `--nao-mover`: brutos continuam em `brutas`; se precisar reconstruir o master, o editor procura os arquivos desse ensaio também em `brutas`.
6. Limpeza verifica que a pasta é subdiretório de `processadas` e se chama `temporarios`; não segue links simbólicos.
7. Nenhuma limpeza retroativa de pastas antigas ou outros ensaios nesta versão.

## Limitações conhecidas e testes de homologação

- A revisão ativa e suas prévias continuam em `_sistema/revisao` para não quebrar a interface. Não são os WAVs de 40 GB acumulados anteriormente.
- A finalização já existente substitui arquivos de saída com o mesmo nome. Proteger outputs de substituição acidental continua como melhoria futura.
- Ainda é necessária **homologação com gravações reais no Windows**, FFmpeg e a interface web: analisar, identificar música, editar segmento, gerar vídeo, verificar arquivo final, conferir brutos e pasta temporária.
- Não rodar uma nova análise no mesmo dia caso a pasta temporária contenha um trabalho interrompido: preservar para análise/limpeza controlada.

## Instalação

Na raiz do projeto, execute `atualizar_editor_v3_2_0.bat` com o editor fechado. Faz backup dos arquivos de código em `_sistema/logs/backup_app_antes_v3_2_0_...` e substitui somente os arquivos da pasta `app`; preserva `.venv`, dados, referências, revisão e outputs.

## Testes automatizados

```bash
python -m unittest discover -s tests -v
```

Os testes são executados em diretórios temporários. O GitHub Actions usa Windows/Python 3.13.
