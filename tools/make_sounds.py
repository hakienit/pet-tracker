"""Tạo âm thanh thông báo của Wisp (wav mono 16-bit), chỉ dùng stdlib. Chạy lại khi muốn đổi âm.

    python tools/make_sounds.py   ->  assets/sounds/wait.wav, done.wav
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def tone(freq: float, dur: float, vol: float = 0.35, attack: float = 0.008, decay: float = 6.0) -> list:
    """Một nốt có vài hoạ âm, tắt dần kiểu chuông."""
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-decay * t)
        s = (math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(4 * math.pi * freq * t)
             + 0.12 * math.sin(6 * math.pi * freq * t))
        out.append(vol * env * s / 1.47)
    return out


def mix(*parts) -> list:
    """parts: (độ trễ giây, mẫu). Cộng các nốt lên nhau."""
    n = max(int(RATE * d) + len(p) for d, p in parts)
    buf = [0.0] * n
    for d, p in parts:
        o = int(RATE * d)
        for i, v in enumerate(p):
            buf[o + i] += v
    return buf


def save(name: str, samples: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32000)) for v in samples))
    print(OUT / name)


if __name__ == "__main__":
    # cần bạn: hai nốt đi lên (E6 -> A6), đủ rõ để nghe thấy khi đang làm việc khác
    save("wait.wav", mix((0.0, tone(1318.5, 0.45)), (0.13, tone(1760.0, 0.6))))
    # xong: một nốt thấp, nhẹ (A5)
    save("done.wav", mix((0.0, tone(880.0, 0.5, vol=0.25, decay=7.0))))
