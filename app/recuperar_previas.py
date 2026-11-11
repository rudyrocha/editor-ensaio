#!/usr/bin/env python3
"""Recupera prévias da revisão sem alterar segmentos, manifesto ou referências.

Instalação: copiar para _sistema/app e executar via python do ambiente virtual.
Os MP3 novos usam nomes exclusivos. O índice é substituído apenas ao fim.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def number(value: str, field: str) -> float:
    try:
        return float(str(value).strip().replace(',', '.'))
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f'Valor inválido no campo {field}: {value!r}') from exc


def prepare_rows(csv_path: Path, master_duration: float, before: float = 20.0, after: float = 20.0) -> list[dict]:
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        segments = list(csv.DictReader(handle, delimiter=';'))
    if not segments:
        raise RuntimeError('segmentos.csv está vazio')
    result = []
    seen = set()
    for segment in segments:
        order = int(segment['ordem'])
        if order <= 0 or order in seen:
            raise RuntimeError(f'Número de faixa duplicado ou inválido: {order}')
        seen.add(order)
        start = number(segment['inicio_corte'], f'inicio_corte faixa {order}')
        end = number(segment['fim_corte'], f'fim_corte faixa {order}')
        if not (0 <= start < end <= master_duration + 0.25):
            raise RuntimeError(f'Tempo inválido na faixa {order}: {start}–{end}')
        origin = number(segment.get('inicio_bruto') or str(start), f'inicio_bruto faixa {order}')
        first = max(0.0, start - before)
        last = min(master_duration, end + after)
        if not first < last:
            raise RuntimeError(f'Prévia sem duração na faixa {order}')
        result.append({
            'ordem': order,
            'inicio_preview_master': first,
            'fim_preview_master': last,
            'offset_inicio_corte': start-first,
            'offset_fim_corte': end-first,
            'duration': last-first,
        })
    result.sort(key=lambda r: r['ordem'])
    return result


def recover(
    revision: Path,
    master: Path,
    ffmpeg: str = 'ffmpeg',
    margin_before: float = 20.0,
    margin_after: float = 20.0,
    bitrate: str = '128k',
    run=None,
    now=None,
) -> dict:
    """Gera nova coleção de prévias em diretório versionado e publica índice atomicamente.

    Em caso de erro não altera o índice existente. Não remove arquivos anteriores.
    """
    revision = Path(revision)
    master = Path(master)
    if not master.is_file():
        raise RuntimeError(f'Áudio mestre não encontrado: {master}')
    manifest_path = revision / 'manifesto.json'
    csv_path = revision / 'segmentos.csv'
    index_path = revision / 'previews_web.json'
    if not manifest_path.is_file() or not csv_path.is_file():
        raise RuntimeError('A revisão precisa conter manifesto.json e segmentos.csv')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    duration = float(manifest['duracao_master'])
    rows = prepare_rows(csv_path, duration, margin_before, margin_after)
    start_time = now or datetime.now()
    stamp = start_time.strftime('%Y%m%d_%H%M%S_%f')
    old_dir = revision / 'previews_web'
    old_dir.mkdir(parents=True, exist_ok=True)
    # Nomes exclusivos impedem sobrescrita dos MP3 em uso no navegador.
    backup_dir = revision / 'historico_recuperacao' / stamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    for src in (manifest_path, csv_path, index_path):
        if src.is_file():
            shutil.copy2(src, backup_dir / src.name)
    runner = run or subprocess.run
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    pending_index = revision / ('.previews_web_' + stamp + '.tmp')
    try:
        for row in rows:
            filename = f"{row['ordem']:03d}_rec_{stamp}.mp3"
            # O servidor HTTP aceita apenas arquivos diretamente em previews_web/.
            destination = old_dir / filename
            cmd = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                   '-ss', f"{row['inicio_preview_master']:.6f}",
                   '-to', f"{row['fim_preview_master']:.6f}",
                   '-i', str(master), '-vn', '-c:a', 'libmp3lame', '-b:a', bitrate,
                   str(destination)]
            proc = runner(cmd, check=False, stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          creationflags=flags)
            if proc.returncode != 0:
                detail = (proc.stderr or b'').decode('utf-8', errors='replace')[-1200:]
                raise RuntimeError(f'FFmpeg falhou na faixa {row["ordem"]}: {detail}')
            if not destination.exists() or destination.stat().st_size == 0:
                raise RuntimeError(f'FFmpeg não gerou a prévia da faixa {row["ordem"]}')
            row['arquivo'] = filename
            row.pop('duration', None)
            print(f'Prévia {row["ordem"]}/{len(rows)} gerada', flush=True)
        pending_index.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(pending_index, index_path)
        return {'faixas': len(rows), 'backup': str(backup_dir), 'indice': str(index_path)}
    finally:
        try:
            pending_index.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    app = Path(__file__).resolve().parent
    revision = app.parent / 'revisao'
    config = json.loads((app / 'config.json').read_text(encoding='utf-8-sig'))
    manifest = json.loads((revision / 'manifesto.json').read_text(encoding='utf-8-sig'))
    master = Path(manifest['master'])
    # A recuperação requer o master original, nunca inicia uma nova análise.
    if not master.exists():
        print(f'ERRO: master.wav não encontrado em {master}')
        return 2
    try:
        result = recover(revision, master,
            ffmpeg=str(config.get('ffmpeg', 'ffmpeg')),
            margin_before=float(config.get('ui_preview_margin_seconds', 20.0)),
            margin_after=float(config.get('ui_preview_margin_seconds', 20.0)),
            bitrate=str(config.get('preview_bitrate', '128k')))
        print(f"SUCESSO: {result['faixas']} prévias regeneradas.")
        print(f"Backup da revisão: {result['backup']}")
        print('Reabra o Editor e atualize a página com Ctrl+F5.')
        return 0
    except Exception as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        print('O CSV, o manifesto e o índice anterior foram preservados.')
        return 2


if __name__ == '__main__':
    sys.exit(main())