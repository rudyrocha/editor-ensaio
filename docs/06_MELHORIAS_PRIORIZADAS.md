# Auditoria técnica e backlog priorizado

**Base:** leitura estática de `ensaio.py`/`revisao_web.py` v3.1.3. Não são falhas reproduzidas, salvo o histórico relatado pelo usuário. Prioridade mede impacto na preservação de funcionalidades e dados.

## P0 — proteção contra perda/inconsistência

**P0.1 Finalização transacional (risco inferido).** `command_finalize()` grava saídas em `output`, importa referências e só então move brutos. Se falhar em qualquer etapa intermediária, pode ficar vídeo final existente, referência atualizada e brutos na entrada. `incorporate_selected_references()` grava arquivos de áudio e só ao final escreve os CSVs; falhas no meio podem deixar órfãos. **Proposta:** preparar outputs sob pasta temporária, validar tudo, preparar referências em staging, verificar destinos, efetivar commits com journal/recovery e escrita atômica de CSV/JSON. Testar falha injetada em cada fronteira. **Aceite:** repetir finalização depois de falha não duplica referências nem sobrescreve output aprovado.

**P0.2 Proteção de revisão existente.** `command_analyze()` faz backup de CSV/manifesto, depois `shutil.rmtree(work_dir)` se já existir para aquela data; se um usuário acionar análise novamente, perde master/intermediários da revisão. **Proposta:** confirmação explícita, workspace novo por execução, não substituir revisão ativa até análise completa, rollback simples.

**P0.3 Gravação atômica e locking de revisão.** `save_review()` faz backup e regrava CSV; dividir/unir também regravam. Subprocessos são bloqueados por `self.lock`, mas mutações de revisão não são todas serializadas. **Proposta:** gravar em temporário e `os.replace`, lock único por ensaio, indicador de geração para impedir alterações com dados desatualizados. Evitar corrupção se fechar navegador ou ocorrer falha de disco.

**P0.4 Consistência dos caminhos.** Migração anterior quebrou a finalização por `manifesto.json` com caminhos absolutos. A rotina `repair_manifest_paths()` resolve o caso conhecido, mas não todos os cenários. **Proposta:** esquema relativo à raiz, `schema_version`, migração compatível e validação de arquivos antes de habilitar finalizar. Não converter caminhos existentes sem backup.

## P1 — previsibilidade e diagnóstico

**P1.1 Persistir feedback no processo de finalização.** O código grava feedback na rotina `AppState.status()`, chamada quando o navegador consulta o status; fechar a aba antes desse polling pode impedir o registro. **Proposta:** gravar feedback no backend no momento confirmado de sucesso, com arquivo idempotente e registro de versão do algoritmo.

**P1.2 Congelar versões de dependências e recursos.** `requirements.txt` usa ranges e o motor depende de FFmpeg do PATH. **Proposta:** arquivo de lock para Windows/Python 3.13, versão FFmpeg registrada em log, testes de compatibilidade e versionamento do schema das assinaturas de referência.

**P1.3 Melhorar salvamento da revisão e consistência UI.** Separar dados de revisão do estado de reprodução, oferecer desfazer/redo para divisão/união e salvamento de progresso. **Proposta:** IDs imutáveis de segmentos, eventos auditáveis e versões de revisão; evitar usar apenas `ordem` para identificar o mesmo segmento após recomposição.

**P1.4 Ampliar verificação final.** `verify_final_files()` confere existência e diferença WAV/MP4, não verifica conteúdos da descrição, hashes dos arquivos, qualidade/áudio decodificável, número de capítulos ou referência não truncada. **Proposta:** `ffprobe` de streams, duração esperada por soma, cobertura de canais, validação dos capítulos e output sob staging.

## P2 — evolução funcional

**P2.1 Teste sistemático de reconhecimento.** Montar corpus de execuções já corrigidas, calcular matriz de confusão e erros por música, calibrar score/margem usando validação temporal por ensaio, em vez de apenas subir limiares por correções.

**P2.2 Reuso das correções de cortes.** Extrair métricas por tipo de erro (inicio antecipado/tardio, final, trecho curto) e validar ajustes do algoritmo numa amostra de ensaios; manter limites atuais até demonstração de ganho.

**P2.3 Navegação por ensaio / histórico real.** Atualmente uma revisão é ativa; criar catálogo de ensaios com estado (`novo`, `em revisão`, `finalizado`), reaproveitamento e seleção sem reanalisar, exigindo migração de esquema.

**P2.4 Interface operacional.** Resumo de identificações com confirmação em lote, indicador de trecho não identificado, comparação de referência, status de saída e opção de exportar descrição/áudio por faixa.

## Ordem sugerida
Primeiro P0.1–P0.4 e suíte de regressão, depois P1.1 e P1.4. Só então ampliar reconhecimento e UX: assim as mudanças futuras não dependem de um fluxo de finalização frágil.