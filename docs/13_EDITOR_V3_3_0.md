# Editor de Ensaios v3.3.0 — contrato de atualização

**Data:** 2026-11-11. **Base:** 3.2.1. **Compatibilidade:** mantém `segmentos.csv`, `manifesto.json`, `referencias.csv`, `musicas.json`, arquivos de aprendizado e a pasta `.venv`.

## Alterações

1. **Dividir/unir sem WinError 32** — prévias MP3 com nomes exclusivos para cada geração. Não apaga/substitui prévias abertas pelo player; remoção de arquivos antigos é oportunista, nunca pré-requisito da edição. A estrutura nova só é gravada após gerar todas as prévias. Se geração falhar, índice antigo continua intacto. A interface solta os players antes de operar e os restaura quando há falha.
2. **FFmpeg sem janelas** — cada subprocesso recebe `CREATE_NO_WINDOW` e, no Windows, `STARTUPINFO` oculto; FFmpeg recebe `-nostdin`, além de `stdin=DEVNULL`. Processos Python iniciados pela interface também ficam ocultos. Caso as janelas persistam, verificar se servidor antigo continua ativo na porta local e reiniciar o Editor completamente.
3. **Qualidade opcional** — opção *Não avaliar*; ausências permitidas no navegador, API e leitor CSV. Qualidades anteriores continuam preservadas.
4. **Comentários na mesma linha** — o capítulo do YouTube reúne título, qualidade (quando informada), observações e duração. Ex.: `00:00 Boa Viagem — erro no refrão (3m10)`. A observação continua separada no CSV, para não poluir o banco de reconhecimento musical.
5. **Três sugestões de música** — alternativas distintas ranqueadas com percentual de similaridade; seleção única por radio, sincronizada com dropdown e entrada de outra música. Acrescenta campos **opcionais** `terceira_opcao` e `score_terceira_opcao` ao CSV, mantendo leitura de revisões antigas.
6. **Alertas na faixa** — quando a validação identifica `faixa N`, o erro aparece no topo daquele cartão e a rolagem vai até ele. Erros globais continuam no topo da página.
7. **Saída simplificada** — gera somente `Ensaio.AA.MM.DD.mp4` e `Ensaio.AA.MM.DD.descricao.txt` em `output`. O WAV de edição permanece exclusivamente em `processadas/AAAA-MM-DD/temporarios` durante a finalização e é descartado após validação. O arquivo de capítulos separado deixa de ser criado. O CSV técnico passa a `_sistema/dados/relatorios`, conservando a função avançada de incorporar referências de ensaios antigos. Relatórios legados em `output` continuam legíveis.
8. **Cortes extensos** — retira o limite arbitrário de 120 segundos, mantendo validações por início/fim, gravação mestre e sobreposições.

## Regras de segurança

- Atualizador substitui apenas `app/ensaio.py`, `app/revisao_web.py`, `app/interface.js`, `app/interface.css`. Faz backup do código. Não move, exclui ou sobrescreve arquivos de usuário.
- Qualquer falha na geração das prévias **não deve salvar uma divisão nova**; as alterações de campos que já foram salvas via API permanecem.
- Durante finalização, o MP4 e descrição só são aceitos após validação de duração de áudio e vídeo.
- A rotina automática não verifica o upload para YouTube; **o usuário** decide quando apagar os WAVs originais guardados em `processadas`.
- Arquivos de resultados de versões antigas **não são apagados** automaticamente pela atualização.

## Testes

`python -m unittest discover -s tests -v` — sem dados reais nem alterações na instalação de produção. Foi testada também geração curta de prévias e MP4 com FFmpeg em Linux. Ainda requer ensaio de homologação no Windows.

## Instalação

Acesse o repositório e use **Code → Download ZIP**. Extraia fora de `_sistema`, feche completamente o Editor, rode `atualizar_editor_v3_3_0.bat`, verifique `3.3.0` na página e force atualização do navegador com `Ctrl+F5`. Mantenha as cópias de segurança até validar um ensaio inteiro.
