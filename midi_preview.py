# -*- coding: utf-8 -*-
"""
midi_preview.py - bản gốc của một file MIDI để vẽ lên khuông (chưa normalize).

Không tìm lưới / tempo như engine: chỉ đọc nốt + tempo map + số chỉ nhịp của file, cắt ô nhịp
từ tick 0, rồi đưa cho midi_to_musicxml.song_to_musicxml. Để bản nhạc vẽ ra không bị chồng nốt,
thời điểm nốt được làm tròn về lưới 32nd (theo tick, không phải giây) trước khi chuyển.

Phần nghe thử dùng nguyên file MIDI gốc (trả lại base64), nên tiếng là bản chơi thật.
"""

from __future__ import annotations

import base64
import bisect
import os
import struct
import tempfile
from dataclasses import replace
from types import SimpleNamespace

import normalize_piano_musicxml as N
import midi_to_musicxml as M2X


class _Clock:
    """Tempo map của file: tick <-> giây (giống cách read_midi quy đổi)."""

    def __init__(self, tempos, div):
        self.div = div
        pts, sec, last_t, last_us = [], 0.0, 0, 500000
        for t, us in tempos:
            sec += (t - last_t) * last_us / 1e6 / div
            pts.append((t, sec, us))
            last_t, last_us = t, us
        if not pts or pts[0][0] > 0:
            pts.insert(0, (0, 0.0, 500000))
        self.pts = pts
        self.ticks = [p[0] for p in pts]
        self.secs = [p[1] for p in pts]

    def to_sec(self, tick):
        t0, s0, us = self.pts[max(0, bisect.bisect_right(self.ticks, tick) - 1)]
        return s0 + (tick - t0) * us / 1e6 / self.div

    def to_tick(self, sec):
        t0, s0, us = self.pts[max(0, bisect.bisect_right(self.secs, sec) - 1)]
        return t0 + (sec - s0) * self.div * 1e6 / us


def _read_meta(data):
    header, chunks = N._chunks(data)
    _fmt, _n, div = struct.unpack(">HHH", header[:6])
    if div & 0x8000:
        raise ValueError("MIDI dùng SMPTE time division, chưa hỗ trợ")
    tempos, sig = set(), None
    for tag, body in chunks:
        if tag != b"MTrk":
            continue
        for t, kind, p in N._events(body):
            if kind != "meta":
                continue
            if p[0] == 0x51 and len(p[1]) == 3:
                tempos.add((t, int.from_bytes(p[1], "big")))
            elif p[0] == 0x58 and len(p[1]) >= 2:
                if sig is None or t < sig[0]:
                    sig = (t, p[1][0], 1 << p[1][1])
    return div, sorted(tempos), sig


def midi_to_song(data: bytes, split: str = "C4"):
    """MIDI bytes -> (song cho midi_to_musicxml, ppq, bpm đầu tiên)."""
    div, tempos, sig = _read_meta(data)
    clock = _Clock(tempos, div)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "in.mid")
        with open(path, "wb") as fh:
            fh.write(data)
        inp = N.read_midi(path, N.note_name_to_midi(split))

    # midi_to_musicxml chỉ hiểu ô nhịp theo phách đen: 6/8 -> 3 phách đen (hiện 3/4), x/8 lẻ -> 4/4
    beats, beat_type = (sig[1], sig[2]) if sig else (4, 4)
    bar_q = beats * 4 // beat_type if (beats * 4) % beat_type == 0 and beats > 0 else 4
    bar_ticks = bar_q * div
    grid = div // 8 if div % 8 == 0 else (div // 4 if div % 4 == 0 else div)

    seen, notes, last = set(), [], 0
    for n in sorted(inp.notes, key=lambda x: (x.start, x.pitch)):
        a = int(round(clock.to_tick(n.start) / grid)) * grid
        b = int(round(clock.to_tick(n.end) / grid)) * grid
        if b <= a:
            b = a + grid
        hand = n.hand or (N.LEFT if n.pitch < N.MIDDLE_C else N.RIGHT)
        key = (hand, a, n.pitch)
        if key in seen:
            continue
        seen.add(key)
        notes.append(replace(n, start=clock.to_sec(a), end=clock.to_sec(b), hand=hand))
        last = max(last, b)
    if not notes:
        raise ValueError("file MIDI không có nốt nào")

    nbars = max(2, -(-last // bar_ticks))       # ít nhất 2 ô nhịp để converter tính được độ dài ô nhịp chuẩn
    bar_times = [clock.to_sec(k * bar_ticks) for k in range(nbars)]
    key_fifths = inp.key_fifths if inp.key_fifths is not None else N.estimate_key(notes)
    song = SimpleNamespace(
        notes=notes,
        bar_times=bar_times,
        time_signature=(bar_q, 4),
        key_fifths=key_fifths,
        duration=clock.to_sec(nbars * bar_ticks),
    )
    bpm = 60e6 / tempos[0][1] if tempos else 120.0
    return song, div, bpm


def preview_from_midi_bytes(data: bytes, split: str = "C4") -> dict:
    """Kết quả cho POST /preview khi input là MIDI."""
    song, ppq, bpm = midi_to_song(data, split)
    xml = M2X.song_to_musicxml(song)
    return {
        "xml": xml,
        "midi": base64.b64encode(data).decode("ascii"),   # nghe đúng file gốc
        "bpm": bpm,
        "ppq": ppq,                                       # UI đổi tick của bản nhạc (480/phách đen) sang tick file gốc
        "beats": song.time_signature[0],
        "input_kind": "midi",
    }
