#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xml_regrid_piano.py

Đọc MusicXML partwise, bỏ ý nghĩa ô nhịp cũ, chuyển thành danh sách nốt theo đơn vị phách đen
(1 phách đen = 1 "giây" của engine), rồi gọi engine MIDI của normalize_piano_musicxml.py để
chuẩn hóa về nhịp mong muốn, 2 tay, 1 voice mỗi tay.

Vì nốt được đưa vào engine theo đơn vị phách đen, `--max-bpm 90` (mặc định) làm engine chọn
1 beat = 1 phách đen; nhờ vậy lưới tìm được đúng là phách đen / nốt của bản gốc. Output MusicXML
đúng như bản gốc về nhịp; `clean.bpm` được ghi đè bằng `--tempo-mark` (lấy từ file input nếu có)
chỉ để ghi tempo marking, không làm thay đổi độ dài nốt đã viết.

`--min-dur` ở script này tính bằng phách đen (không phải giây).
"""

import argparse
import normalize_piano_musicxml as N


def read_score_meta(path):
    """(fifths, bpm) của file MusicXML: <key><fifths> đầu tiên và tempo đầu tiên (hoặc None)."""
    root = N.load_musicxml_root(path)
    fifths = None
    for key in root.iter("key"):
        txt = key.findtext("fifths")
        if txt is not None and txt.strip():
            try:
                fifths = int(txt)
            except ValueError:
                fifths = None
            break
    bpm = None
    for sound in root.iter("sound"):
        if sound.get("tempo"):
            try:
                bpm = float(sound.get("tempo"))
                break
            except ValueError:
                pass
    if bpm is None:
        for per in root.iter("per-minute"):
            if per.text and per.text.strip():
                try:
                    bpm = float(per.text)
                    break
                except ValueError:
                    pass
    return fifths, bpm


def extract_notes_from_musicxml(path, split_midi, hand="auto", split_chords=False):
    root = N.load_musicxml_root(path)

    if root.tag != "score-partwise":
        raise ValueError("Chỉ hỗ trợ score-partwise.")

    parts = root.findall("part")
    part_measures = [p.findall("measure") for p in parts]
    max_measures = max((len(x) for x in part_measures), default=0)

    if max_measures == 0:
        return []

    first_attrs = root.find(".//attributes")
    initial_divisions = 1
    initial_beats = 4
    initial_beat_type = 4

    if first_attrs is not None:
        initial_divisions = N.get_child_int(first_attrs, "divisions", 1) or 1
        time_elem = first_attrs.find("time")
        if time_elem is not None:
            initial_beats = N.get_child_int(time_elem, "beats", 4) or 4
            initial_beat_type = N.get_child_int(time_elem, "beat-type", 4) or 4

    states = [
        {
            "divisions": initial_divisions,
            "beats": initial_beats,
            "beat_type": initial_beat_type,
        }
        for _ in parts
    ]

    notes = []
    t = 0.0  # thời gian tuyệt đối, tính bằng phách đen

    for mi in range(max_measures):
        parsed = []
        implicit = False

        for pi, ms in enumerate(part_measures):
            if mi >= len(ms):
                continue

            m = ms[mi]
            if m.get("implicit") == "yes" or m.get("number") == "0":
                implicit = True

            evs = N.parse_measure(pi, m, states[pi], None)
            parsed.append((pi, evs))

        if not parsed:
            continue

        # Độ dài ô nhịp, tính bằng phách đen (divisions của mỗi part có thể khác nhau).
        ends_q = [st.get("measure_end", 0) / max(1, st["divisions"]) for st in states]
        nominal_q = max(N.expected_duration(st) / max(1, st["divisions"]) for st in states)
        end_q = max(ends_q, default=0)
        measure_len = end_q if implicit and 0 < end_q < nominal_q else max(nominal_q, end_q)

        for pi, evs in parsed:
            div = max(1, states[pi]["divisions"])

            for ev in evs:
                if not ev.items:
                    continue

                start_q = t + ev.onset / div
                end_q = t + (ev.onset + ev.duration) / div

                valid_items = [(midi, orig) for midi, orig in ev.items if midi is not None]
                if not valid_items:
                    continue

                bottom = min(midi for midi, _ in valid_items)

                for midi, orig in valid_items:
                    if split_chords:
                        h = N.LEFT if midi < split_midi else N.RIGHT
                    elif hand == "staff":
                        h = N.LEFT if ev.staff == "2" else N.RIGHT
                    elif hand == "pitch":
                        h = N.LEFT if midi < split_midi else N.RIGHT
                    else:
                        # auto
                        if bottom < split_midi:
                            h = N.LEFT
                        elif ev.staff == "2":
                            h = N.LEFT
                        elif ev.staff == "1":
                            h = N.RIGHT
                        else:
                            h = N.LEFT if midi < split_midi else N.RIGHT

                    notes.append(
                        N.Note(
                            pitch=midi,
                            start=start_q,
                            end=end_q,
                            velocity=90,
                            track=0,
                            hand=h,
                        )
                    )

        t += measure_len  # đã tính bằng phách đen

    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes


def build_parser():
    p = argparse.ArgumentParser(
        description="Re-grid MusicXML về nhịp mong muốn, 2 tay piano, 1 voice mỗi tay."
    )

    p.add_argument("input", help="File MusicXML đầu vào (.xml/.musicxml/.mxl)")
    p.add_argument("output", help="File MusicXML đầu ra (.xml)")

    p.add_argument("--beats", type=int, default=4,
                   help="Số phách mỗi ô nhịp, mặc định 4 cho 4/4.")
    p.add_argument("--split", default="C4",
                   help="Ngưỡng tách tay, mặc định C4.")
    p.add_argument("--hand", choices=("auto", "staff", "pitch"), default="auto",
                   help="Cách phân tay.")
    p.add_argument("--split-chords", action="store_true",
                   help="Tách từng nốt trong chord theo --split.")

    p.add_argument("--offset-beats", type=float, default=0.0,
                   help="Dịch toàn bộ nốt sang phải bao nhiêu phách đen.")

    # Vì wrapper dùng đơn vị phách đen, max-bpm ~90 để engine ưu tiên phách đen.
    p.add_argument("--max-bpm", type=float, default=90.0,
                   help="Giới hạn tempo suy luận trong wrapper này (mặc định 90: 1 beat = 1 phách đen).")

    p.add_argument("--downbeat", choices=("auto", "first"), default="auto")

    p.add_argument("--fine", action="store_true",
                   help="cho phép nốt/độ dài trên nửa ô lưới (mặc định: không ghi nốt ngắn hơn 16th)")
    p.add_argument("--min-dur", type=float, default=0.0, metavar="BEATS",
                   help="bỏ nốt ngắn hơn BEATS phách đen trước khi chuẩn hóa (mặc định 0 = giữ hết). "
                        "Lưu ý: đơn vị ở script này là phách đen, không phải giây")
    p.add_argument("--lh-max", type=int, default=None, metavar="N",
                   help="tay trái tối đa N nốt mỗi hợp âm (giữ bass trước). 0 = không giới hạn "
                        "(mặc định 0, hoặc 3 khi --simplify)")
    p.add_argument("--rh-max", type=int, default=None, metavar="N",
                   help="tay phải tối đa N nốt mỗi hợp âm (giữ nốt cao nhất trước). 0 = không giới hạn "
                        "(mặc định 0, hoặc 1 khi --simplify)")
    p.add_argument("--drop-ornaments", action="store_true",
                   help="bỏ nốt láy (nốt rất ngắn, cách nốt dài cùng beat / hợp âm dài kề bên 1-2 bán cung)")
    p.add_argument("--simplify", action="store_true",
                   help="đơn giản hóa: --lh-max 3 --rh-max 1 --drop-ornaments (ghi rõ --lh-max/--rh-max "
                        "thì giá trị đó thắng, kể cả 0)")

    p.add_argument("--key", type=int, default=None,
                   help="Số dấu hóa của khóa. Mặc định lấy từ file input, không có thì 2 (D major).")
    p.add_argument("--tempo-mark", type=float, default=None,
                   help="Tempo marking ghi vào XML. Mặc định lấy từ file input, không có thì 113.")

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    split_midi = N.note_name_to_midi(args.split)

    try:
        fifths_in, bpm_in = read_score_meta(args.input)
    except Exception as e:
        raise SystemExit("Không đọc được file input: %s" % e)

    key = args.key if args.key is not None else (fifths_in if fifths_in is not None else 2)
    tempo_mark = args.tempo_mark if args.tempo_mark is not None else (
        bpm_in if bpm_in is not None else 113.0)

    notes = extract_notes_from_musicxml(
        args.input,
        split_midi=split_midi,
        hand=args.hand,
        split_chords=args.split_chords,
    )

    if not notes:
        raise SystemExit("Không trích xuất được nốt nào từ file input.")

    if args.offset_beats:
        for n in notes:
            n.start += args.offset_beats
            n.end += args.offset_beats

    lh_max = args.lh_max if args.lh_max is not None else (3 if args.simplify else 0)
    rh_max = args.rh_max if args.rh_max is not None else (1 if args.simplify else 0)
    drop_orn = args.drop_ornaments or args.simplify

    try:
        clean = N.normalize(notes, beats_per_bar=args.beats, max_bpm=args.max_bpm,
                            downbeat=args.downbeat, voices="single", tidy=True,
                            fine=args.fine, min_dur=args.min_dur,
                            lh_max=lh_max, rh_max=rh_max, drop_ornaments=drop_orn)
    except (ValueError, RuntimeError) as e:
        raise SystemExit("Không chuẩn hóa được %s: %s" % (args.input, e))

    # Chỉ là tempo marking; không làm thay đổi độ dài nốt đã viết.
    clean.bpm = tempo_mark

    n_written = N.write_musicxml(args.output, clean, key_fifths=key)

    for line in clean.report:
        print(line)

    print(f"Đã xuất: {args.output}")
    print(f"Tổng số nốt: {n_written}")
    print(f"Tay phải: {clean.stats.get('right', 0)}, tay trái: {clean.stats.get('left', 0)}")


if __name__ == "__main__":
    main()
