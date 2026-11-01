# -*- coding: utf-8 -*-
"""
midi_preview.py - bản gốc của một file MIDI để vẽ lên khuông (chưa normalize).

Không tìm lưới / tempo như engine: đọc nốt + tempo map + MỌI thay đổi số chỉ nhịp của file, cắt ô nhịp
từ tick 0 (mỗi ô theo số chỉ nhịp đang có hiệu lực), rồi đưa cho midi_to_musicxml.song_to_musicxml
(song.bar_sigs = số chỉ nhịp của từng ô). Thời điểm nốt được làm tròn về lưới 32nd (theo tick) trước khi
chuyển để bản nhạc không bị chồng nốt.

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
    tempos, sigs = set(), set()
    for tag, body in chunks:
        if tag != b"MTrk":
            continue
        for t, kind, p in N._events(body):
            if kind != "meta":
                continue
            if p[0] == 0x51 and len(p[1]) == 3:
                tempos.add((t, int.from_bytes(p[1], "big")))
            elif p[0] == 0x58 and len(p[1]) >= 2 and p[1][0] > 0:
                sigs.add((t, p[1][0], 1 << p[1][1]))
    return div, sorted(tempos), sorted(sigs)


def midi_to_song(data: bytes, split: str = "C4"):
    """MIDI bytes -> (song cho midi_to_musicxml, ppq, bpm đầu tiên)."""
    div, tempos, sigs = _read_meta(data)
    clock = _Clock(tempos, div)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "in.mid")
        with open(path, "wb") as fh:
            fh.write(data)
        inp = N.read_midi(path, N.note_name_to_midi(split))

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

    # Ô nhịp: mỗi ô dùng số chỉ nhịp có hiệu lực tại tick đầu ô (đổi giữa ô thì có hiệu lực từ ô kế)
    sig_ticks = [s[0] for s in sigs]

    def sig_at(tick):
        k = bisect.bisect_right(sig_ticks, tick) - 1
        return (sigs[k][1], sigs[k][2]) if k >= 0 else (4, 4)

    starts, bar_sigs, tick = [], [], 0
    while True:
        beats, bt = sig_at(tick)
        starts.append(clock.to_sec(tick))
        bar_sigs.append((beats, bt))
        tick += max(1, beats * 4 * div // bt)
        if tick >= last:
            break

    key_fifths = inp.key_fifths if inp.key_fifths is not None else N.estimate_key(notes)
    song = SimpleNamespace(
        notes=notes,
        bar_times=starts,
        bar_sigs=bar_sigs,
        bar_end=clock.to_sec(tick),
        time_signature=bar_sigs[0],
        key_fifths=key_fifths,
        duration=clock.to_sec(tick),
    )
    bpm = 60e6 / tempos[0][1] if tempos else 120.0
    return song, div, bpm


def preview_from_midi_bytes(data: bytes, split: str = "C4") -> dict:
    """Kết quả cho POST /preview khi input là MIDI."""
    song, ppq, bpm = midi_to_song(data, split)
    return {
        "xml": M2X.song_to_musicxml(song),
        "midi": base64.b64encode(data).decode("ascii"),   # nghe đúng file gốc
        "bpm": bpm,
        "ppq": ppq,                                       # UI đổi tick của bản nhạc (480/phách đen) sang tick file gốc
        "beats": song.time_signature[0],
        "input_kind": "midi",
    }
