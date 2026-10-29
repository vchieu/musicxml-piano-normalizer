"""Web UI cho normalize_piano_musicxml: render bản sạch, nghe thử, tải .xml/.mid.

Một endpoint `POST /normalize` nhận file MIDI hoặc MusicXML và trả về bản đã chuẩn hóa
(MusicXML + MIDI base64), danh sách nốt để vẽ cursor khi phát, report/stats và câu lệnh CLI
tương ứng với input.

Chạy:
    python -m uvicorn app:app --reload
"""

import base64
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

import normalize_piano_musicxml as N
import xml_regrid_piano as X

BASE = Path(__file__).resolve().parent

app = FastAPI(title="Piano Normalizer")


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


def _resolve_simplify(simplify, lh_max, rh_max, drop_ornaments):
    """Preset giống CLI: --simplify = 3 / 1 / bỏ nốt láy; giá trị ghi rõ (kể cả 0) thắng."""
    lh = lh_max if lh_max is not None else (3 if simplify else 0)
    rh = rh_max if rh_max is not None else (1 if simplify else 0)
    return lh, rh, drop_ornaments or simplify


def _command(kind, *, beats, split, hand, split_chords, downbeat, max_bpm, fine, min_dur,
             lh_max, rh_max, drop_ornaments, simplify):
    """Câu lệnh CLI đúng cho loại input, chỉ gồm flag khác mặc định."""
    if kind == "midi":
        parts = ["python", "normalize_piano_musicxml.py", "input.mid", "clean.xml"]
        default_max_bpm = float(N.MAX_BPM)
    else:
        parts = ["python", "xml_regrid_piano.py", "input.xml", "clean.xml"]
        default_max_bpm = 90.0

    if beats != 4:
        parts += ["--beats", str(beats)]
    if split != "C4":
        parts += ["--split", split]
    if kind == "xml":
        if hand != "auto":
            parts += ["--hand", hand]
        if split_chords:
            parts.append("--split-chords")
    if downbeat != "auto":
        parts += ["--downbeat", downbeat]
    if abs(float(max_bpm) - default_max_bpm) > 1e-9:
        parts += ["--max-bpm", "%g" % max_bpm]
    if fine:
        parts.append("--fine")
    if min_dur and min_dur > 0:
        parts += ["--min-dur", "%g" % min_dur]
    if simplify:
        parts.append("--simplify")
    if lh_max is not None:
        parts += ["--lh-max", str(lh_max)]
    if rh_max is not None:
        parts += ["--rh-max", str(rh_max)]
    if drop_ornaments:
        parts.append("--drop-ornaments")
    return " ".join(parts)


@app.post("/normalize")
async def normalize(
    file: UploadFile = File(...),
    beats: int = Form(4),
    split: str = Form("C4"),
    hand: str = Form("auto"),
    split_chords: bool = Form(False),
    downbeat: str = Form("auto"),
    max_bpm: float = Form(130.0),
    fine: bool = Form(False),
    min_dur: float = Form(0.0),
    lh_max: Optional[int] = Form(None),
    rh_max: Optional[int] = Form(None),
    drop_ornaments: bool = Form(False),
    simplify: bool = Form(False),
):
    filename = file.filename or "input.mid"
    suffix = os.path.splitext(filename)[1].lower()

    if suffix in N._MIDI_EXT:
        kind = "midi"
    elif suffix in N._XML_IN_EXT:
        kind = "xml"
    else:
        raise HTTPException(400, "Chỉ hỗ trợ .mid/.midi/.xml/.musicxml/.mxl")

    if hand not in ("auto", "staff", "pitch"):
        raise HTTPException(400, "hand phải là auto, staff hoặc pitch")
    if downbeat not in ("auto", "first"):
        raise HTTPException(400, "downbeat phải là auto hoặc first")
    if beats < 1:
        raise HTTPException(400, "beats phải >= 1")
    if max_bpm <= 0:
        raise HTTPException(400, "max_bpm phải > 0")
    if min_dur < 0:
        raise HTTPException(400, "min_dur phải >= 0")
    if lh_max is not None and lh_max < 0:
        raise HTTPException(400, "lh_max phải >= 0")
    if rh_max is not None and rh_max < 0:
        raise HTTPException(400, "rh_max phải >= 0")

    try:
        threshold = N.note_name_to_midi(split)
    except ValueError as e:
        raise HTTPException(400, f"split không hợp lệ: {e}")

    lh, rh, drop_orn = _resolve_simplify(simplify, lh_max, rh_max, drop_ornaments)

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "input" + suffix)
        with open(src, "wb") as fh:
            fh.write(await file.read())

        try:
            if kind == "midi":
                inp = N.load_midi_input(src, "auto", threshold)
                notes = inp.notes
                controls = inp.controls or None
                fifths = inp.key_fifths
                bpm_hint = None
                engine_bpm = max_bpm
                engine_min_dur = min_dur
            else:
                notes = X.extract_notes_from_musicxml(src, threshold, hand=hand,
                                                      split_chords=split_chords)
                controls = None
                fifths, bpm_hint = X.read_score_meta(src)
                # Nốt đưa vào engine theo đơn vị phách đen: 1 beat = 1 phách đen.
                engine_bpm = 90.0
                engine_min_dur = 0.0

            clean = N.normalize(notes, controls=controls, beats_per_bar=beats,
                                max_bpm=engine_bpm, voices="single", chord_end="median",
                                downbeat=downbeat, tidy=True, fine=fine,
                                min_dur=engine_min_dur, lh_max=lh, rh_max=rh,
                                drop_ornaments=drop_orn)
        except ValueError as e:
            raise HTTPException(400, f"Không chuẩn hóa được: {e}")
        except RuntimeError as e:
            raise HTTPException(500, f"Engine MIDI lỗi: {e}")
        except Exception as e:
            raise HTTPException(500, f"Lỗi xử lý: {e}")

        if bpm_hint:
            clean.bpm = bpm_hint

        key = fifths if fifths is not None else N.estimate_key(clean.notes)

        xml_path = os.path.join(td, "clean.xml")
        midi_path = os.path.join(td, "clean.mid")
        try:
            N.write_musicxml(xml_path, clean, key_fifths=key)
            N.write_midi(midi_path, clean, key_fifths=key)
            xml_text = Path(xml_path).read_text(encoding="utf-8")
            midi_b64 = base64.b64encode(Path(midi_path).read_bytes()).decode("ascii")
        except Exception as e:
            raise HTTPException(500, f"Không ghi được output: {e}")

    events = [{"start": n.start, "end": n.end, "pitch": n.pitch, "hand": n.hand}
              for n in clean.notes]
    command = _command(kind, beats=beats, split=split, hand=hand, split_chords=split_chords,
                       downbeat=downbeat, max_bpm=engine_bpm, fine=fine,
                       min_dur=engine_min_dur, lh_max=lh_max, rh_max=rh_max,
                       drop_ornaments=drop_ornaments, simplify=simplify)

    return {
        "xml": xml_text,
        "midi": midi_b64,
        "events": events,
        "report": clean.report,
        "command": command,
        "stats": clean.stats,
        "input_kind": kind,
        "bpm": clean.bpm,
        "beats": clean.beats_per_bar,
        "key": key,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000)
