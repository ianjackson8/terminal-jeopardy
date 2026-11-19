"""Original synthesized sound effects, generated with the standard library.

Sounds are rendered to small WAV files once (cached in the temp dir) and played
asynchronously with the platform's built-in player, so the game never waits on audio.
If no player is available, everything silently becomes a no-op.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

RATE = 22050

# A note segment: (frequencies, seconds, waveform, volume). No frequencies = silence.
Segment = tuple[tuple[float, ...], float, str, float]

C4, E4, F4, Fs4, G4, A4 = 261.63, 329.63, 349.23, 369.99, 392.0, 440.0
C5, Cs5, E5, G5, A5 = 523.25, 554.37, 659.25, 783.99, 880.0
C6, E6, G6 = 1046.5, 1318.5, 1567.98

SOUNDS: dict[str, list[Segment]] = {
    "select":  [((A5,), 0.05, "sine", 0.30), ((E6,), 0.08, "sine", 0.30)],
    "buzz":    [((660.0,), 0.13, "square", 0.22)],
    "early":   [((110.0,), 0.14, "saw", 0.30)],
    "correct": [((G5,), 0.10, "sine", 0.45), ((C6,), 0.26, "sine", 0.45)],
    "wrong":   [((196.0,), 0.18, "square", 0.25), ((147.0,), 0.32, "square", 0.25)],
    "timeout": [((330.0,), 0.09, "square", 0.22), ((), 0.06, "sine", 0),
                ((330.0,), 0.09, "square", 0.22), ((), 0.06, "sine", 0),
                ((262.0,), 0.16, "square", 0.22)],
    "tick":    [((1200.0,), 0.03, "square", 0.12)],
    "dd":      [((C5,), 0.07, "triangle", 0.4), ((E5,), 0.07, "triangle", 0.4), ((G5,), 0.07, "triangle", 0.4),
                ((C6,), 0.07, "triangle", 0.4), ((E6,), 0.07, "triangle", 0.4),
                ((C6, E6, G6), 0.45, "triangle", 0.35)],
    "round":   [((G4,), 0.09, "sine", 0.4), ((C5,), 0.09, "sine", 0.4), ((E5,), 0.09, "sine", 0.4),
                ((C5, E5, G5), 0.5, "sine", 0.35)],
    "final":   [((A4, Cs5, E5), 0.8, "triangle", 0.3)],
    "win":     [((C5,), 0.11, "triangle", 0.4), ((E5,), 0.11, "triangle", 0.4), ((G5,), 0.11, "triangle", 0.4),
                ((C6,), 0.16, "triangle", 0.4), ((), 0.05, "sine", 0),
                ((G5,), 0.11, "triangle", 0.4), ((C5, E5, G5, C6), 0.7, "triangle", 0.35)],
    "lose":    [((G4,), 0.2, "triangle", 0.4), ((Fs4,), 0.2, "triangle", 0.4), ((F4,), 0.2, "triangle", 0.4),
                ((E4,), 0.55, "triangle", 0.4)],
}


def _osc(wave_kind: str, phase: float) -> float:
    x = phase % 1.0
    if wave_kind == "square":
        return 1.0 if x < 0.5 else -1.0
    if wave_kind == "saw":
        return 2.0 * x - 1.0
    if wave_kind == "triangle":
        return 4.0 * abs(x - 0.5) - 1.0
    return math.sin(2 * math.pi * x)


def synth(segments: list[Segment]) -> bytes:
    """Render segments to 16-bit mono WAV bytes with a click-free envelope."""
    frames = bytearray()
    for freqs, secs, kind, vol in segments:
        n = int(RATE * secs)
        attack, release = min(n // 4, int(RATE * 0.005)), min(n // 2, int(RATE * 0.03))
        for i in range(n):
            if freqs:
                v = sum(_osc(kind, f * i / RATE) for f in freqs) / len(freqs)
                env = min(1.0, i / attack if attack else 1.0, (n - i) / release if release else 1.0)
                sample = int(max(-1.0, min(1.0, v * vol * env)) * 32767)
            else:
                sample = 0
            frames += struct.pack("<h", sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def find_player() -> list[str] | None:
    """Command used to play a WAV file, or None if we can't play sound."""
    if sys.platform == "win32":
        return ["winsound"]
    for cmd in (["afplay"], ["paplay"], ["pw-play"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


class Sound:
    def __init__(self, enabled: bool = True, player: list[str] | None = None):
        self.player = player if player is not None else find_player()
        self.enabled = enabled
        self._files: dict[str, Path] = {}
        self._procs: list[subprocess.Popen] = []

    @property
    def available(self) -> bool:
        return bool(self.player)

    def _file(self, name: str) -> Path:
        if name not in self._files:
            spec = SOUNDS[name]
            digest = hashlib.sha1(json.dumps([name, RATE, spec]).encode()).hexdigest()[:10]
            folder = Path(tempfile.gettempdir()) / "terminal-jeopardy-sounds"
            folder.mkdir(exist_ok=True)
            path = folder / f"{name}-{digest}.wav"
            if not path.exists():
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(synth(spec))
                tmp.replace(path)
            self._files[name] = path
        return self._files[name]

    def play(self, name: str) -> None:
        if not (self.enabled and self.player and name in SOUNDS):
            return
        try:
            path = self._file(name)
            if self.player == ["winsound"]:
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            self._procs = [p for p in self._procs if p.poll() is None]
            self._procs.append(subprocess.Popen(
                [*self.player, str(path)], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        except Exception:
            # Sound is a nicety; never let it break the game.
            pass

    def stop(self) -> None:
        for p in self._procs:
            if p.poll() is None:
                p.terminate()
        self._procs = []
