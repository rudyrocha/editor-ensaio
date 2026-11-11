# Versão 3.2.1 — FFmpeg sem console e recuperação de análises interrompidas

## Problemas observados
- FFmpeg/FFprobe abriam janelas do Windows e podiam capturar acidentalmente teclas digitadas pelo usuário, interrompendo o processo.
- Uma análise interrompida deixava `processadas/AAAA-MM-DD/temporarios` com arquivos parciais; a proteção introduzida na v3.2.0 impedia iniciar novamente.

## Correções
1. `ensaio.run_command()` utiliza `stdin=DEVNULL` e `creationflags=CREATE_NO_WINDOW` quando disponíveis; não abre console nem permite comandos interativos ao FFmpeg. Os erros do FFmpeg continuam disponíveis para diagnóstico via `stderr=PIPE`.
2. O processo Python de análise/finalização iniciado pelo servidor web também é aberto sem console e com `stdin=DEVNULL`, mas mantém a gravação normal de logs.
3. A tela inicial identifica a presença de temporários de uma análise anterior para a mesma data dos WAVs em `brutas`. Ao clicar **Iniciar análise**, o usuário confirma se deseja recomeçar.
4. A confirmação fornece `--recomecar` ao comando. O diretório `temporarios` anterior é **renomeado**, sem apagar, para `temporarios_interrompidos_YYYYMMDD_HHMMSS_microssegundos`. Uma nova pasta `temporarios` é criada para a análise atual.
5. A revisão CSV e o manifesto anteriores seguem sendo copiados para `_sistema/revisao/historico` antes de nova análise.
6. Se não houver confirmação, arquivos temporários existentes continuam protegidos; o comando recusa a execução como antes.

## Ações após a conclusão
- Se o ensaio for analisado e finalizado com sucesso e o vídeo estiver correto em `output`, o usuário pode eliminar manualmente as pastas `temporarios_interrompidos_*` do ensaio. Elas **não** são limpas automaticamente para evitar perder dados numa tentativa de recuperação.
- WAVs originais em `brutas`, `processadas` e banco de `referencias` não são afetados.

## Instalação
Fechar Editor, obter ZIP do GitHub e executar `atualizar_editor_v3_2_1.bat`. Atualiza somente `ensaio.py`, `revisao_web.py` e `interface.js`, criando cópias anteriores em `_sistema/logs/backup_app_antes_v3_2_1_*`.

## Limitações
- Não existe bloqueio interprocessos entre instâncias independentes do editor. Não utilizar dois editores simultaneamente nem reiniciar uma análise enquanto ela ainda estiver em execução em outra instância.
- Testes unitários validaram 13 casos em ambiente isolado; ainda se recomenda a confirmação com FFmpeg real em Windows.
