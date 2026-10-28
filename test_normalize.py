"""normalize_piano_musicxml.py: a played-in piece (MIDI) or a messy MusicXML becomes one tidy voice per hand."""
import os
import random

import pytest

import normalize_piano_musicxml as N
from normalize_piano_musicxml import Note, _chunks, _events

CELL = 0.175                     # s: a 16th at 85.7 bpm


def _piece(bars=24, jitter=0.012, drift=0.004, lead=1.7, seed=1, pickup=False):
    """
    A 4/4 piece on a CELL grid, played in: RH melody on most cells, LH bass at each bar's first
    cell (a low note held a bar) and an arpeggio note on the beat; every onset jittered, the
    tempo drifting `drift` slower over the piece. Returns (notes, {id(note): true cell index}).
    """
    rnd = random.Random(seed)
    total = bars * 16
    true, out = {}, []

    def at(cell):
        t = lead + cell * CELL
        return t * (1.0 + drift * cell / total) + rnd.gauss(0, jitter)

    def add(cell, length, pitch, hand):
        s = at(cell)
        e = max(s + 0.05, at(cell + length) - rnd.uniform(0.0, 0.04))
        n = Note(pitch, s, e, 90, 0, hand)
        true[id(n)] = cell
        out.append(n)

    if pickup:
        add(-4, 4, 72, "R")
    for b in range(bars):
        add(b * 16, 6, 40 + (b % 3) * 2, "L")                       # the bass, shorter than the bar
        for beat in range(1, 4):
            add(b * 16 + beat * 4, 4, 52 + beat * 3, "L")
        c = 0
        while c < 16:
            length = rnd.choice((1, 2, 2, 4))
            add(b * 16 + c, min(length, 16 - c), 67 + rnd.randrange(0, 9), "R")
            c += length
    return out, true


def test_recovers_grid_tempo_and_bars():
    notes, true = _piece()
    clean = N.normalize(notes)
    assert clean.bpm == pytest.approx(60 / (CELL * 4), abs=0.6)             # 4 cells to the beat
    assert clean.stats["fit"] > 0.97
    # the first note (the first bass) opens bar 1, so a note of true cell c lands on unit 2c
    assert clean.stats["pickup_units"] == 0
    assert clean.notes[0].start == 0.0
    out = {(n.hand, n.pitch, round(n.start / clean.unit)) for n in clean.notes}
    right = sum(1 for n in notes if (n.hand, n.pitch, 2 * true[id(n)]) in out)
    assert right / len(notes) > 0.97


def test_pickup_is_kept_as_a_pickup():
    notes, _ = _piece(pickup=True)
    clean = N.normalize(notes)
    assert clean.stats["pickup_units"] == 3 * clean.units_per_beat       # one beat of music, three of silence before it
    assert clean.pickup_end == pytest.approx(clean.bar_times[1])


def test_one_voice_per_hand():
    notes, _ = _piece(bars=8)
    single = N.normalize(notes, voices="single")
    for hand in "RL":
        ns = sorted((n for n in single.notes if n.hand == hand), key=lambda n: n.start)
        starts = sorted({n.start for n in ns})
        for a, b in zip(starts, starts[1:]):
            assert max(n.end for n in ns if n.start == a) <= b + 1e-9
    assert single.stats["cut"] > 0
    keep = N.normalize(notes, voices="keep")
    assert keep.stats["cut"] == 0
    assert any(n.end - n.start > keep.unit * keep.units_per_beat for n in keep.notes)   # a held bass survives


def test_chord_shares_one_length():
    notes, _ = _piece(bars=8)
    extra = [Note(n.pitch + 4, n.start + 0.004, n.end + 0.3, 90, 0, "R") for n in notes
             if n.hand == "R"][:20]
    clean = N.normalize(notes + extra)
    by = {}
    for n in clean.notes:
        if n.hand == "R":
            by.setdefault(round(n.start, 6), set()).add(round(n.end, 6))
    assert all(len(v) == 1 for v in by.values())


def test_hand_marks_and_other_fields_survive():
    notes, _ = _piece(bars=6)
    clean = N.normalize(notes)
    assert {n.hand for n in clean.notes} == {"L", "R"}
    assert all(n.track == (0 if n.hand == "R" else 1) for n in clean.notes)
    assert len(clean.notes) == len(notes)


def test_pedal_follows_the_notes():
    notes, _ = _piece(bars=6)
    t = notes[40].start
    clean = N.normalize(notes, controls=[(t, 64, 127), (t + 1.0, 64, 0)])
    assert len(clean.controls) == 2 and clean.controls[0][0] < clean.controls[1][0]
    assert clean.controls[0][0] == pytest.approx(clean.map_time(t))


def test_writer_makes_two_staves(tmp_path):
    notes, _ = _piece(bars=6)
    clean = N.normalize(notes, controls=[(notes[10].start, 64, 127)])
    path = str(tmp_path / "clean.mid")
    assert N.write_midi(path, clean) == len(notes)
    data = open(path, "rb").read()
    header, chunks = _chunks(data)
    tracks = [(t, _events(b)) for t, b in chunks if t == b"MTrk"]
    assert len(tracks) == 3
    ppq = int.from_bytes(header[4:6], "big")
    assert ppq == N.PPQ
    tempo = [p for _, k, p in tracks[0][1] if k == "meta" and p[0] == 0x51]
    assert int.from_bytes(tempo[0][1], "big") == pytest.approx(60_000_000 / clean.bpm, abs=1)
    for (_, ev), ch in zip(tracks[1:], (0, 1)):
        ons = [(t, p) for t, k, p in ev if k == "midi" and p[0] & 0xF0 == 0x90 and p[2] > 0]
        assert ons and all(p[0] & 0x0F == ch for _, p in ons)
        assert all(t % (N.PPQ // clean.units_per_beat) == 0 for t, _ in ons)
        names = [p[1] for _, k, p in ev if k == "meta" and p[0] == 0x03]
        assert names == [b"Right hand" if ch == 0 else b"Left hand"]
        assert any(k == "midi" and p[0] & 0xF0 == 0xB0 for _, k, p in ev)   # the pedal reached both hands


def test_long_note_before_an_ornament_is_tidied():
    """A note held up to a 32nd run that starts between two cells ends on a cell: no second voice."""
    n = lambda p: Note(p, 0.0, 9.0, 90, 0, "R")
    by_u = {112: [(n(72), 125.0)], 125: [(n(76), 126.0)], 126: [(n(74), 127.0)], 127: [(n(72), 128.0)]}
    c = {"cut": 0, "rests": 0, "merged": 0, "tidied": 0}
    out = {u: ends[0] for u, ends, _ in N._voice(by_u, "single", "median", 6, c)}
    assert out[112] == 124 and c["tidied"] == 1                       # a dotted quarter, then a 32nd rest
    assert (out[125], out[126], out[127]) == (126, 127, 128)           # the run itself is untouched
    raw = {u: ends[0] for u, ends, _ in N._voice(by_u, "single", "median", 6, dict(c), tidy=False)}
    assert raw[112] == 125


def test_every_length_is_a_written_value():
    notes, _ = _piece(bars=8)
    clean = N.normalize(notes)
    for n in clean.notes:
        k = round((n.end - n.start) / clean.unit)
        assert k in N.STD_LEN or k > N.STD_LEN[-1]
        assert not (k >= 4 and round(n.end / clean.unit) % 2)


def test_too_few_notes():
    with pytest.raises(ValueError):
        N.find_cell([0.0, 0.3, 0.6])


# --------------------------------------------------------------------------- #
# MusicXML
# --------------------------------------------------------------------------- #

import xml.etree.ElementTree as ET

_STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _read_xml(path):
    """{part id: sorted [(midi, start unit, end unit)]} with ties joined; also voices and bad bars."""
    root = ET.parse(path).getroot()
    out, voices, bad = {}, set(), []
    for part in root.findall("part"):
        notes, open_t, t, div, beats = [], {}, 0, None, 4
        for m in part.findall("measure"):
            a = m.find("attributes")
            if a is not None:
                div = int(a.findtext("divisions") or div)
                if a.find("time") is not None:
                    beats = int(a.findtext("time/beats"))
            bar, pos, last = beats * div, 0, 0
            for n in m:
                if n.tag == "forward":
                    pos += int(n.findtext("duration"))
                    continue
                if n.tag != "note" or n.find("grace") is not None:
                    continue
                voices.add(n.findtext("voice"))
                d = int(n.findtext("duration"))
                chord = n.find("chord") is not None
                s = last if chord else pos
                if not chord:
                    last, pos = pos, pos + d
                p = n.find("pitch")
                if p is None:
                    continue
                midi = (int(p.findtext("octave")) + 1) * 12 + _STEP[p.findtext("step")] + int(p.findtext("alter") or 0)
                ties = [x.get("type") for x in n.findall("tie")]
                a0 = t + s
                st = open_t.pop(midi)[0] if midi in open_t and open_t[midi][1] == a0 and "stop" in ties else a0
                if "start" in ties:
                    open_t[midi] = (st, a0 + d)
                else:
                    notes.append((midi, st, a0 + d))
            implicit = m.get("implicit") == "yes"
            if pos != bar and not implicit:
                bad.append((m.get("number"), pos, bar))
            t += pos if implicit else bar
        assert not open_t
        out[part.get("id")] = sorted(notes)
    return out, voices, bad


def test_split_duration_makes_written_values():
    assert N.split_duration(0, 8, 8) == [8]                  # already a quarter: untouched
    assert N.split_duration(0, 10, 8) == [8, 2]
    assert N.split_duration(16, 13, 8) == [12, 1]
    assert N.split_duration(6, 5, 4) == [2, 3]               # off the beat: fill to the beat first
    assert N.split_duration(0, 5, 3) is None                 # triplet-ish: the caller keeps the old behaviour


def test_midi_to_musicxml_round_trip(tmp_path):
    notes, _ = _piece(bars=8)
    clean = N.normalize(notes)
    path = str(tmp_path / "out.xml")
    assert N.write_musicxml(path, clean, key_fifths=0) == len(notes)
    got, voices, bad = _read_xml(path)
    assert voices == {"1"} and not bad
    u = clean.unit
    for pid, hand in (("P1", "R"), ("P2", "L")):
        want = sorted((n.pitch, round(n.start / u), round(n.end / u)) for n in clean.notes if n.hand == hand)
        assert got[pid] == want


def test_musicxml_in_musicxml_out(tmp_path):
    src = tmp_path / "messy.xml"
    src.write_text('''<?xml version="1.0"?><score-partwise version="3.1"><part-list><score-part id="P1"><part-name>x</part-name></score-part></part-list>
<part id="P1"><measure number="1"><attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
<note><pitch><step>E</step><octave>5</octave></pitch><duration>5</duration><voice>1</voice></note>
<note><pitch><step>A</step><octave>5</octave></pitch><duration>11</duration><voice>1</voice></note>
<backup><duration>16</duration></backup>
<note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>5</voice></note></measure></part></score-partwise>''')
    dst = tmp_path / "out.xml"
    assert N.main([str(src), str(dst)]) == 0
    got, voices, bad = _read_xml(str(dst))
    assert voices == {"1"} and not bad
    assert got["P1"] == [(76, 0, 5), (81, 5, 16)] and got["P2"] == [(48, 0, 16)]


def test_cli_midi_to_midi_and_xml(tmp_path):
    notes, _ = _piece(bars=6)
    clean = N.normalize(notes)
    src = str(tmp_path / "in.mid")
    N.write_midi(src, clean)
    for ext in ("mid", "xml"):
        dst = str(tmp_path / ("out." + ext))
        assert N.main([src, dst]) == 0 and os.path.getsize(dst) > 0
    assert N.main([str(tmp_path / "out.xml"), str(tmp_path / "x.mid")]) == 1      # MusicXML -> MIDI: not supported


_HERE = os.path.dirname(os.path.abspath(__file__))
_MESSY = os.path.join(_HERE, "samples", "piano_messy.xml")


def _run_xml(tmp_path, *opts):
    dst = str(tmp_path / "out.xml")
    assert N.main([_MESSY, dst, *opts]) == 0
    return dst


def test_chord_note_does_not_advance_time(tmp_path):
    src = tmp_path / "chord.xml"
    src.write_text('''<score-partwise version="3.1"><part-list><score-part id="P1"><part-name>x</part-name></score-part></part-list>
<part id="P1"><measure number="1"><attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>
<note><chord/><pitch><step>E</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>
<note><pitch><step>D</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note></measure></part></score-partwise>''')
    dst = str(tmp_path / "o.xml")
    assert N.main([str(src), dst]) == 0
    got, _, _ = _read_xml(dst)
    assert got["P1"] == [(72, 0, 4), (74, 4, 8), (76, 0, 4)]


def test_messy_sample_is_one_voice_per_hand(tmp_path):
    got, voices, bad = _read_xml(_run_xml(tmp_path))
    assert voices == {"1"} and not bad
    assert (59, 16, 20) in got["P2"]                     # B3 written on the right-hand staff -> left hand (auto)
    assert (69, 4, 8) in got["P1"] and (76, 4, 8) in got["P1"]    # a chord stays one chord
    assert (74, 0, 4) in got["P1"]                       # the pickup stays at the start, not padded to a bar


def test_hand_modes(tmp_path):
    got, _, _ = _read_xml(_run_xml(tmp_path, "--hand", "staff"))
    assert (59, 16, 20) in got["P1"]                     # staff wins over pitch
    got, _, _ = _read_xml(_run_xml(tmp_path, "--hand", "pitch", "--split", "C5"))
    assert (74, 0, 4) in got["P1"] and (69, 4, 12) in got["P2"]      # the chord joins the C3 that starts with it
    got, _, _ = _read_xml(_run_xml(tmp_path, "--hand", "part", "--swap-parts"))
    assert (74, 0, 4) in got["P2"]                       # one part -> right; swapped -> left


def test_pickup_grace_and_time_change(tmp_path):
    dst = _run_xml(tmp_path)
    root = ET.parse(dst).getroot()
    right = root.findall("part")[0].findall("measure")
    assert right[0].get("implicit") == "yes"
    assert len(root.findall(".//grace")) == 1
    assert right[3].find("attributes/time/beats").text == "3"
    assert len(_run_xml_graceless(tmp_path).findall(".//grace")) == 0


def _run_xml_graceless(tmp_path):
    return ET.parse(_run_xml(tmp_path, "--drop-grace")).getroot()


def test_keep_ties_only_keeps_matching_pairs(tmp_path):
    dst = _run_xml(tmp_path, "--keep-ties")
    root = ET.parse(dst).getroot()
    starts = root.findall(".//tie[@type='start']")
    stops = root.findall(".//tie[@type='stop']")
    assert len(starts) == len(stops) == 1
    got, _, _ = _read_xml(dst)
    assert (79, 12, 28) in got["P1"]                     # G5 tied across the barline joins up


def test_no_fill_rests_uses_forward(tmp_path):
    root = ET.parse(_run_xml(tmp_path, "--no-fill-rests")).getroot()
    assert not root.findall(".//rest") and root.findall(".//forward")
    got, voices, bad = _read_xml(str(tmp_path / "out.xml"))
    assert not bad


def test_mxl_input(tmp_path):
    import zipfile
    mxl = str(tmp_path / "in.mxl")
    with zipfile.ZipFile(mxl, "w") as z:
        z.writestr("META-INF/container.xml",
                   '<container><rootfiles><rootfile full-path="s.xml"/></rootfiles></container>')
        z.writestr("s.xml", open(_MESSY, encoding="utf-8").read())
    dst = str(tmp_path / "o.xml")
    assert N.main([mxl, dst]) == 0
    assert _read_xml(dst)[0] == _read_xml(_run_xml(tmp_path))[0]


def test_single_track_midi_gets_two_hands_by_position():
    """A bass line low and a melody high, with the melody dipping below middle C: hands follow position."""
    notes = []
    for i in range(40):
        t = i * 0.5
        notes.append(Note(43 + (i % 4) * 4, t, t + 0.4, 80, 0, None))
        notes.append(Note(62 + (i % 5), t + 0.25, t + 0.45, 80, 0, None))
    N.split_hands(notes, 60)
    assert all(n.hand == ("L" if n.pitch < 56 else "R") for n in notes)


def test_dangling_ties_are_removed():
    part = ET.fromstring(
        '<part><measure number="1"><note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration>'
        '<tie type="start"/><voice>1</voice><notations><tied type="start"/></notations></note>'
        '<note><pitch><step>D</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>'
        '</measure></part>')
    N.sanitize_ties(part)
    assert not part.findall(".//tie") and not part.findall(".//notations")


def test_revoice_after_a_note_changes_hand():
    notes, _ = _piece(bars=6)
    clean = N.normalize(notes)
    moved = next(n for n in clean.notes if n.hand == "R")
    moved.hand, moved.track = "L", 1                   # a note edited onto the left hand
    again, pairs = N.revoice(clean)
    assert len(again.notes) <= len(clean.notes) and pairs
    for hand in "RL":
        ns = sorted((n for n in again.notes if n.hand == hand), key=lambda n: n.start)
        starts = sorted({n.start for n in ns})
        for a, b in zip(starts, starts[1:]):
            assert max(n.end for n in ns if n.start == a) <= b + 1e-9
    assert any(old is moved and new.hand == "L" for old, new in pairs)


def test_fingering_labels_are_written_before_their_notes(tmp_path):
    notes, _ = _piece(bars=4)
    clean = N.normalize(notes)
    first = next(n for n in clean.notes if n.hand == "R")
    path = str(tmp_path / "f.mid")
    N.write_midi(path, clean, fingers={id(first): "R3"})
    header, chunks = _chunks(open(path, "rb").read())
    ev = [e for t, b in chunks if t == b"MTrk" for e in _events(b)]
    texts = [(t, p[1]) for t, k, p in ev if k == "meta" and p[0] == 0x01]
    assert texts == [(round(first.start / clean.unit) * (N.PPQ // clean.units_per_beat), b"R3")]


def test_write_midi_rejects_a_beat_that_does_not_divide_ppq(tmp_path):
    notes, _ = _piece(bars=4)
    clean = N.normalize(notes)
    bad = N.replace(clean, units_per_beat=7)
    with pytest.raises(ValueError):
        N.write_midi(str(tmp_path / "x.mid"), bad)
