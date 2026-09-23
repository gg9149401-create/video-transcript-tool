import os, shutil, subprocess, uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = FastAPI(title="Video Transcript Tool")
app.mount("/static", StaticFiles(directory=BASE/"static"), name="static")

HTML = (BASE/"static"/"index.html").read_text(encoding="utf-8")

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    allowed = {".mp4",".mkv",".mov",".webm",".avi",".m4v"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, "Unsupported video format")

    job = uuid.uuid4().hex
    video = UPLOADS / f"{job}{ext}"
    audio = OUTPUTS / f"{job}.wav"
    txt = OUTPUTS / f"{job}.txt"

    with video.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    try:
        subprocess.run([
            "ffmpeg","-y","-i",str(video),"-vn",
            "-ac","1","-ar","16000",str(audio)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Put Whisper/your preferred STT engine here.
        # Example with local Whisper:
        #   pip install openai-whisper
        #   whisper audio.wav --model turbo --output_format txt --output_dir outputs
        #
        # This prototype returns a clear setup message until the STT engine is installed.
        txt.write_text(
            "Audio extraction completed successfully.\\n\\n"
            "Install a Speech-to-Text engine (for example Whisper) and connect it "
            "inside /transcribe to generate the final transcript.\\n",
            encoding="utf-8"
        )

        return {
            "ok": True,
            "job": job,
            "download": f"/download/{job}.txt",
            "message": "Video uploaded and audio extracted. Connect Whisper/STT for transcription."
        }
    except subprocess.CalledProcessError:
        raise HTTPException(500, "FFmpeg could not process this video")
    finally:
        if video.exists():
            video.unlink()
        if audio.exists():
            audio.unlink()

@app.get("/download/{job}.txt")
def download(job: str):
    path = OUTPUTS / f"{job}.txt"
    if not path.exists():
        raise HTTPException(404, "Transcript not found")
    return FileResponse(path, filename="transcript.txt", media_type="text/plain")
