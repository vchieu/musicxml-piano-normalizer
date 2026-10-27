# AGENTS.md

Tài liệu dành cho AI agent hoặc developer khi đọc, sửa, mở rộng source `normalize_piano_musicxml.py`.

> Quy tắc quan trọng nhất:
>
> **Mọi thay đổi code làm ảnh hưởng hành vi, CLI, output, giới hạn hoặc ví dụ đều phải cập nhật tài liệu tương ứng trong `README.md` và `AGENTS.md`.**
>
> Nếu chưa cập nhật tài liệu, thay đổi chưa được xem là hoàn thành.

---

## 1. Tổng quan project

Project này chuẩn hóa piano về dạng "sạch": 2 tay, mỗi tay đúng 1 voice, ô nhịp đúng độ dài.
Một file duy nhất nhận cả MIDI lẫn MusicXML:

| input | output | đường xử lý |
|---|---|---|
| `.mid` / `.midi` | `.mid` | engine MIDI: tìm lưới + tempo, quantize, 1 voice mỗi tay (`normalize()` + `write_midi()`) |
| `.mid` / `.midi` | `.xml` | engine MIDI như trên, rồi `write_musicxml()` (P1 phải, P2 trái, voice 1, tie khi cần) |
| `.xml` / `.musicxml` / `.mxl` | `.xml` | đường MusicXML cũ (`run_musicxml()`): 2 part, mỗi part voice 1 |
| `.xml` | `.mid` | CHƯA hỗ trợ (báo lỗi) |
| bất kỳ | `.mxl` | CHƯA hỗ trợ (báo lỗi); `.mxl` chỉ đọc được làm input |

Output MusicXML (cả hai đường):

- 2 part: `P1` tay phải, `P2` tay trái
- mỗi part chỉ có 1 voice: `<voice>1</voice>`
- mỗi part có 1 MIDI channel riêng

Runtime:

- Đường MusicXML: chỉ thư viện chuẩn Python, đọc/ghi MusicXML partwise, không xử lý `.mxl` nén.
- Engine MIDI: cần **numpy** (`requirements.txt`; import tùy chọn: thiếu numpy thì chỉ đường MIDI báo lỗi,
  đường MusicXML vẫn chạy).
- Chạy độc lập được. `midi_loader` của project là tùy chọn: `--reader auto` dùng `midi_loader.load_song` nếu
  import được (lấy hand từ `hand_split` của project), không thì dùng reader có sẵn trong file.

---

## 2. Cấu trúc file

```text
musicxml-piano-normalizer/
├── normalize_piano_musicxml.py   # script chính (MIDI + MusicXML)
├── requirements.txt              # numpy (chỉ cho MIDI)
├── test_normalize.py             # pytest: engine MIDI, writer MIDI/MusicXML, đường MusicXML
├── Makefile                      # chạy output/test nhanh
├── .gitignore                    # bỏ qua output/cache
├── CHANGELOG.md                  # lịch sử thay đổi
├── README.md                     # tài liệu người dùng
├── AGENTS.md                     # tài liệu cho AI/dev
├── tests/
│   └── check_output.py           # test cấu trúc output MusicXML
├── samples/                      # file mẫu
│   ├── input_tempo180.xml
│   ├── reference_tempo90.xml
│   └── piano_messy.xml           # chord, grace, tie, pickup, đổi nhịp, nhiều voice/staff
└── output/                       # kết quả sinh ra khi chạy
```

Khi đọc source để sửa, AI/dev nên đọc theo thứ tự:

1. `AGENTS.md`
2. `README.md`
3. `normalize_piano_musicxml.py`
4. `test_normalize.py`, `tests/check_output.py`
5. `CHANGELOG.md`

`normalize.py` cũ đã được gộp vào `normalize_piano_musicxml.py`. Code project khác đang `import normalize`
phải đổi thành `import normalize_piano_musicxml as normalize` (API `normalize`, `write_midi`, `clean_song`,
`Clean` giữ nguyên).

---

## 3. File nguồn chính

### `normalize_piano_musicxml.py`

Đây là file duy nhất chứa logic chính. Không tách file nếu chưa thật sự cần thiết. Thứ tự trong file:

1. `Note`, import (numpy tùy chọn)
2. Engine MIDI: `find_cell`, `_snap`, `_downbeat`, `_tidy_len`, `_voice`, `normalize`, `write_midi`, `clean_song`
3. Reader MIDI: `_chunks`, `_events`, `split_hands`, `read_midi`, `estimate_key`, `load_midi_input`
4. Helper MusicXML: `strip_namespaces`, `parse_measure`, `duration_type_and_dots`, `make_rest`, ...
5. Ghi MusicXML dùng chung: `split_duration`, `spell`, `make_note_from_orig`, `make_grace_note`, `append_sequence_to_measure`
6. MusicXML -> MusicXML: `build_sequence`, `build_part_hand_map`, `assign_hand`, `sanitize_ties`, `load_musicxml_root`, `run_musicxml`
7. Writer MIDI -> MusicXML: `clean_to_sequences`, `write_musicxml`
8. CLI: `run_midi`, `build_parser`, `main`

---

## 4. Dữ liệu mẫu quan trọng

### `samples/input_tempo180.xml`

Đặc điểm:

- 1 part `P1`
- 2 staff
- 1 MIDI channel
- có nhiều voice:
  - voice 1
  - voice 2
  - voice 5
  - voice 6
- có clef change giữa bài
- có note nằm ở staff tay phải nhưng pitch trầm (`samples/piano_messy.xml` có cả hai ca này)
- có note nằm ở staff tay trái nhưng pitch cao

Dùng để test:

- tách 1 part 2 staff thành 2 part
- gộp mọi voice của một tay thành một chuỗi (không chọn "voice chính")
- chord (`<chord/>`) không làm thời gian chạy tiếp
- phân tay theo staff/pitch
- xử lý rest
- xử lý clef change

---

### `samples/reference_tempo90.xml`

Đặc điểm:

- 2 part:
  - `P1`
  - `P2`
- 2 MIDI channel:
  - channel 1
  - channel 2
- mỗi part có voice 1
- có grace note
- có tie
- có beam
- có part-group brace

Dùng để test:

- input đã có 2 part
- giữ channel riêng
- giữ tempo
- xử lý grace note
- tie: bỏ mặc định, `--keep-ties` giữ cặp nguyên vẹn (`--keep-beams` không còn tác dụng)

---

## 5. Output contract hiện tại

Output phải có dạng:

```xml
<score-partwise version="4.0">
  <part-list>
    <part-group type="start" number="1">
      <group-symbol>brace</group-symbol>
      <group-barline>yes</group-barline>
    </part-group>

    <score-part id="P1">...</score-part>
    <score-part id="P2">...</score-part>

    <part-group type="stop" number="1"/>
  </part-list>

  <part id="P1">...</part>
  <part id="P2">...</part>
</score-partwise>
```

Mặc định:

- `P1`: tay phải
- `P2`: tay trái
- `P1`: MIDI channel 1
- `P2`: MIDI channel 2
- mỗi measure trong `P1` và `P2` dùng `<voice>1</voice>`
- note không có `<staff>`
- note không có `<instrument>`
- clef mặc định:
  - `P1`: G clef line 2
  - `P2`: F clef line 4

---

## 6. Luồng xử lý chính

```text
main()
  ├── parse args, nhận dạng đuôi input/output
  ├── input MIDI  -> run_midi()
  │     ├── load_midi_input()   # midi_loader (auto) hoặc read_midi()
  │     ├── normalize()         # lưới, tempo, ô nhịp, 1 voice mỗi tay, tidy
  │     ├── key: từ file, không có thì estimate_key()
  │     └── write_midi()  hoặc  write_musicxml()
  └── input XML   -> run_musicxml()
        ├── parse XML, strip_namespaces()
        ├── với mỗi measure: parse_measure() mỗi part, tách tay theo --threshold
        ├── build_sequence() cho từng tay (rest, cắt note vào onset kế)
        └── append_sequence_to_measure() ghi P1/P2, voice 1
```

---

## 7. Các hàm quan trọng

### Engine MIDI

- `normalize(notes, controls, beats_per_bar, max_bpm, voices, chord_end, downbeat, tidy)` -> `Clean`.
  Notes phải có `.hand` ("R"/"L"). Trả về note trên đồng hồ mới (giây, bội của `clean.unit` = nửa ô lưới).
- `find_cell`: tìm chu kỳ ô lưới bằng comb filter (numpy). Cần >= vài chục onset.
- `_snap`: đặt hợp âm lên lưới, bám tempo trôi; hợp âm lệch nhiều thì thử nửa ô (ornament, "fine").
- `_voice`: mỗi tay thành chuỗi hợp âm không chồng; hợp âm cùng độ dài; `voices="single"` cắt nốt ngân.
- `_tidy_len(u, e)` (bước `tidy`, mặc định bật): nốt dài >= 4 đơn vị không kết thúc ở đơn vị lẻ; độ dài hạ về
  giá trị ghi được `STD_LEN`; phần chênh thành nghỉ ngắn. Lý do: phần mềm chấm nhạc làm tròn kết thúc nốt dài
  rồi tách nó sang voice 2 khi một chuỗi 32nd bắt đầu giữa ô lưới. Tắt bằng `--no-tidy`.
- `write_midi`: 3 track (conductor, Right hand, Left hand), pedal đi theo nốt.

### Reader MIDI

- `read_midi(path, threshold)`: stdlib. Phân tay: >= 2 track/channel có nốt thì theo tên "Right"/"Left",
  không thì nhóm có pitch trung bình cao là tay phải; 1 nhóm thì gọi `split_hands`.
- `split_hands(notes, split, span=14, tol=0.04, follow=0.15)`: theo dõi vị trí hai tay. Mỗi hợp âm cắt ở chỗ
  rẻ nhất (giá = khoảng cách tới tâm tay + phạt giãn quá `span`), tâm đi theo nốt vừa chơi. Trên bài Lưu Niên khớp
  98,5% với `hand_split` của project (cắt cứng ở C4: 94,3%). Sửa heuristic này phải đo lại trên file thật.
- `estimate_key`: số dấu hóa có nhiều thời lượng nốt nhất nằm trong gam; chỉ dùng khi file không có key.

### Đường MusicXML

- `parse_measure`: đọc 1 measure thành `Event`. `<chord/>` nằm cùng onset với note trước và KHÔNG làm thời gian
  chạy tiếp (lỗi cũ: chord làm lệch cả bài, có test). Grace note gắn vào note chính kế tiếp cùng voice.
  Bỏ rest, note không pitch. `state["measure_end"]` là điểm cuối thật của measure (cho ô nhịp lấy đà).
- `assign_hand(ev, mode, split, part_hand)`: `pitch` / `staff` / `part` / `auto` (xem README). `auto`: pitch thấp
  nhất < split -> trái; không thì staff 2 -> trái, staff 1 -> phải; không có staff -> theo part.
  `build_part_hand_map`: part có pitch trung bình cao hơn là tay phải; một part -> tay phải.
- `build_sequence`: gộp mọi event cùng onset (mọi voice) thành hợp âm (độ dài lớn nhất, bị chặn bởi onset kế),
  cắt nốt ngân tại onset kế, thêm rest, giữ grace của event đầu. KHÔNG chọn "voice chính": mọi voice được gộp.
- `run_musicxml`: đọc hết measure trước (để có pitch trung bình mỗi part), rồi phân tay, dựng chuỗi, ghi P1/P2.
  Ô nhịp `implicit="yes"`/số 0 ngắn hơn nominal giữ độ dài thật. Đổi time/key/divisions giữa bài được ghi lại.
- `sanitize_ties(part)`: bỏ tie treo (start không có note cùng pitch nối ngay sau, stop không có note trước).
  Luôn chạy sau khi ghi.

### Ghi MusicXML (dùng chung hai đường)

- `split_duration(pos, dur, divisions)`: độ dài đã là giá trị ghi được (có thể 1 chấm) thì giữ nguyên;
  không thì chia thành các nốt ghi được (lấp tới phách trước, rồi nốt lớn), nối bằng tie. Trả `None` nếu
  không chia đúng (tuplet...) -> dùng nốt gần nhất như bản cũ.
- `make_grace_note`: grace, [chord], pitch, voice 1, type, accidental (không có duration).
- `make_note_from_orig(orig_note, ..., midi=None, ...)`: `orig_note` có (đường MusicXML) thì copy pitch/accidental;
  `orig_note=None` (đường MIDI) thì dựng pitch từ `midi` (`spell`) và chỉ ghi `<accidental>` khi khác khóa
  / khác nốt trước trong ô nhịp. Thứ tự phần tử: chord, pitch, duration, tie, voice, type, dot, accidental, notations.
- `append_sequence_to_measure(..., fifths=None, keep_ties=False, no_fill_rests=False)`: `fifths` khác None = đường
  MIDI. Rest dài lạ được chia nhiều rest. `keep_ties`: giữ tie input khi độ dài không đổi. `no_fill_rests`: dùng
  `<forward>` thay rest.
- `clean_to_sequences`, `write_musicxml`: `Clean` -> 2 part; nốt qua vạch nhịp cắt đôi và nối tie;
  `divisions = units_per_beat`; tempo ghi bằng `<direction>` ở measure đầu P1; pickup là rest đầu measure 1.

---

## 8. CLI hiện tại

```text
input                  .mid/.midi/.xml/.musicxml/.mxl
output                 (tùy chọn; mặc định <input>_clean.mid hoặc _clean.xml)
--hand {auto,staff,pitch,part}   (MusicXML) mặc định auto
--split / --threshold  mặc định C4 (--threshold là tên cũ). MusicXML: pitch thấp nhất < split là tay trái.
                       MIDI 1 track: điểm xuất phát của split_hands
--split-chords         (MusicXML, auto/pitch) tách từng note của chord
--swap-parts           (MusicXML)
--keep-ties            (MusicXML) giữ tie input khi độ dài nốt không đổi
--keep-beams           không còn tác dụng, chỉ nhận để không vỡ lệnh cũ (in cảnh báo)
--drop-grace           (MusicXML)
--no-fill-rests        (MusicXML) dùng <forward> thay rest
--channel1 --channel2 --program --volume1 --volume2 --no-brace --no-final-barline
--reader {auto,loader,builtin}   (MIDI)
--beats N                        (MIDI) số phách mỗi ô nhịp, mặc định 4
--max-bpm X                      (MIDI)
--voices {single,keep}           (MIDI; keep chỉ khi xuất .mid)
--no-tidy                        (MIDI)
--chord-end {median,max,min}     (MIDI)
--downbeat {auto,first}          (MIDI)
```

Tie/beam của input: tie bỏ mặc định (xem `--keep-ties`), beam luôn bỏ, rest luôn được thêm (trừ `--no-fill-rests`).
Không có `--reduce`, `--hand-from` hay chọn "voice chính".

Khi thêm option mới:

1. thêm vào `build_parser`
2. giữ giá trị mặc định tương thích ngược
3. cập nhật bảng option trong `README.md`
4. cập nhật phần CLI trong `AGENTS.md`
5. thêm ví dụ nếu cần
6. test với file mẫu

---

## 9. Quy ước sửa code

### Giữ tương thích ngược

Không được thay đổi hành vi mặc định một cách phá vỡ nếu chưa có lý do rõ ràng.

Nếu thay đổi mặc định:

- phải ghi rõ trong README
- phải có test so sánh
- phải cảnh báo mất dữ liệu nếu có

---

### Ưu tiên an toàn

Nếu không chắc có nên giữ một element hay không:

- với tie/beam: mặc định xóa là an toàn
- với grace: mặc định giữ nếu có thể
- với directions phức tạp: không vội copy nếu chưa hiểu
- với note: không xóa nếu chưa xác định chồng voice

---

### Không phá XML hợp lệ

Sau khi sửa, output tối thiểu phải:

- là XML well-formed
- có root hợp lệ
- có part-list
- có part tương ứng

---

### Không thêm dependency nếu không cần

Ưu tiên standard library.

Nếu cần thêm thư viện:

- phải giải thích
- phải cập nhật tài liệu
- phải đảm bảo user dễ cài

---

## Testing bắt buộc

Mọi thay đổi ảnh hưởng đến output đều phải chạy test.

Chạy test (pytest + numpy):

```bash
pytest test_normalize.py
python normalize_piano_musicxml.py samples/input_tempo180.xml output/test_output.xml
python tests/check_output.py output/test_output.xml --channels 1,2 --min-notes 1
```

`tests/check_output.py` kiểm tra cấu trúc output MusicXML, độ dài từng measure (implicit chỉ cần không dài quá),
không có `<backup>`, tie không treo (`--no-timing` để bỏ). Chạy nó trên output của cả đường MIDI và MusicXML.

`test_normalize.py` kiểm tra thêm: engine MIDI (lưới, tempo, ô nhịp, pickup, 1 voice mỗi tay, tidy),
writer MIDI, round-trip MIDI -> MusicXML (từng nốt khớp sau khi nối tie, mỗi ô nhịp đủ độ dài, chỉ voice 1),
`split_duration`, đường MusicXML -> MusicXML (`samples/piano_messy.xml`: chord không đẩy thời gian, các chế độ
`--hand`, grace, ô nhịp lấy đà, đổi nhịp, `--keep-ties`, `--no-fill-rests`, `.mxl`), `split_hands`, `sanitize_ties`, CLI. Máy không có pytest thì test bằng tay các lệnh trên.

Test hiện tại kiểm tra:

- root là `<score-partwise>`
- có đúng 2 `<score-part>`
- có đúng 2 `<part>`
- mỗi `<score-part>` có đúng 1 `<midi-instrument>`
- có đúng 2 MIDI channel, mặc định là 1 và 2
- mỗi part chỉ dùng `<voice>1</voice>`
- tổng số note/rest đạt ngưỡng tối thiểu nếu dùng `--min-notes`

Nếu thay đổi output contract, ví dụ:

- từ 2 part sang 1 part có 2 staff
- từ 2 channel sang 1 channel
- từ voice 1 sang voice 1 + voice 2
- thêm/bớt `<staff>`
- thay đổi cách đặt `<midi-channel>`

thì bắt buộc phải sửa `tests/check_output.py` cho phù hợp.

---

## 11. Acceptance checklist

Sau khi sửa code, output phải thỏa mãn các điều kiện tối thiểu:

### Cấu trúc

- [ ] root là `<score-partwise>`
- [ ] có đúng 2 `<score-part>`: `P1`, `P2`
- [ ] có `<part id="P1">` và `<part id="P2">`
- [ ] nếu không dùng `--no-brace`, có part-group brace

### Voice

- [ ] mỗi part chỉ dùng `<voice>1</voice>`
- [ ] không còn voice 2, 5, 6 trong output
- [ ] không còn voice chồng gây rối trong cùng part

### Channel

- [ ] `P1` có MIDI channel riêng
- [ ] `P2` có MIDI channel riêng
- [ ] mặc định:
  - [ ] P1 channel 1
  - [ ] P2 channel 2

### Timing

- [ ] tổng duration trong mỗi measure hợp lý
- [ ] không bị thiếu duration nghiêm trọng
- [ ] không bị dư note overlap
- [ ] nếu không dùng `--no-fill-rests`, rest được thêm hợp lý

### Nhạc

- [ ] tay phải chủ yếu là melody/note cao
- [ ] tay trái chủ yếu là bass/chord/note trầm
- [ ] tempo không bị thay đổi tùy tiện
- [ ] không tự scale duration theo tempo

### Khả năng mở

- [ ] file output mở được trong MuseScore hoặc phần mềm MusicXML
- [ ] không lỗi XML nghiêm trọng
- [ ] không crash khi chạy lại

---

## 12. Những điểm dễ lỗi khi sửa code

### 1. Namespace

Nếu XML có namespace, `find("note")` sẽ không hoạt động.

Phải strip namespace trước.

---

### 2. Chord note

Note có `<chord/>` không được tăng thời gian.

Nếu xử lý sai:

- duration bị dư
- timing bị lệch
- note bị lặp

---

### 3. Grace note

Grace note thường không có duration.

Nếu thêm grace vào timeline như note thường:

- offset sai
- measure duration sai
- có thể tạo event duration 0

---

### 4. Backup / forward

`<backup>` làm lùi thời gian.

Nếu bỏ qua:

- voice chồng sẽ bị parse thành sequential
- timing sai hoàn toàn

---

### 5. Measure duration

Nếu không tính đúng:

- rest fill sai
- note bị truncate
- measure quá dài/ngắn

---

### 6. Voice selection

Nếu chọn sai primary voice:

- mất melody
- mất bass
- giữ nhầm voice phụ

---

### 7. Xóa tie/beam

Nếu giữ tie/beam sau khi bỏ note:

- tie có thể dangling
- beam có thể gãy
- hiển thị xấu hoặc lỗi

Vì vậy mặc định xóa tie/beam là an toàn hơn.

---

### 8. Thứ tự phần tử MusicXML

MusicXML khá nhạy về thứ tự element trong `<note>`.

Không nên thêm element tùy tiện.

Ví dụ:

- `<duration>` thường nằm sau pitch/rest/chord
- `<voice>` thường nằm sau duration
- `<chord/>` nằm trước pitch/rest trong note chord

---

## 13. Quy tắc cập nhật tài liệu — BẮT BUỘC

Đây là phần quan trọng nhất.

### Nguyên tắc

Bất kỳ thay đổi nào sau đây đều phải cập nhật tài liệu:

1. thêm option CLI
2. sửa option CLI
3. xóa option CLI
4. đổi giá trị mặc định
5. đổi hành vi phân tay
6. đổi hành vi chọn voice
7. đổi output MusicXML
8. đổi xử lý tie/beam/grace
9. đổi xử lý rest
10. đổi xử lý tempo
11. thêm giới hạn mới
12. sửa bug có ảnh hưởng hành vi
13. thêm dependency
14. đổi yêu cầu Python
15. đổi cấu trúc project

Nếu không cập nhật tài liệu tương ứng, task được xem là **chưa hoàn thành**.

---

## 14. Mapping cập nhật tài liệu

| Thay đổi code | Tài liệu phải cập nhật |
|---|---|
| Thêm/sửa CLI flag | `README.md` phần Options, ví dụ; `AGENTS.md` phần CLI |
| Đổi hành vi phân tay | `README.md` phần Hành vi / Giới hạn; `AGENTS.md` phần `assign_hand` |
| Đổi cách gộp voice của một tay | `README.md` phần Hành vi mục 3; `AGENTS.md` phần `build_sequence` |
| Đổi output part/channel | `README.md` phần Output; `AGENTS.md` phần Output contract |
| Thêm phụ thuộc | `README.md` phần Yêu cầu; `AGENTS.md` phần Runtime |
| Sửa bug timing | thêm test case trong `AGENTS.md`; cập nhật Known issues nếu cần |
| Thêm giới hạn | `README.md` phần Giới hạn; `AGENTS.md` phần Known limitations |
| Thêm chế độ mới | thêm ví dụ trong `README.md`; thêm architecture note trong `AGENTS.md` |
| Thêm/sửa target trong `Makefile` | `README.md` phần Kiểm tra tự động; `AGENTS.md` phần Testing bắt buộc |
| Thay đổi `tests/check_output.py` | `README.md` phần Kiểm tra tự động; `AGENTS.md` phần Testing bắt buộc |
| Thay đổi output contract làm test cũ không còn đúng | `tests/check_output.py`, `README.md`, `AGENTS.md` |
| Thêm file mới vào project | `README.md` phần Cấu trúc project; `AGENTS.md` phần Cấu trúc file |
| Thay đổi hành vi người dùng | `CHANGELOG.md`, `README.md`, `AGENTS.md` nếu ảnh hưởng kiến trúc |
| Thêm dependency hoặc công cụ dev | `README.md` phần Yêu cầu; `AGENTS.md` phần Runtime/Testing |
| Chuẩn bị release | `CHANGELOG.md`, version nếu có, `README.md` nếu có thay đổi cách dùng |

---

## Definition of Done

Một thay đổi chỉ được xem là hoàn thành khi:

- [ ] code chạy được
- [ ] không crash với 2 file mẫu
- [ ] output thỏa mãn acceptance checklist
- [ ] đã chạy `make test` hoặc test tương đương
- [ ] nếu đổi output contract, đã sửa `tests/check_output.py`
- [ ] đã cập nhật `README.md` nếu thay đổi liên quan đến người dùng
- [ ] đã cập nhật `AGENTS.md` nếu thay đổi liên quan đến kiến trúc, test, quy tắc AI/dev
- [ ] đã cập nhật `CHANGELOG.md` cho thay đổi đáng chú ý

---

## 16. Mẫu ghi chú khi thay đổi

Khi sửa code, nên ghi chú theo format:

```text
Change:
- mô tả thay đổi

Reason:
- vì sao cần thay đổi

Behavior impact:
- ảnh hưởng gì đến output

Docs updated:
- README.md section nào
- AGENTS.md section nào

Tested with:
- samples/input_tempo180.xml
- samples/reference_tempo90.xml
```

---

## 17. Các hướng mở rộng có thể làm trong tương lai

Nếu được yêu cầu mở rộng, có thể cân nhắc:

### Thêm chế độ output 1 part 2 staff

Hiện tại output là 2 part. Có thể thêm option:

```bash
--output-mode two_parts
--output-mode one_part_two_staves
```

Nếu làm:

- phải định nghĩa voice:
  - staff 1 voice 1
  - staff 2 voice 2
- phải xử lý `<backup>`/`<forward>`
- phải cập nhật README và AGENTS

---

### Thêm chế độ giữ dynamics

Hiện tại script không copy đầy đủ directions.

Nếu thêm:

- cần lọc direction theo staff/part
- cần xử lý `<voice>` trong direction
- cần cập nhật tài liệu

---

### Thêm chế độ debug

Có thể thêm:

```bash
--debug
```

để in ra:

- number of measures
- voices found per hand
- primary voice
- number of dropped events
- warnings

Nếu thêm, phải cập nhật CLI docs.

---

### Cải thiện heuristic phân tay

Có thể thêm:

- ngưỡng split khác nhau cho tay trái/tay phải
- phát hiện bass pattern
- phát hiện chord pattern
- ưu tiên giữ staff gốc nhiều hơn
- phát hiện melody voice theo contour

Mọi heuristic mới phải có test với file mẫu.

---

## 18. Known limitations hiện tại

- Mọi voice của một tay được gộp thành một chuỗi: nốt ngân dài dưới giai điệu chạy bị cắt tại onset kế.
  Note trùng pitch cùng onset được gộp.
- Engine MIDI cắt nốt ngân khi tay đó có hợp âm kế; `tidy` rút ngắn vài nốt và để lại nghỉ ngắn.
- Tie input bỏ mặc định; `--keep-ties` chỉ giữ cặp nguyên vẹn. Beam, dynamics, pedal (MusicXML), lyrics bị bỏ.
- Tuplet: độ dài không chia đúng thì ghi nốt gần nhất (MusicXML); engine MIDI chia lưới đều, không nhận tuplet.
- Phân tay MusicXML `auto` đưa note trầm ở staff tay phải sang tay trái; staff chéo (cross-staff) không được nhận ra.
- `split_hands` cho MIDI 1 track chỉ dựa vào vị trí/pitch; hai tay đan nhau có thể sai.
- Một tempo cho cả bài (MusicXML: tempo đầu tiên; MIDI: tempo tìm được). Output luôn khóa Sol/Fa.
- Engine MIDI cần numpy và giả định phách đen (x/4).
- Chưa thử mở output bằng MuseScore trong môi trường phát triển; cần kiểm tra bằng mắt ô nhịp có nốt ngân + ornament.
- Chưa validate DTD nghiêm ngặt, chưa ghi `.mxl`, chưa hỗ trợ MusicXML -> MIDI và `score-timewise`.
- Chưa có chế độ output 1 part 2 staff.

---

## 19. Checklist nhanh trước khi commit

Trước khi commit hoặc bàn giao:

- [ ] đã chạy thử với `samples/input_tempo180.xml`
- [ ] đã chạy thử với `samples/reference_tempo90.xml`
- [ ] output không còn nhiều voice trong mỗi part
- [ ] output có 2 part P1/P2
- [ ] output có channel đúng
- [ ] không làm thay đổi tempo ngoài ý muốn
- [ ] đã cập nhật `README.md`
- [ ] đã cập nhật `AGENTS.md`