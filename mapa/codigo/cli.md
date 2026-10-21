---
tipo: modulo
arquivo: logica/cli.py
camada: interface
linhas: 1093
simbolos: [SessaoCLI, HELP_TEXT, parsear_lista_classes, normalizar_lista_classes, cmd_run, confirmar, autorizar_saida]
pendencias: ["[[P-14]]", "[[P-15]]", "[[P-23]]"]
tags: [codigo]
---
# cli
REPL do operador (prompt `bancada>`): do comando `run` à fonte energizada.
- **Faz:** Estima capturas e gravações TRACe, recusa acima de 216 (P-23) e recusa listas ambíguas antes de confirmar (P-14).
- Pede confirmação digitada (case-sensitive), cria pasta de sessão nova e autoriza a saída só durante o comando.
- No fim: recalibração e relatório HTML (padrão 3 capturas/classe/perfil, P-15).
- `run falhas [pasta]` / `rerun <pasta> <id|NN>`: repete só o que está em `falhas.json` (mesma seed/perfil/nível), em sessão nova com `rerun_de`; recusa sem energizar se tensão/frequência/P-09/passo SINE/limites/calibração diferirem.
- **Importa:** [[mapa/codigo/mestre|mestre]], [[mapa/codigo/perfis|perfis]], [[mapa/codigo/preflight_new|preflight_new]], [[mapa/codigo/relatorio_html|relatorio_html]], [[mapa/codigo/sessao_io|sessao_io]]. **Importado por:** nenhum módulo do projeto.
> [!danger] Limites
> - Nenhum comando que energiza a saída roda sem confirmação digitada, case-sensitive.
> - `autorizar_saida(False)` sempre no `finally`.
Detalhe: [[docs/codigo/cli|guia completo]]
