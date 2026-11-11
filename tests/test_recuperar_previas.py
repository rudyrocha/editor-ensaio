"""Testes não destrutivos com dados sintéticos (sem arquivos pessoais)."""
from __future__ import annotations
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'app'))
from recuperar_previas import recover, prepare_rows

class TestRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.master=self.root/'master.wav'
        self.master.write_bytes(b'fake master')
        (self.root/'manifesto.json').write_text(json.dumps({'data_codigo':'261106','duracao_master':900}),encoding='utf-8')
        with (self.root/'segmentos.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['ordem','inicio_corte','fim_corte','inicio_bruto'],delimiter=';')
            w.writeheader()
            w.writerows([
                {'ordem':'1','inicio_corte':'10,000','fim_corte':'60,000','inicio_bruto':'15,000'},
                {'ordem':'2','inicio_corte':'100,000','fim_corte':'180,000','inicio_bruto':'105,000'},
                {'ordem':'3','inicio_corte':'200,000','fim_corte':'800,000','inicio_bruto':'200,000'},
            ])
        (self.root/'previews_web.json').write_text('[{"ordem": 1, "arquivo": "001.mp3"}]',encoding='utf-8')
        self.csv_before=(self.root/'segmentos.csv').read_bytes()
        self.index_before=(self.root/'previews_web.json').read_bytes()
    def fake_run(self,cmd,**kwargs):
        self.assertIn('-nostdin',cmd)
        Path(cmd[-1]).write_bytes(b'mock mp3')
        return SimpleNamespace(returncode=0,stderr=b'')
    def test_recover_publishes_three_unique_previews(self):
        info=recover(self.root,self.master,run=self.fake_run)
        self.assertEqual(info['faixas'],3)
        rows=json.loads((self.root/'previews_web.json').read_text())
        self.assertEqual([x['ordem'] for x in rows],[1,2,3])
        self.assertEqual(rows[2]['offset_inicio_corte'],20)
        self.assertEqual(len({r['arquivo'] for r in rows}),3)
        self.assertTrue(all((self.root/'previews_web'/r['arquivo']).exists() for r in rows))
        self.assertEqual((self.root/'segmentos.csv').read_bytes(),self.csv_before)
        self.assertEqual(len(list(self.root.glob('historico_recuperacao/*/segmentos.csv'))),1)
    def test_failed_ffmpeg_never_changes_index_or_csv(self):
        calls=[0]
        def fail_on_second(cmd,**kwargs):
            calls[0]+=1
            return SimpleNamespace(returncode=1,stderr=b'failure') if calls[0]==2 else self.fake_run(cmd,**kwargs)
        with self.assertRaisesRegex(RuntimeError,'faixa 2'):
            recover(self.root,self.master,run=fail_on_second)
        self.assertEqual((self.root/'previews_web.json').read_bytes(),self.index_before)
        self.assertEqual((self.root/'segmentos.csv').read_bytes(),self.csv_before)
    def test_missing_master_does_not_change_anything(self):
        self.master.unlink()
        with self.assertRaisesRegex(RuntimeError,'mestre'):
            recover(self.root,self.master,run=self.fake_run)
        self.assertEqual((self.root/'previews_web.json').read_bytes(),self.index_before)
    def test_rejects_overlapping_and_invalid_duration(self):
        rows=prepare_rows(self.root/'segmentos.csv',900)
        self.assertEqual(len(rows),3)
        with self.assertRaisesRegex(RuntimeError,'Tempo inválido'):
            prepare_rows(self.root/'segmentos.csv',100)

if __name__=='__main__':unittest.main(verbosity=2)