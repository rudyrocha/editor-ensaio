"""Testes NAO DESTRUTIVOS: usam apenas TemporaryDirectory.

Executar numa COPIA de codigo v3.3.0. Fonte via ENSAIO_SOURCE_DIR ou ao lado de tests/.
Nao aponta para D: nem instala dependencias e nao exige FFmpeg.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(os.environ.get('ENSAIO_SOURCE_DIR', str(Path(__file__).resolve().parent.parent / 'app'))).resolve()
if not (SRC / 'ensaio.py').is_file():
    raise RuntimeError('Coloque a pasta tests junto a ensaio.py (em COPIA de teste) ou configure ENSAIO_SOURCE_DIR.')
sys.path.insert(0, str(SRC))
import ensaio  # noqa: E402


def cfg(root: Path) -> ensaio.Config:
    return ensaio.Config(
        raiz=root, pasta_brutas=root/'brutas', pasta_processadas=root/'processadas',
        pasta_referencias=root/'referencias', pasta_output=root/'output',
        pasta_revisao=root/'_sistema'/'revisao', pasta_trabalho=root/'processadas',
        pasta_dados=root/'_sistema'/'dados', pasta_aprendizado=root/'_sistema'/'dados'/'aprendizado',
        logo=root/'_sistema'/'assets'/'Logo.jpg')


def seg(order=1, start=0., end=75., title='Boa Viagem', quality='boa', obs='') -> ensaio.Segment:
    return ensaio.Segment(
        ordem=order, inicio_bruto=start, fim_bruto=end, inicio_corte=start, fim_corte=end,
        duracao=end-start, incluir=True, titulo=title, classificacao='musica',
        qualidade=quality, observacao=obs, inicio_corte_original=start, fim_corte_original=end,
    )


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_01_roundtrip_csv_observacao_e_decimais(self):
        a = seg(start=1.25, end=77.75, obs='Entrou atrasado no refrão')
        a.ajuste_inicio = 1.25
        p = self.root/'segmentos.csv'
        ensaio.write_review_csv(p, [a])
        content = p.read_text(encoding='utf-8-sig')
        self.assertIn('1,250', content)
        self.assertIn(';', content)
        loaded = ensaio.read_review_csv(p)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].observacao, a.observacao)
        self.assertAlmostEqual(loaded[0].inicio_corte, 1.25)

    def test_02_capitulos_duracao_qualidade(self):
        p = self.root/'capitulos.txt'
        ensaio.write_chapters(p, [seg(end=75), seg(order=2, start=75, end=170, title='Bohemia', quality='com erros')])
        lines = p.read_text(encoding='utf-8').splitlines()
        self.assertEqual(lines[0], '00:00 Boa Viagem — boa (1m15)')
        self.assertEqual(lines[1], '01:15 Bohemia — com erros (1m35)')

    def test_03_descricao_observacoes_na_linha_do_capitulo(self):
        p = self.root/'descricao.txt'
        ensaio.write_video_description(p, [seg(end=75, obs='Erro no refrão')])
        content = p.read_text(encoding='utf-8')
        self.assertTrue(content.startswith('00:00 Boa Viagem — boa · Erro no refrão (1m15)\n'))
        self.assertNotIn('Observações:', content)

    def test_04_descricao_sem_observacoes(self):
        p = self.root/'descricao.txt'
        ensaio.write_video_description(p, [seg()])
        self.assertNotIn('Observações:', p.read_text(encoding='utf-8'))

    def test_05_reparar_manifesto_apos_migracao(self):
        c = cfg(self.root)
        master = ensaio.work_dir_for_date(c,'261001')/'master.wav'
        master.parent.mkdir(parents=True)
        master.write_bytes(b'fake master; no audio processing')
        raw = c.pasta_brutas/'261001_0307.wav'
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b'fake input')
        p = self.root/'manifesto.json'
        p.write_text(json.dumps({'app_version':'3.0','data_codigo':'261001',
            'arquivos_brutos':[r'D:\OFFline\Videos\@ensaio\wk\brutas\261001_0307.wav'],
            'master':r'D:\OFFline\Videos\@ensaio\wk\.trabalho\261001\master.wav',
            'duracao_master':200.0}),encoding='utf-8')
        m = ensaio.repair_manifest_paths(c,p)
        self.assertEqual(Path(m['master']),master)
        self.assertEqual(Path(m['arquivos_brutos'][0]),raw)
        self.assertIn('caminhos_reparados_em',m)
        self.assertEqual(m, json.loads(p.read_text(encoding='utf-8')))

    def test_06_reparar_manifesto_idempotente(self):
        c=cfg(self.root)
        master=ensaio.work_dir_for_date(c,'261001')/'master.wav'
        master.parent.mkdir(parents=True)
        master.write_bytes(b'a')
        p=self.root/'manifesto.json'
        p.write_text(json.dumps({'data_codigo':'261001','master':'old.wav','arquivos_brutos':[]}), encoding='utf-8')
        ensaio.repair_manifest_paths(c,p)
        first=p.read_bytes()
        ensaio.repair_manifest_paths(c,p)
        self.assertEqual(first,p.read_bytes())

    def test_07_rejeita_sobreposicao(self):
        with self.assertRaises(ensaio.EnsaioError):
            ensaio.validate_selected_segments([seg(end=75),seg(order=2,start=74,end=100)],200)

    def test_08_rejeita_fora_do_master(self):
        with self.assertRaises(ensaio.EnsaioError):
            ensaio.validate_selected_segments([seg(start=0,end=201)],200)

    def test_09_nomes_arquivo_com_data(self):
        self.assertEqual(ensaio.output_basename('261001'),'Ensaio.26.10.01')

    def test_10_nao_exclui_brutos_em_regressao(self):
        c=cfg(self.root)
        raw=c.pasta_brutas/'261001_0307.wav'
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b'a')
        self.assertTrue(raw.exists())
        # Testes nao invocam archive_raw_files e nao mexem em D:.

if __name__=='__main__': unittest.main(verbosity=2)