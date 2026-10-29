import os
import json
import asyncio
import shutil
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.ad_engine import (
    get_video_info,
    generate_ad_cues_with_gemini,
    synthesize_cue_audio,
    synthesize_all_cues,
    export_accessible_video,
    export_ad_only_audio_track,
    parse_time_to_seconds,
    DEFAULT_VOICE,
    ALT_VOICE
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TTS_DIR = os.path.join(OUTPUT_DIR, "tts")
DEFAULT_VIDEO = os.path.join(BASE_DIR, "DOCUMENTAL EL PAJARILLO_demo.mp4")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TTS_DIR, exist_ok=True)

app = FastAPI(title="MUSA · Gestor Universal de Audiodescripción (Musaraña)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# App state
state = {
    "is_analyzing": False,
    "is_synthesizing": False,
    "is_exporting": False,
    "status_message": "Listo",
    "selected_voice": DEFAULT_VOICE,
    "current_video": DEFAULT_VIDEO
}

class CueItem(BaseModel):
    id: int
    start: str
    end: str
    start_seconds: float
    end_seconds: float
    text: str
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    audio_file: Optional[str] = None

class SaveCuesRequest(BaseModel):
    cues: List[CueItem]
    voice: Optional[str] = DEFAULT_VOICE

def get_cues_filepath(video_path: str) -> str:
    filename = os.path.basename(video_path)
    base_name = os.path.splitext(filename)[0]
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base_name)
    if "pajarillo" in safe_name.lower():
        return os.path.join(DATA_DIR, "ad_cues.json")
    return os.path.join(DATA_DIR, f"{safe_name}_cues.json")

def load_cues(video_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = video_path or state["current_video"]
    data_file = get_cues_filepath(path)
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_cues_to_disk(cues: List[Dict[str, Any]], video_path: Optional[str] = None):
    path = video_path or state["current_video"]
    data_file = get_cues_filepath(path)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(cues, f, ensure_ascii=False, indent=2)

def get_accessible_video_path(video_path: str) -> str:
    base = os.path.splitext(os.path.basename(video_path))[0]
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base)
    target = os.path.join(OUTPUT_DIR, f"{safe_name}_accesible.mp4")
    if not os.path.exists(target):
        alt = os.path.join(OUTPUT_DIR, f"{safe_name.replace('_demo', '')}_accesible.mp4")
        if os.path.exists(alt):
            return alt
    return target

def get_audio_track_paths(video_path: str) -> Dict[str, str]:
    base = os.path.splitext(os.path.basename(video_path))[0]
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base)
    return {
        "wav": os.path.join(OUTPUT_DIR, f"{safe_name}_audiodescripcion_sincronizada.wav"),
        "mp3": os.path.join(OUTPUT_DIR, f"{safe_name}_audiodescripcion_sincronizada.mp3")
    }

def list_available_videos():
    videos = []
    # Check default root videos
    for f in sorted(os.listdir(BASE_DIR)):
        if f.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
            p = os.path.join(BASE_DIR, f)
            videos.append({"filename": f, "path": p, "is_default": f == os.path.basename(DEFAULT_VIDEO)})
    # Check uploads
    if os.path.exists(UPLOADS_DIR):
        for f in sorted(os.listdir(UPLOADS_DIR)):
            if f.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
                p = os.path.join(UPLOADS_DIR, f)
                videos.append({"filename": f, "path": p, "is_default": False})
    return videos

@app.get("/api/project")
def get_project_data():
    video_path = state["current_video"]
    if not os.path.exists(video_path) and os.path.exists(DEFAULT_VIDEO):
        video_path = DEFAULT_VIDEO
        state["current_video"] = video_path

    video_info = None
    if os.path.exists(video_path):
        try:
            video_info = get_video_info(video_path)
            if video_path.startswith(UPLOADS_DIR):
                video_info["url"] = f"/media/uploads/{os.path.basename(video_path)}"
            else:
                video_info["url"] = f"/media/video/{os.path.basename(video_path)}"
        except Exception as e:
            video_info = {"error": str(e), "filename": os.path.basename(video_path)}

    accessible_path = get_accessible_video_path(video_path)
    accessible_info = None
    if os.path.exists(accessible_path):
        try:
            accessible_info = get_video_info(accessible_path)
            acc_name = os.path.basename(accessible_path)
            accessible_info["url"] = f"/media/accessible/{acc_name}"
            accessible_info["vtt_url"] = f"/media/accessible/{acc_name.rsplit('.', 1)[0]}.vtt"
        except Exception:
            pass

    audio_paths = get_audio_track_paths(video_path)
    audio_tracks = {
        "wav_available": os.path.exists(audio_paths["wav"]),
        "wav_url": f"/media/accessible/{os.path.basename(audio_paths['wav'])}" if os.path.exists(audio_paths["wav"]) else None,
        "mp3_available": os.path.exists(audio_paths["mp3"]),
        "mp3_url": f"/media/accessible/{os.path.basename(audio_paths['mp3'])}" if os.path.exists(audio_paths["mp3"]) else None
    }

    cues = load_cues(video_path)

    return {
        "video": video_info,
        "accessible_video": accessible_info,
        "audio_tracks": audio_tracks,
        "cues": cues,
        "state": state,
        "available_videos": list_available_videos(),
        "voices": [
            {"id": DEFAULT_VOICE, "name": "Álvaro (Voz natural española masculina)"},
            {"id": ALT_VOICE, "name": "Elvira (Voz natural española femenina)"}
        ]
    }

@app.post("/api/upload_video")
async def upload_video(file: UploadFile = File(...)):
    filename = file.filename
    clean_name = "".join(c if c.isalnum() or c in (".", "-", "_") else "_" for c in filename)
    target_path = os.path.join(UPLOADS_DIR, clean_name)

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    state["current_video"] = target_path
    state["status_message"] = f"Nuevo vídeo cargado: {clean_name}"

    return get_project_data()

@app.post("/api/select_video")
def select_video(filename: str = Form(...)):
    for v in list_available_videos():
        if v["filename"] == filename:
            state["current_video"] = v["path"]
            state["status_message"] = f"Vídeo seleccionado: {filename}"
            return get_project_data()
    raise HTTPException(status_code=404, detail="Vídeo no encontrado.")

@app.post("/api/save_cues")
def save_cues(req: SaveCuesRequest):
    cues_dict = [c.dict() for c in req.cues]
    for c in cues_dict:
        if "start" in c and c["start"]:
            c["start_seconds"] = parse_time_to_seconds(c["start"])
        if "end" in c and c["end"]:
            c["end_seconds"] = parse_time_to_seconds(c["end"])
    save_cues_to_disk(cues_dict)
    state["selected_voice"] = req.voice or state["selected_voice"]
    return {"status": "ok", "count": len(cues_dict)}

@app.post("/api/generate")
async def generate_cues_endpoint(background_tasks: BackgroundTasks):
    if state["is_analyzing"]:
        raise HTTPException(status_code=400, detail="Ya hay un análisis de IA en curso.")

    video_path = state["current_video"]
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Vídeo de origen no encontrado.")

    def run_generation():
        state["is_analyzing"] = True
        state["status_message"] = "Analizando vídeo con Gemini Multimodal..."
        try:
            cues = generate_ad_cues_with_gemini(video_path)
            state["status_message"] = "Sintetizando locuciones de audiodescripción..."
            cues = asyncio.run(synthesize_all_cues(cues, voice=state["selected_voice"], output_dir=TTS_DIR))
            save_cues_to_disk(cues, video_path)
            state["status_message"] = f"Audiodescripción generada con éxito ({len(cues)} intervenciones)."
        except Exception as e:
            state["status_message"] = f"Error: {str(e)}"
        finally:
            state["is_analyzing"] = False

    background_tasks.add_task(run_generation)
    return {"status": "started", "message": "Análisis y generación iniciados en segundo plano."}

@app.post("/api/synthesize_cue")
async def synthesize_single_cue(cue: CueItem, voice: Optional[str] = None):
    chosen_voice = voice or state["selected_voice"]
    cue_dict = cue.dict()
    updated = await synthesize_cue_audio(cue_dict, voice=chosen_voice, output_dir=TTS_DIR)

    cues = load_cues()
    for i, c in enumerate(cues):
        if c.get("id") == cue.id:
            cues[i] = updated
            break
    save_cues_to_disk(cues)
    return updated

@app.post("/api/synthesize_all")
async def synthesize_all_endpoint(voice: Optional[str] = Form(None)):
    chosen_voice = voice or state["selected_voice"]
    state["selected_voice"] = chosen_voice
    cues = load_cues()
    if not cues:
        raise HTTPException(status_code=400, detail="No hay marcas de audiodescripción registradas.")

    state["is_synthesizing"] = True
    state["status_message"] = f"Sintetizando {len(cues)} pistas con voz {chosen_voice}..."
    try:
        updated_cues = await synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR)
        save_cues_to_disk(updated_cues)
        state["status_message"] = "Síntesis completada."
        return {"status": "ok", "cues": updated_cues}
    finally:
        state["is_synthesizing"] = False

@app.post("/api/export_audio_track")
def export_audio_track_endpoint(background_tasks: BackgroundTasks, format: str = Form("wav")):
    if state["is_exporting"]:
        raise HTTPException(status_code=400, detail="Ya hay un renderizado en marcha.")

    cues = load_cues()
    video_path = state["current_video"]
    chosen_voice = state["selected_voice"]

    def run_audio_export():
        state["is_exporting"] = True
        state["status_message"] = "Verificando audios para exportar pista profesional..."
        try:
            cues_to_synth = [c for c in cues if not c.get("audio_file") or not os.path.exists(c.get("audio_file", "")) or os.path.getsize(c.get("audio_file", "")) < 500]
            if cues_to_synth:
                asyncio.run(synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR))
                save_cues_to_disk(cues)

            info = get_video_info(video_path)
            target_ext = "wav" if format.lower() == "wav" else "mp3"
            audio_paths = get_audio_track_paths(video_path)
            target_path = audio_paths[target_ext]

            state["status_message"] = f"Generando pista {target_ext.upper()} sincronizada a código de tiempo..."
            export_ad_only_audio_track(
                video_duration=info["duration"],
                cues=cues,
                output_audio_path=target_path
            )
            state["status_message"] = f"Pista {target_ext.upper()} profesional generada con éxito."
        except Exception as e:
            state["status_message"] = f"Error al generar pista de audio: {str(e)}"
        finally:
            state["is_exporting"] = False

    background_tasks.add_task(run_audio_export)
    return {"status": "started", "message": "Generación de pista de audio iniciada."}

@app.post("/api/export")
def export_video_endpoint(background_tasks: BackgroundTasks):
    if state["is_exporting"]:
        raise HTTPException(status_code=400, detail="Ya hay una exportación en marcha.")
    if state["is_synthesizing"]:
        raise HTTPException(status_code=400, detail="La síntesis de voz aún está en curso. Por favor, espera a que termine.")

    cues = load_cues()
    video_path = state["current_video"]
    chosen_voice = state["selected_voice"]

    def run_export():
        state["is_exporting"] = True
        state["status_message"] = "Verificando audios y sintetizando locuciones pendientes..."
        try:
            cues_to_synth = [c for c in cues if not c.get("audio_file") or not os.path.exists(c.get("audio_file", "")) or os.path.getsize(c.get("audio_file", "")) < 500]
            if cues_to_synth:
                state["status_message"] = f"Sintetizando {len(cues_to_synth)} intervenciones de voz..."
                asyncio.run(synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR))
                save_cues_to_disk(cues)

            target_video = get_accessible_video_path(video_path)
            state["status_message"] = "Renderizando vídeo final accesible con audio ducking..."
            export_accessible_video(
                video_path=video_path,
                cues=cues,
                output_video_path=target_video
            )

            try:
                info = get_video_info(video_path)
                tracks = get_audio_track_paths(video_path)
                export_ad_only_audio_track(info["duration"], cues, tracks["wav"])
                export_ad_only_audio_track(info["duration"], cues, tracks["mp3"])
            except Exception:
                pass

            state["status_message"] = "Vídeo final para el museo renderizado con éxito."
        except Exception as e:
            state["status_message"] = f"Error en exportación: {str(e)}"
        finally:
            state["is_exporting"] = False

    background_tasks.add_task(run_export)
    return {"status": "started", "message": "Renderizado de vídeo iniciado en segundo plano."}

# Media routes
app.mount("/media/accessible", StaticFiles(directory=OUTPUT_DIR), name="accessible_media")
app.mount("/media/tts", StaticFiles(directory=TTS_DIR), name="tts_media")
app.mount("/media/video", StaticFiles(directory=BASE_DIR), name="video_media")
app.mount("/media/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads_media")

# Frontends
@app.get("/")
def kiosk_page():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

@app.get("/editor")
def editor_page():
    return FileResponse(os.path.join(BASE_DIR, "static", "editor.html"))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
