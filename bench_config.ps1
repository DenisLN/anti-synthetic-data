# Configuração da bancada Windows. Revise os campos marcados como OBRIGATÓRIO.
$env:BENCH_MODE = "1"
$env:ARM_OUTPUT = "NO"

$env:AMETEK_PORT = "COM10"
$env:AMETEK_BAUDRATE = "115200"
$env:AMETEK_TIMEOUT_S = "5"
$env:AMETEK_QUERY_EOT = "1"
$env:AMETEK_EXPECTED_MODEL = "MX30"
# Autorizado para esta bancada: apaga as formas arbitrárias do usuário uma vez
# por conexão, mantendo as formas internas SIN/SQU/CSIN.
$env:AMETEK_CLEAR_USER_WAVEFORMS = "1"

$env:KEYSIGHT_RESOURCE = "USB0::0x0957::0x17A4::MY59240844::0::INSTR"
$env:KEYSIGHT_EXPECTED_MODEL = "DSOX4034A"
$env:KEYSIGHT_TIMEOUT_MS = "15000"

# OBRIGATÓRIO: substitua pelo fator escrito na probe diferencial instalada.
$env:VOLTAGE_PROBE_ATTENUATION = ""

# Limites de comissionamento e operacionais da bancada.
$env:BASE_VOLTAGE_RMS = "127"
$env:SOURCE_VOLTAGE_RANGE_RMS = "150"
$env:EUT_MAX_VOLTAGE_RMS = "140"
$env:EUT_MAX_PEAK_V = "400"
$env:CURRENT_LIMIT_A = "0.5"
$env:CURRENT_PROTECTION_DELAY_S = "0.1"

$env:EXT_TRIGGER_PROBE_ATTENUATION = "1"
$env:EXT_TRIGGER_RANGE_V = "8"
$env:EXT_TRIGGER_LEVEL_V = "1.5"

$env:CAPTURE_CURRENT = "0"
$env:CURRENT_PROBE_ATTENUATION = ""
$env:CURRENT_BASE_A = ""
$env:REAL_CAPTURES_PER_CLASS = "1"
$env:SNR_LEVELS_DB = "30"
