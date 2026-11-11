# Recuperação das prévias MP3 da revisão atual

**Objetivo:** restaurar a reprodução das prévias do ensaio de 06/11/2026 sem refazer análise, cortes ou identificação musical.

## Diagnóstico

O arquivo `segmentos.csv` enviado pelo usuário tem 35 faixas; o índice `previews_web.json` tem 34 entradas. A divisão da faixa 22 falhou durante a regeneração das prévias após o CSV já ter sido salvo, deixando o índice de áudio inconsistente. Os dados da revisão devem ser preservados.

## Execução no Windows

1. Antes de qualquer ação, copie `segmentos.csv`, `manifesto.json` e `previews_web.json` para uma pasta de backup fora de `_sistema`.
2. Feche completamente a janela do Editor de Ensaios e a aba do navegador. Não reinicie análise.
3. Em `https://github.com/rudyrocha/editor-ensaio`, escolha **Code → Download ZIP** e extraia fora de `_sistema`.
4. Na pasta extraída, copie `app/recuperar_previas.py` e `app/Recuperar previas.bat` para `D:\OFFline\Videos\@ensaio\_sistema\app\`, **sem substituir outros arquivos**.
5. Dê duplo clique em `Recuperar previas.bat`, confirme e observe a mensagem final. A rotina deve gerar 35 prévias com nomes únicos. **Não feche a janela até ver SUCESSO ou ERRO.**
6. Ao ver **SUCESSO**, abra o Editor pelo atalho usual, atualize o navegador com Ctrl+F5 e teste as faixas 21, 22, 23 e 35. As identificações e cortes deverão ser os mesmos.

## Garantias e limites

- `segmentos.csv`, `manifesto.json` e o banco de referências não são editados.
- Todos os MP3 novos são gerados com nomes exclusivos em `_sistema/revisao/previews_web/`.
- `previews_web.json` só é atualizado depois da criação de todos os MP3; antes, os arquivos de controle recebem backup em `_sistema/revisao/historico_recuperacao/<data>/`.
- Em erro do FFmpeg, o índice anterior permanece ativo e o processo pode ser repetido com segurança.
- O procedimento **não** apaga automaticamente MP3 antigos, para evitar bloqueios do Windows; limpeza poderá ser feita depois.
- A rotina foi testada com FFmpeg simulado e dados de teste; precisa ser validada no Windows real.
- Se `master.wav` não existir, interrompe sem iniciar nova análise. Nesse caso, conserve os backups e o log.