"""
Audio Processing & Speaker Diarization Configuration
====================================================
Tập trung toàn bộ các tham số xử lý âm thanh, cắt chunk VAD, nhận diện người nói (diarization),
và gộp lượt thoại (turn merging).

Bạn có thể điều chỉnh trực tiếp các giá trị bên dưới hoặc thiết lập qua biến môi trường (.env).
"""

import os


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


# ==============================================================================
# 1. CẤU HÌNH NHẬN DIỆN NGƯỜI NÓI (SPEAKER DIARIZATION)
# ==============================================================================

# Thời lượng cửa sổ quét embedding (milliseconds)
# 2000ms = 2.0 giây (khớp 100% src-tauri).
FINE_WINDOW_MS: int = _get_int("DIARIZE_FINE_WINDOW_MS", 2_000)

# Bước dịch cửa sổ quét embedding (milliseconds)
# 2000ms = 2.0 giây (cắt cửa sổ kế tiếp, khớp 100% src-tauri).
FINE_HOP_MS: int = _get_int("DIARIZE_FINE_HOP_MS", 2_000)

# Ngưỡng khoảng cách Cosine để gom cụm người nói (Hierarchical Clustering)
# 0.58: Tối ưu cho ResNet34 tránh phân mảnh người nói trên các câu thoại ngắn (short utterances).
DIARIZE_DISTANCE_THRESHOLD: float = _get_float("DIARIZE_DISTANCE_THRESHOLD", 0.58)

# Số người nói tối đa trong 1 cuộc họp
DEFAULT_MAX_SPEAKERS: int = _get_int("DIARIZE_MAX_SPEAKERS", 8)

# Thời lượng tối thiểu (giây) để bắt đầu nhận diện một người nói mới (debounce)
DIARIZE_MIN_SECONDS: float = _get_float("DIARIZE_MIN_SECONDS", 1.5)
NEW_SPEAKER_MIN_SECONDS: float = _get_float("NEW_SPEAKER_MIN_SECONDS", 1.5)

# Ngưỡng biên độ âm lượng coi là khoảng lặng khi trích xuất embedding
FINE_SILENCE_RMS: float = _get_float("DIARIZE_FINE_SILENCE_RMS", 0.01)


# ==============================================================================
# 2. CẤU HÌNH CẮT CHUNK ÂM THANH GỬI VÀO STT (SPEAKER-AWARE VAD CHUNKING)
# ==============================================================================

# Độ dài chunk âm thanh tối thiểu (milliseconds). Khớp src-tauri (8s).
CHUNK_MIN_MS: int = _get_int("CHUNK_MIN_MS", 8_000)

# Độ dài chunk âm thanh mục tiêu lý tưởng (milliseconds). Khớp src-tauri (22s).
CHUNK_TARGET_MS: int = _get_int("CHUNK_TARGET_MS", 22_000)

# Độ dài chunk âm thanh tối đa (milliseconds). Khớp src-tauri (28s).
CHUNK_MAX_MS: int = _get_int("CHUNK_MAX_MS", 28_000)

# Thời lượng khoảng lặng tối thiểu (giây) để FFmpeg coi là một điểm ngắt câu
SILENCE_MIN_DURATION_S: float = _get_float("SILENCE_MIN_DURATION_S", 0.3)
SILENCE_NOISE_DB: int = _get_int("SILENCE_NOISE_DB", -30)

# Biên độ hút khoảng lặng (milliseconds). Khớp src-tauri SNAP_WINDOW_MS (1500ms).
# Khi phát hiện đổi giọng nói tại điểm T, tìm khoảng lặng trong bán kính ±1500ms
# để neo ranh giới cắt, giúp câu không bị chém ngang từ.
SNAP_WINDOW_MS: int = _get_int("SNAP_WINDOW_MS", 1_500)
SPEAKER_SNAP_TOLERANCE_MS: int = SNAP_WINDOW_MS

# Độ dài tối thiểu của một lượt lời (milliseconds). Khớp src-tauri MIN_TURN_MS (1200ms).
MIN_TURN_MS: int = _get_int("MIN_TURN_MS", 1_200)

# Độ chồng lấn giữa các chunk (milliseconds). Khớp src-tauri OVERLAP_MS (1500ms).
OVERLAP_MS: int = _get_int("OVERLAP_MS", 1_500)


# ==============================================================================
# 3. CẤU HÌNH GỘP LƯỢT THOẠI CỦA CÙNG MỘT NGƯỜI (TURN MERGING)
# ==============================================================================

# Khoảng lặng tối đa (milliseconds) giữa 2 đoạn liên tiếp của CÙNG 1 người để gộp lại:
# 1500ms = 1.5 giây.
# - Nếu khoảng nghỉ <= 1.5s: Tự động nối text thành 1 lượt thoại hoàn chỉnh.
# - Nếu khoảng nghỉ > 1.5s: Tách thành 2 dòng thoại riêng biệt để thấy rõ khoảng dừng.
MERGE_MAX_GAP_MS: int = _get_int("MERGE_MAX_GAP_MS", 1500)
