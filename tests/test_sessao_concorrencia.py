"""Lock de sessão entre processos: recuperação nunca consome spool ativo."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

LOGICA = Path(__file__).resolve().parents[1] / 'logica'
sys.path.insert(0, str(LOGICA))
import sessao_io as io


class ExclusaoSessaoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.sessao = self.base / 'sessao_concorrente'

    def test_dois_processos_scan_nao_consume_ativo_e_morte_preserva_ambos_ids(self):
        writer_code = '''
import sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from pathlib import Path
import sessao_io as io
a = io.ArquivoDaClasse(Path(sys.argv[2]), "02", "SAG")
for n in (1, 2):
    ident = f"02-{n:04d}"
    a.adicionar("norma", id_captura=ident, medida=np.full(8, n),
                tempo_ms=np.arange(8.), fs_hz=30000.,
                metadado={"id_captura": ident, "perfil": "norma"})
    print(ident, flush=True)
    sys.stdin.readline()
'''
        scanner_code = '''
import json, sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import sessao_io as io
print(json.dumps([str(p) for p in io.recuperar_sessoes_interrompidas(Path(sys.argv[2]), avisar=None)]))
'''
        writer = subprocess.Popen([sys.executable, '-u', '-c', writer_code,
                                   str(LOGICA), str(self.sessao)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(writer.stdout.readline().strip(), '02-0001')
            scan = subprocess.run([sys.executable, '-c', scanner_code,
                                   str(LOGICA), str(self.base)], capture_output=True,
                                  text=True, timeout=20, check=True)
            self.assertEqual(json.loads(scan.stdout), [])
            self.assertEqual(len(list((self.sessao / 'parcial').rglob('*.npz'))), 1)
            self.assertFalse((self.sessao / '02_sag.npz').exists())
            writer.stdin.write('\n')
            writer.stdin.flush()
            self.assertEqual(writer.stdout.readline().strip(), '02-0002')
            writer.kill()  # Sem close, finally ou __del__: o SO deve liberar o lock.
            writer.wait(timeout=10)
            scan = subprocess.run([sys.executable, '-c', scanner_code,
                                   str(LOGICA), str(self.base)], capture_output=True,
                                  text=True, timeout=20, check=True)
            self.assertEqual(json.loads(scan.stdout), [str(self.sessao / '02_sag.npz')])
            with np.load(self.sessao / '02_sag.npz', allow_pickle=False) as d:
                self.assertEqual(list(d['norma/id_captura']), ['02-0001', '02-0002'])
                np.testing.assert_array_equal(d['norma/medida'], [[1]*8, [2]*8])
            self.assertFalse((self.sessao / 'parcial').exists())
            self.assertTrue((self.sessao / io.ARQUIVO_BLOQUEIO).is_file())
            self.assertEqual(io.recuperar_sessoes_interrompidas(self.base, avisar=None), [])
        finally:
            if writer.poll() is None:
                writer.kill()
            writer.communicate(timeout=10)

    def test_lease_compartilhado_so_libera_apos_ultimo_writer(self):
        a = io.ArquivoDaClasse(self.sessao, '02', 'SAG')
        self.addCleanup(a.close)
        lease = io.BloqueioSessao(self.sessao)
        self.addCleanup(lease.close)
        a.adicionar('norma', id_captura='02-0001', medida=np.arange(8.),
                    tempo_ms=np.arange(8.), fs_hz=30000.)
        with self.assertRaises(io.SessaoEmUsoError):
            io.recuperar_parcial(self.sessao)
        lease.close()
        self.assertEqual(io.recuperar_sessoes_interrompidas(self.base, avisar=None), [])
        a.close()
        a.close()
        self.assertEqual(io.recuperar_parcial(self.sessao), [self.sessao / '02_sag.npz'])

    def test_writer_fechado_nao_pode_gravar_nem_apagar_spool(self):
        a = io.ArquivoDaClasse(self.sessao, '02', 'SAG')
        a.adicionar('norma', id_captura='02-0001', medida=np.arange(8.),
                    tempo_ms=np.arange(8.), fs_hz=30000.)
        a.close()
        for acao in (a.consolidar, a._apagar_spool,
                     lambda: a.iniciar_perfil('norma'),
                     lambda: a.adicionar('norma', id_captura='02-0002',
                                         medida=np.arange(8.), tempo_ms=np.arange(8.), fs_hz=30000.)):
            with self.assertRaisesRegex(RuntimeError, 'encerrado'):
                acao()
        self.assertEqual(len(list(a.pasta_spool.glob('*.npz'))), 1)

    def test_legado_sem_lock_exige_recuperacao_explicita_offline(self):
        a = io.ArquivoDaClasse(self.sessao, '02', 'SAG')
        a.adicionar('norma', id_captura='02-0001', medida=np.arange(8.),
                    tempo_ms=np.arange(8.), fs_hz=30000.)
        a.close()
        # Fixture histórica: versões antigas não criavam o marcador.
        (self.sessao / io.ARQUIVO_BLOQUEIO).unlink()
        self.assertEqual(io.recuperar_sessoes_interrompidas(self.base, avisar=None), [])
        self.assertTrue((self.sessao / 'parcial').exists())
        self.assertEqual(io.recuperar_parcial(self.sessao), [self.sessao / '02_sag.npz'])


if __name__ == '__main__':
    unittest.main()
