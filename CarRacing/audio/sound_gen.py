"""Generates simple placeholder sounds with the standard library only.

Files are written to assets/sounds/ the first time the game runs (only if no
file with that name exists as .ogg/.mp3/.wav).  Replace any of them with your
own file of the same name to customise the audio.
"""
import math
import random
import sys
import wave
from array import array

RATE = 22050
MUSIC_RATE = 16000


def _write(path, samples, rate=RATE, gain=0.9):
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = gain / peak * 32767.0
    data = array("h", (int(max(-32767.0, min(32767.0, s * scale))) for s in samples))
    if sys.byteorder == "big":
        data.byteswap()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())


def make_engine(path):
    f = 48                                   # integer cycles per second -> seamless loop
    out = []
    for i in range(RATE):
        t = i / RATE
        ph = 2 * math.pi * f * t
        firing = sum(
            math.sin(k * ph + 0.16 * k) / (k ** 0.72)
            for k in range(1, 13))
        low_rumble = 0.42 * math.sin(ph) + 0.24 * math.sin(2 * ph + 0.3)
        exhaust = 0.13 * math.sin(0.5 * ph + 0.8) ** 3
        intake = 0.16 * math.sin(3 * ph + 0.4) * (0.5 + 0.5 * math.sin(2 * math.pi * 3 * t))
        v = (0.62 * firing + low_rumble + exhaust + intake)
        v *= 0.82 + 0.12 * math.sin(2 * math.pi * 3 * t)
        out.append(math.tanh(v * 0.58))
    _write(path, out)


def make_tire(path):
    rng = random.Random(5)
    n, m = RATE, 2000
    raw = [rng.uniform(-1, 1) for _ in range(n + m + 1)]
    hp = [raw[i] - 0.85 * raw[i - 1] for i in range(1, len(raw))]
    out = []
    for i in range(n):
        v = hp[i]
        if i < m:                              # crossfade the loop point
            w = i / m
            v = hp[i] * w + hp[n + i] * (1 - w)
        t = i / RATE
        squeal = 0.45 * math.sin(2 * math.pi * 1100 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 7 * t))
        out.append(v * 0.6 + squeal)
    _write(path, out)


def make_rain(path):
    rng = random.Random(17)
    n = RATE * 2
    raw = []
    low = 0.0
    for _ in range(n):
        noise = rng.uniform(-1.0, 1.0)
        low += (noise - low) * 0.08
        raw.append(noise * 0.72 + low * 0.28)

    crossfade = int(RATE * 0.1)
    out = raw[crossfade:]
    for i in range(crossfade):
        blend = (i + 1) / crossfade
        out[-crossfade + i] = raw[-crossfade + i] * (1.0 - blend) + raw[i] * blend
    _write(path, out, gain=0.3)


def make_crash(path):
    rng = random.Random(9)
    n = int(RATE * 0.6)
    out = []
    for i in range(n):
        t = i / RATE
        out.append(rng.uniform(-1, 1) * math.exp(-t * 9) + 1.2 * math.sin(2 * math.pi * 70 * t) * math.exp(-t * 7))
    _write(path, out)


def _tone(freq, dur, decay=4.0, rate=RATE):
    n = int(rate * dur)
    return [math.sin(2 * math.pi * freq * i / rate) * min(1.0, i / 200.0) * math.exp(-decay * i / rate)
            for i in range(n)]


def make_beep(path):
    _write(path, _tone(520, 0.22, 5.0))


def make_go(path):
    _write(path, _tone(1040, 0.5, 3.5))


def make_finish(path):
    out = []
    for freq, dur in ((523, 0.2), (659, 0.2), (784, 0.2), (1047, 0.7)):
        out += _tone(freq, dur, 2.5)
    _write(path, out)


def make_music(path):
    rate = MUSIC_RATE
    bpm = 128.0
    beat = 60.0 / bpm
    bars = 8
    total = int(rate * beat * 4 * bars)
    buf = [0.0] * total
    rng = random.Random(3)

    def add(start_s, samples, amp):
        i0 = int(start_s * rate)
        for k, v in enumerate(samples):
            if i0 + k >= total:
                break
            buf[i0 + k] += v * amp

    def osc(freq, dur, shape, decay):
        n = int(rate * dur)
        out = []
        for i in range(n):
            ph = (freq * i / rate) % 1.0
            if shape == "saw":
                w = 2 * ph - 1
            elif shape == "tri":
                w = 4 * abs(ph - 0.5) - 1
            else:
                w = math.sin(2 * math.pi * ph)
            out.append(w * min(1.0, i / 80.0) * math.exp(-decay * i / rate))
        return out

    kick = [math.sin(2 * math.pi * (45 * t + 75 * (1 - math.exp(-t * 30)) / 30)) * math.exp(-t * 18)
            for t in (i / rate for i in range(int(rate * 0.22)))]
    hat = [rng.uniform(-1, 1) * math.exp(-i / rate * 90) for i in range(int(rate * 0.05))]
    snare = [(rng.uniform(-1, 1) * 0.7 + math.sin(2 * math.pi * 190 * i / rate) * 0.5) * math.exp(-i / rate * 22)
             for i in range(int(rate * 0.16))]
    roots = (110.0, 110.0, 87.3, 98.0, 110.0, 110.0, 87.3, 82.4)           # A A F G A A F E
    chords = (((440, 523, 659),) * 2 + ((349, 440, 523), (392, 494, 587)) +
              ((440, 523, 659),) * 2 + ((349, 440, 523), (330, 415, 494)))
    arp = (0, 1, 2, 1, 0, 1, 2, 1)
    for bar in range(bars):
        t0 = bar * 4 * beat
        for b in range(4):
            add(t0 + b * beat, kick, 0.9)
            if b in (1, 3):
                add(t0 + b * beat, snare, 0.35)
        for e in range(8):
            te = t0 + e * beat / 2
            if e % 2 == 1:
                add(te, hat, 0.22)
            root = roots[bar] * (2 if e in (2, 5) else 1)
            add(te, osc(root, beat / 2, "saw", 7.0), 0.28)
            add(te, osc(chords[bar][arp[e]], beat / 2, "tri", 5.0), 0.22)
    _write(path, buf, rate=rate, gain=0.8)


GENERATORS = {
    "engine": make_engine,
    "tire": make_tire,
    "rain": make_rain,
    "crash": make_crash,
    "beep": make_beep,
    "go": make_go,
    "finish": make_finish,
    "music": make_music,
}
EXTENSIONS = (".ogg", ".mp3", ".wav")


def ensure_sounds(sounds_dir, status=None):
    """Create any missing sound (as .wav) unless a custom file already exists."""
    try:
        sounds_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print("Cannot create sounds folder:", exc)
        return
    for name, generator in GENERATORS.items():
        if any((sounds_dir / (name + ext)).is_file() for ext in EXTENSIONS):
            continue
        if status:
            status("Generating audio: %s" % name)
        try:
            generator(sounds_dir / (name + ".wav"))
        except Exception as exc:                 # read-only folder, etc.
            print("Could not generate %s.wav: %s" % (name, exc))
