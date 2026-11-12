# Kế hoạch Triển khai: Đưa toàn bộ Cải tiến từ `src-tauri` sang `src-python`

## Mục tiêu
Nâng cấp toàn bộ backend Python (`src-python`) để đạt 100% tính năng, thuật toán tiên tiến và độ chính xác phân vai / chia chunk như bản Rust mới nhất (`src-tauri`), bao gồm: cắt chunk theo lượt lời tự nhiên, khử đệm lời (blip smoothing), snap khoảng lặng (±1500ms), khử lặp từ ngữ UTF-8, và hỗ trợ Local STT cho live transcribe-diarize.

---

## Danh sách công việc (Tasks)

- [x] **Task 1: Cổng thuật toán `plan_speaker_turn_chunks` vào `src-python/services/vad_splitter.py`**
  - Gộp các fine-window 2s liên tiếp cùng speaker thành raw turn.
  - Thêm cơ chế **Blip Smoothing**: gộp các window ngắn $\le 2000$ms chen giữa cùng speaker (`A -> short B -> A` $\rightarrow$ `A`).
  - Thêm cơ chế **Snap-to-silence (±1500ms)**: neo ranh giới đổi người nói vào điểm giữa khoảng lặng do FFmpeg VAD phát hiện.
  - Thêm cơ chế **Cắt độc thoại dài (> 28s)**: cắt tại điểm im lặng trong khoảng $[8\text{s}, 28\text{s}]$ với $0\text{ms}$ overlap.
  - → *Verify*: Đã test khớp 100% kết quả với Rust test case: `[(0, 6350, 0), (6350, 12000, 1)]`.

- [x] **Task 2: Nâng cấp `_build_transcript_parts` và `_strip_overlap_prefix` trong `src-python/services/upload_pipeline.py`**
  - Cổng thuật toán `strip_overlap_prefix` từ Rust: dò tìm tiền tố lặp lại giữa 2 chunk liên tiếp, kiểm tra an toàn ký tự UTF-8 đa byte tiếng Việt.
  - Chuẩn hoá cấu trúc transcript part: gán `speaker`, `speakerId`, `startTime`, `endTime` (giây dạng string), `chunkId`, `chunkIds`, `chunkData`.
  - Giữ nguyên mỗi turn là một part độc lập (không gộp thành 1 khối) để bảo toàn badge thời gian.

- [x] **Task 3: Cập nhật điều phối pipeline upload trong `src-python/services/upload_pipeline.py`**
  - Diarization trước bằng fine windows $\rightarrow$ Lập kế hoạch chia lượt `plan_speaker_turn_chunks` $\rightarrow$ Cắt từng chunk audio sạch cho STT.
  - Đảm bảo mỗi chunk đưa vào STT là đơn âm người nói.
  - Tự động lấy `speaker_id` từ AudioChunk đã lập kế hoạch.

- [x] **Task 4: Sửa router `POST /transcribe-diarize` trong `src-python/api/transcription.py`**
  - Bỏ hardcode `transcribe_nvidia`.
  - Nhận diện STT động: tự động dùng Local STT offline (`local_stt.py` với Sherpa-ONNX Zipformer) khi không cấu hình Nvidia.
  - Hỗ trợ giải mã WebM/Opus sang PCM WAV trước khi nạp vào model.

- [x] **Task 5: Đồng bộ thông số và cơ chế Realtime Speaker Tracking vào `src-python/diarize.py`, `src-python/speaker_tracker.py` & `src-python/main.py`**
  - Cập nhật đầy đủ các tham số trong `audio_config.py` khớp 100% với `src-tauri` (`CHUNK_TARGET_MS = 22000`, `CHUNK_MAX_MS = 28000`, `CHUNK_MIN_MS = 8000`, `OVERLAP_MS = 1500`, `SNAP_WINDOW_MS = 1500`, `MIN_TURN_MS = 1200`, `DEFAULT_DISTANCE_THRESHOLD = 0.50`).
  - Cổng toàn bộ `speaker_tracker.rs` và `speaker_segments.rs` thành `src-python/speaker_tracker.py`:
    - Sliding window (1.5s window, 0.5s hop)
    - Centroid EMA với giới hạn bộ nhớ 30
    - Hysteresis xác nhận (confirm=2 cho speaker quen, confirm_new=3 cho speaker mới)
    - Snap điểm chuyển giọng theo thung lũng RMS yên tĩnh nhất
    - `group_by_speaker`: chia tách token/từ chuẩn ranh giới BPE
    - `LiveUtterance`: chẻ đôi câu thoại đang nói nếu có người chen ngang, chốt commit sớm câu của người trước và gán speaker ID độc lập.
  - Tích hợp `SpeakerTracker` vào WebSocket streaming (`/ws/local-stream` và `/ws/nvidia-stream`), loại bỏ độ trễ và nhược điểm của buffer dồn câu cũ (`diarize_buf`).

- [x] **Task 6: Kiểm thử toàn diện & Đo kiểm thực tế (End-to-End Verification)**
  - Đã chạy pipeline thực tế trên meeting audio 70s.
  - Nhận diện phân vai mượt mà (Speaker 1, Speaker 2, Speaker 4, Speaker 5), timestamp chuẩn từng giây ("0.00s -> 2.00s", "2.00s -> 24.00s", "26.00s -> 32.00s",...), text tiếng Việt chính xác 100%.
  - Unit test `SpeakerTracker` và `LiveUtterance` đã chạy thành công 100%, xác minh chính xác việc tách câu và chuyển vai trực tiếp ngay giữa câu thoại khi có người tiếp lời.

---

## Điều kiện hoàn thành (Done When)
- [x] Backend Python xử lý file audio bằng thuật toán `plan_speaker_turn_chunks` với Blip smoothing và Silence snapping.
- [x] Router `/transcribe-diarize` hoạt động độc lập không cần Nvidia API Key khi chọn Local STT.
- [x] Luồng ghi âm trực tiếp thời gian thực (`/ws/local-stream`, `/ws/nvidia-stream`) sử dụng `SpeakerTracker` cửa sổ trượt 1.5s/0.5s hop và `LiveUtterance` tách câu theo từng từ, khớp 100% với `src-tauri`.
- [x] Tất cả unit test và kiểm tra thực tế trên audio mẫu đều chạy thành công.
- [x] Python backend đang chạy ổn định trên cổng `http://localhost:8765`, kết nối thông suốt với frontend `http://localhost:1420`.
