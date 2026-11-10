# Resultado da execução inicial dos testes

Data: 2026-11-10. Baseline: v3.1.3 recomposta dos pacotes de distribuição. Ambiente: Python em contêiner Linux (não é o Windows do usuário).

**10/10 testes aprovados**, 0 falhas. Cobertura efetiva: roundtrip CSV, capítulos e qualidade, observações da descrição, reparo/idempotência de manifesto, validação de limites/sobreposição, nome do output.

**Não testados:** FFmpeg/FFprobe, UI/JavaScript/timeline, reconhecimento chroma com áudio real, importação de referências, migração Windows, finalização ponta a ponta. `test_10` só confirma isolamento básico da suíte, não a segurança da finalização.

Os testes não foram executados no computador do usuário e não provam identidade dos bytes instalados; comparar hashes antes de usar esta baseline para alterações.