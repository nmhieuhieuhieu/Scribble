# Scribble — Trợ lý cuộc họp AI (AI Meeting Assistant)

> Ứng dụng trợ lý cuộc họp thông minh: Ghi âm, phiên âm thời gian thực (Speech-to-Text), phân biệt người nói (Speaker Diarization), dịch thuật trực tiếp và tóm tắt biên bản cuộc họp tự động (Meeting Minutes) bằng LLM.

---

## 🏗️ Kiến trúc hệ thống

Ứng dụng gồm 2 phần chính hoạt động phối hợp:

1. **Frontend (Web/Desktop Client)**:
   - **Công nghệ**: React 19, TypeScript, Vite, Tailwind CSS v4, Zustand.
   - **Cổng chạy (Port)**: `1420` (truy cập: [http://localhost:1420](http://localhost:1420)).
   - **Reverse Proxy**: Tự động chuyển tiếp các request `/api` và `/ws` sang Backend cổng `8765`.
   - **Mã nguồn**: Thư mục [`src/`](src/).

2. **Backend (Python Sidecar Server)**:
   - **Công nghệ**: FastAPI, Uvicorn, SQLite (`voicescribe.db`).
   - **Cổng chạy (Port)**: `8765`.
   - **Model AI cục bộ**:
     - **Speaker Diarization**: CAM++ / ResNet34 ONNX (`models/speaker_embedding_resnet34.onnx`).
     - **STT Offline**: Sherpa-ONNX Zipformer (hỗ trợ tiếng Việt on-device).
     - **STT Cloud**: Soniox Streaming WebSocket (hỗ trợ song ngữ & dịch trực tiếp).
     - **Tóm tắt LLM**: Tương thích các provider OpenAI, DeepSeek, Google Gemini, Anthropic, hoặc local qua Ollama / vLLM.
   - **Mã nguồn**: Thư mục [`src-python/`](src-python/).

---

## ⚡ Khởi chạy nhanh (Quick Start)

### Cách 1: Chạy bằng 1 cú nhấp chuột (Khuyên dùng trên Windows)

Chỉ cần nhấp đúp chuột vào file:
👉 **[`start.bat`](start.bat)**

File này sẽ tự động:
1. Mở cửa sổ Backend chạy FastAPI trên cổng `8765`.
2. Chờ 3 giây và mở cửa sổ Frontend chạy Vite trên cổng `1420`.
3. Bạn mở trình duyệt truy cập: **[http://localhost:1420](http://localhost:1420)**.

*(Bạn cũng có thể chạy riêng lẻ [`run-backend.bat`](run-backend.bat) hoặc [`run-frontend.bat`](run-frontend.bat) khi cần).*

---

### Cách 2: Chạy thủ công bằng dòng lệnh (Terminal / PowerShell)

#### Bước 1: Yêu cầu môi trường
- **Node.js**: Phiên bản 20+ và `npm` (hoặc `pnpm`).
- **Python**: Phiên bản 3.10 hoặc 3.11.

#### Bước 2: Cài đặt thư viện (chỉ cần chạy lần đầu)

* **Frontend**:
  ```bash
  npm install
  ```

* **Backend**:
  ```bash
  cd src-python
  pip install -r requirements.txt
  cd ..
  ```

#### Bước 3: Khởi động Backend (Terminal 1)
> ⚠️ **Lưu ý quan trọng**: Cần đặt biến môi trường `VOICESCRIBE_DATA` để database SQLite và file âm thanh được lưu cục bộ trong dự án, tránh lỗi phân quyền thư mục người dùng.

* **Windows (PowerShell)**:
  ```powershell
  $env:VOICESCRIBE_DATA = "$PSScriptRoot\.voicescribe_data"
  # Hoặc đường dẫn tuyệt đối:
  # $env:VOICESCRIBE_DATA = "D:\Scribble\.voicescribe_data"

  cd src-python
  python main.py
  ```

* **Windows (Command Prompt - CMD)**:
  ```cmd
  set VOICESCRIBE_DATA=%cd%\.voicescribe_data
  cd src-python
  python main.py
  ```

* **macOS / Linux**:
  ```bash
  export VOICESCRIBE_DATA="$(pwd)/.voicescribe_data"
  cd src-python
  python3 main.py
  ```

Backend sẽ khởi động tại: `http://127.0.0.1:8765`.

#### Bước 4: Khởi động Frontend (Terminal 2)
Mở một cửa sổ Terminal mới tại thư mục gốc dự án:

```bash
npm run dev
```

Frontend sẽ khởi động tại: **[http://localhost:1420](http://localhost:1420)**.

---

## ⚙️ Cấu hình dịch vụ AI

Sau khi mở giao diện tại `http://localhost:1420`, vào mục **Cài đặt (Settings)** (biểu tượng bánh răng ở góc phải) để cấu hình:

1. **Phiên âm (Speech-to-Text)**:
   - **Offline / Cục bộ**: Sử dụng Sherpa-ONNX Zipformer (không cần API key, bảo mật 100%).
   - **Cloud (Soniox)**: Điền Soniox API Key (đăng ký tại [soniox.com](https://soniox.com)) để có độ chính xác cao và hỗ trợ dịch cabin trực tiếp đa ngôn ngữ.

2. **Biên bản họp & Tóm tắt (LLM)**:
   - Điền API Key và chọn model (OpenAI `gpt-4o-mini`, DeepSeek `deepseek-chat`, Groq, v.v.).
   - Hoặc trỏ vào local LLM (Ollama) qua URL `http://localhost:11434/v1`.

---

## 🛠️ Xử lý lỗi thường gặp (Troubleshooting)

1. **Lỗi `[Errno 13] Permission denied: 'C:\Users\...\.voicescribe\sidecar.log'`**:
   - Nguyên nhân: Thiếu biến môi trường `VOICESCRIBE_DATA`, chương trình mặc định ghi vào thư mục User bị hạn chế quyền.
   - Khắc phục: Chạy qua file `start.bat` hoặc gán biến môi trường `VOICESCRIBE_DATA` trỏ vào thư mục làm việc như hướng dẫn ở trên.

2. **Frontend không gọi được API / hiển thị "Đang khởi động..."**:
   - Kiểm tra xem Backend (cửa sổ Python) đã chạy xong và báo `Application startup complete` chưa.
   - Kiểm tra endpoint kiểm tra sức khỏe tại: [http://localhost:1420/api/health](http://localhost:1420/api/health) — nếu trả về JSON `{"status": "ok", ...}` là kết nối đã thông suốt.

---

## 📂 Cấu trúc thư mục

```
Scribble/
├── start.bat                  # Script khởi động 1-click cả BE & FE trên Windows
├── run-backend.bat            # Script khởi động riêng Backend
├── run-frontend.bat           # Script khởi động riêng Frontend
├── .voicescribe_data/         # Thư mục lưu database SQLite (voicescribe.db) và cache audio
├── src/                       # Giao diện Frontend (React 19 + TypeScript + Vite)
│   ├── components/            # Các component UI (MeetingDetail, UploadAudioModal, Settings...)
│   ├── lib/                   # API client, sidecar proxy helper
│   └── stores/                # Zustand state stores
├── src-python/                # Máy chủ Backend (FastAPI)
│   ├── api/                   # Router API (meetings, upload, settings, transcription...)
│   ├── models/                # File ONNX model cho diarization (ResNet34, CAM++)
│   ├── services/              # Pipeline xử lý audio, VAD chunking, Diarizer
│   ├── db.py                  # Quản lý SQLite database và schema migrations
│   └── main.py                # Điểm khởi chạy chính của Backend (FastAPI / Uvicorn)
├── package.json               # Cấu hình dependency của Frontend
└── vite.config.ts             # Cấu hình Vite & reverse proxy sang cổng 8765
```
