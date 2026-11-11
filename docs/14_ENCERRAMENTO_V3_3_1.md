# Editor de Ensaios 3.3.1 — encerramento e instância única

## Problema observado
Fechar a aba do navegador não encerra o servidor local. O lançador podia iniciar um novo Python ao encontrar outra instância usando uma porta diferente, porque o servidor tentava várias portas consecutivas. O usuário confirmou dois processos Python em execução e um servidor antigo exibindo a versão 3.2.1 após instalar a 3.3.0.

## Correções
- O servidor utiliza somente a porta solicitada (8765 por padrão). Se já existir Editor nessa porta, reutiliza a página; se estiver ocupada por outro serviço, não abre porta alternativa.
- A saída por **Encerrar** usa o desligamento HTTP, libera o socket em um bloco `finally` e não deixa sair enquanto análise ou finalização estiver em andamento.
- O atualizador usa `verificar_editor_fechado.ps1` para procurar processos `pythonw.exe` ou `python.exe` cuja linha de comando contenha o caminho exato de `revisao_web.py`. Não substitui código quando algum processo estiver aberto.
- A verificação impede a atualização quando não consegue consultar processos; não considera silêncio uma confirmação.
- Não é necessário fechar manualmente um navegador inteiro: use o botão **Encerrar** e depois feche a aba.

## Limitações e validação
O Windows permite que versões anteriores do serviço tenham ficado abertas em portas alternativas. Elas devem ser encerradas uma única vez antes da instalação. A versão 3.3.1 impede que isso volte a ocorrer por abertura de portas adicionais.

Teste no Windows: abrir o Editor, clicar novamente no atalho, confirmar que há apenas um processo `revisao_web.py`; usar **Encerrar**; confirmar que o processo desaparece; executar o atualizador; abrir e conferir versão 3.3.1.

Os dados `brutas/`, `processadas/`, `referencias/`, `output/`, `_sistema/revisao` e `_sistema/dados` não são alterados.
