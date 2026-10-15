# Classe 15: HARMONICS_FLICKER (exemplo de ficha)

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` {bdg-danger}`PENDENTE` {bdg-secondary}`FORA DA MAIN`

**Pergunta:** o que a classe 15 produz? **Resposta:** uma senoide com harmônicas (3.ª, 5.ª, 7.ª) modulada em amplitude por um flicker nos 200 ms inteiros.

:::{note} Nota de verificação
Valores de `gerar()` conferidos offline; nenhuma captura de bancada.
:::

:::{warning} Decisão em aberto
Manter ou reverter as extensões das compostas sorteadas.
:::

:::{important} Pendência P-11
Ver a página de pendências: manter ou reverter as extensões das compostas.
:::

## Modelo

$$
v(t) = \left[1 + m \sin(2\pi f_{fl}\, t)\right]\left[\sin(\omega t) + \sum_{h\in\{3,5,7\}} c_h \sin(h\,\omega t)\right]
$$

## Fluxo

```{mermaid}
flowchart LR
    G["gerar()"] --> F["forma_para_bancada()"] --> P["program_capture()"] --> A["arm_transient()"] --> T["*TRG"]
```

## Listagem do código real

Listagem por **símbolo** (recomendada: não envelhece quando o arquivo muda; o carimbo do commit fica no rodapé da página):

```{literalinclude} ../../experimentos_waveform/15.py
:language: python
:caption: experimentos_waveform/15.py, Experimento.gerar
:pyobject: Experimento.gerar
```

Listagem por linhas (só para trechos sem símbolo, como constantes; a linha deve ser conferida a cada release):

```{literalinclude} ../../experimentos_waveform/15.py
:language: python
:caption: experimentos_waveform/15.py (atributos da classe)
:lines: 9-14
:linenos:
:lineno-start: 9
```

| Condição | Valor | Fonte |
|---|---|---|
| 127 V / 60 Hz | exemplo | `CHANGELOG/v1.15.md` |
