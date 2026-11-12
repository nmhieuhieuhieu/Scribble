"""Split long audio into STT-sized chunks using ffmpeg silencedetect.

Why ffmpeg, not Silero VAD: the project ships with ffmpeg, and silencedetect
gives accurate silence boundaries for sentence-aligned cuts. Adding a Silero
ONNX model just for VAD would inflate the installer with no quality win.

Output chunks satisfy:
  - duration ≤ 28s (Nvidia Riva offline_recognize cap)
  - duration ≥ ~8s (avoid wasteful short STT calls)
  - 1.5s overlap with previous chunk (de-duped at merge time)
  - cuts prefer silence boundaries to keep words intact
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from services.audio import find_ffmpeg, read_wav_floats, wav_duration_ms
from audio_config import (
    CHUNK_TARGET_MS,
    CHUNK_MAX_MS,
    CHUNK_MIN_MS,
    OVERLAP_MS,
    SILENCE_MIN_DURATION_S,
    SILENCE_NOISE_DB,
    SNAP_WINDOW_MS,
    MIN_TURN_MS,
    FINE_WINDOW_MS,
    SPEAKER_SNAP_TOLERANCE_MS,
)

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class AudioChunk:
    idx: int
    start_ms: int
    end_ms: int
    path: Path
    speaker_id: int | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")
_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")


def estimate_noise_floor_db(wav_path: Path) -> int:
    """Estimate background noise level in dB dynamically from audio frames."""
    try:
        sr, samples = read_wav_floats(wav_path)
        if len(samples) == 0 or sr <= 0:
            return SILENCE_NOISE_DB
        slice_samples = samples[: 30 * sr]
        frame_len = int(sr * 0.05)  # 50ms
        rms_list = []
        for i in range(0, len(slice_samples) - frame_len, frame_len):
            rms = np.sqrt(np.mean(slice_samples[i : i + frame_len] ** 2))
            if rms > 1e-6:
                rms_list.append(float(20 * np.log10(rms)))
        if rms_list:
            p20 = float(np.percentile(rms_list, 20))
            # Set silence threshold above noise floor, clamped between -45dB and -25dB
            return int(min(-25, max(-45, p20 + 5)))
    except Exception as exc:
        log.debug("[vad] estimate_noise_floor_db fallback: %s", exc)
    return SILENCE_NOISE_DB


def detect_silence_boundaries(
    wav_path: Path,
    total_ms: int,
    noise_db: int | None = None,
    min_duration_s: float = SILENCE_MIN_DURATION_S,
) -> list[int]:
    """Run ffmpeg silencedetect and return midpoints (ms) of silence regions.

    Always includes total_ms as the last boundary so the splitter can cut
    the tail without needing a trailing silence.
    """
    if noise_db is None:
        noise_db = estimate_noise_floor_db(wav_path)

    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(wav_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_duration_s:.2f}",
        "-f",
        "null",
        "-",
    ]
    kwargs: dict = {"capture_output": True, "timeout": 300}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        log.warning("[vad] silencedetect timed out, using time-based splits only")
        return [total_ms]

    stderr = result.stderr.decode("utf-8", errors="replace")

    # Pair up silence_start / silence_end into (start, end) ms regions; take midpoint.
    starts_s: list[float] = []
    ends_s: list[float] = []
    for line in stderr.splitlines():
        m = _SILENCE_START_RE.search(line)
        if m:
            starts_s.append(float(m.group(1)))
            continue
        m = _SILENCE_END_RE.search(line)
        if m:
            ends_s.append(float(m.group(1)))

    boundaries: list[int] = []
    for i, end in enumerate(ends_s):
        start = starts_s[i] if i < len(starts_s) else end
        midpoint_ms = int(((start + end) / 2.0) * 1000)
        if 0 < midpoint_ms < total_ms:
            boundaries.append(midpoint_ms)
    boundaries.append(total_ms)
    boundaries.sort()
    return boundaries


def _find_best_cut(
    boundaries: list[int], min_ms: int, target_ms: int, max_ms: int
) -> int:
    """Pick silence boundary closest to target_ms within [min_ms, max_ms].

    Falls back to max_ms (hard cut) when no boundary qualifies — happens for
    continuous speech with no detectable pauses.
    """
    candidates = [b for b in boundaries if min_ms <= b <= max_ms]
    if not candidates:
        return max_ms
    return min(candidates, key=lambda b: abs(b - target_ms))


def _wav_total_ms(wav_path: Path) -> int:
    try:
        return wav_duration_ms(wav_path)
    except Exception as exc:
        log.warning("[vad] wav_duration_ms failed for %s: %s", wav_path, exc)
        return 0


def _extract_chunk_with_ffmpeg(
    src: Path, dst: Path, start_ms: int, duration_ms: int
) -> None:
    """Copy a slice [start, start+duration] from src WAV to dst WAV.

    Uses ffmpeg (not direct WAV slicing) so we always produce a properly
    framed 16kHz mono PCM WAV regardless of any quirks in the source.
    """
    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_ms / 1000.0:.3f}",
        "-t",
        f"{duration_ms / 1000.0:.3f}",
        "-i",
        str(src),
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        "1",
        "-acodec",
        "pcm_s16le",
        "-f",
        "wav",
        str(dst),
    ]
    kwargs: dict = {"capture_output": True, "timeout": 60}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg extract failed (rc={result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:300]}"
        )


def plan_speaker_turn_chunks(
    timeline: list[tuple[int, int, int]],
    silence_boundaries: list[int],
    total_ms: int,
    fine_window_ms: int = FINE_WINDOW_MS,
    snap_window_ms: int = SNAP_WINDOW_MS,
    min_turn_ms: int = MIN_TURN_MS,
    chunk_min_ms: int = CHUNK_MIN_MS,
    chunk_target_ms: int = CHUNK_TARGET_MS,
    chunk_max_ms: int = CHUNK_MAX_MS,
    overlap_ms: int = OVERLAP_MS,
) -> list[tuple[int, int, int]]:
    """Plan natural chunks from a diarization timeline + silence boundaries.

    Port of src-tauri/src/pipeline/mod.rs::plan_speaker_turn_chunks:
      1. Merge consecutive fine windows of the same speaker into raw turns.
      2. Blip smoothing: merge isolated 1-window blips (A -> short B -> A)
         where B <= fine_window_ms into Speaker A, so coughs/noise don't slice sentences.
      3. Snap turn transitions to the nearest silence midpoint within +-1500ms.
      4. Renumber speakers by order of appearance (0, 1, 2...).
      5. Split single-speaker monologues (> CHUNK_MAX_MS) at natural silence boundaries
         with 0ms overlap (falling back to overlap_ms only when continuous speech offers no pause).
    """
    if not timeline or total_ms <= 0:
        return []

    # 1. Merge consecutive fine windows of the same speaker into raw turns
    turns: list[list[int]] = []  # [start_ms, end_ms, speaker_id]
    for seg_start, seg_end, spk_id in timeline:
        s = min(seg_start, total_ms)
        e = min(seg_end, total_ms)
        if e <= s:
            continue
        if turns and turns[-1][2] == spk_id:
            turns[-1][1] = max(turns[-1][1], e)
        else:
            turns.append([s, e, spk_id])

    if not turns:
        return []

    # Smooth isolated 1-window blips (A -> short B -> A) so a cough or brief
    # backchannel doesn't slice Speaker A's sentence in half.
    if len(turns) >= 3:
        smoothed: list[list[int]] = []
        i = 0
        while i < len(turns):
            if (
                i + 2 < len(turns)
                and turns[i][2] == turns[i + 2][2]
                and (turns[i + 1][1] - turns[i + 1][0]) <= fine_window_ms
            ):
                merged_end = turns[i + 2][1]
                spk = turns[i][2]
                start = turns[i][0]
                smoothed.append([start, merged_end, spk])
                i += 3
            else:
                smoothed.append(turns[i])
                i += 1

        # Re-merge any adjacent turns that now share a speaker.
        collapsed: list[list[int]] = []
        for t in smoothed:
            if collapsed and collapsed[-1][2] == t[2]:
                collapsed[-1][1] = max(collapsed[-1][1], t[1])
            else:
                collapsed.append(t)
        turns = collapsed

    # 2. Compute contiguous turn boundaries covering [0, total_ms], snapping
    # each speaker change to the nearest silence pause within +-snap_window_ms.
    cut_points: list[int] = [0]
    for i in range(len(turns) - 1):
        prev_cut = cut_points[-1]
        pair_curr = turns[i]
        pair_next = turns[i + 1]
        raw_mid = (pair_curr[1] + pair_next[0]) // 2

        candidates = [
            b
            for b in silence_boundaries
            if (b > prev_cut + min_turn_ms)
            and (b + min_turn_ms < total_ms)
            and abs(b - raw_mid) <= snap_window_ms
        ]
        if candidates:
            snapped = min(candidates, key=lambda b: abs(b - raw_mid))
        else:
            snapped = raw_mid

        clamped = max(min(prev_cut + 500, total_ms), min(snapped, total_ms))
        cut_points.append(clamped)
    cut_points.append(total_ms)

    # 3. Renumber speakers in order of first appearance (0, 1, 2, ...) and
    # split any long single-speaker turn (> CHUNK_MAX_MS) at natural pauses.
    seen_speakers: dict[int, int] = {}
    out: list[tuple[int, int, int]] = []

    for idx, (_, _, raw_spk) in enumerate(turns):
        if raw_spk not in seen_speakers:
            seen_speakers[raw_spk] = len(seen_speakers)
        spk = seen_speakers[raw_spk]
        turn_start = cut_points[idx]
        turn_end = cut_points[idx + 1]
        if turn_end <= turn_start:
            continue

        cursor = turn_start
        while cursor < turn_end:
            rem = turn_end - cursor
            if rem <= chunk_max_ms:
                out.append((cursor, turn_end, spk))
                break

            # Look for a silence boundary inside this speaker's monologue.
            min_b = cursor + chunk_min_ms
            target_b = cursor + chunk_target_ms
            max_b = min(cursor + chunk_max_ms, turn_end)

            silence_cuts = [
                b for b in silence_boundaries if min_b <= b <= max_b and b + 1000 < turn_end
            ]
            if silence_cuts:
                silence_cut = min(silence_cuts, key=lambda b: abs(b - target_b))
                out.append((cursor, silence_cut, spk))
                # Clean silence pause -> no overlap needed.
                cursor = silence_cut
            else:
                out.append((cursor, max_b, spk))
                cursor = max(max_b - overlap_ms, cursor + 1)

    return out


def split_into_chunks(wav_path: Path, out_dir: Path) -> list[AudioChunk]:
    """Split a normalized WAV into overlapping chunks based purely on VAD.
    
    Port of src-tauri/src/pipeline/mod.rs::split_into_chunks.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total_ms = _wav_total_ms(wav_path)
    if total_ms <= 0:
        return []

    if total_ms < CHUNK_MIN_MS:
        chunk_path = out_dir / "chunk_0000.wav"
        _extract_chunk_with_ffmpeg(wav_path, chunk_path, 0, total_ms)
        return [AudioChunk(idx=0, start_ms=0, end_ms=total_ms, path=chunk_path)]

    boundaries = detect_silence_boundaries(wav_path, total_ms)
    chunks: list[AudioChunk] = []
    cursor_ms = 0
    chunk_idx = 0

    while cursor_ms < total_ms:
        remaining = total_ms - cursor_ms
        if remaining <= CHUNK_MAX_MS:
            end_ms = total_ms
        else:
            end_ms = _find_best_cut(
                boundaries,
                cursor_ms + CHUNK_MIN_MS,
                cursor_ms + CHUNK_TARGET_MS,
                cursor_ms + CHUNK_MAX_MS,
            )

        if end_ms <= cursor_ms:
            break

        chunk_path = out_dir / f"chunk_{chunk_idx:04d}.wav"
        _extract_chunk_with_ffmpeg(wav_path, chunk_path, cursor_ms, end_ms - cursor_ms)
        chunks.append(
            AudioChunk(
                idx=chunk_idx,
                start_ms=cursor_ms,
                end_ms=end_ms,
                path=chunk_path,
            )
        )

        if end_ms >= total_ms:
            break
        cursor_ms = max(end_ms - OVERLAP_MS, cursor_ms + 1)
        chunk_idx += 1

    log.info("[vad] split %dms into %d chunks (overlap %dms)", total_ms, len(chunks), OVERLAP_MS)
    return chunks


def split_into_speaker_chunks(
    wav_path: Path,
    out_dir: Path,
    timeline: list[tuple[int, int, int]] | None = None,
    min_ms: int = CHUNK_MIN_MS,
    target_ms: int = CHUNK_TARGET_MS,
    max_ms: int = CHUNK_MAX_MS,
    silence_min_s: float = SILENCE_MIN_DURATION_S,
) -> list[AudioChunk]:
    """Split normalized audio into single-speaker chunks.

    Port of src-tauri/src/pipeline/mod.rs::diarize_and_split_into_chunks:
    Uses `plan_speaker_turn_chunks` when a timeline is available to slice
    cleanly along natural speaker turns and pauses. Falls back to VAD-only
    `split_into_chunks` when timeline is empty.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total_ms = _wav_total_ms(wav_path)
    if total_ms <= 0:
        return []

    if timeline:
        silence_boundaries = detect_silence_boundaries(
            wav_path, total_ms, min_duration_s=silence_min_s
        )
        planned = plan_speaker_turn_chunks(
            timeline,
            silence_boundaries,
            total_ms,
            chunk_min_ms=min_ms,
            chunk_target_ms=target_ms,
            chunk_max_ms=max_ms,
        )
        if planned:
            chunks: list[AudioChunk] = []
            for idx, (start_ms, end_ms, spk) in enumerate(planned):
                chunk_path = out_dir / f"chunk_{idx:04d}.wav"
                _extract_chunk_with_ffmpeg(wav_path, chunk_path, start_ms, end_ms - start_ms)
                chunks.append(
                    AudioChunk(
                        idx=idx,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        path=chunk_path,
                        speaker_id=spk,
                    )
                )
            log.info(
                "[pipeline] diarized first -> split %dms into %d natural speaker-turn chunks",
                total_ms,
                len(chunks),
            )
            return chunks

    return split_into_chunks(wav_path, out_dir)
