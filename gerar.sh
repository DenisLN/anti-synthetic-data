#!/bin/bash

# Criar estrutura de diretórios
mkdir -p experimentos resultados

# Template de geração dos 20 experimentos corrigidos para PyMeasure, SCPI e simulação

cat << 'EOF' > experimentos/01.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "01"
    print(f"[{exp_id}] Executando: SINAL NORMAL (200 ms)")
    
    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True
        
        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            v_data = 179.6 * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * np.sin(2 * np.pi * 60 * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="NORMAL", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/02.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "02"
    sag_pu = 0.5
    print(f"[{exp_id}] Executando: SAG ({sag_pu} pu)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0 * sag_pu, 60.0
            fonte.output_enabled = True
        
        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            envelope = np.ones_like(t)
            mask = (t >= 0.060) & (t <= 0.120)
            envelope[mask] = sag_pu
            v_data = 179.6 * envelope * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * envelope * np.sin(2 * np.pi * 60 * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SAG", sag_pu=sag_pu, exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/03.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "03"
    swell_pu = 1.4
    print(f"[{exp_id}] Executando: SWELL ({swell_pu} pu)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0 * swell_pu, 60.0
            fonte.output_enabled = True
        
        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            envelope = np.ones_like(t)
            mask = (t >= 0.060) & (t <= 0.120)
            envelope[mask] = swell_pu
            v_data = 179.6 * envelope * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * envelope * np.sin(2 * np.pi * 60 * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SWELL", swell_pu=swell_pu, exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/04.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "04"
    interr_pu = 0.05
    print(f"[{exp_id}] Executando: INTERRUPTION ({interr_pu} pu)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0 * interr_pu, 60.0
            fonte.output_enabled = True
        
        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            envelope = np.ones_like(t)
            mask = (t >= 0.060) & (t <= 0.120)
            envelope[mask] = interr_pu
            v_data = 179.6 * envelope * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * envelope * np.sin(2 * np.pi * 60 * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="INTERRUPTION", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/05.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "05"
    thd_pct = 20.0
    print(f"[{exp_id}] Executando: HARMONICS (THD={thd_pct}%)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.set_harmonic(3, 12.0)
            fonte.set_harmonic(5, 12.0)
            fonte.set_harmonic(7, 10.0)
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True
        
        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * (np.sin(w * t) + 0.12 * np.sin(3 * w * t) + 0.12 * np.sin(5 * w * t) + 0.10 * np.sin(7 * w * t))
            i_data = 10.0 * (np.sin(w * t - 0.2) + 0.05 * np.sin(3 * w * t))

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="HARMONICS", thd_pct=thd_pct, exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/06.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "06"
    f_flicker = 15.0
    profundidade = 0.10
    print(f"[{exp_id}] Executando: FLICKER ({f_flicker} Hz)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            mod = 1.0 + profundidade * np.sin(2 * np.pi * f_flicker * t)
            v_data = 179.6 * mod * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * mod * np.sin(2 * np.pi * 60 * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="FLICKER", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/07.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "07"
    print(f"[{exp_id}] Executando: NOTCH")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            v_data = 179.6 * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * np.sin(2 * np.pi * 60 * t - 0.2)
            for cycle in range(4):
                t_peak_pos = 0.060 + cycle * (1/60.0) + (1/240.0)
                t_peak_neg = t_peak_pos + (1/120.0)
                notch_mask = ((t >= t_peak_pos - 0.00005) & (t <= t_peak_pos + 0.00005)) | \
                             ((t >= t_peak_neg - 0.00005) & (t <= t_peak_neg + 0.00005))
                v_data[notch_mask] = 0.0

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="NOTCH", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/08.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "08"
    amp_peak_pu = 7.0
    print(f"[{exp_id}] Executando: TRANSIENT ({amp_peak_pu} pu)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            v_data = 179.6 * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * np.sin(2 * np.pi * 60 * t - 0.2)
            pulse_mask = (t >= 0.080) & (t <= 0.08005)
            v_data[pulse_mask] += amp_peak_pu * 179.6

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="TRANSIENT", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/09.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "09"
    f_osc = 1200.0
    tau = 0.005
    print(f"[{exp_id}] Executando: OSCILLATORY TRANSIENT ({f_osc} Hz)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            v_data = 179.6 * np.sin(2 * np.pi * 60 * t)
            i_data = 10.0 * np.sin(2 * np.pi * 60 * t - 0.2)
            mask = (t >= 0.080) & (t <= 0.120)
            t_rel = t[mask] - 0.080
            v_data[mask] += 0.3 * 179.6 * np.sin(2 * np.pi * f_osc * t_rel) * np.exp(-t_rel / tau)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="OSCILLATORY_TRANSIENT", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/10.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "10"
    print(f"[{exp_id}] Executando: SAG + HARMONICS")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.set_harmonic(3, 12.0)
            fonte.set_harmonic(5, 12.0)
            fonte.voltage, fonte.frequency = 127.0 * 0.5, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            mask = (t >= 0.060) & (t <= 0.120)
            v_data[mask] = 179.6 * 0.5 * (np.sin(w * t[mask]) + 0.12 * np.sin(3 * w * t[mask]) + 0.12 * np.sin(5 * w * t[mask]) + 0.10 * np.sin(7 * w * t[mask]))

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SAG_HARMONICS", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/11.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "11"
    print(f"[{exp_id}] Executando: SAG + FLICKER")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0 * 0.5, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            mask = (t >= 0.060) & (t <= 0.120)
            flicker = 1.0 + 0.10 * np.sin(2 * np.pi * 15.0 * t[mask])
            v_data[mask] = 179.6 * 0.5 * flicker * np.sin(w * t[mask])

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SAG_FLICKER", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/12.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "12"
    print(f"[{exp_id}] Executando: SAG + OSCILLATORY TRANSIENT")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0 * 0.5, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            mask_sag = (t >= 0.060) & (t <= 0.120)
            v_data[mask_sag] *= 0.5
            mask_osc = (t >= 0.060) & (t <= 0.100)
            t_rel = t[mask_osc] - 0.060
            v_data[mask_osc] += 0.3 * 179.6 * np.sin(2 * np.pi * 600.0 * t_rel) * np.exp(-t_rel / 0.005)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SAG_OSCILLATORY_TRANSIENT", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/13.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "13"
    print(f"[{exp_id}] Executando: SWELL + HARMONICS")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.set_harmonic(3, 12.0)
            fonte.set_harmonic(5, 12.0)
            fonte.voltage, fonte.frequency = 127.0 * 1.3, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            mask = (t >= 0.060) & (t <= 0.120)
            v_data[mask] = 179.6 * 1.3 * (np.sin(w * t[mask]) + 0.12 * np.sin(3 * w * t[mask]) + 0.12 * np.sin(5 * w * t[mask]) + 0.10 * np.sin(7 * w * t[mask]))

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SWELL_HARMONICS", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/14.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "14"
    print(f"[{exp_id}] Executando: SWELL + OSCILLATORY TRANSIENT")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0 * 1.3, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            mask_swell = (t >= 0.060) & (t <= 0.120)
            v_data[mask_swell] *= 1.3
            mask_osc = (t >= 0.060) & (t <= 0.100)
            t_rel = t[mask_osc] - 0.060
            v_data[mask_osc] += 0.3 * 179.6 * np.sin(2 * np.pi * 600.0 * t_rel) * np.exp(-t_rel / 0.005)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="SWELL_OSCILLATORY_TRANSIENT", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/15.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "15"
    print(f"[{exp_id}] Executando: HARMONICS + FLICKER")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.set_harmonic(3, 12.0)
            fonte.set_harmonic(5, 12.0)
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            flicker = 1.0 + 0.10 * np.sin(2 * np.pi * 15.0 * t)
            v_harm = (np.sin(w * t) + 0.12 * np.sin(3 * w * t) + 0.12 * np.sin(5 * w * t) + 0.10 * np.sin(7 * w * t))
            v_data = 179.6 * flicker * v_harm
            i_data = 10.0 * flicker * np.sin(w * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="HARMONICS_FLICKER", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/16.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "16"
    print(f"[{exp_id}] Executando: INTERRUPTION + HARMONICS")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.set_harmonic(3, 12.0)
            fonte.set_harmonic(5, 12.0)
            fonte.voltage, fonte.frequency = 127.0 * 0.05, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            mask = (t >= 0.060) & (t <= 0.120)
            v_harm = (np.sin(w * t[mask]) + 0.12 * np.sin(3 * w * t[mask]) + 0.12 * np.sin(5 * w * t[mask]) + 0.10 * np.sin(7 * w * t[mask]))
            v_data[mask] = 179.6 * 0.05 * v_harm

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="INTERRUPTION_HARMONICS", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/17.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "17"
    print(f"[{exp_id}] Executando: NOTCH + OSCILLATORY TRANSIENT")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * np.sin(w * t)
            i_data = 10.0 * np.sin(w * t - 0.2)
            for cycle in range(4):
                t_peak_pos = 0.060 + cycle * (1/60.0) + (1/240.0)
                t_peak_neg = t_peak_pos + (1/120.0)
                notch_mask = ((t >= t_peak_pos - 0.00005) & (t <= t_peak_pos + 0.00005)) | \
                             ((t >= t_peak_neg - 0.00005) & (t <= t_peak_neg + 0.00005))
                v_data[notch_mask] = 0.0
            mask_osc = (t >= 0.060) & (t <= 0.120)
            t_rel = t[mask_osc] - 0.060
            v_data[mask_osc] += 0.3 * 179.6 * np.sin(2 * np.pi * 300.0 * t_rel) * np.exp(-t_rel / 0.005)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="NOTCH_OSCILLATORY_TRANSIENT", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/18.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "18"
    print(f"[{exp_id}] Executando: FREQUENCY DRIFT")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 63.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            f_t = 57.0 + (63.0 - 57.0) * (t / 0.2)
            fase = 2 * np.pi * np.cumsum(f_t) / fs
            v_data = 179.6 * np.sin(fase)
            i_data = 10.0 * np.sin(fase - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="FREQUENCY_DRIFT", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/19.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "19"
    dc_pu = 0.05
    print(f"[{exp_id}] Executando: DC OFFSET (+{dc_pu} pu)")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w = 2 * np.pi * 60
            v_data = 179.6 * (np.sin(w * t) + dc_pu)
            i_data = 10.0 * (np.sin(w * t - 0.2) + 0.02)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="DC_OFFSET", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

cat << 'EOF' > experimentos/20.py
import os, numpy as np

def run(fonte, osc):
    exp_id = "20"
    print(f"[{exp_id}] Executando: INTER-HARMÔNICAS")

    try:
        if fonte is not None:
            fonte.clear_harmonics()
            fonte.voltage, fonte.frequency = 127.0, 60.0
            fonte.output_enabled = True

        if osc is not None:
            osc.configure_channel(1, scale=50.0)
            osc.configure_channel(2, scale=5.0)
            osc.configure_timebase(scale=0.02)
            osc.setup_single_trigger(source="EXT", level=1.5)
            osc.arm()
            osc.wait_for_armed()
            if fonte is not None:
                fonte.arm_transient()
                fonte.trigger()
            osc.wait_for_trigger_complete()
            t, v_data = osc.get_waveform(1)
            _, i_data = osc.get_waveform(2)
            fs = osc.sample_rate
        else:
            fs = 200000.0
            t = np.linspace(0, 0.2, int(fs * 0.2), endpoint=False)
            w0 = 2 * np.pi * 60
            v_inter = 0.08 * np.sin(2 * np.pi * 150 * t) + 0.06 * np.sin(2 * np.pi * 210 * t) + 0.05 * np.sin(2 * np.pi * 330 * t)
            v_data = 179.6 * (np.sin(w0 * t) + v_inter)
            i_data = 10.0 * np.sin(w0 * t - 0.2)

        np.savez_compressed(f"resultados/{exp_id}.npz", tempo=t, tensao=v_data, corrente=i_data, fs=fs, classe="INTERHARMONICS", exp_id=exp_id)
        print(f"[{exp_id}] Dados salvos em resultados/{exp_id}.npz")
    finally:
        if fonte is not None:
            fonte.output_enabled = False
EOF

chmod +x experimentos/*.py
echo "Todos os 20 scripts de experimentos foram gerados e corrigidos com sucesso!"
