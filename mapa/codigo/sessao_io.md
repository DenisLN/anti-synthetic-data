---
tipo: modulo
arquivo: logica/sessao_io.py
camada: persistencia
linhas: 1070
simbolos: [ArquivoDaClasse, gravar_npz, ler_capturas, ler_pasta, recuperar_parcial, BloqueioSessao, MetadadosDaSessao, hash_captura]
pendencias: ["[[P-13]]", "[[P-15]]", "[[P-22]]"]
tags: [codigo]
---
# sessao_io
Leitura e escrita dos `.npz` de uma sessão (formato 2 por classe; formato 1 legado).
- **Faz:** Escrita captura a captura, atômica, via `ArquivoDaClasse`; `consolidar` e espelhos por perfil/SNR.
- Leitura única para todos os consumidores (`ler_capturas`/`ler_pasta`, ambos os formatos).
- Lock de sessão e `recuperar_parcial` após morte abrupta (P-13); benchmark em `scripts/benchmark_sessao_io.py` (P-22).
- **Importa:** nenhum módulo do projeto. **Importado por:** [[mapa/codigo/analisar_sessao|analisar_sessao]], [[mapa/codigo/cli|cli]], [[mapa/codigo/mestre|mestre]], [[mapa/codigo/recortar_margem|recortar_margem]], [[mapa/codigo/relatorio_html|relatorio_html]].
Detalhe: [[docs/codigo/sessao_io|guia completo]]
