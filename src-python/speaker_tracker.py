"""Realtime speaker tracking for local streaming STT.

Direct Python port of src-tauri/src/stt/speaker_tracker.rs and speaker_segments.rs:
- Sliding window embedding (1.5s window, 0.5s hop)
- Centroid running mean with Exponential Moving Average (EMA, cap 30 windows)
- Hysteresis decision rules (confirm=2 for known, confirm_new=3 for new speaker)
- Self-similarity check (self_sim >= 0.35) to reject coughs/noise
- Word/token-level splitting based on Sherpa timestamps
"""
from __future__ import annotations

import collections
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

SR: int = 16_000
TURN_MEMORY: int = 6
RMS_HISTORY_FRAMES: int = 400
CENTROID_MEMORY: float = 30.0
FINE_SILENCE_RMS: float = 0.01


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm < 1e-8:
        return np.zeros_like(vec)
    return vec / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


@dataclass
class TrackerParams:
    window: int = 24_000         # 1.5s @ 16kHz
    hop: int = 8_000             # 0.5s @ 16kHz
    min_speech_ratio: float = 0.5
    match_sim: float = 0.45
    strong_sim: float = 0.65
    switch_gap: float = 0.08
    new_max_sim: float = 0.15
    self_sim: float = 0.35
    confirm: int = 2
    confirm_new: int = 3
    update_min_sim: float = 0.45
    change_sim: float = 0.50


class Centroid:
    """One speaker's running centroid (L2-normalised mean of window embeddings)."""

    def __init__(self, emb: np.ndarray):
        self.mean = emb.astype(np.float32).copy()
        self.count = 1
        self.unit = l2_normalize(self.mean)

    def add(self, emb: np.ndarray) -> None:
        self.count += 1
        alpha = 1.0 / min(float(self.count), CENTROID_MEMORY)
        self.mean += alpha * (emb - self.mean)
        self.unit = l2_normalize(self.mean)

    def sim(self, emb: np.ndarray) -> float:
        return cosine_similarity(self.unit, emb)


class SpeakerTimeline:
    """sample -> speaker map produced by the tracker (Thread-safe, port of Rust SpeakerTimeline)."""

    def __init__(self, turns: Optional[list[tuple[int, int]]] = None, stable_until: int = 0):
        import threading
        self.turns: list[tuple[int, int]] = turns if turns is not None else [(0, 0)]
        self._stable_until: int = stable_until
        self._lock = threading.Lock()

    @property
    def stable_until(self) -> int:
        with self._lock:
            return self._stable_until

    @stable_until.setter
    def stable_until(self, val: int) -> None:
        with self._lock:
            self._stable_until = max(self._stable_until, val)

    def speaker_at(self, t: int) -> int:
        with self._lock:
            for start, sid in reversed(self.turns):
                if start <= t:
                    return sid
            return 0

    def add_turn(self, at: int, sid: int) -> None:
        with self._lock:
            self.turns = [(s, s_id) for (s, s_id) in self.turns if s < at]
            self.turns.append((at, sid))

    def reset_first(self, sid: int) -> None:
        with self._lock:
            self.turns = [(0, sid)]


@dataclass
class PendingWindow:
    start: int
    emb: np.ndarray
    cand: str  # "known:{idx}" or "new"


class TrackerCore:
    """Realtime speaker tracker core maintaining a sample -> speaker timeline."""

    def __init__(
        self,
        embed_fn: Callable[[np.ndarray], Optional[np.ndarray]],
        params: Optional[TrackerParams] = None,
        profiles: Optional[list[Centroid]] = None,
    ):
        self.params = params or TrackerParams()
        self.embed = embed_fn
        self.profiles: list[Centroid] = profiles if profiles is not None else []
        self.timeline = SpeakerTimeline(turns=[(0, 0)], stable_until=0)

        self.buf = np.array([], dtype=np.float32)
        self.buf_start: int = 0
        self.next_window_end: int = self.params.window
        self.current: Optional[int] = None
        self.pending: list[PendingWindow] = []
        self.turn: collections.deque[np.ndarray] = collections.deque(maxlen=TURN_MEMORY)
        self.frame_rms: collections.deque[tuple[int, float]] = collections.deque(
            maxlen=RMS_HISTORY_FRAMES
        )
        self.next_rms_sample: int = 0

    def remember_in_turn(self, emb: np.ndarray) -> None:
        self.turn.append(emb.copy())

    def push(self, samples: np.ndarray) -> None:
        """Feed audio samples (float32 in [-1, 1]); processes completed windows."""
        if len(samples) == 0:
            return
        if len(self.buf) == 0:
            self.buf = samples.copy()
        else:
            self.buf = np.concatenate((self.buf, samples))

        buf_end = self.buf_start + len(self.buf)

        # Record 20ms (320-sample) frame RMS for silence-valley snapping
        while self.next_rms_sample + 320 <= buf_end:
            if self.next_rms_sample >= self.buf_start:
                lo = int(self.next_rms_sample - self.buf_start)
                hi = lo + 320
                if hi <= len(self.buf):
                    frame = self.buf[lo:hi]
                    r = float(np.sqrt(np.mean(frame ** 2)))
                    self.frame_rms.append((self.next_rms_sample, r))
            self.next_rms_sample += 320

        while self.next_window_end <= buf_end:
            end = self.next_window_end
            start = end - self.params.window
            lo = int(start - self.buf_start)
            hi = int(end - self.buf_start)
            window = self.buf[lo:hi]
            self._process_window(start, window)
            self.next_window_end += self.params.hop

        # Keep only what the next window still needs
        keep_from = max(0, self.next_window_end - self.params.window)
        if keep_from > self.buf_start:
            drop = min(int(keep_from - self.buf_start), len(self.buf))
            self.buf = self.buf[drop:]
            self.buf_start += drop

    def flush(self) -> None:
        """End of stream: mark stable_until at the end of feed."""
        end = self.buf_start + len(self.buf)
        self.timeline.stable_until = end

    def _speech_ratio(self, window: np.ndarray) -> float:
        n_frames = len(window) // 320
        if n_frames == 0:
            return 0.0
        voiced = 0
        for i in range(0, n_frames * 320, 320):
            frame = window[i:i + 320]
            if float(np.sqrt(np.mean(frame ** 2))) > FINE_SILENCE_RMS:
                voiced += 1
        return float(voiced / n_frames)

    def _settle_point(self, start: int) -> int:
        return start + self.params.window // 2

    def _settle(self, start: int) -> None:
        if not self.pending:
            p = self._settle_point(start)
            if p > self.timeline.stable_until:
                self.timeline.stable_until = p

    def _quietest_sample_in_range(self, lo_sample: int, hi_sample: int, fallback: int) -> int:
        in_range = [(s, r) for (s, r) in self.frame_rms if lo_sample <= s <= hi_sample]
        if len(in_range) < 3:
            return fallback
        mean_rms = float(sum(r for _, r in in_range) / len(in_range))
        if mean_rms <= 1e-6:
            return fallback

        best_sample = fallback
        best_rms = float("inf")
        for i in range(len(in_range) - 2):
            avg = (in_range[i][1] + in_range[i + 1][1] + in_range[i + 2][1]) / 3.0
            if avg < best_rms:
                best_rms = avg
                best_sample = in_range[i + 1][0] + 160

        if best_rms < mean_rms * 0.85:
            return best_sample
        return fallback

    def _process_window(self, start: int, window: np.ndarray) -> None:
        is_speech = self._speech_ratio(window) >= self.params.min_speech_ratio
        emb = self.embed(window) if is_speech else None
        if emb is None:
            self._settle(start)
            return

        # First voice of the session
        if not self.profiles:
            self.pending.append(PendingWindow(start=start, emb=emb, cand="new"))
            self._try_confirm()
            return

        sims = [c.sim(emb) for c in self.profiles]
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])
        cur_sim = float(sims[self.current]) if self.current is not None else -1.0

        # Local evidence from current turn
        turn_sim: Optional[float] = None
        if len(self.turn) >= 2:
            mean_turn = l2_normalize(np.mean(np.array(self.turn), axis=0))
            turn_sim = cosine_similarity(mean_turn, emb)

        local_change = turn_sim is not None and turn_sim < self.params.change_sim

        if not local_change and best_idx == self.current and best_sim >= self.params.match_sim:
            cand = None  # Confirmed current speaker
        elif (
            not local_change
            and turn_sim is not None
            and self.current is not None
            and best_sim < self.params.match_sim
        ):
            self._settle(start)
            return
        elif (
            best_idx != self.current
            and best_sim >= self.params.match_sim
            and (best_sim - cur_sim) >= self.params.switch_gap
        ):
            cand = f"known:{best_idx}"
        elif best_sim < self.params.new_max_sim or (local_change and best_sim < self.params.match_sim):
            cand = "new"
        else:
            self._settle(start)
            return

        if cand is None:
            if self.current is not None and best_sim >= self.params.update_min_sim:
                self.profiles[self.current].add(emb)
            self.remember_in_turn(emb)
            self.pending.clear()
            self._settle(start)
        else:
            if self.pending:
                first = self.pending[0]
                if first.cand != cand:
                    self.pending.clear()

            is_strong = cand.startswith("known:") and best_sim >= self.params.strong_sim
            self.pending.append(PendingWindow(start=start, emb=emb, cand=cand))

            needed = self.params.confirm if cand.startswith("known:") else self.params.confirm_new
            if is_strong or len(self.pending) >= needed:
                self._try_confirm()

    def _try_confirm(self) -> None:
        if not self.pending:
            return
        first = self.pending[0]
        first_start = first.start
        cand = first.cand

        if cand.startswith("known:"):
            target_idx = int(cand.split(":")[1])
            for w in self.pending:
                self.profiles[target_idx].add(w.emb)
            spk_id = target_idx
        else:
            # Candidate New
            first_ever = len(self.profiles) == 0
            if len(self.pending) < 2 and not first_ever:
                return

            coherent = True
            for i in range(len(self.pending) - 1):
                if cosine_similarity(self.pending[i].emb, self.pending[i + 1].emb) < self.params.self_sim:
                    coherent = False
                    break

            if not coherent and not first_ever:
                self.pending.clear()
                return

            # Average check against existing centroids
            avg_emb = l2_normalize(np.mean([w.emb for w in self.pending], axis=0))
            if any(c.sim(avg_emb) >= self.params.match_sim for c in self.profiles):
                self.pending.clear()
                return

            new_c = Centroid(avg_emb)
            self.profiles.append(new_c)
            spk_id = len(self.profiles) - 1

        first_speaker = self.current is None
        changed = self.current != spk_id
        self.current = spk_id
        last_start = self.pending[-1].start if self.pending else first_start
        if changed:
            self.turn.clear()
        for w in self.pending:
            self.remember_in_turn(w.emb)
        self.pending.clear()
        settled = self._settle_point(last_start)

        if first_speaker:
            self.timeline.reset_first(spk_id)
        elif changed:
            span = max(0, self.params.window - self.params.hop)
            midpoint = first_start + span // 2
            valley = self._quietest_sample_in_range(first_start, first_start + span, midpoint)
            at = max(valley, self.timeline.stable_until)
            self.timeline.add_turn(at, spk_id)

        self.timeline.stable_until = max(self.timeline.stable_until, settled)


class SpeakerTracker:
    """Thread wrapper owning TrackerCore on a dedicated OS thread (100% port of Rust SpeakerTracker).

    ONNX inference and sliding-window diarization run off the async event loop thread.
    """

    def __init__(
        self,
        embed_fn: Callable[[np.ndarray], Optional[np.ndarray]],
        params: Optional[TrackerParams] = None,
        profiles: Optional[list[Centroid]] = None,
    ):
        import queue
        import threading

        self.core = TrackerCore(embed_fn=embed_fn, params=params, profiles=profiles)
        self.timeline = self.core.timeline
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="speaker-tracker", daemon=True)
        self._thread.start()

    @property
    def buf_start(self) -> int:
        return self.core.buf_start

    @property
    def buf(self) -> list[float]:
        return self.core.buf

    @classmethod
    def start(
        cls,
        embed_fn: Callable[[np.ndarray], Optional[np.ndarray]],
        params: Optional[TrackerParams] = None,
        profiles: Optional[list[Centroid]] = None,
    ) -> "SpeakerTracker":
        return cls(embed_fn=embed_fn, params=params, profiles=profiles)

    def feed(self, audio: np.ndarray | bytes) -> None:
        """Feed audio samples (non-blocking). Can be float32 array or int16 PCM bytes."""
        if audio is None:
            return
        if isinstance(audio, bytes):
            if not audio:
                return
            samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            samples = audio
        self._queue.put(samples)

    def push(self, samples: np.ndarray | bytes) -> None:
        """Alias for feed() to keep backward compatibility."""
        self.feed(samples)

    def finish(self) -> None:
        """Flush remaining audio, mark timeline stable, and join worker thread."""
        self._queue.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def flush(self) -> None:
        """Alias for finish()."""
        self.finish()

    def _run(self) -> None:
        while True:
            chunk = self._queue.get()
            if chunk is None:
                break
            # Coalesce backlog like Rust
            chunks = [chunk]
            stopping = False
            while not self._queue.empty():
                try:
                    more = self._queue.get_nowait()
                    if more is None:
                        stopping = True
                        break
                    chunks.append(more)
                except Exception:
                    break

            if chunks:
                merged = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
                self.core.push(merged)
            if stopping:
                break
        self.core.flush()


@dataclass
class TokenGroup:
    start: int
    end: int
    speaker: int


def group_by_speaker(
    tokens: list[str],
    times: list[float] | list[int],
    from_idx: int,
    to_idx: int,
    speaker_at_fn: Callable[[int], int],
    sample_rate: int = SR,
) -> list[TokenGroup]:
    """Group tokens[from_idx..to_idx] by speaker using word-level boundaries and token timestamps.

    Port of src-tauri/src/stt/speaker_segments.rs::group_by_speaker.
    Supports either seconds (float) or sample offsets (int).
    """
    to_idx = min(to_idx, len(tokens), len(times))
    groups: list[TokenGroup] = []
    word_speaker = 0

    for i in range(from_idx, to_idx):
        tok = tokens[i]
        # BPE space check: token starts with space or ' ' or at start
        is_word_start = (i == from_idx) or tok.startswith(" ") or tok.startswith(" ")
        if is_word_start:
            t_val = times[i]
            sample_pos = (
                int(t_val * sample_rate)
                if isinstance(t_val, float) and t_val < 10000.0
                else int(t_val)
            )
            word_speaker = speaker_at_fn(sample_pos)

        if groups and groups[-1].speaker == word_speaker:
            groups[-1].end = i + 1
        else:
            groups.append(TokenGroup(start=i, end=i + 1, speaker=word_speaker))

    return groups


def tokens_text(tokens: list[str], start: int, end: int) -> str:
    """Concatenate BPE pieces into plain text."""
    end = min(end, len(tokens))
    raw = "".join(tokens[start:end])
    return raw.replace(" ", " ").strip()


class LiveUtterance:
    """Per-stream state of the speaker-aware worker (100% port of src-tauri LiveUtterance)."""

    def __init__(
        self,
        language: str,
        timeline: Optional[SpeakerTimeline],
        on_event: Callable[[dict], None],
        clean_text_fn: Optional[Callable[[str, str], str]] = None,
        partial_interval: float = 0.250,
        sample_rate: int = SR,
    ):
        import time

        self.language = language
        self.timeline = timeline
        self.on_event = on_event
        self.clean_text = clean_text_fn or (lambda text, lang: text)
        self.partial_interval = partial_interval
        self.sample_rate = sample_rate

        self.session_tag = int(time.time() * 1000)
        self.seg_index = 0
        self.total_samples = 0
        self.origin = 0
        self.committed = 0
        self.utt_start: Optional[int] = None
        self.last_partial = ""
        self.last_partial_at = 0.0

    def next_chunk_id(self) -> str:
        self.seg_index += 1
        return f"local-{self.session_tag}-{self.seg_index}"

    def speaker_at(self, t: int) -> int:
        if self.timeline is not None:
            return self.timeline.speaker_at(t)
        return 0

    def stable_until(self) -> int:
        if self.timeline is not None:
            return self.timeline.stable_until
        return 2**63 - 1

    def token_times(self, ts: list[float]) -> list[int]:
        return [self.origin + int(max(0.0, s) * self.sample_rate) for s in ts]

    def emit_groups(
        self,
        tokens: list[str],
        times: list[int],
        groups: list[TokenGroup],
        end_of_last: int,
    ) -> None:
        for gi, g in enumerate(groups):
            raw_chunk = tokens_text(tokens, g.start, g.end)
            text = self.clean_text(raw_chunk, self.language)
            start = (
                (self.utt_start if self.utt_start is not None else times[0])
                if g.start == 0
                else times[g.start]
            )
            end = times[groups[gi + 1].start] if (gi + 1 < len(groups)) else end_of_last
            if text:
                cid = self.next_chunk_id()
                self.on_event({
                    "text": text,
                    "is_final": True,
                    "speaker": f"Speaker {g.speaker + 1}",
                    "speaker_id": g.speaker,
                    "chunk_id": cid,
                    "start_ms": int(start * 1000 // self.sample_rate),
                    "end_ms": int(max(start, end) * 1000 // self.sample_rate),
                })

    def finish_utterance(self, engine: Any) -> None:
        tokens, ts = engine.tokens()
        times = self.token_times(ts)
        whole_text = engine.finalize(self.language)
        if tokens and len(times) == len(tokens):
            groups = group_by_speaker(
                tokens, times, self.committed, len(tokens), self.speaker_at, sample_rate=self.sample_rate
            )
            if self.committed == 0 and len(groups) == 1:
                # Single speaker, nothing emitted early: use engine's own text
                if whole_text:
                    start = min(self.utt_start if self.utt_start is not None else times[0], times[0])
                    cid = self.next_chunk_id()
                    self.on_event({
                        "text": whole_text,
                        "is_final": True,
                        "speaker": f"Speaker {groups[0].speaker + 1}",
                        "speaker_id": groups[0].speaker,
                        "chunk_id": cid,
                        "start_ms": int(start * 1000 // self.sample_rate),
                        "end_ms": int(self.total_samples * 1000 // self.sample_rate),
                    })
            else:
                self.emit_groups(tokens, times, groups, self.total_samples)
        elif whole_text:
            start = self.utt_start if self.utt_start is not None else self.origin
            cid = self.next_chunk_id()
            spk = self.speaker_at(start)
            self.on_event({
                "text": whole_text,
                "is_final": True,
                "speaker": f"Speaker {spk + 1}",
                "speaker_id": spk,
                "chunk_id": cid,
                "start_ms": int(start * 1000 // self.sample_rate),
                "end_ms": int(self.total_samples * 1000 // self.sample_rate),
            })

        self.origin = self.total_samples
        self.committed = 0
        self.utt_start = None
        self.last_partial = ""

    def update(self, engine: Any, batch_start: int) -> None:
        import time

        tokens, ts = engine.tokens()
        if not tokens or len(ts) != len(tokens):
            partial = engine.partial_text(self.language)
            now = time.time()
            if partial and partial != self.last_partial and now - self.last_partial_at >= self.partial_interval:
                spk = self.speaker_at(batch_start)
                self.last_partial = partial
                self.last_partial_at = now
                self.on_event({
                    "text": partial,
                    "is_final": False,
                    "speaker": f"Speaker {spk + 1}",
                    "speaker_id": spk,
                })
            return

        if self.utt_start is None:
            self.utt_start = batch_start
        times = self.token_times(ts)
        force_partial = False

        stable = self.stable_until()
        settled = self.committed
        for t in times[self.committed:]:
            if t < stable:
                settled += 1
            else:
                break

        groups = group_by_speaker(
            tokens, times, self.committed, settled, self.speaker_at, sample_rate=self.sample_rate
        )
        if len(groups) >= 2:
            done = groups[:-1]
            next_start = groups[-1].start
            end = times[next_start]
            self.emit_groups(tokens, times, done, end)
            self.committed = next_start
            force_partial = True

        raw = tokens_text(tokens, self.committed, len(tokens))
        partial = self.clean_text(raw, self.language)
        now = time.time()
        if partial and (
            force_partial
            or (partial != self.last_partial and now - self.last_partial_at >= self.partial_interval)
        ):
            spk_idx = self.committed if self.committed < len(times) else len(times) - 1
            spk = self.speaker_at(times[spk_idx])
            self.last_partial = partial
            self.last_partial_at = now
            self.on_event({
                "text": partial,
                "is_final": False,
                "speaker": f"Speaker {spk + 1}",
                "speaker_id": spk,
            })

