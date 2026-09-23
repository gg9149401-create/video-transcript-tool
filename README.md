# Video Transcript Tool

## Run

1. Install Python 3.10+
2. Install FFmpeg and make sure `ffmpeg` is in PATH.
3. In this folder:

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

4. Open `http://127.0.0.1:8000`

## Important

This starter already handles video upload and audio extraction. The `/transcribe` endpoint has a marked place to connect Whisper or another Speech-to-Text engine.

For 1GB+ videos, production deployment should use resumable/chunked uploads and object storage rather than keeping large files only on the web server.
