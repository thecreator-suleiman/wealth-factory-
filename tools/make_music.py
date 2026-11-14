"""Compose original, copyright-free slow piano background tracks.

Run once: python tools/make_music.py  -> assets/music/*.mp3
Every note is generated from scratch, so YouTube Content ID has nothing to match.
"""
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "music"

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def freq(name: str) -> float:
    n, octave = name[:-1], int(name[-1])
    midi = 12 * (octave + 1) + NOTE[n]
    return 440.0 * 2 ** ((midi - 69) / 12)


def piano_note(f: float, dur: float, vel: float, rng) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    out = np.zeros_like(t)
    B = 0.00035  # string stiffness -> slightly stretched overtones like a real piano
    for n in range(1, 11):
        fn = n * f * np.sqrt(1 + B * n * n)
        if fn > 9000:
            break
        amp = (1 / n ** 1.15) * (0.6 + 0.4 * rng.random())
        decay = 0.55 + 0.38 * n + f / 900
        detune = 1 + rng.normal(0, 0.0004)
        out += amp * np.exp(-decay * t) * np.sin(2 * np.pi * fn * detune * t + rng.random() * 6.28)
    attack = 0.5 - 0.5 * np.cos(np.pi * np.minimum(t / 0.012, 1.0))  # soft, click-free start
    release = np.ones_like(t)
    tail = int(SR * 0.25)
    release[-tail:] = np.linspace(1, 0, tail)
    return out * attack * release * vel


def reverb(x: np.ndarray, seconds: float, rng) -> np.ndarray:
    n = int(SR * seconds)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, n) * np.exp(-t * 6.9 / seconds)
    ir = sosfilt(butter(2, 3500, "low", fs=SR, output="sos"), ir)
    ir[0] = 0
    ir /= np.max(np.abs(ir))
    wet = fftconvolve(x, ir)[: len(x)]
    wet /= np.max(np.abs(wet)) + 1e-9
    return 0.62 * x / (np.max(np.abs(x)) + 1e-9) + 0.38 * wet


def chord_notes(root: str, kind: str, octave: int) -> list[str]:
    names = list(NOTE)
    i = NOTE[root]
    steps = {"m": [0, 3, 7], "M": [0, 4, 7], "sus2": [0, 2, 7], "add9": [0, 4, 7, 14], "m7": [0, 3, 7, 10]}[kind]
    notes = []
    for s in steps:
        k = i + s
        notes.append(f"{names[k % 12]}{octave + k // 12}")
    return notes


def compose(progression, bpm: float, seconds: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    total = int(SR * (seconds + 6))
    mix = np.zeros(total)

    def place(sig, start):
        s = max(int(start * SR), 0)
        e = min(s + len(sig), total)
        if s < total:
            mix[s:e] += sig[: e - s]

    t = 0.0
    bar = 0
    while t < seconds:
        root, kind = progression[bar % len(progression)]
        # left hand: low root + fifth, held for the whole bar
        bass = chord_notes(root, "M" if kind in ("M", "add9") else "m", 2)
        place(piano_note(freq(bass[0]), beat * 4.2, 0.55, rng), t)
        place(piano_note(freq(bass[2]), beat * 4.0, 0.25, rng), t + beat * 0.02)
        # right hand: slow broken chord, 8 gentle notes per bar
        upper = chord_notes(root, kind, 4)
        pattern = [0, 1, 2, 1, 0, 2, 1, 2] if bar % 2 == 0 else [0, 2, 1, 2, 0, 1, 2, 1]
        for k, idx in enumerate(pattern):
            note = upper[idx % len(upper)]
            vel = 0.20 + 0.06 * rng.random() + (0.05 if k == 0 else 0)
            jitter = rng.normal(0, 0.012)  # human timing
            place(piano_note(freq(note), beat * 1.6, vel, rng), t + k * beat / 2 + jitter)
        # occasional high melody note
        if bar % 2 == 1:
            top = chord_notes(root, kind, 5)[rng.integers(0, 3)]
            place(piano_note(freq(top), beat * 3, 0.16, rng), t + beat * 2)
        t += beat * 4
        bar += 1

    mix = reverb(mix, 2.8, rng)
    n = int(SR * seconds)
    mix = mix[:n]
    fade = int(SR * 3)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = sosfilt(butter(2, 60, "high", fs=SR, output="sos"), mix)
    mix = sosfilt(butter(2, 6000, "low", fs=SR, output="sos"), mix)
    return mix / (np.max(np.abs(mix)) + 1e-9) * 0.85


TRACKS = {
    "reflection_am": ([("A", "m"), ("F", "M"), ("C", "M"), ("G", "M")], 64, 11),
    "quiet_ambition_dm": ([("D", "m"), ("A#", "M"), ("F", "M"), ("C", "M")], 60, 23),
    "turning_point_em": ([("E", "m"), ("C", "add9"), ("G", "M"), ("D", "sus2")], 68, 37),
    "long_road_cm": ([("C", "m"), ("G#", "M"), ("D#", "M"), ("A#", "M")], 58, 51),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (prog, bpm, seed) in TRACKS.items():
        audio = compose(prog, bpm, 100, seed)
        wav = OUT / f"{name}.wav"
        pcm = (audio * 32767).astype("<i2")
        import wave

        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                        "-ac", "2", "-b:a", "160k", str(OUT / f"{name}.mp3")], check=True)
        wav.unlink()
        print("made", name)


if __name__ == "__main__":
    main()
