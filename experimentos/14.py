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
