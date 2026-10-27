# Changelog

Tài liệu này ghi lại các thay đổi quan trọng của project.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `normalize_piano_musicxml.py` nhận thêm input MIDI (`.mid`/`.midi`) và xuất `.mid` hoặc `.xml`: engine MIDI
  (từ `normalize.py` cũ, đã gộp vào) tìm lưới và tempo từ cách chơi, đặt nốt lên lưới chính xác, tìm ô nhịp và nốt
  lấy đà, mỗi tay một voice. Cần `numpy` (chỉ cho MIDI), thêm `requirements.txt`.
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

- Gộp `normalize.py` vào `normalize_piano_musicxml.py`. Code khác đang `import normalize` đổi thành
  `import normalize_piano_musicxml as normalize` (API `normalize`, `write_midi`, `clean_song`, `Clean` giữ nguyên).
- Phân tay MusicXML mặc định là `--hand auto` với `--split C4` (trước đây chỉ theo pitch với ngưỡng C5 và `<=`).
  `--threshold` vẫn dùng được như tên cũ của `--split`, nhưng so sánh là `<` ngưỡng.
- `--keep-beams` còn nhận để không vỡ lệnh cũ nhưng không có tác dụng.
- Cập nhật `README.md` và `AGENTS.md` cho khớp code thật (bản cũ mô tả `--hand`, `--keep-ties`... và hàm chưa có).
- Cập nhật `README.md` với hướng dẫn test tự động.
- Cập nhật `AGENTS.md` với quy tắc sửa code phải đi kèm cập nhật test và tài liệu.

### Fixed

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