# Fluxos e regras de negócio

## Entrada e análise
- Entrada padrão: `@ensaio/brutas`, WAV (extensões `.wav`, `.wave`). Arquivos são descobertos e ordenados com base no nome/data `YYMMDD`; regras completas em `discover_raw_files()`.
- Criação de `trabalho/<YYMMDD>/master.wav` por normalização e concatenação.
- Análise adaptativa de volume: janela configurável (`analysis_frame_seconds=0.5` no `config.json` distribuído), limiares `min_threshold_db=-42`, `max_threshold_db=-18`, confirmação de atividade sustentada e histerese; detalhes matemáticos nas funções `adaptive_volume_threshold`, `detect_music_regions_hysteresis` e `analyze_loudness`.
- `pre_roll_seconds=5`: intenção de preservar cinco segundos antes do início musical; `min_music_seconds=60`: tentativas curtas não são incluídas automaticamente. Ambas são parâmetros configuráveis, não uma garantia de detecção perfeita.
- A cada análise, o trabalho do mesmo `date_code` pode ser excluído e recriado (`shutil.rmtree(work_dir)`). Isso exige confirmação e backup antes de reanalisar ensaio em andamento.

## Reconhecimento musical
- Usa assinaturas **chroma** calculadas sobre janelas, com comparação de sequências; armazenamento de assinaturas em cache interno de referências.
- Score é **similaridade**, não probabilidade calibrada.
- Valores configurados: `recognition_auto_score=0.72`, `recognition_auto_margin=0.06`, janela de 24 segundos, até 3 janelas por faixa, amostras a 12 kHz.
- Preenche automaticamente o título se o nome estiver vazio, o score atingir o limite e a diferença para a segunda opção atingir o limite.
- `Identificar músicas novamente` atualiza sugestões com a análise existente; não deve sobrescrever título já preenchido.
- O aprendizado atual **não treina um novo classificador**: ele pode aumentar conservadoramente os limiares de preenchimento automático usando correções históricas. As referências aprovadas ampliam o conjunto de exemplos de reconhecimento.

## Revisão humana
- Uma faixa tem número de ordem, limites brutos, limites sugeridos, ajustes manuais, limites efetivos, título, qualidade, inclusão, observação, marcação de referência e sugestão de reconhecimento.
- Ajuste de início positivo corta mais o começo; ajuste de fim positivo corta mais o fim. Ajustes negativos acrescentam áudio, respeitados limites do master.
- A interface valida ajuste absoluto de até 120 segundos, e duração final mínima de 1 segundo.
- `Dividir no ponto atual`: cria duas faixas; conserva identificação/qualidade na primeira, limpa identificação/qualidade da segunda; backups em `historico_estrutura`; gera novas prévias.
- `Unir com a próxima`: inclui o intervalo entre os limites existentes, reúne observações e preserva título apenas quando não há conflito relevante; desmarca o uso como referência exceto quando os títulos coincidem.
- O player oferece timeline, início ajustado, últimos dez segundos e reprodução exclusiva de uma faixa; isso exige regressão manual em navegador real.

## Finalização
- Lê/recupera manifesto, verifica brutos e master e lê somente faixas incluídas com título/qualidade preenchidos.
- Extrai trechos em WAV, concatena, renderiza vídeo com imagem estática 1920×1080, 1 fps, H.264 e áudio AAC (conforme configuração).
- Gera `Ensaio.AA.MM.DD.wav`, `.mp4`, `.capitulos.txt`, `.descricao.txt`, `.segmentos.csv`.
- Capítulos: `00:00 Título, qualidade (2m35)`; descrição: capítulos seguidos de `Observações:` com notas por faixa. As notas não entram nos timestamps.
- Verifica existência e tamanho dos arquivos finais e diferença de duração WAV/MP4 dentro de tolerância aproximada de dois segundos.
- Depois da verificação, incorpora somente referências marcadas manualmente; aplica hash SHA-256 para evitar duplicados e bloqueia duplicado com nome de música divergente.
- Por fim move brutos para `processadas/YYYY-MM-DD`, salvo opção `--nao-mover`/flag de interface; movimentação tenta rollback caso falhe.
- **Importante:** o log de aprendizado só é apensado em `AppState.status()` após o término bem-sucedido da finalização. Se o serviço/página fechar antes do polling, o registro pode não ocorrer.