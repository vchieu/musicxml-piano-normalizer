# Changelog

Tài liệu này ghi lại các thay đổi quan trọng của project.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- MIDI: `--fine` (cho phép nửa ô lưới), `--min-dur SEC` (bỏ nốt rác), `--lh-max N` / `--rh-max N`
  (giới hạn số nốt mỗi hợp âm; tay trái giữ bass, tay phải giữ giai điệu), `--drop-ornaments` (bỏ nốt láy),
  `--simplify` (preset `--lh-max 3 --rh-max 1 --drop-ornaments`). Giá trị `--lh-max`/`--rh-max` ghi rõ
  (kể cả `0`) thắng preset.
- `xml_regrid_piano.py`: đưa MusicXML qua engine MIDI để re-grid (nốt tính bằng phách đen, `--max-bpm 90`
  làm 1 beat = 1 phách đen); `read_score_meta` lấy key/tempo từ input.
- `app.py` + `static/index.html`: web UI upload MIDI/MusicXML, render bản sạch bằng OSMD, phát bằng
  Web Audio + soundfont, cursor theo MIDI, tải `.xml`/`.mid`, copy câu lệnh CLI, hiện bản gốc khi input là
  MusicXML.
- `pyproject.toml`, `uv.lock`, `requirements-web.txt` (fastapi, uvicorn, python-multipart, numpy).
- Test mới: luật 16th floor, `--fine`, `--lh-max`/`--rh-max`, `--min-dur`, `--drop-ornaments`, preset
  `--simplify`, `revoice(fine=...)`, cảnh báo flag MIDI-only, endpoint `app.normalize`, `xml_regrid_piano.py`.
- `Makefile`: target `web`; `make test` chạy pytest + `check_output`; input mẫu mới.
- `normalize_piano_musicxml.py` nhận thêm input MIDI (`.mid`/`.midi`) và xuất `.mid` hoặc `.xml`: engine MIDI
  (từ `normalize.py` cũ, đã gộp vào) tìm lưới và tempo từ cách chơi, đặt nốt lên lưới chính xác, tìm ô nhịp và nốt
  lấy đà, mỗi tay một voice. Cần `numpy` (chỉ cho MIDI), thêm `requirements.txt`.
- Port từ `normalize.py` mới: `revoice(clean, ...)` (voice lại sau khi sửa nốt trên đồng hồ sạch, ví dụ đổi tay,
  trả về `(Clean, [(nốt cũ, nốt mới)])`); `write_midi(..., fingers={id(note): "R3"})` ghi nhãn ngón tay thành
  text event ngay trước nốt (định dạng `midi_loader.read_markers` đọc); `write_midi` báo lỗi nếu `units_per_beat`
  không chia hết PPQ; `clean_song` gắn `out.normalized = True` và `out.clean = clean`.
- Ghi MusicXML từ MIDI (`write_musicxml`): 2 part, voice 1, tie qua vạch nhịp, dấu hóa theo khóa, tempo ở P1.
- Reader MIDI có sẵn (không cần `midi_loader`) và bộ theo dõi vị trí hai tay cho file 1 track (`split_hands`);
  `--reader auto` vẫn dùng `midi_loader.load_song` nếu import được.
- Bước `tidy` cho MIDI (`--no-tidy` để tắt): nốt dài không kết thúc giữa hai ô lưới, độ dài là giá trị ghi được,
  để phần mềm chấm nhạc không tự tách voice 2 (ví dụ nốt dài trước chuỗi 32nd).
- MusicXML: `--hand auto|staff|pitch|part`, `--split`, `--swap-parts`, `--keep-ties`, `--drop-grace`,
  `--no-fill-rests` (đúng như README mô tả trước đây nhưng code chưa có).
- MusicXML: giữ grace note, đọc `.mxl`, ô nhịp lấy đà/ngắn (`implicit`), đổi số chỉ nhịp/khóa/divisions giữa bài.
- Nốt/nghỉ có độ dài lạ được chia thành nốt ghi được nối bằng tie (`split_duration`).
- `samples/piano_messy.xml`, `test_normalize.py` (pytest), `requirements.txt`.
- `tests/check_output.py` kiểm tra thêm độ dài từng measure, không có `<backup>`, tie không treo (`--no-timing` để bỏ).
- Thêm `Makefile` để chạy nhanh:
  - `make output`
  - `make test`
  - `make test-reference`
  - `make test-all`
  - `make clean`
- Thêm `tests/check_output.py` để kiểm tra output:
  - có đúng 2 score-part hay không
  - có đúng 2 part hay không
  - mỗi part có chỉ dùng voice 1 hay không
  - có đúng 2 MIDI channel riêng hay không
- Thêm `.gitignore` cho thư mục output và cache Python.
- Thêm `CHANGELOG.md`.

### Changed

- `xml_regrid_piano.py`: `--beats` mặc định lấy từ file input (không có / không phải x/4 thì 4). Thêm
  `read_bar_meta()`; `normalize(..., bar_anchor=...)` ghi đè việc đoán downbeat khi biết vạch nhịp.

- Lưới MIDI mặc định: **không ghi nốt ngắn hơn 16th**. Khi ô lưới là 16th hoặc ngắn hơn, mọi hợp âm và độ
  dài nằm trên ô lưới nguyên; khi ô lưới là 8th hoặc dài hơn, nửa ô (vẫn ≥ 16th) được phép. `--fine` cho
  phép nửa ô trong mọi trường hợp (hành vi cũ, tái tạo output cũ byte-for-byte trên 2 file mẫu MIDI).
- `revoice(clean, ..., fine=False)`: mặc định chỉ độ dài nguyên ô; `fine=True` = hành vi cũ.
- `--lh-max` / `--rh-max` mặc định `None` (không phải `0`) để phân biệt "không ghi" với "ghi rõ 0".
- `Makefile`, `README.md`, `AGENTS.md` dùng lại `samples/Luu_Nien_messy.mid` và `samples/piano_messy.xml`
  thay cho hai file mẫu đã bị xóa.
- Gộp `normalize.py` vào `normalize_piano_musicxml.py`. Code khác đang `import normalize` đổi thành
  `import normalize_piano_musicxml as normalize` (API `normalize`, `write_midi`, `clean_song`, `Clean` giữ nguyên).
- Phân tay MusicXML mặc định là `--hand auto` với `--split C4` (trước đây chỉ theo pitch với ngưỡng C5 và `<=`).
  `--threshold` vẫn dùng được như tên cũ của `--split`, nhưng so sánh là `<` ngưỡng.
- `load_midi_input` gọi `midi_loader.load_song(path, normalize=False)` (project mới normalize mặc định, tránh làm
  hai lần); `midi_loader` cũ chưa có tham số này thì tự gọi lại không tham số.
- `--keep-beams` còn nhận để không vỡ lệnh cũ nhưng không có tác dụng.
- Cập nhật `README.md` và `AGENTS.md` cho khớp code thật (bản cũ mô tả `--hand`, `--keep-ties`... và hàm chưa có).
- Cập nhật `README.md` với hướng dẫn test tự động.
- Cập nhật `AGENTS.md` với quy tắc sửa code phải đi kèm cập nhật test và tài liệu.

### Fixed

- `xml_regrid_piano.py` / web UI: nốt nối (tie) được gộp thành một nốt dài, không còn bị gõ lại ở bản
  sạch và file `.mid`.
- `xml_regrid_piano.py` / web UI: phân tay theo part như `run_musicxml` (part trầm là tay trái khi không có
  staff); `--split-chords` chỉ áp dụng cho `--hand auto/pitch`, không còn ghi đè `--hand staff`.
- `revoice()` dùng cùng luật "16th floor" như `normalize` (chỉ ép ô nguyên khi `units_per_beat >= 8`); trước
  đây với ô lưới 8th, 16th lẻ bị kéo thành 8th.
- `xml_regrid_piano.py` / web UI: số phách lấy từ số chỉ nhịp x/4 của file gốc và vạch nhịp đầu (kể cả ô
  nhịp lấy đà) được truyền cho engine qua `bar_anchor`, không còn mặc định 4/4 và đoán downbeat.
- `app.py`: phần xử lý nặng chạy trong threadpool (không chặn event loop); giới hạn upload 20 MB (413).
- `.mxl`: từ chối file giải nén quá 64 MB.
- `write_musicxml` báo `ValueError` rõ ràng khi nốt cùng tay chồng nhau (trước đây `KeyError`).

- `app.py` và `xml_regrid_piano.py` gọi `N.denoise` / `--phase` không tồn tại (luôn 500/crash); đã bỏ và
  dùng đúng option của `normalize`.
- Web UI in các flag không tồn tại (`--max-chord`, `--min-len`, `--min-vel-ratio`, `--merge-gap`); giờ chỉ
  dùng flag thật và câu lệnh đúng theo loại input.
- Flag MIDI-only bị bỏ qua im lặng trên đường MusicXML -> MusicXML; giờ in cảnh báo stderr.
- `--simplify` ghi đè `--lh-max 0` / `--rh-max 0`; giờ giá trị ghi rõ thắng preset.
- `xml_regrid_piano.py` tính sai độ dài ô nhịp khi advance (giây vs phách đen); giờ dùng `measure_end` /
  `expected_duration` theo phách đen.
- Engine MIDI: bộ đếm `merged` dùng biến `_` bị che trong generator (đã đổi tên biến).
- MusicXML: note có `<chord/>` làm thời gian chạy tiếp, nên mọi note sau chord bị lệch và note trong chord bị
  đặt sai chỗ. Chord giờ nằm cùng onset với note trước.
- MusicXML: nghỉ/nốt có độ dài không ghi được trước đây ghi `<duration>` đúng nhưng `<type>` gần đúng; giờ chia thành
  nốt ghi được (tie) hoặc nhiều dấu nghỉ.
- MusicXML: ô nhịp lấy đà bị thêm nghỉ cho đủ ô nhịp (làm lệch cả bài); giờ giữ đúng độ dài thật.
- MusicXML: đổi số chỉ nhịp giữa bài không được ghi vào output.
- MIDI: phần mềm chấm nhạc tách voice 2 ở ô nhịp có nốt dài + ornament (xem `tidy`).

## [0.1.0]

### Added

- Script `normalize_piano_musicxml.py`:
  - đọc file MusicXML piano
  - chuẩn hóa về 2 part
  - mỗi part một voice
  - hỗ trợ MIDI channel riêng cho từng part
  - hỗ trợ option phân tay theo auto / staff / pitch / part
- Tài liệu `README.md` cho người dùng.
- Tài liệu `AGENTS.md` cho AI/dev.