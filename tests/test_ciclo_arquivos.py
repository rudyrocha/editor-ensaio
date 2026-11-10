"""Proteções da v3.2.0: arquivos efêmeros nunca são confundidos com originais."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

APP = Path(__file__).resolve().parent.parent / 'app'
sys.path.insert(0, str(APP))
import ensaio


def make_cfg(root):
    return ensaio.Config(
        raiz=root, pasta_brutas=root/'brutas', pasta_processadas=root/'processadas',
        pasta_referencias=root/'referencias', pasta_output=root/'output',
        pasta_revisao=root/'_sistema'/'revisao', pasta_trabalho=root/'processadas',
        pasta_dados=root/'_sistema'/'dados', pasta_aprendizado=root/'_sistema'/'dados'/'aprendizado',
        logo=root/'logo.jpg',
    )

class CicloArquivos(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.cfg=make_cfg(self.root)
        ensaio.ensure_directories(self.cfg)
        self.work=ensaio.work_dir_for_date(self.cfg,'261001')
        self.work.mkdir(parents=True)
        (self.work/'master.wav').write_bytes(b'fake master')
        self.original=self.cfg.pasta_processadas/'2026-10-01'/'261001_0307.wav'
        self.original.write_bytes(b'raw original')
        self.reference=self.cfg.pasta_referencias/'original.wav'
        self.reference.write_bytes(b'reference')
        self.output=self.cfg.pasta_output/'Ensaio.26.10.01.mp4'
        self.output.write_bytes(b'output')

    def test_local_do_trabalho_usa_data_e_temporarios(self):
        self.assertEqual(self.work,self.root/'processadas'/'2026-10-01'/'temporarios')

    def test_limpeza_preserva_originais_referencias_e_saida(self):
        self.assertTrue(ensaio.cleanup_work_dir(self.cfg,'261001'))
        self.assertFalse(self.work.exists())
        self.assertEqual(self.original.read_bytes(),b'raw original')
        self.assertEqual(self.reference.read_bytes(),b'reference')
        self.assertEqual(self.output.read_bytes(),b'output')

    def test_limpeza_idempotente(self):
        self.assertTrue(ensaio.cleanup_work_dir(self.cfg,'261001'))
        self.assertTrue(ensaio.cleanup_work_dir(self.cfg,'261001'))

    def test_limpeza_recusa_pasta_fora_de_processadas(self):
        self.cfg.pasta_trabalho=self.root/'_sistema'/'trabalho'
        with self.assertRaises(ensaio.EnsaioError):
            ensaio.cleanup_work_dir(self.cfg,'261001')
        self.assertTrue(self.work.exists())

    def test_limpeza_recusa_link_simbolico(self):
        # Links simbólicos no Windows podem depender de permissão; pular se não suportado.
        shutil=__import__('shutil')
        shutil.rmtree(self.work)
        target=self.root/'target';target.mkdir()
        (target/'keep.wav').write_bytes(b'keep')
        try:self.work.symlink_to(target,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlink indisponível')
        with self.assertRaises(ensaio.EnsaioError):
            ensaio.cleanup_work_dir(self.cfg,'261001')
        self.assertEqual((target/'keep.wav').read_bytes(),b'keep')

    def test_reparacao_manifesto_aponta_para_novo_master(self):
        manifest=self.root/'manifesto.json'
        manifest.write_text(json.dumps({'data_codigo':'261001','master':'old',
            'arquivos_brutos':[str(self.original)]}),encoding='utf-8')
        result=ensaio.repair_manifest_paths(self.cfg,manifest)
        self.assertEqual(result['master'],str((self.work/'master.wav').resolve()))

    def test_falha_de_finalizacao_preserva_intermediarios(self):
        self.cfg.pasta_revisao.mkdir(exist_ok=True,parents=True)
        manifest=self.cfg.pasta_revisao/'manifesto.json'
        manifest.write_text(json.dumps({'data_codigo':'261001','master':str(self.work/'master.wav'),
            'arquivos_brutos':[str(self.original)]}),encoding='utf-8')
        (self.cfg.pasta_revisao/'segmentos.csv').write_text('dummy',encoding='utf-8')
        with patch.object(ensaio,'check_dependencies'), patch.object(ensaio,'read_review_csv',return_value=[]), \
             patch.object(ensaio,'media_duration',return_value=100), \
             patch.object(ensaio,'validate_selected_segments'), \
             patch.object(ensaio,'extract_selected_segments',side_effect=ensaio.EnsaioError('falha simulada')):
            with self.assertRaises(ensaio.EnsaioError):
                ensaio.command_finalize(self.cfg,verbose=False,no_move=False)
        self.assertTrue((self.work/'master.wav').exists())
        self.assertTrue(self.original.exists())

    def test_finalizacao_sucesso_move_brutos_e_apaga_apenas_temporarios(self):
        original_bruto=self.cfg.pasta_brutas/'261001_0308.wav'
        original_bruto.write_bytes(b'new raw')
        self.cfg.pasta_revisao.mkdir(exist_ok=True,parents=True)
        (self.cfg.pasta_revisao/'manifesto.json').write_text(json.dumps({
            'data_codigo':'261001','master':str(self.work/'master.wav'),
            'arquivos_brutos':[str(original_bruto)]}),encoding='utf-8')
        (self.cfg.pasta_revisao/'segmentos.csv').write_text('dummy')
        selected=[ensaio.Segment(ordem=1,inicio_bruto=0,fim_bruto=60,
                 inicio_corte=0,fim_corte=60,duracao=60,incluir=True,
                 titulo='Teste',classificacao='musica')]
        def fake_extract(cfg,master,segments,work):
            p=work/'parte.wav';p.write_bytes(b'part');return [p]
        def fake_concat(cfg,paths,out):out.write_bytes(b'audio')
        def fake_video(cfg,audio,video):video.write_bytes(b'video')
        with patch.object(ensaio,'check_dependencies'), \
             patch.object(ensaio,'read_review_csv',return_value=selected), \
             patch.object(ensaio,'media_duration',return_value=60), \
             patch.object(ensaio,'validate_selected_segments'), \
             patch.object(ensaio,'extract_selected_segments',side_effect=fake_extract), \
             patch.object(ensaio,'concatenate_wavs',side_effect=fake_concat), \
             patch.object(ensaio,'create_static_video',side_effect=fake_video), \
             patch.object(ensaio,'verify_final_files'), \
             patch.object(ensaio,'incorporate_selected_references',return_value=(0,0)):
            ensaio.command_finalize(self.cfg,verbose=False,no_move=False)
        self.assertFalse(self.work.exists())
        self.assertFalse(original_bruto.exists())
        self.assertTrue((self.cfg.pasta_processadas/'2026-10-01'/original_bruto.name).exists())
        self.assertTrue((self.cfg.pasta_output/'Ensaio.26.10.01.mp4').exists())
        self.assertTrue(self.reference.exists())

    def test_reanalise_nao_apaga_trabalho_ativo(self):
        self.cfg.pasta_revisao.mkdir(exist_ok=True,parents=True)
        (self.cfg.pasta_revisao/'manifesto.json').write_text(json.dumps({'data_codigo':'261001'}))
        with patch.object(ensaio,'check_dependencies'),patch.object(ensaio,'discover_raw_files',return_value=([], '261001')):
            with self.assertRaises(ensaio.EnsaioError):
                ensaio.command_analyze(self.cfg,verbose=False,no_previews=True)
        self.assertTrue((self.work/'master.wav').exists())

if __name__=='__main__':unittest.main()
