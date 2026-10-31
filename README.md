# Piano Normalizer (MIDI + MusicXML)

Một script Python độc lập, chuẩn hóa piano về dạng sạch cho 2 tay. Nhận **MIDI** hoặc **MusicXML**:

- **2 part riêng biệt**
  - `P1`: tay phải (khóa Sol)
  - `P2`: tay trái (khóa Fa)
- **Mỗi part chỉ còn 1 voice duy nhất**: `<voice>1</voice>`
- **Mỗi tay 1 MIDI channel riêng** (mặc định tay phải channel 1, tay trái channel 2)
- **Mỗi ô nhịp đúng độ dài**, độ dài lạ được chia thành nốt ghi được nối bằng tie
- MIDI chơi tay (lệch nhịp, tempo trôi) được đặt lên lưới chính xác, tìm lại tempo và ô nhịp

| Input | Output | Dùng khi |
|---|---|---|
| `.mid` / `.midi` | `.mid` | MIDI chơi tay -> MIDI sạch 2 track (Right hand / Left hand) |
| `.mid` / `.midi` | `.xml` | MIDI chơi tay -> bản nhạc MusicXML 2 part, mỗi tay 1 voice |
| `.xml` / `.musicxml` / `.mxl` | `.xml` | MusicXML nhiều voice/staff -> 2 part, mỗi part 1 voice |

MusicXML -> MIDI chưa hỗ trợ. Muốn ra MIDI từ MusicXML thì mở bằng MuseScore rồi export.

---

## Yêu cầu

- Python 3.11 trở lên
- MusicXML: không cần cài gì thêm (chỉ thư viện chuẩn)
- MIDI: cần `numpy` (`pip install -r requirements.txt`)
- Web UI (`app.py` + `static/index.html`): cần `fastapi`, `uvicorn`, `python-multipart`
  (`pip install -r requirements-web.txt`, hoặc `uv sync` nếu dùng `pyproject.toml`)
- Chạy độc lập, không cần `midi_loader` hay project khác. Nếu chạy trong project có `midi_loader` thì
  script tự dùng nó để đọc MIDI (xem `--reader`).

---

## Cách sử dụng cơ bản

```bash
python normalize_piano_musicxml.py bai.mid bai_clean.mid
python normalize_piano_musicxml.py bai.mid bai_clean.xml
python normalize_piano_musicxml.py ban_goc.xml ban_chuan.xml
```

Bỏ `output` thì file ra là `<input>_clean.mid` (input MIDI) hoặc `<input>_clean.xml` (input MusicXML).

Script in ra báo cáo ngắn: tempo và lưới tìm được, số nốt bị cắt/rút ngắn, số nốt mỗi tay.

---

## Kiểm tra tự động

```bash
pytest test_normalize.py
python normalize_piano_musicxml.py samples/Luu_Nien_messy.mid output/test_output.xml --beats 4
python tests/check_output.py output/test_output.xml --channels 1,2 --min-notes 1
python xml_regrid_piano.py samples/piano_messy.xml output/regrid.xml
python tests/check_output.py output/regrid.xml --channels 1,2 --min-notes 1
```

Với Make (như trước):

```bash
make test            # pytest + check_output trên samples/Luu_Nien_messy.mid
make test-reference  # samples/piano_messy.xml
make test-all
make web             # uvicorn app:app --reload
```

`tests/check_output.py` kiểm tra output MusicXML: 2 score-part, 2 part, mỗi part chỉ voice 1, 2 MIDI
channel riêng, mỗi measure đủ độ dài (ô nhịp `implicit` chỉ cần không dài quá), không có `<backup>`, tie
không bị treo. Thêm `--no-timing` để bỏ hai kiểm tra cuối. In `PASS` nghĩa là đạt.

`test_normalize.py` (pytest, cần numpy) kiểm tra thêm engine MIDI, round-trip MIDI -> MusicXML từng nốt,
phân tay, grace, tie, ô nhịp lấy đà, `.mxl`, luật "không ghi nốt ngắn hơn 16th", `--fine`, `--lh-max` /
`--rh-max`, `--min-dur`, `--drop-ornaments`, `--simplify`, `revoice(..., fine=...)`, cảnh báo flag
MIDI-only trên đường MusicXML, endpoint `app.normalize` và `xml_regrid_piano.py`.

Máy này không cho pytest ghi vào `%TEMP%\pytest-of-Admin`, nên nếu gặp lỗi quyền thì thêm
`--basetemp=C:\Users\Admin\AppData\Local\Temp\opencode\pt`.

---

## Tùy chọn dòng lệnh

### Chung

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---:|---|
| `input` | bắt buộc | `.mid`/`.midi`/`.xml`/`.musicxml`/`.mxl` |
| `output` | `<input>_clean.*` | `.mid` (chỉ khi input MIDI) hoặc `.xml`/`.musicxml` |
| `--split`, `--threshold` | `C4` | Ngưỡng tách tay (xem bên dưới). `--threshold` là tên cũ |
| `--channel1` / `--channel2` | `1` / `2` | MIDI channel tay phải / tay trái |
| `--program` | `1` | MIDI program (1 = piano) |
| `--volume1` / `--volume2` | `78.7402` | Âm lượng tay phải / tay trái |
| `--no-final-barline` | tắt | Không thêm barline kết thúc |
| `--no-brace` | tắt | Không thêm brace nhóm piano |

### Input MusicXML

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---:|---|
| `--hand` | `auto` | `auto`, `staff`, `pitch`, `part` (xem bên dưới) |
| `--split-chords` | tắt | Tách từng note của một chord theo `--split` (chỉ với `auto`/`pitch`) |
| `--swap-parts` | tắt | Đảo tay phải/trái theo part |
| `--keep-ties` | tắt | Giữ tie của input khi độ dài nốt không đổi |
| `--drop-grace` | tắt | Bỏ grace note (mặc định giữ) |
| `--no-fill-rests` | tắt | Không ghi dấu nghỉ, khoảng trống dùng `<forward>` |
| `--keep-beams` | tắt | Không còn tác dụng (beam luôn do phần mềm chấm nhạc tự vẽ) |

### Input MIDI

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---:|---|
| `--reader` | `auto` | `auto`: dùng `midi_loader.load_song` nếu import được, không thì reader có sẵn. `loader` / `builtin` để chọn cứng |
| `--beats` | `4` | Số phách (đen) mỗi ô nhịp |
| `--max-bpm` | `130` | Giữ phách đen dưới tempo này (quyết định đô-đen là ô lưới nào) |
| `--voices` | `single` | `single`: mỗi tay 1 voice. `keep`: giữ nốt ngân (chỉ khi output `.mid`) |
| `--no-tidy` | tắt | Giữ độ dài như đã chơi (phần mềm chấm nhạc có thể tự tách voice 2) |
| `--chord-end` | `median` | Hợp âm kết thúc theo `median`/`max`/`min` của các nốt |
| `--downbeat` | `auto` | `first`: ép nốt đầu là phách 1 |
| `--fine` | tắt | Cho phép đặt hợp âm/độ dài lên nửa ô lưới (32nd, ornament). Mặc định chỉ dùng ô lưới nguyên khi ô là 16th hoặc ngắn hơn; khi ô là 8th hoặc dài hơn thì nửa ô (vẫn ≥ 16th) được phép |
| `--min-dur` | `0` | Bỏ nốt ngắn hơn `SEC` giây trước khi chuẩn hóa (0 = giữ hết). Nếu bỏ xong còn dưới 8 nốt thì giữ nguyên |
| `--lh-max` | `0` | Tay trái tối đa `N` nốt mỗi hợp âm (giữ nốt bass trước). 0 = không giới hạn; mặc định thành 3 khi `--simplify` |
| `--rh-max` | `0` | Tay phải tối đa `N` nốt mỗi hợp âm (giữ nốt cao nhất = giai điệu trước). 0 = không giới hạn; mặc định thành 1 khi `--simplify` |
| `--drop-ornaments` | tắt | Bỏ nốt láy: nốt rất ngắn, cách nốt dài cùng beat hoặc hợp âm dài kề bên 1-2 bán cung (cùng phím thì không bỏ) |
| `--simplify` | tắt | Preset `--lh-max 3 --rh-max 1 --drop-ornaments`. Ghi rõ `--lh-max`/`--rh-max` thì giá trị đó thắng, kể cả `0` |

Các flag `--fine`, `--min-dur`, `--lh-max`, `--rh-max`, `--drop-ornaments`, `--simplify` (và các flag
MIDI khác như `--beats`, `--max-bpm`, `--voices`, `--no-tidy`, `--chord-end`, `--downbeat`) chỉ áp dụng
cho input MIDI. Khi input là MusicXML -> MusicXML, script in cảnh báo ra stderr và bỏ qua chúng; muốn
re-grid MusicXML bằng engine MIDI thì dùng `xml_regrid_piano.py`.

---

## Ví dụ sử dụng

```bash
# MusicXML: chạy mặc định
python normalize_piano_musicxml.py input.xml output.xml

# MusicXML: phân tay theo staff gốc, giữ tie
python normalize_piano_musicxml.py input.xml output.xml --hand staff --keep-ties

# MusicXML: phân tay theo pitch, ngưỡng D4
python normalize_piano_musicxml.py input.xml output.xml --hand pitch --split D4

# MusicXML: phân tay theo part, đảo tay
python normalize_piano_musicxml.py input.xml output.xml --hand part --swap-parts

# MIDI -> MIDI sạch
python normalize_piano_musicxml.py bai.mid bai_clean.mid

# MIDI -> MusicXML, ô nhịp 3/4
python normalize_piano_musicxml.py bai.mid bai_clean.xml --beats 3

# MIDI: đơn giản hóa hợp âm (LH tối đa 3 nốt, RH giữ giai điệu), bỏ nốt láy
python normalize_piano_musicxml.py bai.mid bai_clean.xml --simplify

# MIDI: giữ 16th/ornament (cho phép nửa ô lưới)
python normalize_piano_musicxml.py bai.mid bai_clean.xml --fine

# MIDI: bỏ nốt rác ngắn hơn 50 ms
python normalize_piano_musicxml.py bai.mid bai_clean.xml --min-dur 0.05

# Đổi channel và volume
python normalize_piano_musicxml.py input.xml output.xml --channel1 1 --channel2 2 --volume1 90 --volume2 70
```

---

## Hành vi chuẩn hóa chính

### 1. Output luôn có 2 part

`P1` = tay phải, `P2` = tay trái.

### 2. Phân tay

**MusicXML** (`--hand`). Mỗi event (một note hoặc một chord) được gán cho một tay:

- `pitch`: pitch thấp nhất < `--split` thì tay trái, không thì tay phải
- `staff`: `<staff>2` là tay trái, `<staff>1` là tay phải, không có staff thì theo part
- `part`: theo part; part có pitch trung bình cao hơn là tay phải (một part duy nhất là tay phải);
  `--swap-parts` đảo lại
- `auto` (mặc định): pitch thấp nhất < `--split` thì tay trái; không thì theo staff; không có staff thì theo part

Note ở staff tay phải nhưng quá trầm sẽ sang tay trái (với `auto`); muốn giữ đúng staff gốc thì dùng `--hand staff`.

**MIDI**. File có từ 2 track/channel có nốt thì dùng chúng (tên chứa "Right"/"Left" được ưu tiên, không thì
nhóm có pitch trung bình cao là tay phải). File 1 track thì script theo dõi vị trí hai tay: mỗi hợp âm cắt ở
chỗ rẻ nhất giữa "nốt thấp -> tay trái, nốt cao -> tay phải", tâm của mỗi tay đi theo các nốt vừa chơi, một tay
không giãn quá 14 bán cung. `--split` là điểm xuất phát của hai tâm. Trên bài thử, cách này khớp 98,5% với
`hand_split` của project (cắt cứng ở C4 chỉ khớp 94,3%). Vẫn có thể sai ở chỗ hai tay đan nhau.

### 3. Mỗi part chỉ còn 1 voice

Với MusicXML, mọi voice của một tay được gộp thành một chuỗi theo thời gian: các note bắt đầu cùng lúc (kể cả
khác voice) thành một hợp âm có độ dài lớn nhất, nốt đang ngân bị cắt khi note kế tiếp bắt đầu, khoảng trống
thành dấu nghỉ. Không bỏ note nào, nhưng nốt ngân dài bên dưới một giai điệu chạy bị cắt ngắn.

Với MIDI, mỗi tay là một chuỗi hợp âm không chồng nhau (hợp âm cùng độ dài), nốt ngân bị cắt tại hợp âm kế của tay đó.

### 4. Ô nhịp đúng độ dài, độ dài ghi được

- Độ dài đã là một giá trị nốt nhạc (có thể một chấm) thì giữ nguyên.
- Độ dài lạ (5, 10, 13 đơn vị...) được chia thành các nốt ghi được nối bằng tie (nghỉ thì chia thành nhiều nghỉ).
- Nốt đi qua vạch nhịp được cắt đôi và nối tie.
- Chord (`<chord/>`) luôn nằm cùng onset với note trước nó và không làm thời gian chạy tiếp.
- Ô nhịp lấy đà (`implicit="yes"` hoặc số 0) và ô nhịp ngắn khác được giữ đúng độ dài thật, không thêm nghỉ cho đủ.
- Đổi số chỉ nhịp, khóa, divisions giữa bài được ghi lại ở ô nhịp tương ứng.

### 5. Bước `tidy` của MIDI

MIDI chơi tay sau khi đặt lên lưới có thể vẫn khiến phần mềm chấm nhạc tách voice 2, thường ở chỗ một nốt dài
đứng trước một chuỗi nốt 32nd bắt đầu giữa hai ô lưới (ornament). `tidy` (bật mặc định) rút nốt dài đó về một giá
trị ghi được và kết thúc nó ở ranh giới ô lưới, phần chênh thành một nghỉ ngắn. Chỉ ảnh hưởng vài nốt mỗi bài.
Tắt bằng `--no-tidy`.

Mặc định engine còn không ghi nốt ngắn hơn **16th**: khi ô lưới là 16th hoặc ngắn hơn, mọi hợp âm và độ dài
nằm trên ô lưới nguyên, nên không còn 32nd vụn hay hợp âm bị tách. Khi ô lưới là 8th hoặc dài hơn thì nửa ô
vẫn là 16th trở lên, nên 16th/ornament được giữ. `--fine` cho phép nửa ô trong mọi trường hợp (hành vi cũ,
dùng khi muốn giữ nguyên 32nd).

### 6. Tempo

Không scale duration theo tempo. MusicXML: giữ tempo đầu tiên tìm thấy (ghi ở P1). MIDI: tempo tìm được từ
cách chơi, ghi ở đầu P1 (MusicXML) hoặc track Conductor (MIDI). Chỉ hỗ trợ một tempo cho cả bài.

### 7. Grace, tie, beam

- Grace note được giữ và gắn vào note chính kế tiếp (bỏ bằng `--drop-grace`).
- Tie của input mặc định bị bỏ. Với `--keep-ties`, tie chỉ được giữ khi độ dài nốt không đổi, và tie
  nào không còn cặp thì bị dọn để không có tie treo. Tie do script tạo ra (qua vạch nhịp, độ dài lạ) luôn có.
- Beam luôn do phần mềm chấm nhạc tự vẽ.

---

## Output tạo ra

File MusicXML partwise:

```xml
<part-list>
  <part-group type="start" number="1">
    <group-symbol>brace</group-symbol>
    <group-barline>yes</group-barline>
  </part-group>

  <score-part id="P1">
    <midi-instrument id="P1-I1">
      <midi-channel>1</midi-channel>
      <midi-program>1</midi-program>
    </midi-instrument>
  </score-part>

  <score-part id="P2">
    <midi-instrument id="P2-I1">
      <midi-channel>2</midi-channel>
      <midi-program>1</midi-program>
    </midi-instrument>
  </score-part>

  <part-group type="stop" number="1"/>
</part-list>

<part id="P1">...</part>
<part id="P2">...</part>
```

- mỗi measure trong từng part chỉ có `<voice>1</voice>`
- không có `<staff>` trong note vì mỗi part là một staff riêng
- MIDI output: 3 track (Conductor, Right hand ở channel 0, Left hand ở channel 1), pedal đi theo nốt

---

## Web UI (nghe thử)

`app.py` là một FastAPI nhỏ phục vụ `static/index.html`: upload file, xem bản sạch, nghe thử và tải về.

```bash
uv sync                                  # hoặc: pip install -r requirements-web.txt
uv run uvicorn app:app --reload          # hoặc: python -m uvicorn app:app --reload
# mở http://127.0.0.1:8000/
```

Trang làm được:

- upload `.mid`/`.midi`/`.xml`/`.musicxml`/`.mxl`, chỉnh các flag thật của CLI (beats, split, hand,
  downbeat, max bpm, `--fine`, `--min-dur`, `--lh-max`, `--rh-max`, `--drop-ornaments`, `--simplify`)
- chọn file MusicXML là bản gốc hiện ngay trên khuông nhạc (OpenSheetMusicDisplay), nghe thử được; bấm Normalize thì khuông đó được thay bằng bản sạch. MIDI không có bản nhạc để vẽ nên chỉ hiện sau khi Normalize
- Play/Pause/Stop bằng Web Audio + soundfont (`acoustic_grand_piano`), cursor chạy theo MIDI
- tải `clean.xml` / `clean.mid`, copy câu lệnh CLI đúng với loại input
- xem report/stats và tempo/key tìm được

Soundfont và các thư viện render được tải từ CDN, nên **cần internet** cho phần nghe thử. Không có mạng
thì trang vẫn normalize và tải file được, chỉ không có tiếng. Đây là công cụ nghe thử, không phải trình
soạn nhạc: chưa có loop, click-to-play, hay chọn đoạn.

---

## `xml_regrid_piano.py` (MusicXML -> engine re-grid)

Script phụ đưa MusicXML qua chính engine MIDI để làm sạch lưới, thay vì chỉ gộp voice như đường
MusicXML -> MusicXML.

```bash
python xml_regrid_piano.py ban_goc.xml ban_sach.xml
python xml_regrid_piano.py ban_goc.xml ban_sach.xml --simplify
```

Cách hoạt động: đọc nốt theo đơn vị phách đen (1 phách đen = 1 "giây" của engine), gọi engine với
`--max-bpm 90` để engine chọn đúng 1 beat = 1 phách đen, rồi ghi lại MusicXML. Vì vậy `--min-dur` ở
script này tính bằng **phách đen**, không phải giây. `--key` và `--tempo-mark` mặc định lấy từ file
input (nếu có), có thể ép bằng flag.

---

## Dùng như thư viện

```python
import normalize_piano_musicxml as N
clean = N.normalize(notes, controls=..., beats_per_bar=4)    # notes có .hand "R"/"L"
N.write_midi("out.mid", clean, fingers={id(note): "R3"})     # fingers tùy chọn: nhãn ngón thành text event
N.write_musicxml("out.xml", clean, key_fifths=0)
clean2, pairs = N.revoice(clean)                             # voice lại sau khi sửa nốt (đổi tay...)
```

Trong project có `midi_loader`: `N.clean_song(song)` trả về `MidiSong` đã chuẩn hóa.

---

## Giới hạn

Script ưu tiên **làm sạch và đơn giản hóa**, không bảo tồn mọi chi tiết engraving.

Có thể mất hoặc đổi:

- độ ngân của nốt dài bị cắt khi note kế tiếp của cùng tay bắt đầu
- tie/beam của input (xem mục 7), tuplet (độ dài tuplet không chia đúng được sẽ ghi gần đúng)
- dynamics, pedal, text, articulations, directions phức tạp, đổi khóa giữa bài (output luôn Sol/Fa). Lyrics thì được giữ ở nốt đầu của mỗi hợp âm (mất nếu nốt đó bị bỏ bởi `--simplify`/`--rh-max`/`--drop-ornaments`)
- tempo thứ hai trở đi
- MIDI: tuplet không được nhận ra (lưới chia đều), cần numpy
- MIDI: mặc định không ghi nốt ngắn hơn 16th (32nd vụn bị gộp/lên ô); dùng `--fine` để giữ
- `--simplify` / `--rh-max` giữ nốt cao nhất làm giai điệu: có thể mất nốt giữa của hợp âm
- MusicXML output từ MIDI chưa có pedal và nhãn ngón (chỉ có trong output `.mid`)
- flag MIDI-only bị bỏ qua (kèm cảnh báo) ở đường MusicXML -> MusicXML
- web UI cần internet cho soundfont; chưa có loop/click-to-play

Chưa hỗ trợ: `.mxl` đầu ra, MusicXML -> MIDI, `score-timewise`.

---

## Cấu trúc project

```text
musicxml-piano-normalizer/
├── normalize_piano_musicxml.py   # script chính (MIDI + MusicXML)
├── xml_regrid_piano.py           # MusicXML -> engine MIDI re-grid
├── app.py                        # FastAPI cho web UI
├── static/
│   └── index.html                # UI: render + nghe thử + tải file
├── requirements.txt              # numpy (CLI)
├── requirements-web.txt          # fastapi, uvicorn, python-multipart, numpy
├── pyproject.toml                # metadata + dependency groups (uv)
├── uv.lock
├── test_normalize.py             # pytest
├── Makefile
├── .gitignore
├── CHANGELOG.md
├── README.md
├── AGENTS.md
├── tests/
│   └── check_output.py
├── samples/
│   ├── Luu_Nien_messy.mid        # MIDI chơi tay, có 32nd vụn
│   ├── Luu_Nien_messy.musicxml
│   ├── Luu_Nien_messy_clean.mid
│   └── piano_messy.xml           # mẫu nhỏ: chord, grace, tie, pickup, đổi nhịp, nhiều voice
└── output/
```

---

## Khắc phục sự cố

### Phân tay chưa đúng

- MusicXML: thử `--hand staff`, `--hand part`, hoặc `--hand pitch --split D4`; tay bị ngược thì thêm `--swap-parts`.
- MIDI 1 track: chỉnh `--split` (điểm xuất phát), hoặc đưa file 2 track "Right hand"/"Left hand".
  Trong project có `midi_loader` thì để `--reader auto` để dùng `hand_split` của project.

### Phần mềm chấm nhạc vẫn hiện nhiều voice (MIDI)

Đảm bảo không dùng `--no-tidy` và `--voices single`. Nếu vẫn còn, xuất sang `.xml` thay vì `.mid`: MusicXML ghi rõ
voice nên không bị phần mềm đoán lại.

### Bị mất note (MusicXML)

Nốt ngân bị cắt khi note kế tiếp của cùng tay bắt đầu; note trùng pitch cùng onset bị gộp. Thử `--hand staff`
nếu note bị đưa sang tay không mong muốn.

### Lỗi "engine MIDI cần numpy"

`pip install numpy` (hoặc `pip install -r requirements.txt`).

---

## Lịch sử thay đổi

Xem `CHANGELOG.md`. Khi thay đổi hành vi, CLI, output hoặc test, cập nhật `CHANGELOG.md`, `README.md`, và
`AGENTS.md` (nếu ảnh hưởng kiến trúc, test hoặc quy tắc cho AI/dev).

---

## Ghi chú

Nếu phát triển thêm, hãy đọc `AGENTS.md` trước: kiến trúc, quy ước sửa code, điểm dễ lỗi, checklist test và quy
tắc cập nhật tài liệu.
