# Contrato de compatibilidade e regras de evolução

Estas são **regras recomendadas para próximas versões**, não características integralmente garantidas da v3.1.3.

## Invariantes a preservar
1. Arquivos originais não são alterados nem movidos antes de validação do produto final e autorização do usuário.
2. Nenhuma alteração do app sobrescreve sem backup o banco `referencias/`, `musicas.json`, aprendizado, revisões, brutos ou outputs existentes.
3. A escolha humana de música e qualidade prevalece sobre sugestão automática.
4. O reconhecedor pode sugerir, mas não cria referência automaticamente; só marcação humana explícita pode entrar no banco.
5. Dividir/unir não perde áudio inadvertidamente; alterações estruturais devem ser desfazíveis.
6. Qualquer mudança de diretórios preserva revisão antiga, compatibilidade ou migrador versionado.
7. Timestamps de capítulos e observações têm apresentação estável; observações não quebram capítulos do YouTube.
8. MP4 deve ser compatível, manter logo sem distorção e áudio/chapters sincronizados.
9. Qualquer falha de finalização deixa estado recuperável e idempotente; não duplica referência ao tentar novamente.
10. Sistema de testes jamais usa o diretório de produção como raiz.

## Política de release
- `major.minor.patch`: major para incompatibilidade documentada e migrada; minor para funcionalidade; patch para correção compatível.
- Tag Git e changelog; não criar subpastas de código por versão.
- Alterações de formato de dados exigem `schema_version`, migrador reversível ou backup e testes com fixtures antigas.
- Cada release traz diff de arquivos, riscos, testes executados (e o que ficou pendente), modo de instalar e rollback.
- Aceite do usuário para mudanças que alterem cortes, reconhecimento, referência, movimentação de brutos ou publicação.