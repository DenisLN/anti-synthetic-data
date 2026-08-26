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
