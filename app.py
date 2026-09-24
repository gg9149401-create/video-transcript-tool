import os
import uuid
import shutil
import traceback
import subprocess
from pathlib import Path
from threading import Thread

import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles


BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
TEMP = BASE / "temp"

UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)
TEMP.mkdir(exist_ok=True)

app = FastAPI(title="Video Transcript Tool")

app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


JOBS = {}


def run_ffmpeg(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:])


def srt_time(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    total = int(seconds)

    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60

    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_audio(audio_file, offset):
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    url = "https://api.groq.com/openai/v1/audio/transcriptions"

    with open(audio_file, "rb") as f:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}"
            },
            files={
                "file": (
    "audio.mp3",
    f,
    "audio/mpeg"
                )
            },
            data={
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json",
                "temperature": "0"
            },
            timeout=600
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Groq API error: {response.text}"
        )

    return response.json()


def process_video(job_id, video_path):
    try:
        JOBS[job_id] = {
            "status": "processing",
            "progress": 0
        }

        job_dir = TEMP / job_id
        job_dir.mkdir(exist_ok=True)

        audio_pattern = job_dir / "part_%03d.mp3"

        # Convert video to small MP3 chunks automatically.
        # 20 minutes per chunk, 64 kbps mono.
        run_ffmpeg([
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            "-f",
            "segment",
            "-segment_time",
            "1200",
            "-reset_timestamps",
            "1",
            str(audio_pattern)
        ])

        parts = sorted(job_dir.glob("part_*.mp3"))

        if not parts:
            raise RuntimeError("Could not extract audio")

        all_text = []
        all_srt = []
        subtitle_number = 1

        total = len(parts)

        for index, part in enumerate(parts):

            JOBS[job_id]["progress"] = int(
                (index / total) * 90
            )

            data = transcribe_audio(
                part,
                index * 1200
            )

            text = data.get("text", "").strip()

            if text:
                all_text.append(text)

            segments = data.get("segments", [])

            for segment in segments:
                start = float(segment.get("start", 0))
                end = float(segment.get("end", 0))
                text_segment = segment.get(
                    "text", ""
                ).strip()

                if not text_segment:
                    continue

                start += index * 1200
                end += index * 1200

                all_srt.append(
                    f"{subtitle_number}\n"
                    f"{srt_time(start)} --> "
                    f"{srt_time(end)}\n"
                    f"{text_segment}\n"
                )

                subtitle_number += 1

        txt_name = f"{job_id}.txt"
        srt_name = f"{job_id}.srt"

        txt_path = OUTPUTS / txt_name
        srt_path = OUTPUTS / srt_name

        txt_path.write_text(
            "\n\n".join(all_text),
            encoding="utf-8"
        )

        srt_path.write_text(
            "\n".join(all_srt),
            encoding="utf-8"
        )

        JOBS[job_id] = {
            "status": "completed",
            "progress": 100,
            "txt": f"/download/{txt_name}",
            "srt": f"/download/{srt_name}"
        }
 except Exception as e:
    traceback.print_exc()
    JOBS[job_id] = {
        "status": "error",
        "error": str(e)
    }
    finally:
        try:
            shutil.rmtree(TEMP / job_id)
        except Exception:
            pass

        try:
            video_path.unlink()
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
async def home():
    index = BASE / "static" / "index.html"

    if index.exists():
        return index.read_text(encoding="utf-8")

    return """
    <h2>Video Transcript Tool</h2>
    <p>static/index.html not found.</p>
    """


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected"
        )

    job_id = str(uuid.uuid4())

    extension = Path(file.filename).suffix or ".mp4"

    video_path = UPLOADS / f"{job_id}{extension}"

    try:
        with open(video_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                buffer.write(chunk)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    JOBS[job_id] = {
        "status": "queued",
        "progress": 0
    }

    Thread(
        target=process_video,
        args=(job_id, video_path),
        daemon=True
    ).start()

    return {
        "job_id": job_id,
        "status": "queued"
    }


@app.get("/status/{job_id}")
async def status(job_id: str):

    job = JOBS.get(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job


@app.get("/download/{filename}")
async def download(filename: str):

    path = OUTPUTS / Path(filename).name

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return FileResponse(
        path,
        filename=path.name
    )
