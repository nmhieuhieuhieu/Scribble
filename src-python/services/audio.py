"""
Audio services — ffmpeg utilities, PCM conversion, media type helpers.
"""

import os
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from logger import get_logger

log = get_logger(__name__)


_FFMPEG_CACHE: str | None = None


def find_ffmpeg() -> str:
    """Resolve an ffmpeg binary path, preferring the bundled one.

    Resolution order (first hit wins):
      1. imageio-ffmpeg's bundled static binary — ships in the Python wheel
         and is picked up by PyInstaller via `collect_all('imageio_ffmpeg')`.
         This is the path end users hit in a packaged install (no homebrew /
         choco required — zero manual setup).
      2. ffmpeg sitting next to the sidecar executable — Windows CI copies
         the build-host's ffmpeg.exe here as a legacy fallback.
      3. System PATH (`shutil.which`).
      4. Common per-OS install locations (Homebrew prefix, ProgramFiles,
         Scoop, etc.) for dev environments that have ffmpeg installed but
         not in the inherited PATH (Tauri-launched apps on macOS get a
         stripped PATH that excludes /opt/homebrew/bin).

    Cached after first lookup so we don't subprocess-spawn ffmpeg dozens of
    times for the import-resolution side effect on every audio call.
    """
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE and os.path.isfile(_FFMPEG_CACHE):
        return _FFMPEG_CACHE

    import shutil
    import sys as _sys

    # 1. Prefer the bundled static binary from imageio-ffmpeg. This is the
    # path that makes the app actually self-contained for end users.
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.isfile(bundled):
            # Defensive: ensure exec bit (PyInstaller _MEIPASS preserves it
            # but the static-binary may land in a tarball-extracted dir
            # without +x on Linux).
            if not _sys.platform == "win32":
                try:
                    os.chmod(bundled, 0o755)
                except OSError:
                    pass
            _FFMPEG_CACHE = bundled
            log.info("[ffmpeg] Using bundled imageio-ffmpeg binary: %s", bundled)
            return bundled
    except Exception as e:
        log.warning("[ffmpeg] imageio-ffmpeg not available, falling back to system search: %s", e)

    # 2. Next to the sidecar executable (CI bundling path for Windows).
    exe_dir = Path(_sys.executable).parent
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = exe_dir / name
        if candidate.is_file():
            _FFMPEG_CACHE = str(candidate)
            return _FFMPEG_CACHE

    # 3. System PATH.
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_CACHE = found
        return found

    # 4. Common install locations (dev fallback).
    if _sys.platform == "win32":
        win_candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"),
            Path.home() / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe",
            Path.home() / "scoop" / "shims" / "ffmpeg.exe",
        ]
        for c in win_candidates:
            try:
                if c.is_file():
                    _FFMPEG_CACHE = str(c)
                    return _FFMPEG_CACHE
            except Exception:
                pass
        raise FileNotFoundError(
            "ffmpeg binary not found in the app bundle (this should never happen — "
            "imageio-ffmpeg ships it with the sidecar). Reinstall Scribble from "
            "https://scribble-rho.vercel.app or contact support."
        )
    else:
        for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                _FFMPEG_CACHE = candidate
                return candidate
        raise FileNotFoundError(
            "ffmpeg binary not found in the app bundle (this should never happen — "
            "imageio-ffmpeg ships it with the sidecar). Reinstall Scribble from "
            "https://scribble-rho.vercel.app or contact support."
        )


def transcode_audio_for_export(source: Path, fmt: str) -> Path:
    """Transcode audio to the desired export format using ffmpeg.

    Returns a temp file path — caller is responsible for cleanup via _safe_unlink().
    """
    ffmpeg = find_ffmpeg()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}")
    tmp_path = Path(tmp.name)
    tmp.close()

    # Internal system-audio archive may be raw PCM16 (16kHz mono)
    if source.suffix.lower() == ".pcm":
        input_args = ["-f", "s16le", "-ar", "16000", "-ac", "1", "-i", str(source)]
    else:
        input_args = ["-i", str(source)]

    if fmt == "wav":
        cmd = [ffmpeg, "-y", *input_args, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(tmp_path)]
    elif fmt == "mp3":
        # 96 kbps mono → ~43MB/hour (vs WAV ~115MB/hour). Good speech-quality
        # at this rate. libmp3lame ships with the standard ffmpeg build.
        cmd = [
            ffmpeg, "-y", *input_args, "-vn",
            "-acodec", "libmp3lame", "-b:a", "96k", "-ar", "16000", "-ac", "1",
            str(tmp_path),
        ]
    else:  # mp4
        cmd = [ffmpeg, "-y", *input_args, "-vn", "-acodec", "aac", "-b:a", "192k", str(tmp_path)]

    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        safe_unlink(str(tmp_path))
        stderr = result.stderr.decode(errors="replace")[:300]
        raise RuntimeError(stderr or "ffmpeg convert failed")
    return tmp_path


def audio_media_type(ext: str) -> str:
    """Return MIME type for a given audio file extension."""
    ext_l = ext.lower()
    mapping = {".wav": "audio/wav", ".mp4": "audio/mp4", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".webm": "audio/webm", ".pcm": "application/octet-stream"}
    return mapping.get(ext_l, "application/octet-stream")


def safe_unlink(path: str) -> None:
    """Delete a file silently — ignores errors."""
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            p.unlink()
    except Exception:
        pass


def read_wav_floats(path: str | Path) -> tuple[int, np.ndarray]:
    """Pure-Python + numpy WAV reader supporting both PCM and IEEE float.

    Avoids importing scipy (which is excluded from PyInstaller builds).
    Returns (sample_rate, samples_float32_mono).
    """
    p = Path(path)
    with open(p, "rb") as f:
        riff = f.read(12)
        if len(riff) < 12 or riff[:4] != b"RIFF" or riff[8:12] != b"WAVE":
            raise ValueError(f"Not a valid RIFF/WAVE file: {p}")

        fmt_tag = None
        channels = 1
        sample_rate = 16000
        bits_per_sample = 16
        data_bytes = None

        while True:
            chunk_hdr = f.read(8)
            if len(chunk_hdr) < 8:
                break
            chunk_id = chunk_hdr[:4]
            chunk_size = struct.unpack("<I", chunk_hdr[4:])[0]

            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                if len(fmt_data) >= 16:
                    fmt_tag, channels, sample_rate, _, _, bits_per_sample = struct.unpack(
                        "<HHIIHH", fmt_data[:16]
                    )
                    if fmt_tag == 0xFFFE and len(fmt_data) >= 26:
                        fmt_tag = struct.unpack("<H", fmt_data[24:26])[0]
            elif chunk_id == b"data":
                data_bytes = f.read(chunk_size)
                break
            else:
                f.seek(chunk_size, 1)

            if chunk_size % 2 == 1:
                f.seek(1, 1)

    if data_bytes is None or fmt_tag is None:
        raise ValueError(f"WAV data or fmt chunk missing in {p}")

    if fmt_tag == 1:  # PCM
        if bits_per_sample == 16:
            samples = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif bits_per_sample == 8:
            samples = (np.frombuffer(data_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif bits_per_sample == 24:
            raw = np.frombuffer(data_bytes, dtype=np.uint8)
            n_samples = len(raw) // 3
            raw = raw[: n_samples * 3].reshape(-1, 3)
            int24 = (
                raw[:, 0].astype(np.int32)
                | (raw[:, 1].astype(np.int32) << 8)
                | (raw[:, 2].astype(np.int32) << 16)
            )
            int24 = np.where(int24 >= 0x800000, int24 - 0x1000000, int24)
            samples = int24.astype(np.float32) / 8388608.0
        elif bits_per_sample == 32:
            samples = np.frombuffer(data_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported PCM bits per sample: {bits_per_sample}")
    elif fmt_tag == 3:  # IEEE float
        if bits_per_sample == 32:
            samples = np.frombuffer(data_bytes, dtype=np.float32).copy()
        elif bits_per_sample == 64:
            samples = np.frombuffer(data_bytes, dtype=np.float64).astype(np.float32)
        else:
            raise ValueError(f"Unsupported float bits per sample: {bits_per_sample}")
    else:
        raise ValueError(f"Unsupported WAV format tag: {fmt_tag}")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    return sample_rate, samples


def wav_duration_ms(path: str | Path) -> int:
    """Return total duration of a WAV file in milliseconds without scipy."""
    sr, samples = read_wav_floats(path)
    if sr <= 0:
        return 0
    return int(len(samples) * 1000 / sr)
