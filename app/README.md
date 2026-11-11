# Editor de Ensaios — v3.3.0

Editor local para gravações de ensaios. Esta versão corrige a geração de prévias e aprimora a revisão, reconhecimento e exportação dos ensaios.

## Pastas e ciclo de vida

- `brutas/`: WAVs originais pendentes de análise.
- `processadas/AAAA-MM-DD/temporarios/`: normalizações, `master.wav`, cortes e áudio intermediário. **Excluídos após a finalização bem-sucedida**.
- `processadas/AAAA-MM-DD/*.wav`: WAVs originais, movidos apenas se a opção de mover estiver ativa e a finalização for validada. **Nunca são excluídos automaticamente.**
- `output/`: MP4 e TXT de descrição. O CSV técnico de segmentos fica em `_sistema/dados/relatorios/`.
- `referencias/`: base de reconhecimento e índices, protegida de toda limpeza automática.
- `_sistema/revisao/`: a revisão ativa e prévias MP3; permanece acessível após finalizar. `_sistema/dados/` guarda aprendizado.

**A publicação no YouTube é manual.** O editor não consegue verificar se o upload foi realizado. Só apague os originais de `processadas` e os resultados de `output` após conferir a publicação e eventuais necessidades de recuperação.

## Fluxo

1. Copie os WAVs para `brutas/`.
2. Abra o atalho **Editor de Ensaios**.
3. Analise o ensaio e revise nomes, cortes, observações e referências.
4. Clique em **Salvar e gerar vídeo**.
5. O sistema só elimina os intermediários após verificar os arquivos finais, incorporar as referências escolhidas e arquivar os originais quando solicitado.
6. Publique o MP4 no YouTube; se necessário, exclua manualmente os originais em `processadas/AAAA-MM-DD` e os arquivos finais em `output/`.

Se a geração falhar, a pasta `temporarios` permanece intacta. Uma nova análise do mesmo ensaio não apaga os intermediários existentes; o editor exige solução explícita do conflito para preservar a revisão.

## Atualização

Execute o atualizador distribuído com a versão 3.3.0; ele preserva `.venv`, dados, revisões e referências. Em caso de erro, consulte os logs em `_sistema/revisao` e `_sistema/logs`.

## Verificações

Execute `py -3.13 -m unittest discover -s tests -v` na raiz do repositório para os testes de regressão. Os testes unitários não substituem um ensaio completo de homologação com FFmpeg, navegador e confirmação no YouTube.
