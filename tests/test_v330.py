"""Regressão não destrutiva das mudanças de UI, previews e saída (v3.3.0)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'app'))
import ensaio
import revisao_web


def config(root):
    return ensaio.Config(
        raiz=root, pasta_brutas=root/'brutas', pasta_processadas=root/'processadas',
        pasta_referencias=root/'referencias', pasta_output=root/'output',
        pasta_revisao=root/'_sistema'/'revisao', pasta_trabalho=root/'processadas',
        pasta_dados=root/'_sistema'/'dados', pasta_aprendizado=root/'_sistema'/'dados'/'aprendizado',
        logo=root/'logo.jpg'
    )


def segment(order=1, title='Boa Viagem', observation='', quality='', start=0., end=90.):
    return ensaio.Segment(ordem=order, inicio_bruto=start, fim_bruto=end,
        inicio_corte=start, fim_corte=end, duracao=end-start, incluir=True,
        titulo=title, classificacao='musica', observacao=observation, qualidade=quality,
        inicio_corte_original=start, fim_corte_original=end)


class TestsV330(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.cfg=config(self.root)
        ensaio.ensure_directories(self.cfg)
        self.work=ensaio.work_dir_for_date(self.cfg,'261106')
        self.work.mkdir(parents=True)
        self.master=self.work/'master.wav'
        self.master.write_bytes(b'master')

    def test_qualidade_opcional_no_csv_e_na_finalizacao(self):
        csv=self.cfg.pasta_revisao/'segmentos.csv'
        ensaio.write_review_csv(csv,[segment(quality='')])
        parsed=ensaio.read_review_csv(csv)
        self.assertEqual(len(parsed),1)
        self.assertEqual(parsed[0].qualidade,'')

    def test_comentarios_na_mesma_linha_do_capitulo(self):
        path=self.root/'descricao.txt'
        ensaio.write_video_description(path,[segment(observation='Erro no solo'),segment(2,'Boemia','',start=90,end=160)])
        text=path.read_text()
        self.assertIn('00:00 Boa Viagem — Erro no solo (1m30)',text)
        self.assertIn('01:30 Boemia (1m10)',text)
        self.assertNotIn('Observações:',text)

    def test_terceira_sugestao_persistida_e_leitura_legado(self):
        csv=self.root/'segmentos.csv'
        s=segment();s.terceira_opcao='Universo Mental';s.score_terceira_opcao=.65
        ensaio.write_review_csv(csv,[s])
        self.assertEqual(ensaio.read_review_csv(csv)[0].terceira_opcao,'Universo Mental')
        # Arquivos CSV anteriores não possuíam as duas colunas novas.
        text=csv.read_text(encoding='utf-8-sig')
        lines=[line for line in text.splitlines() if line]
        header=lines[0].split(';');data=lines[1].split(';')
        for field in ('terceira_opcao','score_terceira_opcao'):
            pos=header.index(field);header.pop(pos);data.pop(pos)
        csv.write_text(';'.join(header)+'\n'+';'.join(data)+'\n',encoding='utf-8-sig')
        old=ensaio.read_review_csv(csv)[0]
        self.assertEqual(old.terceira_opcao,'')

    def test_previews_gerados_sem_sobrescrever_mp3_aberto(self):
        p=self.cfg.pasta_revisao/'previews_web';p.mkdir(parents=True)
        old=p/'001.mp3';old.write_bytes(b'old')
        idx=self.cfg.pasta_revisao/'previews_web.json'
        idx.write_text(json.dumps([{'ordem':1,'arquivo':'001.mp3'}]),encoding='utf-8')
        def fake_ffmpeg(cmd,*,capture=False):
            Path(cmd[-1]).write_bytes(b'new mp3')
        with patch.object(ensaio,'media_duration',return_value=120),\
             patch.object(ensaio,'run_command',side_effect=fake_ffmpeg),\
             patch.object(Path,'unlink',autospec=True) as unlink:
            ensaio.create_previews(self.cfg,self.master,[segment()])
            # A limpeza antiga pode falhar, mas a atualização deve funcionar.
            new_index=json.loads(idx.read_text())
            self.assertNotEqual(new_index[0]['arquivo'],'001.mp3')
            self.assertTrue((p/new_index[0]['arquivo']).exists())
            self.assertTrue(old.exists())
        self.assertIn('previews_web',str(p))

    def test_falha_de_ffmpeg_mantem_indice_antigo(self):
        idx=self.cfg.pasta_revisao/'previews_web.json';idx.write_text('[{"ordem":1,"arquivo":"001.mp3"}]')
        with patch.object(ensaio,'media_duration',return_value=120),patch.object(ensaio,'run_command',side_effect=ensaio.EnsaioError('ffmpeg falhou')):
            with self.assertRaises(ensaio.EnsaioError):
                ensaio.create_previews(self.cfg,self.master,[segment()])
        self.assertIn('001.mp3',idx.read_text())

    def test_saida_apenas_mp4_e_descricao_com_relatorio_interno(self):
        src=self.cfg.pasta_brutas/'261106_001.wav';src.write_bytes(b'raw')
        revision=self.cfg.pasta_revisao
        ensaio.write_review_csv(revision/'segmentos.csv',[segment(quality='')])
        (revision/'manifesto.json').write_text(json.dumps({
            'data_codigo':'261106','master':str(self.master),
            'arquivos_brutos':[str(src)],'duracao_master':90}),encoding='utf-8')
        def extract(cfg,master,selected,work):
            f=work/'part.wav';f.write_bytes(b'part');return [f]
        def concatenate(cfg,files,target):target.write_bytes(b'final')
        def movie(cfg,source,target):target.write_bytes(b'mp4')
        with patch.object(ensaio,'check_dependencies'),patch.object(ensaio,'media_duration',return_value=90),\
             patch.object(ensaio,'extract_selected_segments',side_effect=extract),\
             patch.object(ensaio,'concatenate_wavs',side_effect=concatenate),\
             patch.object(ensaio,'create_static_video',side_effect=movie),\
             patch.object(ensaio,'incorporate_selected_references',return_value=(0,0)):
            ensaio.command_finalize(self.cfg,verbose=False,no_move=False)
        self.assertEqual(sorted(x.name for x in self.cfg.pasta_output.iterdir()),
                         ['Ensaio.26.11.06.descricao.txt','Ensaio.26.11.06.mp4'])
        self.assertTrue((self.cfg.pasta_dados/'relatorios'/'Ensaio.26.11.06.segmentos.csv').exists())
        self.assertFalse(self.work.exists())
        self.assertTrue((self.cfg.pasta_processadas/'2026-11-06'/src.name).exists())

    def test_corte_longo_sem_limite_artificial_e_qualidade_opcional(self):
        review=self.cfg.pasta_revisao
        ensaio.write_review_csv(review/'segmentos.csv',[segment(start=0,end=1400,quality='')])
        (review/'manifesto.json').write_text(json.dumps({'data_codigo':'261106',
            'master':str(self.master),'arquivos_brutos':[], 'duracao_master':1500}),encoding='utf-8')
        state=revisao_web.AppState(self.root/'app',self.cfg)
        result=state.save_review({'segmentos':[{'ordem':1,'incluir':True,
            'titulo':'Boa Viagem','qualidade':'','ajuste_inicio':300,'ajuste_fim':0,
            'observacao':'', 'usar_como_referencia':False}]})
        self.assertTrue(result['ok'])
        saved=ensaio.read_review_csv(review/'segmentos.csv')[0]
        self.assertEqual(saved.inicio_corte,300)

    def test_divisao_nao_gravada_se_previa_falha(self):
        review=self.cfg.pasta_revisao
        ensaio.write_review_csv(review/'segmentos.csv',[segment(start=0,end=1200)])
        (review/'manifesto.json').write_text(json.dumps({'data_codigo':'261106',
            'master':str(self.master),'arquivos_brutos':[], 'duracao_master':1200}),encoding='utf-8')
        state=revisao_web.AppState(self.root/'app',self.cfg)
        with patch.object(ensaio,'create_previews',side_effect=ensaio.EnsaioError('MP3 não gerado')):
            with self.assertRaises(ensaio.EnsaioError):
                state.split_segment({'segmentos':[{'ordem':1,'incluir':True,'titulo':'Boa Viagem',
                    'qualidade':'','ajuste_inicio':0,'ajuste_fim':0,
                    'observacao':'','usar_como_referencia':False}],
                    'ordem':1,'ponto_master':300})
        rows=ensaio.read_review_csv(review/'segmentos.csv')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].fim_corte,1200)

    def test_comandos_ffmpeg_ignorando_teclado(self):
        with patch.object(ensaio.subprocess,'run') as run:
            ensaio.run_command(['ffmpeg','-version'],capture=True)
            args=run.call_args.args[0]
            self.assertIn('-nostdin',args)
            self.assertEqual(run.call_args.kwargs['stdin'],ensaio.subprocess.DEVNULL)

if __name__=='__main__': unittest.main()
