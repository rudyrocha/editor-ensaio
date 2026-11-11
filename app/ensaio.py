#!/usr/bin/env python3
"""Automação local para gravações de ensaio.

Fluxo seguro em duas etapas:
  1. python ensaio.py analisar
  2. revisar revisao/segmentos.csv
  3. python ensaio.py finalizar

Os WAV originais só são movidos após a validação do MP4 final.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Iterable, Sequence

APP_VERSION = "3.3.0"
DATE_RE = re.compile(r"^(?P<date>\d{6})")
AUDIO_EXTENSIONS = {".wav", ".wave"}


class EnsaioError(RuntimeError):
    """Erro esperado e apresentável ao usuário."""


@dataclass
class Config:
    raiz: Path
    pasta_brutas: Path
    pasta_processadas: Path
    pasta_referencias: Path
    pasta_output: Path
    pasta_revisao: Path
    pasta_trabalho: Path
    pasta_dados: Path
    pasta_aprendizado: Path
    logo: Path
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    sample_rate: int = 48000
    channels: int = 2
    video_width: int = 1920
    video_height: int = 1080
    video_fps: int = 1
    video_crf: int = 20
    audio_bitrate: str = "320k"
    pre_roll_seconds: float = 5.0
    min_music_seconds: float = 60.0
    merge_gap_seconds: float = 8.0
    fade_seconds: float = 0.03
    preview_bitrate: str = "128k"
    analysis_frame_seconds: float = 1.0
    volume_threshold_db: float | None = None
    min_threshold_db: float = -42.0
    max_threshold_db: float = -18.0
    min_candidate_seconds: float = 5.0
    post_roll_seconds: float = 2.0
    onset_threshold_margin_db: float = 5.0
    onset_window_seconds: float = 8.0
    onset_required_ratio: float = 0.75
    onset_min_consecutive_seconds: float = 2.0
    onset_backtrack_seconds: float = 1.0
    continuation_hysteresis_db: float = 4.0
    music_end_no_high_seconds: float = 15.0
    start_preview_before_seconds: float = 15.0
    start_preview_after_seconds: float = 25.0
    move_raw_after_success: bool = True
    reference_start_offset_seconds: float = 5.0
    reference_end_trim_seconds: float = 2.0
    reference_min_seconds: float = 20.0
    ui_preview_margin_seconds: float = 20.0
    recognition_enabled: bool = True
    recognition_sample_rate: int = 12000
    recognition_feature_seconds: float = 1.0
    recognition_window_seconds: float = 24.0
    recognition_windows_per_track: int = 3
    recognition_candidate_step_seconds: float = 2.0
    recognition_min_seconds: float = 20.0
    recognition_auto_score: float = 0.72
    recognition_auto_margin: float = 0.06


@dataclass
class Segment:
    ordem: int
    inicio_bruto: float
    fim_bruto: float
    inicio_corte: float
    fim_corte: float
    duracao: float
    incluir: bool
    titulo: str
    classificacao: str
    observacao: str = ""
    qualidade: str = ""
    usar_como_referencia: bool = False
    inicio_corte_original: float | None = None
    fim_corte_original: float | None = None
    ajuste_inicio: float = 0.0
    ajuste_fim: float = 0.0
    titulo_sugerido: str = ""
    score_identificacao: float = 0.0
    segunda_opcao: str = ""
    score_segunda_opcao: float = 0.0
    terceira_opcao: str = ""
    score_terceira_opcao: float = 0.0
    identificacao_aplicada: bool = False


def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        raise EnsaioError(f"Arquivo de configuração não encontrado: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    raiz = Path(raw.get("raiz", r"D:\OFFline\Videos\@ensaio"))

    def resolve(value: str | None, default_relative: str) -> Path:
        p = Path(value) if value else Path(default_relative)
        return p if p.is_absolute() else raiz / p

    return Config(
        raiz=raiz,
        pasta_brutas=resolve(raw.get("pasta_brutas"), "brutas"),
        pasta_processadas=resolve(raw.get("pasta_processadas"), "processadas"),
        pasta_referencias=resolve(raw.get("pasta_referencias"), "referencias"),
        pasta_output=resolve(raw.get("pasta_output"), "output"),
        pasta_revisao=resolve(raw.get("pasta_revisao"), "revisao"),
        pasta_trabalho=resolve(raw.get("pasta_trabalho"), "processadas"),
        pasta_dados=resolve(raw.get("pasta_dados"), r"_sistema\dados"),
        pasta_aprendizado=resolve(raw.get("pasta_aprendizado"), r"_sistema\dados\aprendizado"),
        logo=resolve(raw.get("logo"), r"_sistema\assets\Logo.jpg"),
        ffmpeg=raw.get("ffmpeg", "ffmpeg"),
        ffprobe=raw.get("ffprobe", "ffprobe"),
        sample_rate=int(raw.get("sample_rate", 48000)),
        channels=int(raw.get("channels", 2)),
        video_width=int(raw.get("video_width", 1920)),
        video_height=int(raw.get("video_height", 1080)),
        video_fps=int(raw.get("video_fps", 1)),
        video_crf=int(raw.get("video_crf", 20)),
        audio_bitrate=str(raw.get("audio_bitrate", "320k")),
        pre_roll_seconds=float(raw.get("pre_roll_seconds", 5.0)),
        min_music_seconds=float(raw.get("min_music_seconds", 60.0)),
        merge_gap_seconds=float(raw.get("merge_gap_seconds", 8.0)),
        fade_seconds=float(raw.get("fade_seconds", 0.03)),
        preview_bitrate=str(raw.get("preview_bitrate", "128k")),
        analysis_frame_seconds=float(raw.get("analysis_frame_seconds", 1.0)),
        volume_threshold_db=(
            None if raw.get("volume_threshold_db") is None
            else float(raw.get("volume_threshold_db"))
        ),
        min_threshold_db=float(raw.get("min_threshold_db", -42.0)),
        max_threshold_db=float(raw.get("max_threshold_db", -18.0)),
        min_candidate_seconds=float(raw.get("min_candidate_seconds", 5.0)),
        post_roll_seconds=float(raw.get("post_roll_seconds", 2.0)),
        onset_threshold_margin_db=float(raw.get("onset_threshold_margin_db", 5.0)),
        onset_window_seconds=float(raw.get("onset_window_seconds", 8.0)),
        onset_required_ratio=float(raw.get("onset_required_ratio", 0.75)),
        onset_min_consecutive_seconds=float(raw.get("onset_min_consecutive_seconds", 2.0)),
        onset_backtrack_seconds=float(raw.get("onset_backtrack_seconds", 1.0)),
        continuation_hysteresis_db=float(raw.get("continuation_hysteresis_db", 4.0)),
        music_end_no_high_seconds=float(raw.get("music_end_no_high_seconds", 15.0)),
        start_preview_before_seconds=float(raw.get("start_preview_before_seconds", 15.0)),
        start_preview_after_seconds=float(raw.get("start_preview_after_seconds", 25.0)),
        move_raw_after_success=bool(raw.get("move_raw_after_success", True)),
        reference_start_offset_seconds=float(raw.get("reference_start_offset_seconds", 5.0)),
        reference_end_trim_seconds=float(raw.get("reference_end_trim_seconds", 2.0)),
        reference_min_seconds=float(raw.get("reference_min_seconds", 20.0)),
        ui_preview_margin_seconds=float(raw.get("ui_preview_margin_seconds", 20.0)),
        recognition_enabled=bool(raw.get("recognition_enabled", True)),
        recognition_sample_rate=int(raw.get("recognition_sample_rate", 12000)),
        recognition_feature_seconds=float(raw.get("recognition_feature_seconds", 1.0)),
        recognition_window_seconds=float(raw.get("recognition_window_seconds", 24.0)),
        recognition_windows_per_track=int(raw.get("recognition_windows_per_track", 3)),
        recognition_candidate_step_seconds=float(raw.get("recognition_candidate_step_seconds", 2.0)),
        recognition_min_seconds=float(raw.get("recognition_min_seconds", 20.0)),
        recognition_auto_score=float(raw.get("recognition_auto_score", 0.72)),
        recognition_auto_margin=float(raw.get("recognition_auto_margin", 0.06)),
    )


def setup_logging(log_path: Path, verbose: bool) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def _hidden_startupinfo():
    """Windows: solicita janela oculta mesmo quando o subprocesso usa shell externo."""
    if sys.platform != "win32":
        return None
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return startup


def run_command(cmd: Sequence[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = list(cmd)
    if cmd and Path(str(cmd[0])).stem.lower() == "ffmpeg" and "-nostdin" not in cmd:
        cmd.insert(1, "-nostdin")
    logging.debug("Executando: %s", subprocess.list2cmdline(list(cmd)))
    try:
        return subprocess.run(
            list(cmd),
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            # Evita janelas de console do FFmpeg/FFprobe no Windows e
            # impede que teclas digitadas pelo usuário cheguem ao processo.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            startupinfo=_hidden_startupinfo(),
        )
    except FileNotFoundError as exc:
        raise EnsaioError(f"Programa não encontrado: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise EnsaioError(
            f"Falha ao executar {cmd[0]} (código {exc.returncode}).\n{detail[-3000:]}"
        ) from exc


def check_dependencies(cfg: Config, require_analysis: bool) -> None:
    run_command([cfg.ffmpeg, "-version"], capture=True)
    run_command([cfg.ffprobe, "-version"], capture=True)

    if require_analysis:
        try:
            import numpy  # noqa: F401
            import soundfile  # noqa: F401
        except Exception as exc:
            raise EnsaioError(
                "As bibliotecas numpy/soundfile não estão disponíveis. "
                "Execute instalar.bat e tente novamente. "
                f"Detalhe técnico: {exc}"
            ) from exc


def work_dir_for_date(cfg: Config, date_code: str) -> Path:
    """Intermediários do ensaio, agrupados na pasta descartável de processadas.

    Preserva o padrão histórico ``processadas/AAAA-MM-DD/<originais>``.
    Os WAV originais não fazem parte desta pasta e nunca são removidos
    pela limpeza dos temporários.
    """
    date = datetime.strptime(date_code, "%y%m%d")
    return cfg.pasta_trabalho / date.strftime("%Y-%m-%d") / "temporarios"


def cleanup_work_dir(cfg: Config, date_code: str) -> bool:
    """Remove somente os derivados de um ensaio já finalizado e validado.

    Nunca apaga áudios originais, referências ou resultados. Se houver um
    problema de permissão, preserva os arquivos e registra um aviso.
    """
    work_dir = work_dir_for_date(cfg, date_code)
    try:
        work_dir_resolved = work_dir.resolve()
        processed_resolved = cfg.pasta_processadas.resolve()
        if processed_resolved not in work_dir_resolved.parents or work_dir.name != "temporarios":
            raise EnsaioError(f"Pasta temporária fora de processadas: {work_dir}")
        if work_dir.is_symlink():
            raise EnsaioError(f"Pasta temporária não pode ser link simbólico: {work_dir}")
        if work_dir.exists():
            shutil.rmtree(work_dir)
            logging.info("Intermediários excluídos após finalização validada: %s", work_dir)
        return True
    except OSError as exc:
        logging.warning("A finalização foi concluída, mas não foi possível excluir %s: %s", work_dir, exc)
        return False


def ensure_directories(cfg: Config) -> None:
    for directory in (
        cfg.pasta_brutas,
        cfg.pasta_processadas,
        cfg.pasta_referencias,
        cfg.pasta_output,
        cfg.pasta_revisao,
        cfg.pasta_trabalho,
        cfg.pasta_dados,
        cfg.pasta_aprendizado,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def discover_raw_files(cfg: Config) -> tuple[list[Path], str]:
    files = sorted(
        [p for p in cfg.pasta_brutas.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS],
        key=lambda p: p.name.lower(),
    )
    if not files:
        raise EnsaioError(f"Nenhum WAV encontrado em {cfg.pasta_brutas}")

    dates: dict[str, list[str]] = {}
    for path in files:
        match = DATE_RE.match(path.name)
        if not match:
            raise EnsaioError(
                f"O arquivo {path.name} não começa com uma data AAMMDD, como 260710."
            )
        dates.setdefault(match.group("date"), []).append(path.name)

    if len(dates) != 1:
        details = "; ".join(f"{date}: {', '.join(names)}" for date, names in dates.items())
        raise EnsaioError(
            "Há arquivos de mais de uma data na pasta brutas. "
            "Processe uma data por vez para impedir mistura de ensaios. " + details
        )

    date_code = next(iter(dates))
    try:
        datetime.strptime(date_code, "%y%m%d")
    except ValueError as exc:
        raise EnsaioError(f"Data inválida nos nomes dos arquivos: {date_code}") from exc

    return files, date_code


def ffprobe_json(cfg: Config, path: Path) -> dict:
    result = run_command(
        [
            cfg.ffprobe,
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,sample_rate,channels,width,height",
            "-of", "json",
            str(path),
        ],
        capture=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EnsaioError(f"ffprobe retornou dados inválidos para {path}") from exc


def media_duration(cfg: Config, path: Path) -> float:
    data = ffprobe_json(cfg, path)
    try:
        return float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EnsaioError(f"Não foi possível obter a duração de {path}") from exc


def normalize_files(cfg: Config, raw_files: Sequence[Path], work_dir: Path) -> list[Path]:
    normalized_dir = work_dir / "normalizados"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []

    for index, source in enumerate(raw_files, start=1):
        destination = normalized_dir / f"{index:03d}.wav"
        logging.info("Normalizando %s", source.name)
        run_command(
            [
                cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source),
                "-vn",
                "-ar", str(cfg.sample_rate),
                "-ac", str(cfg.channels),
                "-c:a", "pcm_s16le",
                str(destination),
            ]
        )
        result.append(destination)
    return result


def write_concat_list(paths: Iterable[Path], destination: Path) -> None:
    def quote(path: Path) -> str:
        # O concat demuxer aceita caminhos com barras normais; apóstrofos são escapados.
        escaped = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
        return f"file '{escaped}'"

    destination.write_text("\n".join(quote(p) for p in paths) + "\n", encoding="utf-8")


def concatenate_wavs(cfg: Config, files: Sequence[Path], destination: Path) -> None:
    concat_file = destination.with_suffix(".concat.txt")
    write_concat_list(files, concat_file)
    logging.info("Concatenando %d arquivo(s)", len(files))
    run_command(
        [
            cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", str(destination),
        ]
    )


def adaptive_volume_threshold(levels_db, cfg: Config) -> tuple[float, float, tuple[float, float, float]]:
    import numpy as np

    values = np.asarray(levels_db, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise EnsaioError("Não foi possível calcular níveis de volume.")

    # Três grupos: silêncio/pausa, conversa ou atividade intermediária e música.
    centers = np.asarray(np.percentile(values, [15, 50, 85]), dtype=float)
    for _ in range(50):
        distances = np.abs(values[:, None] - centers[None, :])
        labels = np.argmin(distances, axis=1)
        new_centers = centers.copy()
        for group in range(3):
            members = values[labels == group]
            if members.size:
                new_centers[group] = float(members.mean())
        new_centers.sort()
        if float(np.max(np.abs(new_centers - centers))) < 0.001:
            centers = new_centers
            break
        centers = new_centers

    c_low, c_mid, c_high = (float(v) for v in sorted(centers))

    if cfg.volume_threshold_db is not None:
        continuation = float(cfg.volume_threshold_db)
        onset = continuation + cfg.onset_threshold_margin_db
        onset = min(onset, c_high - 0.5)
        onset = max(onset, continuation + 1.0)
        logging.info(
            "Limiares fixos: continuidade %.2f dBFS; início %.2f dBFS",
            continuation, onset,
        )
    else:
        # O início deve separar atividade intermediária (tipicamente conversa) do grupo mais alto.
        onset = (c_mid + c_high) / 2.0
        onset = min(onset, c_high - 0.5)
        continuation = onset - cfg.continuation_hysteresis_db
        # Evita que a continuidade desça para o grupo de silêncio.
        lower_boundary = (c_low + c_mid) / 2.0 + 1.0
        continuation = max(continuation, lower_boundary)
        continuation = max(cfg.min_threshold_db, min(cfg.max_threshold_db, continuation))
        onset = max(onset, continuation + 1.0)

    logging.info(
        "Grupos de volume: baixo %.2f; intermediário %.2f; alto %.2f dBFS",
        c_low, c_mid, c_high,
    )
    logging.info(
        "Limiar de continuidade: %.2f dBFS; limiar de início: %.2f dBFS",
        continuation, onset,
    )
    return continuation, onset, (c_low, c_mid, c_high)

def longest_true_run(values: Sequence[bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def detect_music_regions_hysteresis(
    levels: Sequence[float],
    starts: Sequence[float],
    durations: Sequence[float],
    cfg: Config,
    continuation_threshold: float,
    high_threshold: float,
) -> tuple[list[bool], list[bool], list[tuple[float, float]], float]:
    import numpy as np

    frame_seconds = max(cfg.analysis_frame_seconds, 0.01)
    levels_array = np.asarray(levels, dtype=float)

    onset_frames = max(1, int(round(cfg.onset_window_seconds / frame_seconds)))
    consecutive_frames = max(1, int(round(cfg.onset_min_consecutive_seconds / frame_seconds)))
    backtrack_frames = max(0, int(round(cfg.onset_backtrack_seconds / frame_seconds)))
    max_gap_frames = max(1, int(round(cfg.merge_gap_seconds / frame_seconds)))
    max_no_evidence_frames = max(1, int(round(cfg.music_end_no_high_seconds / frame_seconds)))

    above_high = list(levels_array >= high_threshold)
    above_low = list(levels_array >= continuation_threshold)
    active = [False] * len(levels)
    starts_mask = [False] * len(levels)
    regions_idx: list[tuple[int, int]] = []
    total_frames = len(levels)

    # Evidência musical em janela móvel retrospectiva. Conversas podem ter picos altos,
    # mas normalmente não mantêm volume alto na proporção e continuidade exigidas.
    prefix = [0]
    for value in above_high:
        prefix.append(prefix[-1] + (1 if value else 0))

    evidence = [False] * total_frames
    evidence_window_start = [0] * total_frames
    for end_idx in range(total_frames):
        window_start = max(0, end_idx - onset_frames + 1)
        window_length = end_idx - window_start + 1
        evidence_window_start[end_idx] = window_start
        if window_length < max(2, onset_frames // 2):
            continue
        high_count = prefix[end_idx + 1] - prefix[window_start]
        ratio = high_count / window_length
        consecutive = longest_true_run(above_high[window_start:end_idx + 1])
        evidence[end_idx] = (
            ratio >= cfg.onset_required_ratio
            and consecutive >= consecutive_frames
        )

    i = 0
    while i < total_frames:
        if not evidence[i]:
            i += 1
            continue

        window_start = evidence_window_start[i]
        first_high = window_start
        run_start: int | None = None
        run_length = 0
        for candidate in range(window_start, i + 1):
            if above_high[candidate]:
                if run_length == 0:
                    run_start = candidate
                run_length += 1
                if run_length >= consecutive_frames:
                    first_high = run_start if run_start is not None else candidate
                    break
            else:
                run_start = None
                run_length = 0
        start_idx = first_high
        # Pequeno recuo apenas dentro de atividade acima do limiar de continuidade.
        for _ in range(backtrack_frames):
            if start_idx <= 0 or not above_low[start_idx - 1]:
                break
            start_idx -= 1

        gap_start: int | None = None
        no_evidence_start: int | None = None
        end_candidate: int | None = None
        j = i
        while j < total_frames:
            if above_low[j]:
                gap_start = None
            elif gap_start is None:
                gap_start = j
            elif j - gap_start + 1 > max_gap_frames:
                end_candidate = gap_start
                break

            if evidence[j]:
                no_evidence_start = None
            elif no_evidence_start is None:
                no_evidence_start = j
            elif j - no_evidence_start + 1 > max_no_evidence_frames:
                # A evidência retrospectiva já demora alguns segundos para desaparecer;
                # seu primeiro quadro falso é um ponto de término conservador.
                end_candidate = no_evidence_start
                break
            j += 1

        resume_idx = j + 1 if j < total_frames else total_frames
        end_idx = end_candidate if end_candidate is not None else total_frames
        end_idx = max(end_idx, start_idx + 1)
        for k in range(start_idx, end_idx):
            active[k] = True
        starts_mask[start_idx] = True
        regions_idx.append((start_idx, end_idx))
        i = max(resume_idx, end_idx + 1, i + 1)

    total = starts[-1] + durations[-1] if starts else 0.0
    regions: list[tuple[float, float]] = []
    for start_idx, end_idx in regions_idx:
        start = starts[start_idx]
        end = starts[end_idx - 1] + durations[end_idx - 1]
        if end - start < cfg.min_candidate_seconds:
            continue
        end = min(total, end + cfg.post_roll_seconds)
        regions.append((start, end))

    logging.info(
        "Confirmação do início: janela %.1fs; exigência %.0f%%; sequência mínima %.1fs; "
        "fim após %.1fs sem evidência musical",
        cfg.onset_window_seconds,
        cfg.onset_required_ratio * 100.0,
        cfg.onset_min_consecutive_seconds,
        cfg.music_end_no_high_seconds,
    )
    return active, starts_mask, regions, high_threshold

def analyze_loudness(
    cfg: Config,
    master: Path,
) -> tuple[list[tuple[str, float, float, float]], list[tuple[float, float]]]:
    import numpy as np
    import soundfile as sf

    info = sf.info(str(master))
    sample_rate = int(info.samplerate)
    blocksize = max(1, int(round(sample_rate * cfg.analysis_frame_seconds)))
    levels: list[float] = []
    durations: list[float] = []

    logging.info(
        "Analisando volume em janelas de %.2f segundo(s)",
        cfg.analysis_frame_seconds,
    )
    with sf.SoundFile(str(master), mode="r") as audio:
        while True:
            block = audio.read(blocksize, dtype="float32", always_2d=True)
            if block.size == 0:
                break
            rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
            db = 20.0 * np.log10(max(rms, 1e-8))
            levels.append(float(db))
            durations.append(len(block) / sample_rate)

    if not levels:
        raise EnsaioError("O áudio mestre está vazio.")

    continuation_threshold, onset_threshold, _clusters = adaptive_volume_threshold(levels, cfg)

    starts: list[float] = []
    current = 0.0
    for duration in durations:
        starts.append(current)
        current += duration

    active, starts_mask, regions, high_threshold = detect_music_regions_hysteresis(
        levels,
        starts,
        durations,
        cfg,
        continuation_threshold,
        onset_threshold,
    )

    frame_rows: list[tuple[str, float, float, float]] = []
    for index, (start, duration, level, is_active) in enumerate(zip(starts, durations, levels, active)):
        if starts_mask[index]:
            label = "inicio_confirmado"
        elif level >= high_threshold:
            label = "volume_alto"
        elif is_active:
            label = "continuidade_musical"
        else:
            label = "conversa_ou_intervalo"
        frame_rows.append((label, start, start + duration, level))

    if not regions:
        raise EnsaioError(
            "Nenhuma região musical candidata foi encontrada. "
            "Reduza onset_threshold_margin_db ou onset_required_ratio no config.json e tente novamente."
        )
    return frame_rows, regions

def write_loudness_csv(path: Path, rows: Sequence[tuple[str, float, float, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["tipo", "inicio_segundos", "fim_segundos", "nivel_dbfs"])
        for label, start, end, level in rows:
            writer.writerow([label, f"{start:.3f}", f"{end:.3f}", f"{level:.3f}"])


def build_review_segments(cfg: Config, music_regions: Sequence[tuple[float, float]], total: float) -> list[Segment]:
    result: list[Segment] = []
    for index, (start, end) in enumerate(music_regions, start=1):
        cut_start = max(0.0, start - cfg.pre_roll_seconds)
        cut_end = min(total, end)
        duration = max(0.0, cut_end - cut_start)
        include = duration >= cfg.min_music_seconds
        classification = "musica" if include else "tentativa_curta"
        note = "" if include else f"Excluído por ter menos de {cfg.min_music_seconds:g} s"
        result.append(
            Segment(
                ordem=index,
                inicio_bruto=start,
                fim_bruto=end,
                inicio_corte=cut_start,
                fim_corte=cut_end,
                duracao=duration,
                incluir=include,
                titulo="",
                classificacao=classification,
                observacao=note,
            )
        )
    return result


def write_review_csv(path: Path, segments: Sequence[Segment]) -> None:
    fieldnames = [
        "ordem", "incluir", "titulo", "qualidade", "usar_como_referencia",
        "inicio_corte_original", "fim_corte_original", "ajuste_inicio", "ajuste_fim",
        "inicio_corte", "fim_corte", "duracao", "inicio_bruto", "fim_bruto",
        "classificacao", "observacao", "titulo_sugerido", "score_identificacao",
        "segunda_opcao", "score_segunda_opcao", "terceira_opcao", "score_terceira_opcao", "identificacao_aplicada",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for segment in segments:
            row = asdict(segment)
            row["incluir"] = "SIM" if segment.incluir else "NAO"
            row["usar_como_referencia"] = "SIM" if segment.usar_como_referencia else "NAO"
            row["identificacao_aplicada"] = "SIM" if segment.identificacao_aplicada else "NAO"
            row["score_identificacao"] = f"{float(segment.score_identificacao):.4f}".replace(".", ",")
            row["score_segunda_opcao"] = f"{float(segment.score_segunda_opcao):.4f}".replace(".", ",")
            row["score_terceira_opcao"] = f"{float(segment.score_terceira_opcao):.4f}".replace(".", ",")
            if row.get("inicio_corte_original") is None:
                row["inicio_corte_original"] = segment.inicio_corte
            if row.get("fim_corte_original") is None:
                row["fim_corte_original"] = segment.fim_corte
            # O CSV usa ponto e vírgula como separador e vírgula decimal.
            for key in (
                "inicio_corte_original", "fim_corte_original", "ajuste_inicio", "ajuste_fim",
                "inicio_corte", "fim_corte", "duracao", "inicio_bruto", "fim_bruto",
            ):
                row[key] = f"{float(row[key]):.3f}".replace(".", ",")
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def create_previews(cfg: Config, master: Path, segments: Sequence[Segment]) -> None:
    """Regenera prévias sem sobrescrever arquivos de áudio em uso pelo navegador.

    Cria todos os MP3 com identificador único, publica o índice em operação
    atômica e tenta remover gerações antigas sem bloquear a edição no Windows.
    """
    preview_dir = cfg.pasta_revisao / "previews"
    start_preview_dir = cfg.pasta_revisao / "previews_inicio"
    web_preview_dir = cfg.pasta_revisao / "previews_web"
    for folder in (preview_dir, start_preview_dir, web_preview_dir):
        folder.mkdir(parents=True, exist_ok=True)
    generation = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    master_duration = media_duration(cfg, master)
    preview_index: list[dict[str, float | int | str]] = []
    generated: list[Path] = []
    index_path = cfg.pasta_revisao / "previews_web.json"
    temp_index = cfg.pasta_revisao / f"previews_web_{generation}.tmp"
    try:
        for segment in segments:
            start = segment.inicio_corte
            end = segment.fim_corte
            if start < 0 or end <= start or end > master_duration + .25:
                raise EnsaioError(f"Cortes inválidos na faixa {segment.ordem}.")
            simple = preview_dir / f"{segment.ordem:03d}_{segment.classificacao}_{generation}.mp3"
            detected_start = segment.inicio_bruto
            quick_start = max(0.0, detected_start - cfg.start_preview_before_seconds)
            quick_end = min(master_duration, detected_start + cfg.start_preview_after_seconds)
            if quick_end <= quick_start:
                quick_start, quick_end = start, end
            quick = start_preview_dir / f"{segment.ordem:03d}_inicio_{generation}.mp3"
            web_start = max(0.0, start - cfg.ui_preview_margin_seconds)
            web_end = min(master_duration, end + cfg.ui_preview_margin_seconds)
            web = web_preview_dir / f"{segment.ordem:03d}_{generation}.mp3"
            for path, cut_start, cut_end in (
                (simple, start, end), (quick, quick_start, quick_end),
                (web, web_start, web_end),
            ):
                generated.append(path)
                run_command([
                    cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", format_seconds(cut_start), "-to", format_seconds(cut_end),
                    "-i", str(master), "-vn", "-c:a", "libmp3lame", "-b:a",
                    cfg.preview_bitrate, str(path),
                ])
                if not path.is_file() or path.stat().st_size == 0:
                    raise EnsaioError(f"Não foi possível criar a prévia {path.name}")
            preview_index.append({
                "ordem": segment.ordem,
                "arquivo": web.name,
                "inicio_preview_master": web_start,
                "fim_preview_master": web_end,
                "offset_inicio_corte": start - web_start,
                "offset_fim_corte": end - web_start,
            })
        temp_index.write_text(json.dumps(preview_index, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_index.replace(index_path)
    except Exception:
        for file in generated:
            try: file.unlink(missing_ok=True)
            except OSError: pass
        try: temp_index.unlink(missing_ok=True)
        except OSError: pass
        raise
    # Nunca tentar remover MP3 que o navegador pode ter aberto como requisito
    # para concluir a divisão. Arquivos antigos são apenas limpeza opcional.
    current = {str(path) for path in generated}
    for folder in (preview_dir, start_preview_dir, web_preview_dir):
        for old in folder.glob("*.mp3"):
            if str(old) not in current:
                try: old.unlink()
                except OSError: logging.info("Prévia antiga ainda em uso: %s", old)


def save_manifest(
    cfg: Config,
    manifest_path: Path,
    *,
    date_code: str,
    raw_files: Sequence[Path],
    master: Path,
) -> None:
    payload = {
        "app_version": APP_VERSION,
        "data_codigo": date_code,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "arquivos_brutos": [str(p.resolve()) for p in raw_files],
        "master": str(master.resolve()),
        "duracao_master": media_duration(cfg, master),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise EnsaioError("Manifesto não encontrado. Execute primeiro: ensaio.py analisar")
    return json.loads(path.read_text(encoding="utf-8"))


def repair_manifest_paths(cfg: Config, manifest_path: Path) -> dict:
    """Atualiza caminhos absolutos antigos após mudança da pasta-raiz do projeto.

    Versões anteriores gravavam no manifesto os caminhos absolutos do áudio mestre
    e dos WAVs brutos. Ao mover a estrutura de ``@ensaio\\wk`` para a raiz
    ``@ensaio``, esses valores ficam obsoletos mesmo que os arquivos tenham sido
    migrados corretamente. Esta função localiza os equivalentes na estrutura atual
    e persiste o manifesto reparado, sem refazer a análise nem alterar segmentos.
    """
    manifest = load_manifest(manifest_path)
    date_code = str(manifest.get("data_codigo", "")).strip()
    if not date_code:
        return manifest

    changed = False

    current_master = work_dir_for_date(cfg, date_code) / "master.wav"
    stored_master = str(manifest.get("master", "")).strip()
    if current_master.exists():
        resolved_master = str(current_master.resolve())
        if stored_master != resolved_master:
            manifest["master"] = resolved_master
            changed = True

    raw_values = list(manifest.get("arquivos_brutos", []) or [])
    repaired_raw: list[str] = []
    raw_changed = False
    date = datetime.strptime(date_code, "%y%m%d")
    processed_dir = cfg.pasta_processadas / date.strftime("%Y-%m-%d")

    for item in raw_values:
        original_text = str(item)
        original = Path(original_text)
        legacy_name = PureWindowsPath(original_text).name if "\\" in original_text else original.name
        if original.exists():
            chosen = original
        else:
            in_brutas = cfg.pasta_brutas / legacy_name
            in_processed = processed_dir / legacy_name
            in_processed_nested = processed_dir / "originais" / legacy_name
            if in_brutas.exists():
                chosen = in_brutas
            elif in_processed.exists():
                chosen = in_processed
            elif in_processed_nested.exists():
                chosen = in_processed_nested
            else:
                chosen = original
        resolved = str(chosen.resolve()) if chosen.exists() else str(chosen)
        repaired_raw.append(resolved)
        if resolved != str(item):
            raw_changed = True

    if raw_changed:
        manifest["arquivos_brutos"] = repaired_raw
        changed = True

    if changed:
        manifest["app_version"] = APP_VERSION
        manifest["caminhos_reparados_em"] = datetime.now().isoformat(timespec="seconds")
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logging.info("Manifesto atualizado para a estrutura atual de pastas.")

    return manifest


def parse_yes_no(value: str) -> bool:
    normalized = value.strip().upper()
    if normalized in {"SIM", "S", "1", "TRUE", "YES", "Y"}:
        return True
    if normalized in {"NAO", "NÃO", "N", "0", "FALSE", "NO"}:
        return False
    raise EnsaioError(f"Valor inválido na coluna incluir: {value!r}. Use SIM ou NAO.")


def parse_decimal(value: str, field: str, row_number: int) -> float:
    """Lê segundos em formatos comuns de planilhas brasileiras.

    Aceita, entre outros:
      1004.000   (ponto decimal)
      1004,000   (vírgula decimal)
      1.004,000  (milhar brasileiro + decimal)
      1,004.000  (milhar inglês + decimal)
      1.004.000  (conversão indevida do Excel; interpretado como 1004.000)
      00:16:44.000 ou 00:16:44,000
    """
    original = (value or "").strip()
    compact = re.sub(r"[\s\u00a0]", "", original)
    if not compact:
        raise EnsaioError(f"Valor vazio em {field}, linha {row_number}.")

    # Também permite informar diretamente HH:MM:SS,mmm.
    if ":" in compact:
        try:
            parts = compact.replace(",", ".").split(":")
            if len(parts) not in {2, 3}:
                raise ValueError
            values = [float(part) for part in parts]
            if len(values) == 2:
                result = values[0] * 60 + values[1]
            else:
                result = values[0] * 3600 + values[1] * 60 + values[2]
            if result < 0:
                raise ValueError
            return result
        except ValueError as exc:
            raise EnsaioError(
                f"Valor inválido em {field}, linha {row_number}: {original!r}"
            ) from exc

    normalized = compact
    dot_count = normalized.count(".")
    comma_count = normalized.count(",")

    if dot_count and comma_count:
        # O separador que aparece por último é tratado como decimal;
        # o outro é tratado como separador de milhar.
        decimal_sep = "." if normalized.rfind(".") > normalized.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        normalized = normalized.replace(thousands_sep, "")
        normalized = normalized.replace(decimal_sep, ".")
    elif dot_count > 1:
        # Ex.: 1.004.000, gerado quando 1004.000 é reformatado em pt-BR.
        parts = normalized.split(".")
        normalized = "".join(parts[:-1]) + "." + parts[-1]
    elif comma_count > 1:
        parts = normalized.split(",")
        normalized = "".join(parts[:-1]) + "." + parts[-1]
    elif comma_count == 1:
        normalized = normalized.replace(",", ".")

    try:
        result = float(normalized)
    except ValueError as exc:
        raise EnsaioError(
            f"Valor inválido em {field}, linha {row_number}: {original!r}"
        ) from exc

    if normalized != compact.replace(",", "."):
        logging.warning(
            "Valor localizado normalizado em %s, linha %d: %r -> %.3f",
            field, row_number, original, result,
        )
    return result


def optional_yes_no(value: str | None, default: bool = False) -> bool:
    text = (value or "").strip()
    if not text:
        return default
    return parse_yes_no(text)


def optional_decimal(value: str | None, default: float, field: str, row_number: int) -> float:
    text = (value or "").strip()
    if not text:
        return default
    return parse_decimal(text, field, row_number)


def row_to_segment(row: dict[str, str], row_number: int) -> Segment:
    include = parse_yes_no(row.get("incluir", ""))
    start = parse_decimal(row.get("inicio_corte", ""), "inicio_corte", row_number)
    end = parse_decimal(row.get("fim_corte", ""), "fim_corte", row_number)
    if end <= start:
        raise EnsaioError(f"Fim menor ou igual ao início na linha {row_number}.")
    original_start = optional_decimal(
        row.get("inicio_corte_original"), start, "inicio_corte_original", row_number
    )
    original_end = optional_decimal(
        row.get("fim_corte_original"), end, "fim_corte_original", row_number
    )
    return Segment(
        ordem=int(row.get("ordem", row_number - 1)),
        inicio_bruto=parse_decimal((row.get("inicio_bruto") or str(start)), "inicio_bruto", row_number),
        fim_bruto=parse_decimal((row.get("fim_bruto") or str(end)), "fim_bruto", row_number),
        inicio_corte=start,
        fim_corte=end,
        duracao=end - start,
        incluir=include,
        titulo=(row.get("titulo") or "").strip(),
        classificacao=(row.get("classificacao") or "").strip(),
        observacao=(row.get("observacao") or "").strip(),
        qualidade=(row.get("qualidade") or "").strip(),
        usar_como_referencia=optional_yes_no(row.get("usar_como_referencia"), False),
        inicio_corte_original=original_start,
        fim_corte_original=original_end,
        ajuste_inicio=optional_decimal(row.get("ajuste_inicio"), 0.0, "ajuste_inicio", row_number),
        ajuste_fim=optional_decimal(row.get("ajuste_fim"), 0.0, "ajuste_fim", row_number),
        titulo_sugerido=(row.get("titulo_sugerido") or "").strip(),
        score_identificacao=optional_decimal(row.get("score_identificacao"), 0.0, "score_identificacao", row_number),
        segunda_opcao=(row.get("segunda_opcao") or "").strip(),
        score_segunda_opcao=optional_decimal(row.get("score_segunda_opcao"), 0.0, "score_segunda_opcao", row_number),
        terceira_opcao=(row.get("terceira_opcao") or "").strip(),
        score_terceira_opcao=optional_decimal(row.get("score_terceira_opcao"), 0.0, "score_terceira_opcao", row_number),
        identificacao_aplicada=optional_yes_no(row.get("identificacao_aplicada"), False),
    )


def read_review_csv(path: Path) -> list[Segment]:
    if not path.exists():
        raise EnsaioError(f"CSV de revisão não encontrado: {path}")

    segments: list[Segment] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        required = {"ordem", "incluir", "titulo", "inicio_corte", "fim_corte"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise EnsaioError(f"Colunas ausentes no CSV: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            segments.append(row_to_segment(row, row_number))

    selected = sorted((item for item in segments if item.incluir), key=lambda item: item.ordem)
    if not selected:
        raise EnsaioError("Nenhum segmento está marcado como SIM na revisão.")
    for segment in selected:
        if not segment.titulo:
            raise EnsaioError(f"A faixa {segment.ordem} está sem título.")
    return selected

def validate_selected_segments(segments: Sequence[Segment], master_duration: float) -> None:
    previous_end = -1.0
    for segment in segments:
        if segment.inicio_corte < 0 or segment.fim_corte > master_duration + 0.25:
            raise EnsaioError(
                f"Segmento {segment.ordem} está fora da duração do áudio mestre ({master_duration:.3f} s)."
            )
        if segment.inicio_corte < previous_end - 0.01:
            raise EnsaioError(
                f"Segmento {segment.ordem} sobrepõe o segmento anterior. Corrija o CSV."
            )
        previous_end = segment.fim_corte


def extract_selected_segments(
    cfg: Config,
    master: Path,
    selected: Sequence[Segment],
    work_dir: Path,
) -> list[Path]:
    parts_dir = work_dir / "partes_finais"
    if parts_dir.exists():
        shutil.rmtree(parts_dir)
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []

    for index, segment in enumerate(selected, start=1):
        destination = parts_dir / f"{index:03d}.wav"
        duration = segment.fim_corte - segment.inicio_corte
        fade = min(cfg.fade_seconds, max(0.0, duration / 4))
        filters = [f"afade=t=in:st=0:d={fade:.4f}"]
        if duration > fade:
            filters.append(f"afade=t=out:st={max(0.0, duration-fade):.4f}:d={fade:.4f}")
        run_command(
            [
                cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-ss", format_seconds(segment.inicio_corte),
                "-t", format_seconds(duration),
                "-i", str(master),
                "-vn", "-af", ",".join(filters),
                "-ar", str(cfg.sample_rate), "-ac", str(cfg.channels),
                "-c:a", "pcm_s16le", str(destination),
            ]
        )
        segment.duracao = media_duration(cfg, destination)
        parts.append(destination)
    return parts


def output_basename(date_code: str) -> str:
    date = datetime.strptime(date_code, "%y%m%d")
    return f"Ensaio.{date.strftime('%y.%m.%d')}"


def create_static_video(cfg: Config, audio: Path, destination: Path) -> None:
    if not cfg.logo.exists():
        raise EnsaioError(f"Logo não encontrado: {cfg.logo}")
    audio_duration = media_duration(cfg, audio)

    # Mantém proporção, centraliza e completa o quadro 16:9 com preto.
    video_filter = (
        f"scale={cfg.video_width}:{cfg.video_height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={cfg.video_width}:{cfg.video_height}:(ow-iw)/2:(oh-ih)/2:black,"
        "setsar=1"
    )
    run_command(
        [
            cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", str(cfg.video_fps), "-i", str(cfg.logo),
            "-i", str(audio),
            "-vf", video_filter,
            "-r", str(cfg.video_fps),
            "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
            "-crf", str(cfg.video_crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", cfg.audio_bitrate,
            "-t", format_seconds(audio_duration),
            "-movflags", "+faststart",
            str(destination),
        ]
    )


def chapter_timestamp(seconds: float) -> str:
    value = max(0, int(round(seconds)))
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def duration_label(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    return f"{minutes}m{secs:02d}"


def chapter_label(segment: Segment, index: int) -> str:
    title = segment.titulo or f"[IDENTIFICAR {index:02d}]"
    quality = segment.qualidade.strip()
    note = (segment.observacao or "").strip()
    details = [part for part in (quality, note) if part]
    suffix = " — " + " · ".join(details) if details else ""
    return f"{title}{suffix} ({duration_label(segment.duracao)})"


def write_chapters(path: Path, selected: Sequence[Segment]) -> None:
    """Mantida por compatibilidade; a finalização usa somente a descrição."""
    current = 0.0
    lines = []
    for index, segment in enumerate(selected, start=1):
        lines.append(f"{chapter_timestamp(current)} {chapter_label(segment, index)}")
        current += segment.duracao
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_video_description(path: Path, selected: Sequence[Segment]) -> None:
    """Capítulos prontos para YouTube, com comentários na linha da música."""
    current = 0.0
    lines = []
    for index, segment in enumerate(selected, start=1):
        lines.append(f"{chapter_timestamp(current)} {chapter_label(segment, index)}")
        current += segment.duracao
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_final_files(cfg: Config, video: Path, audio: Path, description: Path) -> None:
    for path in (video, audio, description):
        if not path.exists() or path.stat().st_size == 0:
            raise EnsaioError(f"Arquivo final ausente ou vazio: {path}")
    audio_duration = media_duration(cfg, audio)
    video_duration = media_duration(cfg, video)
    difference = abs(audio_duration - video_duration)
    if difference > max(2.0, 2.0 / max(cfg.video_fps, 1)):
        raise EnsaioError(
            f"Duração incompatível entre áudio ({audio_duration:.2f}s) e vídeo "
            f"({video_duration:.2f}s). Diferença: {difference:.2f}s."
        )


def archive_raw_files(cfg: Config, raw_files: Sequence[Path], date_code: str) -> Path:
    date = datetime.strptime(date_code, "%y%m%d")
    destination_dir = cfg.pasta_processadas / date.strftime("%Y-%m-%d")
    destination_dir.mkdir(parents=True, exist_ok=True)

    for source in raw_files:
        if not source.exists():
            raise EnsaioError(f"Arquivo bruto desapareceu antes do arquivamento: {source}")
        destination = destination_dir / source.name
        if destination.exists():
            raise EnsaioError(
                f"O destino já contém {destination.name}. Nenhum bruto foi movido nesta tentativa."
            )

    moved: list[tuple[Path, Path]] = []
    try:
        for source in raw_files:
            destination = destination_dir / source.name
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
    except Exception as exc:
        # Tenta desfazer para evitar uma movimentação parcial.
        for original, destination in reversed(moved):
            if destination.exists() and not original.exists():
                shutil.move(str(destination), str(original))
        raise EnsaioError(f"Falha ao mover os arquivos brutos: {exc}") from exc
    return destination_dir


def format_seconds(value: float) -> str:
    return f"{value:.6f}"


def backup_previous_review(cfg: Config) -> Path | None:
    candidates = [
        cfg.pasta_revisao / "segmentos.csv",
        cfg.pasta_revisao / "analise_volume.csv",
        cfg.pasta_revisao / "manifesto.json",
        cfg.pasta_revisao / "ensaio.log",
    ]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = cfg.pasta_revisao / "historico" / timestamp
    destination.mkdir(parents=True, exist_ok=False)
    for source in existing:
        shutil.copy2(source, destination / source.name)
    return destination




def _downsample_audio_mean(samples, source_rate: int, target_rate: int):
    import numpy as np
    if source_rate <= target_rate:
        return samples.astype(np.float32, copy=False), source_rate
    ratio = source_rate / target_rate
    factor = int(round(ratio))
    if factor >= 2 and abs(source_rate / factor - target_rate) / target_rate < 0.03:
        usable = (len(samples) // factor) * factor
        if usable <= 0:
            return samples.astype(np.float32, copy=False), source_rate
        reduced = samples[:usable].reshape(-1, factor).mean(axis=1)
        return reduced.astype(np.float32, copy=False), int(round(source_rate / factor))
    duration = len(samples) / source_rate
    target_len = max(1, int(round(duration * target_rate)))
    old_x = np.linspace(0.0, 1.0, num=len(samples), endpoint=True)
    new_x = np.linspace(0.0, 1.0, num=target_len, endpoint=True)
    return np.interp(new_x, old_x, samples).astype(np.float32), target_rate


def chroma_signature(
    path: Path,
    *,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    target_rate: int = 12000,
    feature_seconds: float = 1.0,
):
    """Extrai uma assinatura harmônica compacta (chroma de 12 notas)."""
    import numpy as np
    import soundfile as sf

    with sf.SoundFile(str(path), mode="r") as audio:
        sr = int(audio.samplerate)
        start_frame = max(0, int(round(start_seconds * sr)))
        end_frame = len(audio) if end_seconds is None else min(len(audio), int(round(end_seconds * sr)))
        if end_frame <= start_frame:
            return np.zeros((0, 12), dtype=np.float32)
        audio.seek(start_frame)
        data = audio.read(end_frame - start_frame, dtype="float32", always_2d=True)
    if data.size == 0:
        return np.zeros((0, 12), dtype=np.float32)
    mono = data.mean(axis=1)
    mono, sr = _downsample_audio_mean(mono, sr, target_rate)
    if len(mono) < 256:
        return np.zeros((0, 12), dtype=np.float32)

    frame_size = 4096
    if len(mono) < frame_size:
        mono = np.pad(mono, (0, frame_size - len(mono)))
    hop = 2048
    window = np.hanning(frame_size).astype(np.float32)
    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sr)
    valid = (freqs >= 55.0) & (freqs <= min(4000.0, sr / 2 - 1.0))
    valid_freqs = freqs[valid]
    midi = np.rint(69.0 + 12.0 * np.log2(valid_freqs / 440.0)).astype(int)
    pitch_class = np.mod(midi, 12)

    frames: list = []
    for pos in range(0, max(1, len(mono) - frame_size + 1), hop):
        frame = mono[pos:pos + frame_size]
        if len(frame) < frame_size:
            frame = np.pad(frame, (0, frame_size - len(frame)))
        spectrum = np.fft.rfft(frame * window)
        power = np.abs(spectrum[valid]) ** 2
        chroma = np.bincount(pitch_class, weights=power, minlength=12).astype(np.float64)
        chroma = np.log1p(chroma)
        norm = float(np.linalg.norm(chroma))
        if norm > 1e-10:
            chroma /= norm
        frames.append(chroma.astype(np.float32))
    if not frames:
        return np.zeros((0, 12), dtype=np.float32)
    raw = np.vstack(frames)
    frame_step = hop / sr
    group = max(1, int(round(feature_seconds / frame_step)))
    grouped = []
    for pos in range(0, len(raw), group):
        block = raw[pos:pos + group].mean(axis=0)
        norm = float(np.linalg.norm(block))
        if norm > 1e-10:
            block = block / norm
        grouped.append(block.astype(np.float32))
    result = np.vstack(grouped)
    if len(result) >= 3:
        smoothed = result.copy()
        smoothed[1:-1] = (result[:-2] + result[1:-1] + result[2:]) / 3.0
        norms = np.linalg.norm(smoothed, axis=1, keepdims=True)
        result = smoothed / np.maximum(norms, 1e-8)
    return result.astype(np.float32)


def _resample_feature_sequence(sequence, length: int):
    import numpy as np
    if len(sequence) == length:
        return sequence
    if len(sequence) <= 1:
        return np.repeat(sequence[:1], max(1, length), axis=0)
    old_x = np.linspace(0.0, 1.0, len(sequence))
    new_x = np.linspace(0.0, 1.0, max(1, length))
    cols = [np.interp(new_x, old_x, sequence[:, idx]) for idx in range(sequence.shape[1])]
    out = np.stack(cols, axis=1).astype(np.float32)
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.maximum(norms, 1e-8)


def _signature_similarity(query, reference, *, window_seconds: float, windows_per_track: int, step_seconds: float) -> float:
    import numpy as np
    if len(query) < 4 or len(reference) < 4:
        return 0.0
    win = min(len(query), max(8, int(round(window_seconds))))
    max_start = max(0, len(query) - win)
    if max_start == 0:
        query_starts = [0]
    else:
        count = max(1, min(windows_per_track, max_start + 1))
        query_starts = sorted(set(int(round(v)) for v in np.linspace(0, max_start, count)))
    stretch_factors = (0.88, 0.94, 1.0, 1.06, 1.12)
    candidate_step = max(1, int(round(step_seconds)))
    window_scores: list[float] = []

    for q_start in query_starts:
        q = query[q_start:q_start + win]
        best = 0.0
        for factor in stretch_factors:
            ref_len = int(round(len(q) * factor))
            ref_len = min(len(reference), max(6, ref_len))
            q2 = _resample_feature_sequence(q, ref_len)
            if len(reference) == ref_len:
                starts = [0]
            else:
                starts = range(0, len(reference) - ref_len + 1, candidate_step)
            for r_start in starts:
                r = reference[r_start:r_start + ref_len]
                frame_sim = np.sum(q2 * r, axis=1)
                score = float(np.mean(frame_sim))
                if score > best:
                    best = score
        window_scores.append(best)

    profile_q = query.mean(axis=0)
    profile_r = reference.mean(axis=0)
    nq = float(np.linalg.norm(profile_q))
    nr = float(np.linalg.norm(profile_r))
    profile_score = float(np.dot(profile_q, profile_r) / max(nq * nr, 1e-8))
    sequence_score = float(np.mean(sorted(window_scores, reverse=True)[: max(1, min(2, len(window_scores)))]))
    return max(0.0, min(1.0, 0.82 * sequence_score + 0.18 * profile_score))


def _reference_signature_cache(cfg: Config, row: dict[str, str], path: Path):
    import numpy as np
    cache_dir = cfg.pasta_referencias / "indices" / "chroma_v1"
    cache_dir.mkdir(parents=True, exist_ok=True)
    token = (row.get("sha256") or "").strip() or hashlib.sha256(
        f"{path.resolve()}|{path.stat().st_size}|{path.stat().st_mtime_ns}".encode("utf-8")
    ).hexdigest()
    cache_path = cache_dir / f"{token[:24]}.npz"
    if cache_path.exists():
        try:
            with np.load(cache_path) as data:
                return data["signature"].astype(np.float32)
        except Exception:
            cache_path.unlink(missing_ok=True)
    signature = chroma_signature(
        path,
        target_rate=cfg.recognition_sample_rate,
        feature_seconds=cfg.recognition_feature_seconds,
    )
    np.savez_compressed(cache_path, signature=signature)
    return signature


def load_reference_signatures(cfg: Config) -> list[tuple[str, str, object]]:
    index_path = cfg.pasta_referencias / "referencias.csv"
    rows = read_reference_index(index_path)
    result: list[tuple[str, str, object]] = []
    for row in rows:
        if (row.get("ativa") or "SIM").strip().upper() not in {"SIM", "S", "1", "TRUE"}:
            continue
        rel = (row.get("arquivo") or "").strip()
        title = (row.get("titulo") or "").strip()
        music_id = (row.get("musica_id") or "").strip()
        if not rel or not title:
            continue
        # O índice grava caminhos relativos com "/"; reconstruímos de forma portátil.
        path = cfg.pasta_referencias.joinpath(*Path(rel.replace("\\", "/")).parts)
        if not path.exists():
            logging.warning("Referência ausente e ignorada: %s", path)
            continue
        signature = _reference_signature_cache(cfg, row, path)
        if len(signature) >= 4:
            result.append((music_id, title, signature))
    return result


def learned_recognition_thresholds(cfg: Config) -> tuple[float, float]:
    """Ajusta conservadoramente os limites usando correções humanas anteriores.

    O sistema nunca reduz os limites configurados automaticamente; ele apenas pode
    elevá-los quando houver falsos positivos registrados, reduzindo reincidências.
    """
    import numpy as np
    path = cfg.pasta_aprendizado / "identificacoes.jsonl"
    score_threshold = float(cfg.recognition_auto_score)
    margin_threshold = float(cfg.recognition_auto_margin)
    if not path.exists():
        return score_threshold, margin_threshold
    wrong_scores: list[float] = []
    wrong_margins: list[float] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("resultado", "")).strip().lower() != "corrigida":
            continue
        try:
            wrong_scores.append(float(row.get("score_identificacao", 0.0)))
            wrong_margins.append(float(row.get("margem", 0.0)))
        except (TypeError, ValueError):
            continue
    if wrong_scores:
        q = 0.80 if len(wrong_scores) >= 3 else 1.0
        score_threshold = max(score_threshold, float(np.quantile(wrong_scores, q)) + 0.02)
        margin_threshold = max(margin_threshold, float(np.quantile(wrong_margins, q)) + 0.01)
    return min(score_threshold, 0.94), min(margin_threshold, 0.30)


def identify_segments_from_references(
    cfg: Config,
    master: Path,
    segments: Sequence[Segment],
    *,
    apply_titles: bool = True,
) -> dict[str, int]:
    if not cfg.recognition_enabled:
        return {"referencias": 0, "segmentos": 0, "aplicados": 0}
    references = load_reference_signatures(cfg)
    if not references:
        logging.info("Identificação automática não executada: banco de referências vazio.")
        return {"referencias": 0, "segmentos": 0, "aplicados": 0}

    score_threshold, margin_threshold = learned_recognition_thresholds(cfg)
    logging.info(
        "Identificação automática: %d referências carregadas. Limites atuais: score %.3f; margem %.3f.",
        len(references), score_threshold, margin_threshold,
    )
    identified = 0
    applied = 0
    for segment in segments:
        segment.titulo_sugerido = ""
        segment.score_identificacao = 0.0
        segment.segunda_opcao = ""
        segment.score_segunda_opcao = 0.0
        segment.terceira_opcao = ""
        segment.score_terceira_opcao = 0.0
        segment.identificacao_aplicada = False
        duration = max(0.0, segment.fim_bruto - segment.inicio_bruto)
        if duration < cfg.recognition_min_seconds:
            continue
        query = chroma_signature(
            master,
            start_seconds=segment.inicio_bruto,
            end_seconds=segment.fim_bruto,
            target_rate=cfg.recognition_sample_rate,
            feature_seconds=cfg.recognition_feature_seconds,
        )
        if len(query) < 4:
            continue
        per_song: dict[str, tuple[str, float]] = {}
        for music_id, title, reference in references:
            score = _signature_similarity(
                query,
                reference,
                window_seconds=cfg.recognition_window_seconds,
                windows_per_track=cfg.recognition_windows_per_track,
                step_seconds=cfg.recognition_candidate_step_seconds,
            )
            key = music_id or normalize_title(title)
            previous = per_song.get(key)
            if previous is None or score > previous[1]:
                per_song[key] = (title, score)
        ranking = sorted(per_song.values(), key=lambda item: item[1], reverse=True)
        if not ranking:
            continue
        best_title, best_score = ranking[0]
        second_title, second_score = ranking[1] if len(ranking) > 1 else ("", 0.0)
        third_title, third_score = ranking[2] if len(ranking) > 2 else ("", 0.0)
        segment.titulo_sugerido = best_title
        segment.score_identificacao = float(best_score)
        segment.segunda_opcao = second_title
        segment.score_segunda_opcao = float(second_score)
        segment.terceira_opcao = third_title
        segment.score_terceira_opcao = float(third_score)
        identified += 1
        margin = best_score - second_score
        if apply_titles and not segment.titulo and best_score >= score_threshold and margin >= margin_threshold:
            segment.titulo = best_title
            segment.identificacao_aplicada = True
            applied += 1
        logging.info(
            "Faixa %02d: sugestão %s (%.3f), alternativa %s (%.3f), margem %.3f%s",
            segment.ordem,
            best_title,
            best_score,
            second_title or "-",
            second_score,
            margin,
            " [aplicada]" if segment.identificacao_aplicada else "",
        )
    return {"referencias": len(references), "segmentos": identified, "aplicados": applied}

def command_analyze(cfg: Config, *, verbose: bool, no_previews: bool, recomecar: bool = False) -> None:
    ensure_directories(cfg)
    previous_backup = backup_previous_review(cfg)
    setup_logging(cfg.pasta_revisao / "ensaio.log", verbose)
    if previous_backup:
        logging.info("Revisão anterior preservada em: %s", previous_backup)
    check_dependencies(cfg, require_analysis=True)

    raw_files, date_code = discover_raw_files(cfg)
    work_dir = work_dir_for_date(cfg, date_code)
    # Evita destruir o único áudio mestre de uma revisão ainda em andamento.
    if work_dir.exists() and any(work_dir.iterdir()):
        if recomecar:
            # Confirmação explícita do usuário: renomeia, nunca apaga, os
            # intermediários remanescentes de uma análise interrompida.
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            recovered = work_dir.with_name(f"temporarios_interrompidos_{stamp}")
            work_dir.rename(recovered)
            logging.warning("Análise anterior preservada em %s", recovered)
        else:
            current_manifest = cfg.pasta_revisao / "manifesto.json"
            if current_manifest.exists():
                try:
                    current_date = str(load_manifest(current_manifest).get("data_codigo", ""))
                except (EnsaioError, ValueError, json.JSONDecodeError):
                    current_date = ""
                if current_date == date_code:
                    raise EnsaioError(
                        f"Já existe processamento em andamento para {date_code}: {work_dir}. "
                        "A revisão foi preservada; não será apagada automaticamente."
                    )
            # Não remover automaticamente intermediários de uma sessão antiga.
            raise EnsaioError(
                f"Já existe conteúdo temporário para {date_code}: {work_dir}. "
                "A análise foi interrompida para evitar perda de arquivos."
            )
    work_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Arquivos em ordem cronológica: %s", ", ".join(p.name for p in raw_files))
    normalized = normalize_files(cfg, raw_files, work_dir)
    master = work_dir / "master.wav"
    concatenate_wavs(cfg, normalized, master)
    total = media_duration(cfg, master)

    loudness_rows, music_regions = analyze_loudness(cfg, master)
    write_loudness_csv(cfg.pasta_revisao / "analise_volume.csv", loudness_rows)
    review_segments = build_review_segments(cfg, music_regions, total)
    recognition_stats = identify_segments_from_references(cfg, master, review_segments, apply_titles=True)
    write_review_csv(cfg.pasta_revisao / "segmentos.csv", review_segments)
    save_manifest(
        cfg,
        cfg.pasta_revisao / "manifesto.json",
        date_code=date_code,
        raw_files=raw_files,
        master=master,
    )

    if not no_previews:
        logging.info("Gerando prévias MP3 para revisão")
        create_previews(cfg, master, review_segments)

    included = sum(1 for s in review_segments if s.incluir)
    short = len(review_segments) - included
    logging.info("Análise concluída: %d músicas sugeridas; %d tentativas curtas.", included, short)
    if recognition_stats.get("referencias"):
        logging.info(
            "Reconhecimento: %d faixas comparadas; %d títulos aplicados automaticamente.",
            recognition_stats.get("segmentos", 0), recognition_stats.get("aplicados", 0),
        )
    print("\nANÁLISE CONCLUÍDA")
    print("A interface de revisão será aberta no navegador.")
    print("Também é possível reabri-la depois com: revisar.bat")


def incorporate_selected_references(
    cfg: Config, date_code: str, master: Path, selected: Sequence[Segment]
) -> tuple[int, int]:
    chosen = [item for item in selected if item.usar_como_referencia]
    if not chosen:
        logging.info("Nenhuma execução marcada para o banco de referências.")
        return 0, 0

    catalog_path = cfg.pasta_referencias / "catalogo_musicas.csv"
    index_path = cfg.pasta_referencias / "referencias.csv"
    catalog = read_catalog(catalog_path)
    index_rows = read_reference_index(index_path)
    existing_hashes = {row.get("sha256", "") for row in index_rows}
    master_duration = media_duration(cfg, master)
    temp_dir = cfg.pasta_referencias / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    imported = 0
    duplicates = 0
    date_iso = datetime.strptime(date_code, "%y%m%d").strftime("%Y-%m-%d")

    for segment in chosen:
        start = max(0.0, segment.inicio_corte + cfg.reference_start_offset_seconds)
        end = min(master_duration, segment.fim_corte - cfg.reference_end_trim_seconds)
        if end - start < cfg.reference_min_seconds:
            raise EnsaioError(
                f"A referência da faixa {segment.ordem} teria apenas {end-start:.1f}s. "
                f"O mínimo é {cfg.reference_min_seconds:.1f}s."
            )
        temp = temp_dir / f"{date_iso}_seg{segment.ordem:03d}.tmp.wav"
        run_command([
            cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", format_seconds(start), "-t", format_seconds(end-start),
            "-i", str(master), "-vn", "-ar", str(cfg.sample_rate), "-ac", str(cfg.channels),
            "-c:a", "pcm_s16le", str(temp),
        ])
        digest = file_sha256(temp)
        if digest in existing_hashes:
            existing = next((row for row in index_rows if row.get("sha256") == digest), None)
            temp.unlink(missing_ok=True)
            if existing and normalize_title(existing.get("titulo", "")) != normalize_title(segment.titulo):
                raise EnsaioError(
                    f"A faixa {segment.ordem} já está no banco como "
                    f"{existing.get('titulo', '[sem título]')!r}, mas agora foi identificada como "
                    f"{segment.titulo!r}. Corrija o título antes de finalizar."
                )
            duplicates += 1
            continue
        music = find_or_create_music(catalog, segment.titulo, "")
        music_id = music["musica_id"]
        audio_dir = cfg.pasta_referencias / "audio" / music_id
        audio_dir.mkdir(parents=True, exist_ok=True)
        reference_id = next_reference_id(index_rows)
        destination = audio_dir / f"{date_iso}_seg{segment.ordem:03d}_{reference_id}.wav"
        temp.replace(destination)
        now = datetime.now().isoformat(timespec="seconds")
        index_rows.append({
            "referencia_id": reference_id,
            "musica_id": music_id,
            "titulo": music.get("titulo_canonico", segment.titulo),
            "data_ensaio": date_iso,
            "ordem": str(segment.ordem),
            "arquivo": str(destination.relative_to(cfg.pasta_referencias)).replace("\\", "/"),
            "inicio_master": decimal_text(start),
            "fim_master": decimal_text(end),
            "duracao": decimal_text(media_duration(cfg, destination)),
            "sha256": digest,
            "ativa": "SIM",
            "criado_em": now,
            "observacao": f"Qualidade: {segment.qualidade}. {segment.observacao}".strip(),
        })
        existing_hashes.add(digest)
        imported += 1

    write_catalog(catalog_path, catalog)
    write_reference_index(index_path, index_rows)
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        temp_dir.rmdir()
    logging.info("Referências incorporadas: %d; duplicadas: %d", imported, duplicates)
    return imported, duplicates


def command_finalize(cfg: Config, *, verbose: bool, no_move: bool) -> None:
    ensure_directories(cfg)
    setup_logging(cfg.pasta_revisao / "ensaio.log", verbose)
    check_dependencies(cfg, require_analysis=False)

    manifest_path = cfg.pasta_revisao / "manifesto.json"
    manifest = repair_manifest_paths(cfg, manifest_path)
    date_code = str(manifest["data_codigo"])
    master = Path(manifest["master"])
    if not master.exists():
        # Última tentativa de recuperação sem perder a revisão existente.
        master = source_master_for_date(cfg, date_code)
        manifest["master"] = str(master.resolve())
        manifest["app_version"] = APP_VERSION
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    raw_files = [Path(item) for item in manifest["arquivos_brutos"]]
    for path in raw_files:
        if not path.exists():
            raise EnsaioError(
                f"Arquivo bruto esperado não está mais em brutas: {path}. "
                "A finalização foi interrompida."
            )

    selected = read_review_csv(cfg.pasta_revisao / "segmentos.csv")
    master_duration = media_duration(cfg, master)
    validate_selected_segments(selected, master_duration)

    work_dir = work_dir_for_date(cfg, date_code)
    parts = extract_selected_segments(cfg, master, selected, work_dir)
    base = output_basename(date_code)
    final_video = cfg.pasta_output / f"{base}.mp4"
    description = cfg.pasta_output / f"{base}.descricao.txt"
    # O relatório técnico continua disponível para incorporação manual futura.
    report = cfg.pasta_dados / "relatorios" / f"{base}.segmentos.csv"

    temp_audio = work_dir / "audio_final.wav"
    concatenate_wavs(cfg, parts, temp_audio)
    create_static_video(cfg, temp_audio, final_video)
    write_video_description(description, selected)
    verify_final_files(cfg, final_video, temp_audio, description)
    report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cfg.pasta_revisao / "segmentos.csv", report)
    references_imported, reference_duplicates = incorporate_selected_references(
        cfg, date_code, master, selected
    )

    should_move = cfg.move_raw_after_success and not no_move
    archived_to: Path | None = None
    if should_move:
        archived_to = archive_raw_files(cfg, raw_files, date_code)

    # Somente após gerar e validar vídeo/áudio, incorporar referências e,
    # quando solicitado, arquivar os WAV originais.
    intermediates_removed = cleanup_work_dir(cfg, date_code)
    logging.info("Finalização concluída com êxito.")
    print("\nARQUIVOS GERADOS")
    print(final_video)
    print(description)
    logging.info("Relatório técnico preservado em %s", report)
    print(f"Referências incorporadas: {references_imported}; duplicadas ignoradas: {reference_duplicates}")
    if archived_to:
        print(f"Brutos movidos para: {archived_to}")
    else:
        print("Arquivos brutos mantidos na pasta brutas.")
    if intermediates_removed:
        print("Arquivos intermediários descartados após validação.")
    else:
        print("Aviso: não foi possível limpar os intermediários. Consulte o log.")



def normalize_title(value: str) -> str:
    """Normaliza título para comparação, sem alterar a grafia armazenada."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().strip()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def decimal_text(value: float) -> str:
    return f"{float(value):.3f}".replace(".", ",")


def parse_date_argument(value: str) -> str:
    compact = re.sub(r"\D", "", value or "")
    if len(compact) == 8:
        try:
            return datetime.strptime(compact, "%Y%m%d").strftime("%y%m%d")
        except ValueError as exc:
            raise EnsaioError(f"Data inválida: {value!r}") from exc
    if len(compact) == 6:
        try:
            datetime.strptime(compact, "%y%m%d")
            return compact
        except ValueError as exc:
            raise EnsaioError(f"Data inválida: {value!r}") from exc
    raise EnsaioError("Informe a data como AAMMDD ou AAAA-MM-DD.")


def report_date_code(path: Path) -> str | None:
    match = re.match(r"^Ensaio\.(\d{2})\.(\d{2})\.(\d{2})\.segmentos\.csv$", path.name, re.I)
    if not match:
        return None
    code = "".join(match.groups())
    try:
        datetime.strptime(code, "%y%m%d")
    except ValueError:
        return None
    return code


def find_output_report(cfg: Config, date_code: str | None) -> tuple[Path, str]:
    reports: list[tuple[str, Path]] = []
    for folder in (cfg.pasta_dados / "relatorios", cfg.pasta_output):
        for path in folder.glob("Ensaio.*.segmentos.csv"):
            code = report_date_code(path)
            if code and not any(item[0] == code for item in reports):
                reports.append((code, path))
    if date_code:
        for code, path in reports:
            if code == date_code:
                return path, code
        raise EnsaioError(
            f"Relatório final do ensaio {date_code} não encontrado em {cfg.pasta_output}."
        )
    if not reports:
        raise EnsaioError(
            f"Nenhum arquivo Ensaio.AA.MM.DD.segmentos.csv encontrado em {cfg.pasta_output}."
        )
    reports.sort(key=lambda item: item[0])
    return reports[-1][1], reports[-1][0]


def source_master_for_date(cfg: Config, date_code: str) -> Path:
    work_dir = work_dir_for_date(cfg, date_code)
    master = work_dir / "master.wav"
    if master.exists():
        return master

    date = datetime.strptime(date_code, "%y%m%d")
    processed_dir = cfg.pasta_processadas / date.strftime("%Y-%m-%d")
    raw_files = sorted(
        [p for folder in (processed_dir, processed_dir / "originais")
         for p in folder.glob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS],
        key=lambda p: p.name.lower(),
    )
    if not raw_files:
        # Compatibilidade com --nao-mover: os originais ainda estão em brutas.
        raw_files = sorted(
            [p for p in cfg.pasta_brutas.glob("*")
             if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
             and p.name.startswith(date_code)],
            key=lambda p: p.name.lower(),
        )
    if not raw_files:
        raise EnsaioError(
            f"Áudio mestre não encontrado em {work_dir}; não há WAVs "
            f"do ensaio {date_code} em {processed_dir} ou {cfg.pasta_brutas}."
        )

    logging.info("Reconstruindo o áudio mestre a partir dos WAVs originais de %s", date_code)
    work_dir.mkdir(parents=True, exist_ok=True)
    normalized = normalize_files(cfg, raw_files, work_dir)
    concatenate_wavs(cfg, normalized, master)
    return master


def read_all_review_rows(path: Path) -> list[Segment]:
    if not path.exists():
        raise EnsaioError(f"CSV não encontrado: {path}")
    rows: list[Segment] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        required = {"ordem", "incluir", "titulo", "inicio_corte", "fim_corte"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise EnsaioError(f"Colunas ausentes no CSV: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            rows.append(row_to_segment(row, row_number))
    return rows

def candidate_csv_path(cfg: Config, date_code: str) -> Path:
    date = datetime.strptime(date_code, "%y%m%d")
    return cfg.pasta_referencias / "candidatas" / f"Referencias.{date.strftime('%y.%m.%d')}.csv"


def write_reference_candidates(
    cfg: Config, destination: Path, date_code: str, source_report: Path, segments: Sequence[Segment]
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "data_ensaio", "ordem", "musica_id", "titulo", "usar_como_referencia",
        "inicio_referencia", "fim_referencia", "duracao_referencia",
        "status", "arquivo_origem", "observacao",
    ]
    date_iso = datetime.strptime(date_code, "%y%m%d").strftime("%Y-%m-%d")
    with destination.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for segment in sorted(segments, key=lambda item: item.ordem):
            if not segment.incluir:
                continue
            suggested_start = max(
                segment.inicio_bruto,
                segment.inicio_corte + cfg.reference_start_offset_seconds,
            )
            suggested_end = min(
                segment.fim_bruto,
                segment.fim_corte - cfg.reference_end_trim_seconds,
            )
            if suggested_end <= suggested_start:
                suggested_start = segment.inicio_corte
                suggested_end = segment.fim_corte
            writer.writerow({
                "data_ensaio": date_iso,
                "ordem": segment.ordem,
                "musica_id": "",
                "titulo": segment.titulo,
                "usar_como_referencia": "NAO",
                "inicio_referencia": decimal_text(suggested_start),
                "fim_referencia": decimal_text(suggested_end),
                "duracao_referencia": decimal_text(suggested_end - suggested_start),
                "status": "CANDIDATA",
                "arquivo_origem": source_report.name,
                "observacao": "",
            })


def read_catalog(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write_catalog(path: Path, rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["musica_id", "titulo_canonico", "artista", "aliases", "ativa", "criado_em", "atualizado_em"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def next_music_id(catalog: Sequence[dict[str, str]]) -> str:
    numbers = []
    for row in catalog:
        match = re.fullmatch(r"M(\d+)", (row.get("musica_id") or "").strip(), re.I)
        if match:
            numbers.append(int(match.group(1)))
    return f"M{(max(numbers, default=0) + 1):04d}"


def find_or_create_music(
    catalog: list[dict[str, str]], title: str, requested_id: str
) -> dict[str, str]:
    now = datetime.now().isoformat(timespec="seconds")
    requested_id = requested_id.strip().upper()
    if requested_id:
        for row in catalog:
            if (row.get("musica_id") or "").strip().upper() == requested_id:
                return row
        raise EnsaioError(f"musica_id inexistente no catálogo: {requested_id}")

    target = normalize_title(title)
    for row in catalog:
        values = [row.get("titulo_canonico", "")]
        values.extend(part.strip() for part in (row.get("aliases") or "").split("|") if part.strip())
        if any(normalize_title(value) == target for value in values):
            return row

    row = {
        "musica_id": next_music_id(catalog),
        "titulo_canonico": title.strip(),
        "artista": "",
        "aliases": "",
        "ativa": "SIM",
        "criado_em": now,
        "atualizado_em": now,
    }
    catalog.append(row)
    return row


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_reference_index(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write_reference_index(path: Path, rows: Sequence[dict[str, str]]) -> None:
    fields = [
        "referencia_id", "musica_id", "titulo", "data_ensaio", "ordem", "arquivo",
        "inicio_master", "fim_master", "duracao", "sha256", "ativa", "criado_em", "observacao",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def next_reference_id(rows: Sequence[dict[str, str]]) -> str:
    numbers = []
    for row in rows:
        match = re.fullmatch(r"R(\d+)", (row.get("referencia_id") or "").strip(), re.I)
        if match:
            numbers.append(int(match.group(1)))
    return f"R{(max(numbers, default=0) + 1):05d}"


def command_prepare_references(cfg: Config, *, verbose: bool, date_value: str | None) -> None:
    ensure_directories(cfg)
    setup_logging(cfg.pasta_revisao / "ensaio.log", verbose)
    check_dependencies(cfg, require_analysis=False)
    date_code = parse_date_argument(date_value) if date_value else None
    report, date_code = find_output_report(cfg, date_code)
    segments = read_all_review_rows(report)
    included = [segment for segment in segments if segment.incluir]
    if not included:
        raise EnsaioError(f"Nenhuma música incluída em {report}.")
    destination = candidate_csv_path(cfg, date_code)
    if destination.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history = destination.parent / "historico" / stamp
        history.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, history / destination.name)
    write_reference_candidates(cfg, destination, date_code, report, segments)
    print("\nCSV DE CANDIDATAS GERADO")
    print(destination)
    print("Marque SIM apenas nas execuções sem erros e ajuste os tempos, se necessário.")
    print("Depois execute: incorporar_referencias.bat")


def command_import_references(cfg: Config, *, verbose: bool, date_value: str | None) -> None:
    ensure_directories(cfg)
    setup_logging(cfg.pasta_revisao / "ensaio.log", verbose)
    check_dependencies(cfg, require_analysis=False)
    date_code = parse_date_argument(date_value) if date_value else None
    if date_code is None:
        files = []
        for path in (cfg.pasta_referencias / "candidatas").glob("Referencias.*.csv"):
            match = re.match(r"^Referencias\.(\d{2})\.(\d{2})\.(\d{2})\.csv$", path.name, re.I)
            if match:
                files.append(("".join(match.groups()), path))
        if not files:
            raise EnsaioError("Nenhum CSV de candidatas foi encontrado.")
        files.sort(key=lambda item: item[0])
        date_code, candidates_path = files[-1]
    else:
        candidates_path = candidate_csv_path(cfg, date_code)
    if not candidates_path.exists():
        raise EnsaioError(f"CSV de candidatas não encontrado: {candidates_path}")

    master = source_master_for_date(cfg, date_code)
    master_duration = media_duration(cfg, master)
    catalog_path = cfg.pasta_referencias / "catalogo_musicas.csv"
    index_path = cfg.pasta_referencias / "referencias.csv"
    catalog = read_catalog(catalog_path)
    index_rows = read_reference_index(index_path)
    existing_hashes = {row.get("sha256", "") for row in index_rows}

    with candidates_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = list(reader.fieldnames or [])
        required = {"ordem", "musica_id", "titulo", "usar_como_referencia", "inicio_referencia", "fim_referencia"}
        missing = required - set(fieldnames)
        if missing:
            raise EnsaioError(f"Colunas ausentes no CSV de candidatas: {', '.join(sorted(missing))}")
        candidate_rows = list(reader)
    for name in ("status", "duracao_referencia"):
        if name not in fieldnames:
            fieldnames.append(name)

    imported = 0
    duplicates = 0
    already_imported = 0
    selected = 0
    temp_dir = cfg.pasta_referencias / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for row_number, row in enumerate(candidate_rows, start=2):
        if not parse_yes_no(row.get("usar_como_referencia", "NAO")):
            continue
        selected += 1
        title = (row.get("titulo") or "").strip()
        if not title:
            raise EnsaioError(f"Título vazio na linha {row_number} do CSV de candidatas.")
        if (row.get("status") or "").strip().upper() == "INCORPORADA" and (row.get("musica_id") or "").strip():
            already_imported += 1
            continue
        start = parse_decimal(row.get("inicio_referencia", ""), "inicio_referencia", row_number)
        end = parse_decimal(row.get("fim_referencia", ""), "fim_referencia", row_number)
        if start < 0 or end <= start or end > master_duration + 0.25:
            raise EnsaioError(f"Intervalo inválido na linha {row_number}: {start:.3f}–{end:.3f} s.")
        duration = end - start
        if duration < cfg.reference_min_seconds:
            raise EnsaioError(
                f"A referência da linha {row_number} tem apenas {duration:.1f}s; "
                f"o mínimo configurado é {cfg.reference_min_seconds:.1f}s."
            )
        order = int(row.get("ordem", row_number - 1))
        date_iso = datetime.strptime(date_code, "%y%m%d").strftime("%Y-%m-%d")
        temp = temp_dir / f"{date_iso}_seg{order:03d}_linha{row_number}.tmp.wav"
        run_command([
            cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", format_seconds(start), "-t", format_seconds(duration),
            "-i", str(master), "-vn", "-ar", str(cfg.sample_rate), "-ac", str(cfg.channels),
            "-c:a", "pcm_s16le", str(temp),
        ])
        digest = file_sha256(temp)
        if digest in existing_hashes:
            existing = next((item for item in index_rows if item.get("sha256") == digest), None)
            temp.unlink(missing_ok=True)
            if existing:
                row["musica_id"] = existing.get("musica_id", row.get("musica_id", ""))
            row["status"] = "DUPLICADA"
            row["duracao_referencia"] = decimal_text(duration)
            duplicates += 1
            continue
        music = find_or_create_music(catalog, title, row.get("musica_id", ""))
        music_id = music["musica_id"]
        audio_dir = cfg.pasta_referencias / "audio" / music_id
        audio_dir.mkdir(parents=True, exist_ok=True)
        destination = audio_dir / f"{date_iso}_seg{order:03d}_{next_reference_id(index_rows)}.wav"
        temp.replace(destination)
        reference_id = re.search(r"_(R\d+)\.wav$", destination.name).group(1)
        now = datetime.now().isoformat(timespec="seconds")
        index_rows.append({
            "referencia_id": reference_id,
            "musica_id": music_id,
            "titulo": music.get("titulo_canonico", title),
            "data_ensaio": date_iso,
            "ordem": str(order),
            "arquivo": str(destination.relative_to(cfg.pasta_referencias)).replace("\\", "/"),
            "inicio_master": decimal_text(start),
            "fim_master": decimal_text(end),
            "duracao": decimal_text(media_duration(cfg, destination)),
            "sha256": digest,
            "ativa": "SIM",
            "criado_em": now,
            "observacao": (row.get("observacao") or "").strip(),
        })
        existing_hashes.add(digest)
        row["musica_id"] = music_id
        row["status"] = "INCORPORADA"
        row["duracao_referencia"] = decimal_text(duration)
        imported += 1

    if selected == 0:
        raise EnsaioError("Nenhuma linha está marcada como SIM em usar_como_referencia.")
    write_catalog(catalog_path, catalog)
    write_reference_index(index_path, index_rows)
    with candidates_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(candidate_rows)
    print("\nREFERÊNCIAS PROCESSADAS")
    print(f"Incorporadas: {imported}")
    print(f"Já incorporadas anteriormente: {already_imported}")
    print(f"Duplicadas ignoradas: {duplicates}")
    print(f"Catálogo: {catalog_path}")
    print(f"Índice: {index_path}")
    print(f"Áudios: {cfg.pasta_referencias / 'audio'}")
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        temp_dir.rmdir()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automatiza corte, revisão, vídeo estático e capítulos de ensaios.",
    )
    parser.add_argument(
        "comando",
        choices=["analisar", "finalizar", "preparar-referencias", "incorporar-referencias"],
        help=(
            "analisar cria o CSV; finalizar gera os arquivos finais; "
            "preparar-referencias cria a seleção; incorporar-referencias extrai as aprovadas."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
        help="Caminho do config.json.",
    )
    parser.add_argument("--verbose", action="store_true", help="Log detalhado.")
    parser.add_argument(
        "--recomecar", action="store_true",
        help="Preserva intermediários interrompidos com nome de recuperação e reinicia a análise.",
    )
    parser.add_argument(
        "--data",
        help="Data do ensaio para referências, em AAMMDD ou AAAA-MM-DD. Sem informar, usa a mais recente.",
    )
    parser.add_argument(
        "--sem-previas",
        action="store_true",
        help="Não gerar os MP3 de prévia na análise.",
    )
    parser.add_argument(
        "--nao-mover",
        action="store_true",
        help="Na finalização, manter os WAV em brutas mesmo após sucesso.",
    )
    parser.add_argument("--version", action="version", version=APP_VERSION)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        cfg = load_config(args.config)
        if args.comando == "analisar":
            command_analyze(cfg, verbose=args.verbose, no_previews=args.sem_previas, recomecar=args.recomecar)
        elif args.comando == "finalizar":
            command_finalize(cfg, verbose=args.verbose, no_move=args.nao_mover)
        elif args.comando == "preparar-referencias":
            command_prepare_references(cfg, verbose=args.verbose, date_value=args.data)
        else:
            command_import_references(cfg, verbose=args.verbose, date_value=args.data)
        return 0
    except EnsaioError as exc:
        logging.error("%s", exc)
        print(f"\nERRO: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.", file=sys.stderr)
        return 130
    except Exception as exc:
        logging.exception("Erro inesperado")
        print(f"\nERRO INESPERADO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
