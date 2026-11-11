"""Regressão: subprocessos sem terminal interativo e recuperação não destrutiva."""
import json
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'app'))
import ensaio
import revisao_web


def config(root):
    return ensaio.Config(
        raiz=root, pasta_brutas=root/'brutas', pasta_processadas=root/'processadas',
        pasta_referencias=root/'referencias', pasta_output=root/'output',
        pasta_revisao=root/'_sistema'/'revisao', pasta_trabalho=root/'processadas',
        pasta_dados=root/'_sistema'/'dados', pasta_aprendizado=root/'_sistema'/'dados'/'aprendizado',
        logo=root/'logo.jpg')


class RecuperacaoConsole(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.cfg=config(self.root)
        ensaio.ensure_directories(self.cfg)

    def test_ffmpeg_nao_recebe_teclado_e_nao_abre_console(self):
        completed=subprocess.CompletedProcess(['ffmpeg'],0,stdout='',stderr='')
        with patch.object(ensaio.subprocess,'run',return_value=completed) as run:
            ensaio.run_command(['ffmpeg','-version'], capture=True)
        kw=run.call_args.kwargs
        self.assertEqual(kw['stdin'],subprocess.DEVNULL)
        self.assertEqual(kw['creationflags'],getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(kw['stderr'],subprocess.PIPE)

    def test_processo_da_interface_sem_teclado_e_sem_console(self):
        state=revisao_web.AppState(self.root/'app',self.cfg)
        with patch.object(revisao_web.subprocess,'Popen') as popen:
            state._start_subprocess([sys.executable,'-c','pass'],'analise','teste.log')
        kw=popen.call_args.kwargs
        self.assertEqual(kw['stdin'],subprocess.DEVNULL)
        self.assertEqual(kw['creationflags'],getattr(subprocess,'CREATE_NO_WINDOW',0))
        if state.log_handle:state.log_handle.close()

    def test_recomecar_preserva_temporarios_e_revisao(self):
        work=ensaio.work_dir_for_date(self.cfg,'261106')
        work.mkdir(parents=True)
        (work/'master.wav').write_bytes(b'important')
        raw=self.cfg.pasta_brutas/'261106_001.wav';raw.write_bytes(b'raw')
        (self.cfg.pasta_revisao/'manifesto.json').write_text(json.dumps({'data_codigo':'261106'}),encoding='utf-8')
        (self.cfg.pasta_revisao/'segmentos.csv').write_text('old review',encoding='utf-8')
        def interrupted(*a,**k):
            raise ensaio.EnsaioError('interrompido novamente')
        with patch.object(ensaio,'check_dependencies'),patch.object(ensaio,'normalize_files',side_effect=interrupted):
            with self.assertRaises(ensaio.EnsaioError):
                ensaio.command_analyze(self.cfg,verbose=False,no_previews=True,recomecar=True)
        recovered=list(work.parent.glob('temporarios_interrompidos_*'))
        self.assertEqual(len(recovered),1)
        self.assertEqual((recovered[0]/'master.wav').read_bytes(),b'important')
        self.assertEqual(raw.read_bytes(),b'raw')
        backups=list((self.cfg.pasta_revisao/'historico').glob('*/segmentos.csv'))
        self.assertTrue(backups)
        self.assertEqual(backups[-1].read_text(), 'old review')

    def test_sem_confirmacao_nao_descarta_trabalho(self):
        work=ensaio.work_dir_for_date(self.cfg,'261106');work.mkdir(parents=True)
        (work/'master.wav').write_bytes(b'important')
        raw=self.cfg.pasta_brutas/'261106_001.wav';raw.write_bytes(b'raw')
        with patch.object(ensaio,'check_dependencies'):
            with self.assertRaisesRegex(ensaio.EnsaioError,'temporário'):
                ensaio.command_analyze(self.cfg,verbose=False,no_previews=True)
        self.assertEqual((work/'master.wav').read_bytes(),b'important')

if __name__=='__main__':unittest.main()
