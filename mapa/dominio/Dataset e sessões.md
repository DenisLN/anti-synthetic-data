---
tipo: dominio
tags: [dominio]
---
# Dataset e sessões
- Cada `run` cria `resultados/sessao_<ts>/` nova: `sessao.json`, `NN_classe.npz` (formato 2, um por classe com `<perfil>/medida|modelo|programada`), `snr_XXdb/`, `metadata/*.jsonl`, `corrente/` (opcional).
- Formato 1 (um `.npz` por captura) ainda legível; leitura única em [[mapa/codigo/sessao_io|sessao_io]]; sessão interrompida: `recuperar_parcial` ([[P-13]]).
- Pós-processo offline: [[mapa/codigo/recortar_margem|recortar_margem]], [[mapa/codigo/analisar_sessao|analisar_sessao]], [[mapa/codigo/relatorio_html|relatorio_html]], [[mapa/codigo/bruto_osciloscopio_io|bruto_osciloscopio_io]].
- Docs: [[docs/dataset|dataset]], [[docs/metadata|metadata]], [[docs/tres_versoes|três versões]], [[docs/medicao|medição]]. Classes: [[mapa/dominio/Classes|Classes]].
