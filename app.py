import os
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"

UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = FastAPI(title="Video Transcript Tool")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE / "static")),
    name="static"
)

HTML = (BASE / "static" / "index.html").read_text(
    encoding="utf-8"
)


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):

    allowed = {
        ".mp4",
        ".mkv",
        ".mov",
        ".webm",
        ".avi",
        ".m4v"
    }

    extension = Path(file.filename or "").suffix.lower()

    if extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail="ဒီ Video format ကို မထောက်ပံ့သေးပါ။"
        )

    job_id = uuid.uuid4().hex

    video_path = UPLOADS / f"{job_id}{extension}"

    txt_path = OUTPUTS / f"{job_id}.txt"

    srt_path = OUTPUTS / f"{job_id}.srt"

    try:

        with open(video_path, "wb") as output:

            while True:

                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                output.write(chunk)

        # Whisper will be connected here.
        #
        # The video has now been uploaded successfully.
        #
        # Next step:
        # Video -> Speech Recognition -> TXT + SRT

        txt_path.write_text(
            "Video upload အောင်မြင်ပါတယ်။\n"
            "Speech-to-Text engine ကို ချိတ်ဆက်နေပါတယ်။",
            encoding="utf-8"
        )

        srt_path.write_text(
            "1\n"
            "00:00:00,000 --> 00:00:05,000\n"
            "Transcript engine မချိတ်ရသေးပါ။\n",
            encoding="utf-8"
        )

        return {
            "ok": True,
            "message": "Video upload အောင်မြင်ပါတယ်။",
            "txt": f"/download/txt/{job_id}",
            "srt": f"/download/srt/{job_id}"
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    finally:

        if video_path.exists():
            video_path.unlink()


@app.get("/download/txt/{job_id}")
def download_txt(job_id: str):

    path = OUTPUTS / f"{job_id}.txt"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="File မတွေ့ပါ။"
        )

    return FileResponse(
        path,
        filename="transcript.txt",
        media_type="text/plain"
    )


@app.get("/download/srt/{job_id}")
def download_srt(job_id: str):

    path = OUTPUTS / f"{job_id}.srt"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="SRT file မတွေ့ပါ။"
        )

    return FileResponse(
        path,
        filename="transcript.srt",
        media_type="text/plain"
    )
