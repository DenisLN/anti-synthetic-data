# Perfis de faixas: o que mudou (2026-10-12)

Base: commit 34a0d82 mais a spec Metadata (não commitada). Nada foi commitado. Hardware não tocado (`BENCH_MODE=0`; o relatório de limites usa instrumentos simulados).

Observação sobre o pedido: o perfil norma pedido (sag 0,15–0,85, swell 1,15–1,75) fica DENTRO da faixa da IEEE 1159 (sag 0,1–0,9, swell 1,1–1,8), com folga nas bordas; as bordas ficaram só no perfil fronteira, como a spec manda.

## 1. Um único lugar com as faixas; `gerar()` lê pelo perfil ativo

- Faixas: `logica/perfis.py:35-91` (`FAIXAS`, um componente por entrada, uma coluna por perfil) e `perfis.py:94-107` (`COMPONENTES_POR_CLASSE`). Tabela legível: `docs/perfis.md`.
- Leitura em `gerar()`: `experimentos_nativos/02.py:21`, `03.py:21`, `05.py:31`; `experimentos_waveform/06.py:22`, `10.py:20-21`, `11.py:15-16`, `12.py:17`, `13.py:19-20`, `14.py:17`, `15.py:15-16`, `16.py:19`, `20.py:23`. As compostas herdam os componentes (`sag_composto`, `swell_composto`, `thd_composto`, `flicker_composto`).
- Efeitos colaterais de `NIVEIS`/`NIVEIS_THD` virarem propriedades (02/03/05): `mestre.py` lê `getattr(self, "NIVEIS")` em instância (`total_niveis`, derivação do rms da 02/03), o que continua funcionando; nenhum código lê `NIVEIS` da classe (verificado com Grep em `**/*.py`; só testes com classes próprias). A constante de módulo `NIVEIS_THD` de `05.py` sumiu (nenhuma outra referência).
- Não foram tocados: início, duração, fase, forma, `max_voltage_rms`, `max_peak_v`, `max_current_a`, pré-validação de pico.
- Escolhas minhas (a spec fixa só os extremos): níveis intermediários da norma espaçados uniformemente (sag 0,15/0,325/0,5/0,675/0,85; swell 1,15/1,30/1,45/1,60/1,75); THD da 05 norma 2/5/10/15/20 % (mantém 5 níveis e os 4 validados na bancada, acrescenta 2 %); flicker composto da norma 4,5 % (ponto médio de 2–7 %); fronteira de THD/flicker/inter-harmônicas = literatura; compostas em fronteira alternam 0,1/0,9 (sag) e 1,1/1,8 (swell) por `capture_index`.

## 2. CLI, status, env, metadata

- `set perfil norma|literatura|fronteira`: `cli.py:410-418`; recusa valor inválido (código 1, mantém o anterior). `HELP_TEXT`: `cli.py:111-118`. `status`: `cli.py:269` (`perfil de faixas: ...`). Uso do `set` sem argumento: `cli.py:340-341`.
- Variável de ambiente: `PERFIL` (`mestre.py:322`, `perfis.perfil_do_ambiente`); vazio = literatura, valor inválido levanta `ValueError` na importação do `mestre`.
- `Config.perfil` (`mestre.py:707`, padrão literatura), preenchido em `_build_config` (`mestre.py:768`). Substitutos de config sem o campo (`_ConfigOffline`, `comparar_visual.StubConfig`) caem em literatura (`perfis.perfil_da_config`).
- Metadata: `"perfil"` em todo registro (`mestre.py:2199`, no dicionário comum antes do ramo físico/simulado). Sessões antigas sem o campo são lidas como literatura; `analisar_sessao._reconstruir_esperado` usa o perfil gravado (`analisar_sessao.py:133`).
- Testes: `test_cli_set_perfil_status_e_help`, `test_metadata_grava_perfil_em_cada_captura` (simulado, 3 perfis, classe 02 real), `test_fisica_grava_perfil` (caminho físico simulado), `test_analisar_sessao_reconstroi_com_o_perfil_da_captura`, `test_perfil_invalido_e_padrao`.
- `README.md`: linhas de `set perfil` e `PERFIL` (não pedido; só para não deixar a CLI documentada pela metade).

## 3. Literatura reproduz byte a byte o `gerar()` atual

- Fixture `tests/fixtures/gerar_literatura_34a0d82.json`: 400 SHA-256 de (bytes `<f8` da tensão + `json.dumps(parametros, sort_keys=True)`) para as 20 classes × f0 60/50 Hz × seeds 1234567/7654321 × `capture_index` 0–4. Gerado ANTES de qualquer edição em `gerar()`; `git diff HEAD` em `experimentos_*` e `sinais.py` estava vazio na hora, então a árvore era idêntica ao HEAD (34a0d82) nessas classes. Numpy do fixture: 2.4.6 (gravado no arquivo).
- Teste: `PerfisDeFaixasTests.test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82` (`tests/test_offline.py:4910`+) recalcula as assinaturas com o padrão e com `perfil="literatura"` explícito e exige igualdade. Contra-prova: `test_norma_e_fronteira_mudam_so_o_que_a_spec_manda` exige que norma mude exatamente 02, 03, 05, 06, 11, 15, 20 e fronteira exatamente 02, 03, 10–14 (as demais ficam idênticas); logo o hash realmente detecta mudança.
- Evidência adicional: o relatório de limites do perfil literatura é idêntico ao do código de HEAD (extraído com `git archive HEAD` para o scratchpad e rodado com os mesmos argumentos; `diff --strip-trailing-cr` sem diferenças em 127 V/60 e 50 Hz, plano padrão e `--capturas 5`; só a coluna "perfil" no cabeçalho foi removida na comparação).
- Limite: o fixture depende da versão do numpy (aritmética de `sin`); outra versão pode divergir sem que o código tenha mudado.

## 4. `relatorio_limites_bancada.py` a 127 V

`scripts/relatorio_limites_bancada.py` ganhou `--perfil`. Rodado para cada perfil, 127 V/60 Hz e 127 V/50 Hz, com o plano padrão e com `--capturas 5` (necessário para exercitar todos os níveis de 02/03/05 e as duas fronteiras das compostas). Saídas completas: `docs/analise-2026-10-12/limites_perfis/{perfil}_127V_{60,50}Hz_cap5.md` (o plano padrão é subconjunto; não guardei).

| Perfil | 60 Hz | 50 Hz |
|---|---|---|
| norma | todas as capturas das 20 classes rodam; 0 puladas, 0 com distúrbio reduzido, 0 CLIPA | idem |
| literatura | idem (02 e 03 com 25/25) | idem |
| fronteira | idem (02 e 03 com 10/10, só 2 níveis) | idem |

Contagem feita por `grep` nos 6 arquivos: 0 linhas "NÃO", 0 "CLIPA", 0 de distúrbio < 100 %. Maior extremo previsto: fronteira, classe 14 com swell 1,8 pu, extremo 393,1 V para teto 415,8 V (tela 583 V), `docs/analise-2026-10-12/limites_perfis/fronteira_127V_60Hz_cap5.md`. Nenhum outro valor de tensão (220/230 V) foi rodado, não pedido; a 230 V/50 Hz o histórico da v1.14 mostra que 02/03/04/16 são puladas, então os níveis de fronteira provavelmente não cabem lá (NÃO VERIFICADO neste trabalho).

## 5. Registro

- `AGENTS.md`: seção "Autorização de 2026-10-12", mesmo formato da de 2026-10-07 (antes de "Limites inegociáveis").
- `CHANGELOG/v1.15.md`.

## Verificação

`.\env\Scripts\python.exe -m unittest tests.test_offline -v`: `Ran 262 tests`, `OK` (251 antes; +11: 10 em `PerfisDeFaixasTests` e 1 em `MetadataLegivelERastreavelTests`).

## Achados (com gravidade)

1. Média. Perfil norma torna inter-harmônicas (0,5–2 %) e flicker (2–7 %) pequenos frente ao ruído e à resolução do osciloscópio. O ruído AWGN padrão é `SNR_LEVELS_DB=(30,)`, ou seja, ruído de 10^(-30/20) = 3,16 % do rms do sinal (`mestre.py`, `SNR_LEVELS_DB`), maior que uma inter-harmônica de 0,5–2 % de amplitude (rms 0,35–1,4 %). Na captura física, o osciloscópio lê em BYTE (`oscilloscope_orm.py:109`) e a tela do CH1 no relatório da classe 20 norma é ±305 V; se 256 códigos cobrirem a tela (NÃO VERIFICADO: não conferi o mapeamento do BYTE no guia), 1 LSB ≈ 2,4 V, e a amplitude 0,005–0,02 pu × 182,7 V = 0,9–3,6 V fica em 0,4–1,5 LSB. Detectabilidade real é NÃO VERIFICADA (não rodei classificador nem FFT).
2. Baixa. Com `capturas_padrao=1` (padrão da bancada), o perfil fronteira nas compostas 10–14 só mostra 0,1 (sag) e 1,1 (swell); a outra fronteira (0,9 / 1,8) exige `set capturas 2` ou mais.
3. Baixa. THD de 2 % da 05 norma passa pelo CSINe nativo (`ametek_orm.py:831` aceita `0 < thd <= 20`), mas esse valor nunca foi comandado na bancada real; os 5/10/15/20 % são os já validados. NÃO VERIFICADO em hardware (nem sag/swell de fronteira, nem os intermediários da norma).
4. Baixa. Fronteira em 02/03 tem 2 níveis em vez de 5 (`total_niveis` = 2): o plano com `set capturas N` fica com 2N capturas nessas classes (visto: 10/10 com N=5), mudando o balanceamento por classe se o dataset da campanha for misturado entre perfis.
5. Baixa. `sessao.json` não registra o perfil (varia por `run` dentro da sessão por decisão do `set`); fica só por captura. Se quiser perfil único por sessão, é mudança de formato (outra spec).
6. Informativo. A mudança de `NIVEIS` para propriedade impede acessar `Experimento.NIVEIS` pela classe; nada no repositório faz isso hoje.
7. Informativo. Import `perfis` em `cli.py:28` está fora de ordem alfabética (cosmético, não corrigi).

## NÃO VERIFICADO

- Qualquer comportamento em hardware real (CSINe a 2 %, sag/swell de fronteira, composta 14 a 1,8 pu com oscilação) — só simulado.
- Tensões diferentes de 127 V (220/230/380 V) com os novos perfis.
- Mapeamento do BYTE do osciloscópio e a detectabilidade das amplitudes pequenas da norma (achado 1).
- Reprodutibilidade do fixture com outra versão do numpy.
- Compatibilidade do perfil com sessões já gravadas pelas ferramentas `relatorio_html`/`recortar_margem`: não alterei esses arquivos; `relatorio_html` reconstrói o esperado via `analisar_sessao._reconstruir_esperado` (`relatorio_html.py:219`), que agora lê o perfil, mas não rodei o relatório HTML numa sessão com perfil.
