# Editor de Ensaios — Diógenes

**Versão do aplicativo: 3.2.1.** Projeto local Windows, com interface web para revisar gravações de ensaio, identificar músicas por referências, editar segmentos e gerar vídeo MP4.

## Correções da 3.2.1

- FFmpeg e FFprobe não abrem janelas de console no Windows nem recebem comandos pelo teclado.
- Uma análise interrompida pode ser reiniciada com confirmação, preservando os intermediários antigos em `temporarios_interrompidos_*` e o histórico de revisão.
- Atualizador incremental: execute `atualizar_editor_v3_2_1.bat` no ZIP completo, sem remover a instalação atual.

Veja [detalhes das correções](docs/11_FFMPEG_E_RECUPERACAO_V3_2_1.md).

## Atualização 3.2.0 (base)

A versão 3.2.1 mantém as funções musicais da v3.1.3 e reorganiza os derivados de processamento em `processadas/AAAA-MM-DD/temporarios/`. Depois de uma finalização validada, remove somente essa pasta de intermediários. Mantém os WAVs originais em `processadas/AAAA-MM-DD/` (se a opção **Mover brutos** estiver ativa), os arquivos finais em `output/` e as referências em `referencias/`.

O editor **não envia vídeos ao YouTube nem verifica a publicação**; remova originais/finais manualmente depois de confirmar a publicação.

Veja [as regras, garantias e limitações](docs/10_CICLO_ARQUIVOS_V3_2_0.md).

## Histórico — instalação inicial da v3.2.0 sobre a v3.1.3

1. Feche o Editor.
2. No GitHub, clique em **Code > Download ZIP** e extraia em uma pasta temporária fora de `D:\OFFline\Videos\@ensaio`.
3. Execute `atualizar_editor_v3_2_0.bat` na raiz extraída.
4. Confirme a criação do backup; os dados e `.venv` da instalação existente não são apagados.
5. Abra o atalho habitual do Editor. Faça uma análise de um novo ensaio, revise e gere um vídeo; confira o MP4 e a pasta temporária.

**Não execute um migrador de versões antigas.** O atualizador é destinado a instalações da v3.1.3 na estrutura nova.

## Estrutura do repositório

- `app/`: código executável, interface web, scripts Windows e configuração.
- `tests/`: testes automatizados não destrutivos (somente pastas temporárias).
- `docs/`: arquitetura, contratos, manutenções, testes e histórico de mudanças.
- `.github/workflows/`: validação de testes no GitHub Actions.

Arquivos de áudio e vídeo, referências, dados pessoais do ensaio, `.venv` e revisões locais **não são versionados**.

## Testes

```shell
python -m unittest discover -s tests -v
```

A execução dos testes não usa arquivos de áudio reais. A geração de vídeo com FFmpeg precisa ser homologada na máquina Windows.
