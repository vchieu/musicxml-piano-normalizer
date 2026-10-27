#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_output.py

Kiểm tra file MusicXML output có đúng cấu trúc mong muốn hay không:

1. Có đúng 2 score-part trong part-list.
2. Có đúng 2 part trong body.
3. Mỗi part chỉ dùng voice 1.
4. Có 2 MIDI channel riêng, mặc định là channel 1 và 2.
5. Mỗi score-part có đúng 1 midi-instrument.
6. Mỗi measure đủ độ dài theo số chỉ nhịp (ô nhịp implicit chỉ cần không dài quá), không có <backup>.
7. Tie không bị treo (mỗi tie start có tie stop cùng pitch ngay sau, và ngược lại).

Cách dùng:
    python tests/check_output.py output/test_output.xml

Tuỳ chọn:
    --channels "1,2"
    --min-notes 1
    --no-timing      bỏ qua kiểm tra 6 và 7
"""

import argparse
import sys
import xml.etree.ElementTree as ET

STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def fail(message: str):
    print(f"FAIL: {message}")
    sys.exit(1)


def strip_namespaces(root):
    for elem in root.iter():
        if isinstance(elem.tag, str) and "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

        for key in list(elem.attrib.keys()):
            if "}" in key:
                del elem.attrib[key]


def parse_expected_channels(text: str):
    items = [x.strip() for x in text.split(",") if x.strip()]
    if not items:
        fail("--channels không hợp lệ. Ví dụ hợp lệ: 1,2")
    return sorted(items)


def midi_of(note):
    p = note.find("pitch")
    if p is None:
        return None
    return (int(p.findtext("octave")) + 1) * 12 + STEP[p.findtext("step")] + int(float(p.findtext("alter") or 0))


def check_timing(part_id, part):
    """Độ dài từng measure + tie không treo. Trả về số tie."""
    divisions, beats, beat_type = None, 4, 4
    rows, base, ties = [], 0, 0

    for measure in part.findall("measure"):
        num = measure.get("number")
        attrs = measure.find("attributes")
        if attrs is not None:
            if attrs.findtext("divisions"):
                divisions = int(attrs.findtext("divisions"))
            if attrs.find("time") is not None:
                beats = int(attrs.findtext("time/beats"))
                beat_type = int(attrs.findtext("time/beat-type"))
        if divisions is None:
            fail(f"Part {part_id} measure {num}: chưa có <divisions>")

        pos = last = 0
        for child in measure:
            if child.tag == "backup":
                fail(f"Part {part_id} measure {num}: có <backup>, nghĩa là có nhiều voice")
            if child.tag == "forward":
                pos += int(child.findtext("duration"))
            elif child.tag == "note" and child.find("grace") is None:
                d = int(child.findtext("duration"))
                chord = child.find("chord") is not None
                onset = base + (last if chord else pos)
                if not chord:
                    last, pos = pos, pos + d
                midi = midi_of(child)
                kinds = {t.get("type") for t in child.findall("tie")}
                ties += len(kinds)
                if midi is not None:
                    rows.append((onset, onset + d, midi, kinds, num))

        expected = beats * divisions * 4 // beat_type
        if measure.get("implicit") == "yes":
            if pos > expected:
                fail(f"Part {part_id} measure {num}: ô nhịp implicit dài {pos} > {expected}")
        elif pos != expected:
            fail(f"Part {part_id} measure {num}: dài {pos}, cần {expected} ({beats}/{beat_type})")
        base += pos

    ends = {(e, m) for _, e, m, _, _ in rows}
    starts = {(s, m) for s, _, m, _, _ in rows}
    for s, e, m, kinds, num in rows:
        if "start" in kinds and (e, m) not in starts:
            fail(f"Part {part_id} measure {num}: tie start không có note nối tiếp (pitch {m})")
        if "stop" in kinds and (s, m) not in ends:
            fail(f"Part {part_id} measure {num}: tie stop không có note trước (pitch {m})")
    return ties


def main():
    parser = argparse.ArgumentParser(
        description="Kiểm tra output MusicXML: 2 part, mỗi part 1 voice, 2 MIDI channel, độ dài ô nhịp, tie."
    )

    parser.add_argument(
        "output",
        help="File MusicXML output cần kiểm tra",
    )

    parser.add_argument(
        "--channels",
        default="1,2",
        help="Danh sách MIDI channel mong đợi, phân tách bằng dấu phẩy. Mặc định: 1,2",
    )

    parser.add_argument(
        "--min-notes",
        type=int,
        default=0,
        help="Số lượng note/rest tối thiểu trong toàn bộ output. Mặc định: 0",
    )

    parser.add_argument(
        "--no-timing",
        action="store_true",
        help="Bỏ qua kiểm tra độ dài ô nhịp và tie",
    )

    args = parser.parse_args()

    try:
        tree = ET.parse(args.output)
        root = tree.getroot()
    except Exception as e:
        fail(f"Không đọc được file output: {e}")

    strip_namespaces(root)

    if root.tag != "score-partwise":
        fail(f"Root tag phải là <score-partwise>, nhưng nhận được <{root.tag}>")

    part_list = root.find("part-list")
    if part_list is None:
        fail("Không tìm thấy <part-list>")

    score_parts = part_list.findall("score-part")
    if len(score_parts) != 2:
        fail(f"Cần đúng 2 <score-part>, nhưng tìm thấy {len(score_parts)}")

    part_ids = []
    for score_part in score_parts:
        part_id = score_part.get("id")
        if not part_id:
            fail("Có <score-part> thiếu attribute id")
        part_ids.append(part_id)

    if len(set(part_ids)) != 2:
        fail("Hai <score-part> bị trùng id")

    expected_channels = parse_expected_channels(args.channels)
    found_channels = []

    for score_part in score_parts:
        part_id = score_part.get("id")

        midi_instruments = score_part.findall("midi-instrument")
        if len(midi_instruments) != 1:
            fail(
                f"Score-part {part_id} phải có đúng 1 <midi-instrument>, "
                f"nhưng tìm thấy {len(midi_instruments)}"
            )

        midi_channel_elem = midi_instruments[0].find("midi-channel")
        if midi_channel_elem is None or not midi_channel_elem.text:
            fail(f"Score-part {part_id} thiếu <midi-channel>")

        channel = midi_channel_elem.text.strip()
        found_channels.append(channel)

    if sorted(found_channels) != expected_channels:
        fail(
            "MIDI channel không đúng. "
            f"Mong đợi: {expected_channels}, tìm thấy: {sorted(found_channels)}"
        )

    parts = root.findall("part")
    if len(parts) != 2:
        fail(f"Cần đúng 2 <part> trong body, nhưng tìm thấy {len(parts)}")

    part_by_id = {}
    for part in parts:
        part_id = part.get("id")
        if not part_id:
            fail("Có <part> thiếu attribute id")
        if part_id in part_by_id:
            fail(f"Part id bị trùng: {part_id}")
        part_by_id[part_id] = part

    for part_id in part_ids:
        if part_id not in part_by_id:
            fail(f"Score-part {part_id} không có <part id=\"{part_id}\"> tương ứng")

    total_note_count = 0
    total_ties = 0

    for part_id in part_ids:
        part = part_by_id[part_id]
        notes = part.findall(".//note")

        total_note_count += len(notes)

        voices = set()

        for note in notes:
            voice_elem = note.find("voice")

            if voice_elem is None or voice_elem.text is None:
                fail(f"Part {part_id} có <note> thiếu <voice>")

            voice = voice_elem.text.strip()
            voices.add(voice)

        if voices and voices != {"1"}:
            fail(
                f"Part {part_id} phải chỉ có voice 1, "
                f"nhưng tìm thấy các voice: {sorted(voices)}"
            )

        if not args.no_timing:
            total_ties += check_timing(part_id, part)

    if total_note_count < args.min_notes:
        fail(
            f"Output có {total_note_count} note/rest, "
            f"nhưng yêu cầu tối thiểu là {args.min_notes}"
        )

    print("PASS: Output đạt yêu cầu:")
    print("  - 2 score-part")
    print("  - 2 part")
    print(f"  - MIDI channels: {sorted(found_channels)}")
    print("  - Mỗi part chỉ dùng voice 1")
    if not args.no_timing:
        print("  - Mỗi measure đủ độ dài, không có backup, tie không treo")
    print(f"  - Tổng số note/rest: {total_note_count}")


if __name__ == "__main__":
    main()
