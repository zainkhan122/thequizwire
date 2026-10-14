#!/usr/bin/env python3
"""reelkit/synth.py — seeded, royalty-free music + SFX primitives (numpy/scipy). You own the output.
All functions return float32 arrays at SR (mono unless noted). Mix with `place()` into a stereo bus.
"""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
RNG = np.random.default_rng(1983)


def seed(n):
    global RNG
    RNG = np.random.default_rng(n)


def t_(d):
    return np.arange(int(d * SR)) / SR


def note(name):
    """'A4' -> Hz. Supports b/# e.g. 'Bb2', 'C#4'."""
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    n = names[name[0]]; rest = name[1:]
    if rest[0] in "b#":
        n += -1 if rest[0] == "b" else 1; rest = rest[1:]
    return 440.0 * 2 ** ((n + 12 * (int(rest) - 4)) / 12)


def filt(x, kind, f, order=2):
    if isinstance(f, (list, tuple)):
        sos = butter(order, [f[0] / (SR / 2), f[1] / (SR / 2)], btype="band", output="sos")
    else:
        sos = butter(order, min(f / (SR / 2), 0.99), btype=kind, output="sos")
    return sosfilt(sos, x, axis=0).astype(np.float32)


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.3):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    sus = max(n - a - d - r, 0)
    e = np.concatenate([np.linspace(0, 1, max(a, 1)), np.linspace(1, s, max(d, 1)), np.full(sus, s), np.linspace(s, 0, max(r, 1))])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def saw(f, d, voices=3, detune=7, maxh=60):
    t = t_(d); out = np.zeros_like(t)
    for v in range(voices):
        fv = f * 2 ** ((v - (voices - 1) / 2) * detune / 1200)
        ph = RNG.uniform(0, 2 * np.pi)
        for h in range(1, maxh + 1):
            if fv * h > 9000: break
            out += np.sin(2 * np.pi * fv * h * t + ph * h) / h
    return (out / voices * 0.5).astype(np.float32)


def pad(freqs, d, cutoff=1400, a=1.6, r=2.0, level=0.18):
    x = sum(saw(f, d) for f in freqs) / max(len(freqs), 1)
    x = filt(x, "low", cutoff, 2)
    lfo = 1 + 0.08 * np.sin(2 * np.pi * 0.17 * t_(d) + RNG.uniform(0, 6))
    return (x * env_adsr(len(x), a, 0.5, 0.85, r) * lfo * level).astype(np.float32)


def drone(f, d, cutoff=380, level=0.22):
    t = t_(d)
    x = 0.6 * np.sin(2 * np.pi * f * t) + 0.4 * saw(f, d, voices=2, detune=4) + 0.25 * np.sin(2 * np.pi * f * 1.5 * t)
    x = filt(x, "low", cutoff, 2)
    return (x * env_adsr(len(x), 2.5, 0.5, 1, 2.5) * level).astype(np.float32)


def piano(f, d=4.0, vel=0.6):
    """Additive piano-ish tone: inharmonic partials, per-partial decay, hammer noise."""
    t = t_(d); B = 0.00035; out = np.zeros_like(t)
    for n in range(1, 14):
        fn = f * n * np.sqrt(1 + B * n * n)
        if fn > 12000: break
        amp = (1 / n ** 1.15) * (1.0 if n > 1 else 1.2)
        dec = 0.9 + 0.55 * n + f / 600
        out += amp * np.sin(2 * np.pi * fn * t) * np.exp(-dec * t * (0.6 if n == 1 else 1))
    att = np.minimum(1, t / 0.004)
    hammer = filt(RNG.standard_normal(len(t)) * np.exp(-t * 90), "band", (800, 4000)) * 0.08
    x = (out * att + hammer) * vel * 0.22
    rel = np.ones_like(t); k = int(max(d - 0.25, 0) * SR); rel[k:] = np.linspace(1, 0, len(t) - k)
    return (x * rel).astype(np.float32)


def bell(f, d=3.0, level=0.12):
    t = t_(d)
    parts = [(1, 1), (2.76, .5), (5.4, .3), (8.93, .15)]
    x = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * (1.2 + m * .5)) for m, a in parts)
    return (x * level).astype(np.float32)


def boom(d=1.6, f0=90, f1=32, level=0.8):
    t = t_(d)
    f = f1 + (f0 - f1) * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 2.6)
    thump = filt(RNG.standard_normal(len(t)), "low", 400) * np.exp(-t * 30) * 0.6
    return ((x + thump) * level).astype(np.float32)


def hit(level=0.6):
    """Short cinematic impact: boom + noise crack."""
    b = boom(1.2, 120, 40, level)
    crack = filt(RNG.standard_normal(len(b)), "band", (300, 3500)) * np.exp(-t_(len(b) / SR) * 22) * level * 0.5
    return (b + crack).astype(np.float32)


def tick(hi=True, level=0.12):
    t = t_(0.03)
    x = filt(RNG.standard_normal(len(t)), "band", (2500, 6000) if hi else (1500, 4000)) * np.exp(-t * 260)
    x += np.sin(2 * np.pi * (1900 if hi else 1500) * t) * np.exp(-t * 300) * 0.5
    return (x * level).astype(np.float32)


def projector(d=2.0, level=0.16, fps=24):
    """16 mm projector: 24 Hz shutter clatter + motor hum + hiss, fades in/out (archival inserts)."""
    n = int(d * SR); t = t_(d); x = np.zeros(n)
    click = filt(RNG.standard_normal(int(0.012 * SR)), "band", (900, 5000)) * np.exp(-t_(0.012) * 400)
    for k in range(int(d * fps)):
        i = int(k * SR / fps + RNG.uniform(-40, 40))
        if 0 <= i < n - len(click): x[i:i + len(click)] += click * (0.7 + 0.3 * RNG.random())
    x += np.sin(2 * np.pi * 50 * t) * 0.10 + np.sin(2 * np.pi * 100 * t) * 0.05
    x += filt(RNG.standard_normal(n), "band", (2000, 8000)) * 0.05
    env = np.minimum(1, np.minimum(t / 0.08, (d - t) / 0.15).clip(0))
    return (x * env * level).astype(np.float32)


def heartbeat(level=0.5):
    def thump(f, l):
        t = t_(0.22)
        return np.sin(2 * np.pi * f * t * (1 - t)) * np.exp(-t * 22) * l
    a = thump(52, 1.0); b = thump(46, 0.7)
    x = np.zeros(int(0.6 * SR)); x[:len(a)] += a; o = int(0.26 * SR); x[o:o + len(b)] += b
    return (filt(x, "low", 160) * level).astype(np.float32)


def typekey(level=0.18):
    t = t_(0.05)
    x = filt(RNG.standard_normal(len(t)), "band", (900, 5000)) * np.exp(-t * 120)
    x += np.sin(2 * np.pi * 180 * t) * np.exp(-t * 90) * 0.6
    return (x * level * RNG.uniform(0.7, 1.0)).astype(np.float32)


def typing(n, rate=14, level=0.18):
    out = np.zeros(int((n / rate + 0.2) * SR), np.float32)
    for i in range(n):
        k = int((i / rate + RNG.uniform(-0.012, 0.012)) * SR); k = max(k, 0)
        s = typekey(level); out[k:k + len(s)] += s[: len(out) - k]
    return out


def stamp(level=0.7):
    t = t_(0.5)
    low = np.sin(2 * np.pi * 70 * t) * np.exp(-t * 18)
    slap = filt(RNG.standard_normal(len(t)), "band", (250, 2500)) * np.exp(-t * 45)
    return ((low * 0.9 + slap * 0.6) * level).astype(np.float32)


def whoosh(d=0.7, level=0.35, up=True):
    n = int(d * SR); x = RNG.standard_normal(n).astype(np.float32)
    out = np.zeros(n, np.float32); y = 0.0
    fc = np.geomspace(300, 5000, n) if up else np.geomspace(5000, 300, n)
    alpha = 1 - np.exp(-2 * np.pi * fc / SR)
    for i in range(n):            # time-varying one-pole lowpass
        y += alpha[i] * (x[i] - y); out[i] = y
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (filt(out, "high", 150) * e * level).astype(np.float32)


def riser(d=2.0, level=0.25):
    t = t_(d)
    f = np.geomspace(200, 1800, len(t))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
    nz = filt(RNG.standard_normal(len(t)), "high", 1500) * 0.5
    return ((tone + nz) * (t / d) ** 2.2 * level).astype(np.float32)


def siren(d=2.4, level=0.12):
    t = t_(d)
    f = np.where((t * 2.5).astype(int) % 2 == 0, 660, 880)
    sq = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR))
    x = filt(sq, "band", (500, 2400)) * env_adsr(len(t), 0.05, 0.1, 1, 0.6)
    return (np.tanh(x * 1.5) * level).astype(np.float32)


def paper(d=0.5, level=0.25):
    n = int(d * SR); x = RNG.standard_normal(n)
    gate = (RNG.random(n // 240 + 1) > 0.55).repeat(240)[:n]
    x = filt(x * gate, "band", (1500, 7000)) * np.sin(np.linspace(0, np.pi, n))
    return (x * level).astype(np.float32)


def reverb(x, secs=2.6, wet=0.28, bright=5000):
    """Stereo algorithmic-ish reverb: decorrelated decaying-noise IRs. x mono or stereo -> stereo."""
    if x.ndim == 1: x = np.stack([x, x], 1)
    n = int(secs * SR); t = np.arange(n) / SR
    out = np.zeros((len(x) + n - 1, 2), np.float32)
    for c in range(2):
        ir = RNG.standard_normal(n) * np.exp(-t * 6.9 / secs)
        ir = filt(ir, "low", bright); ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
        ir /= np.sqrt((ir ** 2).sum())
        out[:, c] = fftconvolve(x[:, c], ir)
    dry = np.zeros_like(out); dry[: len(x)] = x
    return (dry * (1 - wet) + out * wet * 1.6).astype(np.float32)


def place(bus, x, t, gain=1.0, pan=0.0):
    """Add mono/stereo x into stereo bus at time t (s)."""
    k = int(round(t * SR))
    if k >= len(bus): return
    if x.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        x = np.stack([x * l * 1.414, x * r * 1.414], 1)
    m = min(len(x), len(bus) - k)
    bus[k:k + m] += x[:m] * gain


def follower(vo_mono, attack=0.03, release=0.35):
    """Envelope follower (abs, smoothed) for sidechain ducking."""
    e = np.abs(vo_mono); out = np.zeros_like(e); y = 0.0
    a, r = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    step = 32                                     # decimate for speed
    a_s, r_s = a ** step, r ** step
    for i in range(0, len(e), step):
        v = e[i:i + step].max()
        y = a_s * y + (1 - a_s) * v if v > y else r_s * y + (1 - r_s) * v
        out[i:i + step] = y
    return out
