#!/usr/bin/env python3
"""Interface web local para revisar e finalizar ensaios.

Não envia dados para a internet. Usa apenas 127.0.0.1 e a biblioteca padrão.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

import ensaio

QUALIDADES = ["com muitos erros", "com erros", "regular", "boa", "ótima"]
DEFAULT_SONGS = [
    "Bohemia",
    "Não é Não",
    "Cadê Você",
    "Guerra Santa",
    "Brasileiro Vira Lata",
    "Boa Viagem",
    "Universo é Mental",
    "Bússola do Tempo",
    "Sonho ou Realidade",
    "O Cultivista",
    "Planta de Poder",
    "Respeitar",
    "Hipótese Nula",
    "Até quando?",
]


class ReviewError(RuntimeError):
    pass


def normalize_title(value: str) -> str:
    return ensaio.normalize_title(value)


class AppState:
    def __init__(self, script_dir: Path, cfg: ensaio.Config, config_path: Path | None = None):
        self.script_dir = script_dir
        self.cfg = cfg
        self.config_path = (config_path or (script_dir / "config.json")).resolve()
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.process_kind: str | None = None
        self.log_handle = None
        self.started_at: float | None = None
        self.last_return_code: int | None = None
        self.log_path = cfg.pasta_revisao / "finalizacao_web.log"
        self.song_path = cfg.pasta_dados / "musicas.json"
        self.learning_dir = cfg.pasta_aprendizado
        self.learning_jsonl = self.learning_dir / "ajustes_cortes.jsonl"
        self.learning_csv = self.learning_dir / "ajustes_cortes.csv"
        self.identification_jsonl = self.learning_dir / "identificacoes.jsonl"
        self.identification_csv = self.learning_dir / "identificacoes.csv"
        self.pending_learning_payload: dict | None = None
        self.learning_logged = False
        self.ensure_song_file()

    def ensure_song_file(self) -> None:
        self.song_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.song_path.exists():
            self.write_songs(DEFAULT_SONGS)

    def read_songs(self) -> list[str]:
        self.ensure_song_file()
        try:
            data = json.loads(self.song_path.read_text(encoding="utf-8"))
            values = data.get("musicas", []) if isinstance(data, dict) else data
            songs = [str(item).strip() for item in values if str(item).strip()]
        except Exception as exc:
            raise ReviewError(f"Não foi possível ler {self.song_path}: {exc}") from exc
        unique: list[str] = []
        seen: set[str] = set()
        for title in songs:
            key = normalize_title(title)
            if key and key not in seen:
                seen.add(key)
                unique.append(title)
        return unique

    def write_songs(self, songs: list[str]) -> None:
        payload = {"musicas": songs}
        self.song_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def add_songs(self, additions: list[str]) -> list[str]:
        songs = self.read_songs()
        known = {normalize_title(item) for item in songs}
        changed = False
        for title in additions:
            clean = title.strip()
            key = normalize_title(clean)
            if clean and key and key not in known:
                songs.append(clean)
                known.add(key)
                changed = True
        if changed:
            self.write_songs(songs)
        return songs

    def preview_index(self) -> dict[int, dict]:
        path = self.cfg.pasta_revisao / "previews_web.json"
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))
            return {int(row["ordem"]): row for row in rows}
        result = {}
        for audio in sorted((self.cfg.pasta_revisao / "previews").glob("*.mp3")):
            try:
                order = int(audio.name.split("_", 1)[0])
            except ValueError:
                continue
            result[order] = {
                "ordem": order,
                "arquivo": audio.name,
                "inicio_preview_master": 0.0,
                "fim_preview_master": 0.0,
                "offset_inicio_corte": 0.0,
                "offset_fim_corte": 0.0,
                "legacy": True,
            }
        return result

    def load_payload(self) -> dict:
        manifest_path = self.cfg.pasta_revisao / "manifesto.json"
        manifest = ensaio.load_manifest(manifest_path)
        segments = ensaio.read_all_review_rows(self.cfg.pasta_revisao / "segmentos.csv")
        previews = self.preview_index()
        items = []
        for segment in sorted(segments, key=lambda item: item.ordem):
            original_start = (
                segment.inicio_corte_original
                if segment.inicio_corte_original is not None
                else segment.inicio_corte
            )
            original_end = (
                segment.fim_corte_original
                if segment.fim_corte_original is not None
                else segment.fim_corte
            )
            preview = previews.get(segment.ordem, {})
            items.append({
                "ordem": segment.ordem,
                "incluir": segment.incluir,
                "titulo": segment.titulo,
                "qualidade": segment.qualidade,
                "usar_como_referencia": segment.usar_como_referencia,
                "inicio_corte_original": original_start,
                "fim_corte_original": original_end,
                "inicio_corte": segment.inicio_corte,
                "fim_corte": segment.fim_corte,
                "ajuste_inicio": segment.ajuste_inicio,
                "ajuste_fim": segment.ajuste_fim,
                "duracao": segment.fim_corte - segment.inicio_corte,
                "inicio_bruto": segment.inicio_bruto,
                "fim_bruto": segment.fim_bruto,
                "classificacao": segment.classificacao,
                "observacao": segment.observacao,
                "titulo_sugerido": segment.titulo_sugerido,
                "score_identificacao": segment.score_identificacao,
                "segunda_opcao": segment.segunda_opcao,
                "score_segunda_opcao": segment.score_segunda_opcao,
                "identificacao_aplicada": segment.identificacao_aplicada,
                "audio_url": (
                    f"/audio/{preview.get('arquivo', '')}?v="
                    f"{(self.cfg.pasta_revisao / 'previews_web' / preview.get('arquivo', '')).stat().st_mtime_ns}"
                    if preview and (self.cfg.pasta_revisao / 'previews_web' / preview.get('arquivo', '')).exists()
                    else (f"/audio/{preview.get('arquivo', '')}" if preview else "")
                ),
                "preview": preview,
            })
        return {
            "app_version": ensaio.APP_VERSION,
            "data_codigo": manifest.get("data_codigo"),
            "data_exibicao": format_date(str(manifest.get("data_codigo", ""))),
            "duracao_master": float(manifest.get("duracao_master", 0.0)),
            "musicas": self.read_songs(),
            "qualidades": QUALIDADES,
            "segmentos": items,
            "mover_brutos_padrao": bool(self.cfg.move_raw_after_success),
            "arquivo_musicas": str(self.song_path),
        }

    def save_review(self, payload: dict, require_complete: bool = True) -> dict:
        incoming = payload.get("segmentos")
        if not isinstance(incoming, list):
            raise ReviewError("Dados de segmentos ausentes ou inválidos.")
        existing = ensaio.read_all_review_rows(self.cfg.pasta_revisao / "segmentos.csv")
        by_order = {item.ordem: item for item in existing}
        manifest = ensaio.load_manifest(self.cfg.pasta_revisao / "manifesto.json")
        master_duration = float(manifest.get("duracao_master", 0.0))
        additions: list[str] = []

        for row in incoming:
            try:
                order = int(row.get("ordem"))
            except Exception as exc:
                raise ReviewError("Número de faixa inválido.") from exc
            if order not in by_order:
                raise ReviewError(f"Faixa desconhecida: {order}.")
            segment = by_order[order]
            include = bool(row.get("incluir", False))
            title = str(row.get("titulo", "")).strip()
            quality = str(row.get("qualidade", "")).strip()
            if quality and quality not in QUALIDADES:
                raise ReviewError(f"Qualidade inválida na faixa {order}: {quality}.")
            try:
                delta_start = float(row.get("ajuste_inicio", 0.0))
                delta_end = float(row.get("ajuste_fim", 0.0))
            except (TypeError, ValueError) as exc:
                raise ReviewError(f"Ajuste de corte inválido na faixa {order}.") from exc
            if abs(delta_start) > 120 or abs(delta_end) > 120:
                raise ReviewError(
                    f"Ajustes da faixa {order} excedem 120 segundos. Verifique os valores."
                )
            original_start = (
                segment.inicio_corte_original
                if segment.inicio_corte_original is not None
                else segment.inicio_corte
            )
            original_end = (
                segment.fim_corte_original
                if segment.fim_corte_original is not None
                else segment.fim_corte
            )
            effective_start = original_start + delta_start
            effective_end = original_end - delta_end
            if effective_start < 0 or effective_end > master_duration + 0.25:
                raise ReviewError(
                    f"Os cortes da faixa {order} ficaram fora da gravação mestre."
                )
            if effective_end - effective_start < 1.0:
                raise ReviewError(f"A faixa {order} ficou com menos de 1 segundo.")
            if require_complete and include and not title:
                raise ReviewError(f"Informe o nome da faixa {order}.")
            if require_complete and include and not quality:
                raise ReviewError(f"Avalie a qualidade da faixa {order}.")

            segment.incluir = include
            segment.titulo = title
            segment.qualidade = quality
            segment.usar_como_referencia = bool(row.get("usar_como_referencia", False)) and include
            segment.inicio_corte_original = original_start
            segment.fim_corte_original = original_end
            segment.ajuste_inicio = delta_start
            segment.ajuste_fim = delta_end
            segment.inicio_corte = effective_start
            segment.fim_corte = effective_end
            segment.duracao = effective_end - effective_start
            segment.observacao = str(row.get("observacao", segment.observacao or "")).strip()
            if bool(row.get("adicionar_lista", False)) and title:
                additions.append(title)

        selected = sorted((item for item in existing if item.incluir), key=lambda item: item.ordem)
        if not selected:
            raise ReviewError("Mantenha pelo menos uma faixa no ensaio.")
        try:
            ensaio.validate_selected_segments(selected, master_duration)
        except ensaio.EnsaioError as exc:
            raise ReviewError(str(exc)) from exc

        review_path = self.cfg.pasta_revisao / "segmentos.csv"
        backup_dir = self.cfg.pasta_revisao / "historico_interface"
        backup_dir.mkdir(parents=True, exist_ok=True)
        if review_path.exists():
            stamp = time.strftime("%Y%m%d_%H%M%S")
            (backup_dir / f"segmentos_{stamp}.csv").write_bytes(review_path.read_bytes())
        ensaio.write_review_csv(review_path, sorted(existing, key=lambda item: item.ordem))
        songs = self.add_songs(additions)
        return {"ok": True, "mensagem": "Alterações salvas.", "musicas": songs}

    def _review_path(self) -> Path:
        return self.cfg.pasta_revisao / "segmentos.csv"

    def _backup_structure(self, label: str) -> None:
        path = self._review_path()
        if not path.exists():
            return
        backup_dir = self.cfg.pasta_revisao / "historico_estrutura"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        destination = backup_dir / f"segmentos_{stamp}_{label}.csv"
        counter = 1
        while destination.exists():
            destination = backup_dir / f"segmentos_{stamp}_{label}_{counter}.csv"
            counter += 1
        destination.write_bytes(path.read_bytes())

    def _master_audio(self) -> Path:
        manifest_path = self.cfg.pasta_revisao / "manifesto.json"
        manifest = ensaio.repair_manifest_paths(self.cfg, manifest_path)
        master_value = str(manifest.get("master", "")).strip()
        if master_value:
            master = Path(master_value)
            if master.exists():
                return master
        date_code = str(manifest.get("data_codigo", "")).strip()
        if not date_code:
            raise ReviewError("A data do ensaio não está disponível no manifesto.")
        return ensaio.source_master_for_date(self.cfg, date_code)

    def _write_structure(self, segments: list[ensaio.Segment], label: str) -> dict:
        ordered = sorted(segments, key=lambda item: (item.inicio_corte, item.fim_corte))
        for index, segment in enumerate(ordered, start=1):
            segment.ordem = index
            segment.duracao = segment.fim_corte - segment.inicio_corte
        manifest = ensaio.load_manifest(self.cfg.pasta_revisao / "manifesto.json")
        master_duration = float(manifest.get("duracao_master", 0.0))
        try:
            ensaio.validate_selected_segments(
                [item for item in ordered if item.incluir], master_duration
            )
        except ensaio.EnsaioError as exc:
            raise ReviewError(str(exc)) from exc
        # Preparar as novas prévias antes de confirmar a divisão/união no CSV.
        # Se o FFmpeg falhar, as identificações e cortes já salvos permanecem.
        ensaio.create_previews(self.cfg, self._master_audio(), ordered)
        self._backup_structure(label)
        ensaio.write_review_csv(self._review_path(), ordered)
        return self.load_payload()

    @staticmethod
    def _append_observation(current: str, message: str) -> str:
        current = (current or "").strip()
        return f"{current} | {message}" if current else message

    def split_segment(self, payload: dict) -> dict:
        self.save_review(payload, require_complete=False)
        try:
            order = int(payload.get("ordem"))
            split_at = float(payload.get("ponto_master"))
        except (TypeError, ValueError) as exc:
            raise ReviewError("Ponto de divisão inválido.") from exc
        segments = sorted(ensaio.read_all_review_rows(self._review_path()), key=lambda item: item.ordem)
        target_index = next((i for i, item in enumerate(segments) if item.ordem == order), None)
        if target_index is None:
            raise ReviewError(f"Faixa {order} não encontrada.")
        target = segments[target_index]
        if split_at <= target.inicio_corte + 1.0 or split_at >= target.fim_corte - 1.0:
            raise ReviewError("O ponto de divisão deve deixar pelo menos 1 segundo em cada parte.")
        stamp = ensaio.chapter_timestamp(split_at)
        first = replace(
            target,
            fim_bruto=min(max(split_at, target.inicio_bruto), target.fim_bruto),
            inicio_corte_original=target.inicio_corte,
            fim_corte_original=split_at,
            ajuste_inicio=0.0,
            ajuste_fim=0.0,
            inicio_corte=target.inicio_corte,
            fim_corte=split_at,
            duracao=split_at - target.inicio_corte,
            classificacao="dividido_manual",
            observacao=target.observacao,
        )
        second = replace(
            target,
            inicio_bruto=min(max(split_at, target.inicio_bruto), target.fim_bruto),
            inicio_corte_original=split_at,
            fim_corte_original=target.fim_corte,
            ajuste_inicio=0.0,
            ajuste_fim=0.0,
            inicio_corte=split_at,
            fim_corte=target.fim_corte,
            duracao=target.fim_corte - split_at,
            titulo="",
            qualidade="",
            usar_como_referencia=False,
            titulo_sugerido="",
            score_identificacao=0.0,
            segunda_opcao="",
            score_segunda_opcao=0.0,
            identificacao_aplicada=False,
            classificacao="dividido_manual",
            observacao="",
        )
        segments[target_index:target_index + 1] = [first, second]
        data = self._write_structure(segments, "dividir")
        return {
            "ok": True,
            "mensagem": "Faixa dividida. A primeira parte manteve os dados; identifique a segunda parte.",
            "foco_ordem": order,
            "dados": data,
        }

    def merge_segments(self, payload: dict) -> dict:
        self.save_review(payload, require_complete=False)
        try:
            order = int(payload.get("ordem"))
        except (TypeError, ValueError) as exc:
            raise ReviewError("Faixa para união inválida.") from exc
        segments = sorted(ensaio.read_all_review_rows(self._review_path()), key=lambda item: item.ordem)
        target_index = next((i for i, item in enumerate(segments) if item.ordem == order), None)
        if target_index is None:
            raise ReviewError(f"Faixa {order} não encontrada.")
        if target_index >= len(segments) - 1:
            raise ReviewError("A última faixa não pode ser unida a uma faixa seguinte.")
        first = segments[target_index]
        second = segments[target_index + 1]
        first_key = normalize_title(first.titulo)
        second_key = normalize_title(second.titulo)
        if first_key and second_key and first_key == second_key:
            title = first.titulo
        elif first_key and not second_key:
            title = first.titulo
        elif second_key and not first_key:
            title = second.titulo
        else:
            title = ""
        if first.qualidade == second.qualidade:
            quality = first.qualidade
        elif first.qualidade and not second.qualidade:
            quality = first.qualidade
        elif second.qualidade and not first.qualidade:
            quality = second.qualidade
        else:
            quality = ""
        same_named_song = bool(title and first_key and second_key and first_key == second_key)
        notes = [value.strip() for value in (first.observacao, second.observacao) if value and value.strip()]
        merged = replace(
            first,
            inicio_bruto=min(first.inicio_bruto, second.inicio_bruto),
            fim_bruto=max(first.fim_bruto, second.fim_bruto),
            inicio_corte_original=first.inicio_corte,
            fim_corte_original=second.fim_corte,
            ajuste_inicio=0.0,
            ajuste_fim=0.0,
            inicio_corte=first.inicio_corte,
            fim_corte=second.fim_corte,
            duracao=second.fim_corte - first.inicio_corte,
            incluir=first.incluir or second.incluir,
            titulo=title,
            qualidade=quality,
            usar_como_referencia=same_named_song and (first.usar_como_referencia or second.usar_como_referencia),
            classificacao="unido_manual",
            observacao=" | ".join(dict.fromkeys(notes)),
            titulo_sugerido="",
            score_identificacao=0.0,
            segunda_opcao="",
            score_segunda_opcao=0.0,
            identificacao_aplicada=False,
        )
        segments[target_index:target_index + 2] = [merged]
        data = self._write_structure(segments, "unir")
        message = "Faixas unidas."
        if not title and first.titulo and second.titulo and first_key != second_key:
            message += " Como os títulos eram diferentes, o título da faixa unida foi deixado em branco para confirmação."
        return {
            "ok": True,
            "mensagem": message,
            "foco_ordem": order,
            "dados": data,
        }

    def review_exists(self) -> bool:
        return (self.cfg.pasta_revisao / "manifesto.json").exists() and self._review_path().exists()

    def overview(self) -> dict:
        raw_files = sorted(
            [p for p in self.cfg.pasta_brutas.glob("*") if p.is_file() and p.suffix.lower() in ensaio.AUDIO_EXTENSIONS],
            key=lambda p: p.name.lower(),
        )
        current = None
        if self.review_exists():
            try:
                manifest = ensaio.load_manifest(self.cfg.pasta_revisao / "manifesto.json")
                current = {
                    "data_codigo": str(manifest.get("data_codigo", "")),
                    "data_exibicao": format_date(str(manifest.get("data_codigo", ""))),
                    "segmentos": len(ensaio.read_all_review_rows(self._review_path())),
                }
            except Exception:
                current = None
        pending_temporary = None
        if raw_files:
            try:
                _, date_code = ensaio.discover_raw_files(self.cfg)
                pending_dir = ensaio.work_dir_for_date(self.cfg, date_code)
                if pending_dir.is_dir() and any(pending_dir.iterdir()):
                    pending_temporary = str(pending_dir)
            except (ensaio.EnsaioError, OSError, ValueError):
                pass
        references = ensaio.read_reference_index(self.cfg.pasta_referencias / "referencias.csv")
        active_refs = [row for row in references if (row.get("ativa") or "SIM").strip().upper() in {"SIM", "S", "1", "TRUE"}]
        return {
            "app_version": ensaio.APP_VERSION,
            "brutos": [p.name for p in raw_files],
            "quantidade_brutos": len(raw_files),
            "revisao_disponivel": self.review_exists(),
            "revisao_atual": current,
            "temporarios_pendentes": pending_temporary,
            "referencias_ativas": len(active_refs),
            "musicas": len(self.read_songs()),
            "processo": self.process_kind,
        }

    def _start_subprocess(self, command: list[str], kind: str, log_name: str) -> None:
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ReviewError("Já existe uma operação em execução.")
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:
                    pass
            self.log_path = self.cfg.pasta_revisao / log_name
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_handle = self.log_path.open("w", encoding="utf-8", errors="replace")
            self.process = subprocess.Popen(
                command,
                cwd=str(self.script_dir),
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.process_kind = kind
            self.started_at = time.time()
            self.last_return_code = None

    def start_analysis(self, payload: dict | None = None) -> dict:
        raw_files = [p for p in self.cfg.pasta_brutas.glob("*") if p.is_file() and p.suffix.lower() in ensaio.AUDIO_EXTENSIONS]
        if not raw_files:
            raise ReviewError(f"Nenhum WAV encontrado em {self.cfg.pasta_brutas}.")
        command = [
            sys.executable, str(self.script_dir / "ensaio.py"), "analisar",
            "--config", str(self.config_path),
        ]
        if payload and payload.get("recomecar") is True:
            command.append("--recomecar")
        self.pending_learning_payload = None
        self.learning_logged = False
        self._start_subprocess(command, "analise", "analise_web.log")
        return {"ok": True, "iniciado": True, "tipo": "analise"}

    def reidentify(self, payload: dict) -> dict:
        if not self.review_exists():
            raise ReviewError("Não há uma análise atual para identificar.")
        if self.process and self.process.poll() is None:
            raise ReviewError("Aguarde a operação atual terminar.")
        if isinstance(payload.get("segmentos"), list):
            self.save_review(payload, require_complete=False)
        segments = ensaio.read_all_review_rows(self._review_path())
        master = self._master_audio()
        stats = ensaio.identify_segments_from_references(self.cfg, master, segments, apply_titles=True)
        ensaio.write_review_csv(self._review_path(), sorted(segments, key=lambda item: item.ordem))
        return {
            "ok": True,
            "mensagem": (
                f"Identificação concluída: {stats.get('segmentos', 0)} faixas comparadas; "
                f"{stats.get('aplicados', 0)} títulos preenchidos automaticamente."
            ),
            "estatisticas": stats,
            "dados": self.load_payload(),
        }

    def learning_parameters(self) -> dict:
        return {
            "pre_roll_seconds": self.cfg.pre_roll_seconds,
            "post_roll_seconds": self.cfg.post_roll_seconds,
            "analysis_frame_seconds": self.cfg.analysis_frame_seconds,
            "volume_threshold_db": self.cfg.volume_threshold_db,
            "min_threshold_db": self.cfg.min_threshold_db,
            "max_threshold_db": self.cfg.max_threshold_db,
            "onset_threshold_margin_db": self.cfg.onset_threshold_margin_db,
            "onset_window_seconds": self.cfg.onset_window_seconds,
            "onset_required_ratio": self.cfg.onset_required_ratio,
            "onset_min_consecutive_seconds": self.cfg.onset_min_consecutive_seconds,
            "onset_backtrack_seconds": self.cfg.onset_backtrack_seconds,
            "continuation_hysteresis_db": self.cfg.continuation_hysteresis_db,
            "music_end_no_high_seconds": self.cfg.music_end_no_high_seconds,
            "merge_gap_seconds": self.cfg.merge_gap_seconds,
            "recognition_enabled": self.cfg.recognition_enabled,
            "recognition_window_seconds": self.cfg.recognition_window_seconds,
            "recognition_auto_score": self.cfg.recognition_auto_score,
            "recognition_auto_margin": self.cfg.recognition_auto_margin,
        }

    def append_learning_log(self, payload: dict) -> None:
        manifest = ensaio.load_manifest(self.cfg.pasta_revisao / "manifesto.json")
        segments = ensaio.read_all_review_rows(self.cfg.pasta_revisao / "segmentos.csv")
        timestamp = datetime.now().isoformat(timespec="seconds")
        params = self.learning_parameters()
        self.learning_dir.mkdir(parents=True, exist_ok=True)

        existing_ids: set[str] = set()
        if self.learning_jsonl.exists():
            for line in self.learning_jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    existing_ids.add(str(json.loads(line).get("registro_id", "")))
                except Exception:
                    continue

        records: list[dict] = []
        for segment in sorted(segments, key=lambda item: item.ordem):
            original_start = segment.inicio_corte_original if segment.inicio_corte_original is not None else segment.inicio_corte
            original_end = segment.fim_corte_original if segment.fim_corte_original is not None else segment.fim_corte
            raw_key = "|".join([
                str(manifest.get("data_codigo", "")), str(segment.ordem), segment.titulo,
                f"{original_start:.6f}", f"{original_end:.6f}",
                f"{segment.inicio_corte:.6f}", f"{segment.fim_corte:.6f}",
            ])
            record_id = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:20]
            if record_id in existing_ids:
                continue
            records.append({
                "registro_id": record_id,
                "registrado_em": timestamp,
                "app_version": ensaio.APP_VERSION,
                "data_ensaio": manifest.get("data_codigo", ""),
                "ordem": segment.ordem,
                "titulo": segment.titulo,
                "incluir": segment.incluir,
                "qualidade": segment.qualidade,
                "usar_como_referencia": segment.usar_como_referencia,
                "classificacao": segment.classificacao,
                "inicio_bruto": segment.inicio_bruto,
                "fim_bruto": segment.fim_bruto,
                "inicio_sugerido": original_start,
                "fim_sugerido": original_end,
                "ajuste_inicio": segment.ajuste_inicio,
                "ajuste_fim": segment.ajuste_fim,
                "inicio_final": segment.inicio_corte,
                "fim_final": segment.fim_corte,
                "duracao_sugerida": original_end - original_start,
                "duracao_final": segment.fim_corte - segment.inicio_corte,
                "observacao": segment.observacao,
                "arquivos_brutos": manifest.get("arquivos_brutos", []),
                "parametros_algoritmo": params,
                "analise_volume": str(self.cfg.pasta_revisao / "analise_volume.csv"),
            })
            existing_ids.add(record_id)

        if not records:
            return
        with self.learning_jsonl.open("a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        fieldnames = [
            "registro_id", "registrado_em", "app_version", "data_ensaio", "ordem", "titulo",
            "incluir", "qualidade", "usar_como_referencia", "classificacao", "inicio_bruto",
            "fim_bruto", "inicio_sugerido", "fim_sugerido", "ajuste_inicio", "ajuste_fim",
            "inicio_final", "fim_final", "duracao_sugerida", "duracao_final", "observacao",
            "arquivos_brutos", "parametros_algoritmo", "analise_volume",
        ]
        write_header = not self.learning_csv.exists() or self.learning_csv.stat().st_size == 0
        with self.learning_csv.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            if write_header:
                writer.writeheader()
            for record in records:
                row = dict(record)
                for key in (
                    "inicio_bruto", "fim_bruto", "inicio_sugerido", "fim_sugerido",
                    "ajuste_inicio", "ajuste_fim", "inicio_final", "fim_final",
                    "duracao_sugerida", "duracao_final",
                ):
                    row[key] = f"{float(row[key]):.3f}".replace(".", ",")
                row["incluir"] = "SIM" if row["incluir"] else "NAO"
                row["usar_como_referencia"] = "SIM" if row["usar_como_referencia"] else "NAO"
                row["arquivos_brutos"] = json.dumps(row["arquivos_brutos"], ensure_ascii=False)
                row["parametros_algoritmo"] = json.dumps(row["parametros_algoritmo"], ensure_ascii=False, sort_keys=True)
                writer.writerow(row)

    def append_identification_feedback(self) -> None:
        if not self.review_exists():
            return
        manifest = ensaio.load_manifest(self.cfg.pasta_revisao / "manifesto.json")
        segments = ensaio.read_all_review_rows(self._review_path())
        records = []
        now = datetime.now().isoformat(timespec="seconds")
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        existing_ids: set[str] = set()
        if self.identification_jsonl.exists():
            for line in self.identification_jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    existing_ids.add(str(json.loads(line).get("registro_id", "")))
                except Exception:
                    continue
        for segment in sorted(segments, key=lambda item: item.ordem):
            suggested = (segment.titulo_sugerido or "").strip()
            final_title = (segment.titulo or "").strip()
            if not suggested or not final_title:
                continue
            correct = normalize_title(suggested) == normalize_title(final_title)
            raw_key = "|".join([
                str(manifest.get("data_codigo", "")), str(segment.ordem), suggested,
                f"{segment.score_identificacao:.6f}", final_title,
                f"{segment.inicio_corte:.3f}", f"{segment.fim_corte:.3f}",
            ])
            record_id = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:20]
            if record_id in existing_ids:
                continue
            records.append({
                "registro_id": record_id,
                "registrado_em": now,
                "app_version": ensaio.APP_VERSION,
                "data_ensaio": manifest.get("data_codigo", ""),
                "ordem": segment.ordem,
                "titulo_sugerido": suggested,
                "score_identificacao": segment.score_identificacao,
                "segunda_opcao": segment.segunda_opcao,
                "score_segunda_opcao": segment.score_segunda_opcao,
                "margem": segment.score_identificacao - segment.score_segunda_opcao,
                "identificacao_aplicada": segment.identificacao_aplicada,
                "titulo_final": final_title,
                "resultado": "correta" if correct else "corrigida",
                "incluir": segment.incluir,
                "usar_como_referencia": segment.usar_como_referencia,
                "qualidade": segment.qualidade,
                "classificacao": segment.classificacao,
            })
            existing_ids.add(record_id)
        if not records:
            return
        with self.identification_jsonl.open("a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        fields = [
            "registro_id", "registrado_em", "app_version", "data_ensaio", "ordem",
            "titulo_sugerido", "score_identificacao", "segunda_opcao", "score_segunda_opcao",
            "margem", "identificacao_aplicada", "titulo_final", "resultado", "incluir",
            "usar_como_referencia", "qualidade", "classificacao",
        ]
        write_header = not self.identification_csv.exists() or self.identification_csv.stat().st_size == 0
        with self.identification_csv.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            if write_header:
                writer.writeheader()
            for record in records:
                row = dict(record)
                for key in ("score_identificacao", "score_segunda_opcao", "margem"):
                    row[key] = f"{float(row[key]):.4f}".replace(".", ",")
                for key in ("identificacao_aplicada", "incluir", "usar_como_referencia"):
                    row[key] = "SIM" if row[key] else "NAO"
                writer.writerow(row)

    def start_finalize(self, payload: dict) -> dict:
        result = self.save_review(payload)
        move_raw = bool(payload.get("mover_brutos", True))
        command = [
            sys.executable, str(self.script_dir / "ensaio.py"), "finalizar",
            "--config", str(self.config_path),
        ]
        if not move_raw:
            command.append("--nao-mover")
        self.pending_learning_payload = payload
        self.learning_logged = False
        self._start_subprocess(command, "finalizacao", "finalizacao_web.log")
        result.update({"iniciado": True, "mover_brutos": move_raw})
        return result

    def status(self) -> dict:
        with self.lock:
            process = self.process
            kind = self.process_kind
            if process is None:
                state = "ocioso"
                code = self.last_return_code
            else:
                code = process.poll()
                if code is None:
                    state = "executando"
                else:
                    state = "concluido" if code == 0 else "erro"
                    self.last_return_code = code
                    if self.log_handle:
                        try:
                            self.log_handle.flush()
                            self.log_handle.close()
                        except Exception:
                            pass
                        self.log_handle = None
                    if code == 0 and kind == "finalizacao" and not self.learning_logged and self.pending_learning_payload is not None:
                        try:
                            self.append_learning_log(self.pending_learning_payload)
                            self.append_identification_feedback()
                            self.learning_logged = True
                        except Exception as exc:
                            with self.log_path.open("a", encoding="utf-8", errors="replace") as f:
                                f.write(f"\nAVISO: não foi possível gravar o log de aprendizado: {exc}\n")
                        finally:
                            self.pending_learning_payload = None
                    elif code != 0:
                        self.pending_learning_payload = None
            elapsed = time.time() - self.started_at if self.started_at else 0.0
        return {
            "estado": state,
            "tipo": kind,
            "codigo": code,
            "tempo_segundos": elapsed,
            "log": tail_text(self.log_path, 16000),
        }


def format_date(code: str) -> str:
    if len(code) == 6 and code.isdigit():
        return f"{code[4:6]}/{code[2:4]}/20{code[0:2]}"
    return code


def tail_text(path: Path, max_chars: int) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except Exception:
        return ""


class Handler(BaseHTTPRequestHandler):
    server_version = "EnsaioReview/3.0"

    @property
    def state(self) -> AppState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, content_type: str, cache: bool = False, head_only: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_size = path.stat().st_size
        cache_control = "public, max-age=3600" if cache else "no-store"
        range_header = self.headers.get("Range")
        start = 0
        end = file_size - 1
        status = HTTPStatus.OK
        if range_header and range_header.startswith("bytes="):
            try:
                range_spec = range_header.split("=", 1)[1].strip()
                first, last = range_spec.split("-", 1)
                if first:
                    start = int(first)
                if last:
                    end = int(last)
                if not first and last:
                    length = int(last)
                    start = max(0, file_size - length)
                    end = file_size - 1
                start = max(0, start)
                end = min(file_size - 1, end)
                if start > end:
                    raise ValueError
                status = HTTPStatus.PARTIAL_CONTENT
            except Exception:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache_control)
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/":
            self.send_file(self.state.script_dir / "interface.html", "text/html; charset=utf-8", head_only=True)
            return
        if route == "/interface.css":
            self.send_file(self.state.script_dir / "interface.css", "text/css; charset=utf-8", False, True)
            return
        if route == "/interface.js":
            self.send_file(self.state.script_dir / "interface.js", "text/javascript; charset=utf-8", False, True)
            return
        if route == "/logo":
            suffix = self.state.cfg.logo.suffix.lower()
            content_type = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(suffix, "image/jpeg")
            self.send_file(self.state.cfg.logo, content_type, False, True)
            return
        if route.startswith("/audio/"):
            filename = Path(unquote(route[len("/audio/"):])).name
            path = self.state.cfg.pasta_revisao / "previews_web" / filename
            if not path.exists():
                path = self.state.cfg.pasta_revisao / "previews" / filename
            self.send_file(path, "audio/mpeg", True, True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/":
            self.send_file(self.state.script_dir / "interface.html", "text/html; charset=utf-8")
            return
        if route == "/interface.css":
            self.send_file(self.state.script_dir / "interface.css", "text/css; charset=utf-8", False)
            return
        if route == "/interface.js":
            self.send_file(self.state.script_dir / "interface.js", "text/javascript; charset=utf-8", False)
            return
        if route == "/logo":
            suffix = self.state.cfg.logo.suffix.lower()
            content_type = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(suffix, "image/jpeg")
            self.send_file(self.state.cfg.logo, content_type, False)
            return
        if route == "/api/estado":
            try:
                self.send_json(self.state.overview())
            except Exception as exc:
                self.send_json({"erro": str(exc)}, 500)
            return
        if route == "/api/dados":
            try:
                self.send_json(self.state.load_payload())
            except Exception as exc:
                self.send_json({"erro": str(exc)}, 500)
            return
        if route == "/api/status":
            self.send_json(self.state.status())
            return
        if route.startswith("/audio/"):
            filename = Path(unquote(route[len("/audio/"):])).name
            path = self.state.cfg.pasta_revisao / "previews_web" / filename
            if not path.exists():
                path = self.state.cfg.pasta_revisao / "previews" / filename
            self.send_file(path, "audio/mpeg", True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ReviewError("Tamanho da requisição inválido.") from exc
        if length > 5_000_000:
            raise ReviewError("Requisição excessivamente grande.")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ReviewError("JSON inválido.") from exc
        if not isinstance(value, dict):
            raise ReviewError("Formato de dados inválido.")
        return value

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/analisar":
                self.send_json(self.state.start_analysis(payload))
                return
            if parsed.path == "/api/identificar":
                self.send_json(self.state.reidentify(payload))
                return
            if parsed.path == "/api/salvar":
                self.send_json(self.state.save_review(payload))
                return
            if parsed.path == "/api/finalizar":
                self.send_json(self.state.start_finalize(payload))
                return
            if parsed.path == "/api/dividir":
                self.send_json(self.state.split_segment(payload))
                return
            if parsed.path == "/api/unir":
                self.send_json(self.state.merge_segments(payload))
                return
            if parsed.path == "/api/encerrar":
                self.send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ReviewError as exc:
            self.send_json({"erro": str(exc)}, 400)
        except ensaio.EnsaioError as exc:
            self.send_json({"erro": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"erro": f"Erro inesperado: {exc}"}, 500)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, state: AppState):
        super().__init__(address, handler)
        self.state = state


def existing_editor_url(port: int) -> str | None:
    url = f"http://127.0.0.1:{port}"
    try:
        with urlopen(url + "/api/estado", timeout=0.35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict) and payload.get("app_version"):
            return url + "/"
    except Exception:
        return None
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Abre a revisão local do ensaio no navegador.")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--nao-abrir", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    script_dir = Path(__file__).resolve().parent
    try:
        cfg = ensaio.load_config(args.config)
        ensaio.ensure_directories(cfg)
        if not args.nao_abrir:
            existing = existing_editor_url(args.porta)
            if existing:
                webbrowser.open(existing)
                return 0
        state = AppState(script_dir, cfg, args.config)
        port = args.porta
        server = None
        for candidate in range(port, port + 20):
            try:
                server = Server(("127.0.0.1", candidate), Handler, state)
                port = candidate
                break
            except OSError:
                continue
        if server is None:
            raise ReviewError("Não foi possível encontrar uma porta local livre.")
        url = f"http://127.0.0.1:{port}/"
        print("\nINTERFACE DE REVISÃO")
        print(url)
        print("Mantenha esta janela aberta enquanto usar a página.")
        print("Use Ctrl+C para encerrar manualmente.\n")
        if not args.nao_abrir:
            threading.Timer(0.7, lambda: webbrowser.open(url)).start()
        server.serve_forever(poll_interval=0.3)
        server.server_close()
        return 0
    except (ReviewError, ensaio.EnsaioError) as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterface encerrada.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
