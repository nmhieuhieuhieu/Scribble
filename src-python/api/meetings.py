"""
Meetings API router — CRUD for meetings, audio download, minutes export.
"""

import json
import tempfile
import wave as _wave
from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from db import Database
from logger import get_logger
from services.audio import transcode_audio_for_export, audio_media_type, safe_unlink
from services.minutes import normalize_minutes_markdown, markdown_to_docx

log = get_logger(__name__)
router = APIRouter()
db = Database()


def _voicescribe_data_dir() -> Path:
    import os
    env_dir = os.getenv("VOICESCRIBE_DATA")
    if env_dir:
        return Path(env_dir)
    db_path = getattr(db, "_db_path", None)
    if db_path:
        return Path(db_path).parent
    from pathlib import Path as _P
    return _P.home() / ".voicescribe"


@router.get("/meetings")
async def list_meetings():
    return db.get_all_meetings()


@router.post("/meetings")
async def create_meeting(request: Request):
    body = await request.json()
    mid = db.create_meeting(
        title=body.get("title", "Untitled"),
        transcript=json.dumps(body.get("transcript", [])) if isinstance(body.get("transcript"), list) else body.get("transcript", ""),
        summary=body.get("summary", ""),
        audio_duration=body.get("audioDuration", 0),
        language=body.get("language", "vi"),
    )
    return {"id": mid}


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: int):
    m = db.get_meeting(meeting_id)
    if not m:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return m


@router.put("/meetings/{meeting_id}")
async def update_meeting(meeting_id: int, request: Request):
    body = await request.json()
    m = db.get_meeting(meeting_id)
    if not m:
        return JSONResponse({"error": "Not found"}, status_code=404)
    key_map = {
        "title": "title", "transcript": "transcript", "summary": "summary",
        "translations": "translations", "audioDuration": "audio_duration",
        "language": "language", "status": "status", "audioPath": "audio_path",
    }
    updates = {}
    for js_key, db_key in key_map.items():
        if js_key in body:
            val = body[js_key]
            if isinstance(val, list):
                val = json.dumps(val)
            updates[db_key] = val
    if updates:
        db.update_meeting(meeting_id, **updates)
    return {"ok": True}


@router.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: int):
    db.delete_meeting(meeting_id)
    return {"ok": True}


def _pcm_to_wav_tmp(source_path: Path) -> Path:
    """Wrap raw PCM16 (16 kHz mono) into a WAV container using the stdlib
    `wave` module — no ffmpeg required. Returns a temp .wav path; the caller
    schedules cleanup. Raises on failure so the caller can fall back."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        pcm_data = source_path.read_bytes()
        with _wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_data)
        return tmp_path
    except Exception:
        safe_unlink(str(tmp_path))
        raise


def _resolve_audio_source(meeting_id: int) -> Path | None:
    """Locate the stored audio file for a meeting (audio_path, with a legacy
    meeting_{id}.<ext> fallback). Returns None when no audio exists."""
    m = db.get_meeting(meeting_id)
    audio_path = (m.get("audio_path") or "") if m else ""
    source_path = Path(audio_path) if audio_path else None
    if source_path is None or not source_path.exists() or not source_path.is_file():
        audio_dir = _voicescribe_data_dir() / "audio"
        for ext in (".wav", ".mp4", ".m4a", ".mp3", ".webm", ".pcm"):
            candidate = audio_dir / f"meeting_{meeting_id}{ext}"
            if candidate.exists() and candidate.is_file():
                source_path = candidate
                if m:
                    try:
                        db.update_meeting(meeting_id, audio_path=str(candidate))
                    except Exception:
                        pass
                break
    if source_path is None or not source_path.exists() or not source_path.is_file():
        return None
    return source_path


def send_range_audio_response(
    source_path: Path,
    range_header: str | None,
    media_type: str,
) -> Response:
    """Stream an audio file with HTTP 206 Partial Content / Range support for seeking."""
    try:
        file_size = source_path.stat().st_size
    except OSError:
        return JSONResponse({"error": "Audio file unreadable"}, status_code=500)

    if file_size == 0:
        return Response(
            content=b"",
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "0",
                "Content-Type": media_type,
            },
        )

    if not range_header or not range_header.startswith("bytes="):
        def full_file_iterator():
            with open(source_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": media_type,
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        return StreamingResponse(
            full_file_iterator(),
            status_code=200,
            headers=headers,
            media_type=media_type,
        )

    # Parse Range: bytes=start-end (RFC 7233 / RFC 9110)
    raw_range = range_header.replace("bytes=", "").strip()
    try:
        parts = raw_range.split("-")
        if parts[0] == "":
            suffix_len = int(parts[1])
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        elif parts[1] == "":
            start = int(parts[0])
            end = file_size - 1
        else:
            start = int(parts[0])
            end = min(int(parts[1]), file_size - 1)
    except (ValueError, IndexError):
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}", "Accept-Ranges": "bytes"},
        )

    if start >= file_size or start > end:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}", "Accept-Ranges": "bytes"},
        )

    content_length = end - start + 1

    def range_iterator():
        with open(source_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_to_read = min(64 * 1024, remaining)
                data = f.read(chunk_to_read)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": media_type,
    }
    return StreamingResponse(
        range_iterator(),
        status_code=206,
        headers=headers,
        media_type=media_type,
    )


@router.get("/meetings/{meeting_id}/audio/stream")
async def stream_meeting_audio(meeting_id: int, request: Request):
    """In-app playback with full HTTP Range (206 Partial Content) support so the
    <audio> element can seek without jumping back to 0:00."""
    source_path = _resolve_audio_source(meeting_id)
    if source_path is None:
        return JSONResponse({"error": "Audio not found"}, status_code=404)

    range_header = request.headers.get("range")

    if source_path.suffix.lower() == ".pcm":
        cache_dir = _voicescribe_data_dir() / "audio" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        wav = cache_dir / f"play_{meeting_id}.wav"
        try:
            if not wav.exists() or wav.stat().st_mtime < source_path.stat().st_mtime:
                pcm_data = source_path.read_bytes()
                with _wave.open(str(wav), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(pcm_data)
            return send_range_audio_response(wav, range_header, "audio/wav")
        except Exception as e:
            log.warning("[meetings] stream pcm->wav failed: %s", e)
            return JSONResponse({"error": "Cannot prepare audio"}, status_code=500)

    media_type = audio_media_type(source_path.suffix)
    return send_range_audio_response(source_path, range_header, media_type)


@router.get("/meetings/{meeting_id}/audio")
async def download_meeting_audio(meeting_id: int, format: str = "mp3"):
    source_path = _resolve_audio_source(meeting_id)
    if source_path is None:
        return JSONResponse({"error": "Audio not found"}, status_code=404)

    export_format = (format or "mp3").strip().lower()
    if export_format not in {"wav", "mp3", "mp4"}:
        return JSONResponse({"error": "format must be wav, mp3, or mp4"}, status_code=400)

    export_path = source_path
    actual_ext = source_path.suffix.lower().lstrip(".")
    cleanup_task = None

    if source_path.suffix.lower() != f".{export_format}":
        if source_path.suffix.lower() == ".pcm" and export_format == "wav":
            # Fast path: raw PCM16 -> WAV via stdlib wave (no ffmpeg).
            try:
                export_path = _pcm_to_wav_tmp(source_path)
                actual_ext = "wav"
                cleanup_task = BackgroundTask(safe_unlink, str(export_path))
            except Exception as e:
                log.warning("[meetings] PCM to WAV failed, serving original: %s", e)
        else:
            try:
                import asyncio
                export_path = await asyncio.to_thread(transcode_audio_for_export, source_path, export_format)
                actual_ext = export_format
                cleanup_task = BackgroundTask(safe_unlink, str(export_path))
            except Exception as e:
                # Transcode unavailable (e.g. ffmpeg / libmp3lame missing on
                # Windows). NEVER serve bytes under a mismatched extension —
                # that yields a ".mp3" the OS player rejects. Raw PCM has no
                # playable container, so wrap it as WAV (stdlib, no ffmpeg);
                # already-compressed sources (m4a/webm/mp3) are served as-is
                # under their TRUE extension (Content-Disposition) so the
                # client saves a file that actually plays.
                log.warning("[meetings] Transcode to %s failed (%s); using safe fallback", export_format, e)
                if source_path.suffix.lower() == ".pcm":
                    try:
                        export_path = _pcm_to_wav_tmp(source_path)
                        actual_ext = "wav"
                        cleanup_task = BackgroundTask(safe_unlink, str(export_path))
                    except Exception as e2:
                        log.warning("[meetings] PCM to WAV fallback failed: %s", e2)

    media_type = audio_media_type(export_path.suffix)
    return FileResponse(
        str(export_path),
        media_type=media_type,
        filename=f"meeting_{meeting_id}.{actual_ext}",
        background=cleanup_task,
    )


@router.get("/meetings/{meeting_id}/minutes")
async def download_meeting_minutes(meeting_id: int, format: str = "md"):
    m = db.get_meeting(meeting_id)
    if not m:
        return JSONResponse({"error": "Not found"}, status_code=404)

    summary = str(m.get("summary") or "").strip()
    if not summary:
        return JSONResponse({"error": "Minutes not found"}, status_code=404)

    language = str(m.get("language") or "vi")
    markdown = normalize_minutes_markdown(summary, language)
    if not markdown:
        return JSONResponse({"error": "Minutes not found"}, status_code=404)

    export_format = (format or "md").strip().lower()
    if export_format not in {"md", "docx"}:
        return JSONResponse({"error": "format must be md or docx"}, status_code=400)

    raw_title = str(m.get("title") or f"meeting-{meeting_id}").strip()
    safe_title = "".join(ch for ch in raw_title if ch not in '\\/:*?"<>|').strip() or f"meeting-{meeting_id}"

    if export_format == "md":
        return Response(
            content=markdown.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}-minutes.md"'},
        )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        markdown_to_docx(markdown, tmp_path)
    except ModuleNotFoundError:
        safe_unlink(str(tmp_path))
        return JSONResponse({"error": "python-docx is not installed"}, status_code=500)
    except Exception as e:
        safe_unlink(str(tmp_path))
        log.error("[meetings] DOCX export failed: %s", e)
        return JSONResponse({"error": "minutes export failed"}, status_code=500)

    return FileResponse(
        str(tmp_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{safe_title}-minutes.docx",
        background=BackgroundTask(safe_unlink, str(tmp_path)),
    )
