import os
import json
import asyncio
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
    parse_time_to_seconds,
    DEFAULT_VOICE,
    ALT_VOICE
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "ad_cues.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TTS_DIR = os.path.join(OUTPUT_DIR, "tts")
DEFAULT_VIDEO = os.path.join(BASE_DIR, "DOCUMENTAL EL PAJARILLO_demo.mp4")
ACCESSIBLE_VIDEO = os.path.join(OUTPUT_DIR, "DOCUMENTAL_EL_PAJARILLO_accesible.mp4")

os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(TTS_DIR, exist_ok=True)

app = FastAPI(title="MUSA - Audiodescripción Accesible para Museos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory progress tracking
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

def load_cues() -> List[Dict[str, Any]]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_cues_to_disk(cues: List[Dict[str, Any]]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(cues, f, ensure_ascii=False, indent=2)

@app.get("/api/project")
def get_project_data():
    video_path = state["current_video"]
    video_info = None
    if os.path.exists(video_path):
        try:
            video_info = get_video_info(video_path)
            video_info["url"] = f"/media/video/{os.path.basename(video_path)}"
        except Exception as e:
            video_info = {"error": str(e), "filename": os.path.basename(video_path)}
            
    accessible_info = None
    if os.path.exists(ACCESSIBLE_VIDEO):
        try:
            accessible_info = get_video_info(ACCESSIBLE_VIDEO)
            accessible_info["url"] = "/media/accessible/DOCUMENTAL_EL_PAJARILLO_accesible.mp4"
            accessible_info["vtt_url"] = "/media/accessible/DOCUMENTAL_EL_PAJARILLO_accesible.vtt"
        except Exception:
            pass

    cues = load_cues()

    return {
        "video": video_info,
        "accessible_video": accessible_info,
        "cues": cues,
        "state": state,
        "voices": [
            {"id": DEFAULT_VOICE, "name": "Álvaro (Voz natural española masculina)"},
            {"id": ALT_VOICE, "name": "Elvira (Voz natural española femenina)"}
        ]
    }

@app.post("/api/save_cues")
def save_cues(req: SaveCuesRequest):
    cues_dict = [c.dict() for c in req.cues]
    # Always normalize seconds from start/end strings to prevent desync
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
            save_cues_to_disk(cues)
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
    
    # Update in saved cues
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
            # Check if any cues need TTS synthesis
            cues_to_synth = []
            for c in cues:
                f = c.get("audio_file")
                if not f or not os.path.exists(f) or os.path.getsize(f) < 500:
                    cues_to_synth.append(c)

            if cues_to_synth:
                state["status_message"] = f"Sintetizando {len(cues_to_synth)} intervenciones de voz..."
                asyncio.run(synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR))
                save_cues_to_disk(cues)

            state["status_message"] = "Renderizando vídeo final accesible con audio ducking..."
            export_accessible_video(
                video_path=video_path,
                cues=cues,
                output_video_path=ACCESSIBLE_VIDEO
            )
            state["status_message"] = "Vídeo final para el museo renderizado con éxito."
        except Exception as e:
            state["status_message"] = f"Error en exportación: {str(e)}"
        finally:
            state["is_exporting"] = False

    background_tasks.add_task(run_export)
    return {"status": "started", "message": "Renderizado de vídeo iniciado en segundo plano."}

# Mount media folders for full HTTP Range seeking support
app.mount("/media/accessible", StaticFiles(directory=OUTPUT_DIR), name="accessible_media")
app.mount("/media/tts", StaticFiles(directory=TTS_DIR), name="tts_media")
app.mount("/media/video", StaticFiles(directory=BASE_DIR), name="video_media")

# Frontends
@app.get("/")
def kiosk_page():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

@app.get("/editor")
def editor_page():
    return FileResponse(os.path.join(BASE_DIR, "static", "editor.html"))

# Static files mount
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
