# Operação, backup, atualização e recuperação

## Instalação existente
- Diretório de execução: `D:\OFFline\Videos\@ensaio\_sistema\app`.
- Ambiente Python próprio: `.venv\Scripts\python.exe` e `pythonw.exe`, documentado na árvore atual com Python 3.13.
- Necessita FFmpeg/FFprobe disponíveis no PATH ou configurados em `config.json`.
- Abertura por atalho do Windows via `Editor de Ensaios.vbs`. Scripts `.bat` legados continuam distribuídos como manutenção/compatibilidade.
- Servidor HTTP em `127.0.0.1`, porta dinâmica próxima a 8765 (conferir URL exibida); apenas acesso local.

## Antes de alterar
1. Encerrar interface e processos de análise/finalização.
2. Copiar/compactar `config.json`, `musicas.json`, `referencias/` (CSV + WAV), `_sistema/revisao/`, `_sistema/dados/aprendizado/`, `brutas/`, `processadas/` e outputs importantes.
3. Registrar hash de `ensaio.py`, `revisao_web.py`, `interface.js`, `config.json` e criar tag Git da versão existente.
4. Não copiar `.venv` entre computadores/versões de Python; recriá-lo via instalador quando necessário.
5. Validar atualização em uma **cópia isolada de `@ensaio`**, com brutos de teste e saída de teste; não apontar scripts de regressão para o ambiente produtivo.

## Operação rotineira
1. Colocar novos WAVs em `brutas` (uma data de ensaio por lote).
2. Abrir Editor; clicar `Iniciar análise` apenas para ensaio novo ou quando se deseja descartar/recriar análise atual.
3. Escutar/confirmar títulos, cortes e qualidade; dividir/unir se necessário; marcar referências só quando a execução é apropriada.
4. Salvar alterações e gerar vídeo; conferir saídas e descrição antes de publicar.
5. Confirmar passagem dos brutos para `processadas/YYYY-MM-DD` se essa opção estiver ativada.
6. Verificar registro em arquivos de aprendizado; não presumir que ocorreu se interface foi fechada precocemente.

## Diagnóstico
- Se não encontra `master.wav`, olhar primeiro `manifesto.json` e `trabalho/<YYMMDD>/master.wav`; não reanalisar automaticamente, pois há risco de perder ajustes e trabalho.
- Se o vídeo não foi gerado, conferir `revisao/finalizacao_web.log` e `revisao/ensaio.log` e validar arquivos finais parcialmente criados.
- Se timeline não navega, testar HTTP byte-range do preview (`206 Partial Content`) e cache de `interface.js`.
- Se o reconhecimento está incorreto, verificar quantidade de referências válidas, scores/margem, alterações de limiar por feedback e versões das assinaturas.
- Se ocorrer falha de arquivamento após geração do MP4, conferir se já houve escrita no banco de referências **antes de repetir finalização**.

## Atualizações
As próximas versões devem ter arquivo de versão único, instruções de rollback, checklist de testes, backup automático de dados e migradores idempotentes (executáveis novamente sem duplicar registros). Não mover ou sobrescrever dados persistentes silenciosamente durante instalação de código.