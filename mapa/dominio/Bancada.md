---
tipo: dominio
tags: [dominio]
---
# Bancada
- **Fonte:** AMETEK MX30-3Pi por USB, vista como `COM10` (`ASRL10::INSTR`), 115200 baud 8N1; não conectar o DB9 junto; MX GUI fechado. Card: [[mapa/codigo/ametek_orm|ametek_orm]].
- **Osciloscópio:** Keysight DSO-X 4034A por USB, VISA `USB0::0x0957::0x17A4::MY59240844::0::INSTR` (`KEYSIGHT_RESOURCE=AUTO` faz descoberta). Card: [[mapa/codigo/oscilloscope_orm|oscilloscope_orm]].
- **BNC:** AMETEK *Trigger Out* -> Keysight *EXT Trigger*; sem ele o osciloscópio nunca dispara. Probe diferencial no CH1 (fase A-neutro); o fator digitado deve ser exatamente o da chave.
- **PC da bancada:** Inspiron 15 `DESKTOP-FSEESJI` (Python 3.11.9, NI-VISA 26.5, driver AMETEK TUSB3410); suíte 680 testes OK em `21fb300` ([[P-16]]).
- **Confirmações digitadas:** `ENERGIZAR-TESTE`, `ENERGIZAR-50V`, `ENERGIZAR-127V`, `ENERGIZAR-MARCADORES`, `ENERGIZAR-ACDC`; `run` pede confirmação case-sensitive.
- Disjuntores fonte-probe fechados (aberto em 07/10 gerou medidas a ~0,45 sem erro).
Docs: [[docs/operacao|operação]], [[docs/configuracao|configuração]], [[docs/quirks|quirks]]. Hubs: [[mapa/dominio/Segurança e limites|Segurança]], [[mapa/dominio/Operação na bancada|Operação]].
