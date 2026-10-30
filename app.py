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
    export_full_mixed_audio_track,
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

def get_video_safe_name(video_path: str) -> str:
    if not video_path:
        return ""
    base = os.path.splitext(os.path.basename(video_path))[0]
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base)

def get_cues_filepath(video_path: str) -> str:
    safe_name = get_video_safe_name(video_path)
    if "pajarillo" in safe_name.lower():
        return os.path.join(DATA_DIR, "ad_cues.json")
    return os.path.join(DATA_DIR, f"{safe_name}_cues.json")

def load_cues(video_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = video_path or state["current_video"]
    data_file = get_cues_filepath(path)
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                cues = json.load(f)
                for cue in cues:
                    if cue.get("audio_file"):
                        fname = os.path.basename(cue["audio_file"])
                        local_path = os.path.join(TTS_DIR, fname)
                        if os.path.exists(local_path):
                            cue["audio_file"] = local_path
                return cues
        except Exception:
            return []
    return []

def save_cues_to_disk(cues: List[Dict[str, Any]], video_path: Optional[str] = None):
    path = video_path or state["current_video"]
    data_file = get_cues_filepath(path)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(cues, f, ensure_ascii=False, indent=2)

def get_accessible_video_path(video_path: str) -> str:
    safe_name = get_video_safe_name(video_path)
    target = os.path.join(OUTPUT_DIR, f"{safe_name}_accesible.mp4")
    if not os.path.exists(target):
        alt = os.path.join(OUTPUT_DIR, f"{safe_name.replace('_demo', '')}_accesible.mp4")
        if os.path.exists(alt):
            return alt
    return target

def get_audio_track_paths(video_path: str) -> Dict[str, Dict[str, str]]:
    safe_name = get_video_safe_name(video_path)
    return {
        "isolated": {
            "wav": os.path.join(OUTPUT_DIR, f"{safe_name}_audiodescripcion_AISLADA.wav"),
            "mp3": os.path.join(OUTPUT_DIR, f"{safe_name}_audiodescripcion_AISLADA.mp3")
        },
        "mixed": {
            "wav": os.path.join(OUTPUT_DIR, f"{safe_name}_audio_MEZCLA_COMPLETA.wav"),
            "mp3": os.path.join(OUTPUT_DIR, f"{safe_name}_audio_MEZCLA_COMPLETA.mp3")
        }
    }

def get_video_disk_usage(video_path: str) -> Dict[str, Any]:
    total_bytes = 0
    if not video_path:
        return {"total_bytes": 0, "total_mb": 0.0}

    # 1. Video source file
    if os.path.exists(video_path):
        try:
            total_bytes += os.path.getsize(video_path)
        except Exception:
            pass

    safe_name = get_video_safe_name(video_path)

    # 2. Cues JSON in data/
    cues_file = get_cues_filepath(video_path)
    if os.path.exists(cues_file):
        try:
            total_bytes += os.path.getsize(cues_file)
        except Exception:
            pass

    # 3. Output files matching safe_name
    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            p = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(p):
                if f.startswith(safe_name) or (safe_name != "ad" and safe_name in f):
                    try:
                        total_bytes += os.path.getsize(p)
                    except Exception:
                        pass

    # 4. TTS audio files in output/tts
    if os.path.exists(TTS_DIR):
        for f in os.listdir(TTS_DIR):
            if f.startswith(f"cue_{safe_name}_"):
                p = os.path.join(TTS_DIR, f)
                if os.path.isfile(p):
                    try:
                        total_bytes += os.path.getsize(p)
                    except Exception:
                        pass

    return {
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 1)
    }

def list_available_videos():
    videos = []
    # Check default root videos
    for f in sorted(os.listdir(BASE_DIR)):
        if f.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
            p = os.path.join(BASE_DIR, f)
            is_def = (f == os.path.basename(DEFAULT_VIDEO))
            usage = get_video_disk_usage(p)
            size_mb = round(os.path.getsize(p) / (1024 * 1024), 1) if os.path.exists(p) else 0.0
            videos.append({
                "filename": f,
                "path": p,
                "is_default": is_def,
                "size_mb": size_mb,
                "total_mb": usage["total_mb"],
                "can_delete": not is_def
            })
    # Check uploads
    if os.path.exists(UPLOADS_DIR):
        for f in sorted(os.listdir(UPLOADS_DIR)):
            if f.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
                p = os.path.join(UPLOADS_DIR, f)
                usage = get_video_disk_usage(p)
                size_mb = round(os.path.getsize(p) / (1024 * 1024), 1) if os.path.exists(p) else 0.0
                videos.append({
                    "filename": f,
                    "path": p,
                    "is_default": False,
                    "size_mb": size_mb,
                    "total_mb": usage["total_mb"],
                    "can_delete": True
                })
    return videos

@app.get("/api/project")
def get_project_data():
    video_path = state["current_video"]
    if (not video_path or not os.path.exists(video_path)) and os.path.exists(DEFAULT_VIDEO):
        video_path = DEFAULT_VIDEO
        state["current_video"] = video_path

    video_info = None
    accessible_info = None
    audio_tracks = {
        "isolated": {"wav_available": False, "wav_url": None, "mp3_available": False, "mp3_url": None},
        "mixed": {"wav_available": False, "wav_url": None, "mp3_available": False, "mp3_url": None}
    }
    cues = []

    if video_path and os.path.exists(video_path):
        try:
            video_info = get_video_info(video_path)
            if video_path.startswith(UPLOADS_DIR):
                video_info["url"] = f"/media/uploads/{os.path.basename(video_path)}"
            else:
                video_info["url"] = f"/media/video/{os.path.basename(video_path)}"
        except Exception as e:
            video_info = {"error": str(e), "filename": os.path.basename(video_path)}

        accessible_path = get_accessible_video_path(video_path)
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
            "isolated": {
                "wav_available": os.path.exists(audio_paths["isolated"]["wav"]),
                "wav_url": f"/media/accessible/{os.path.basename(audio_paths['isolated']['wav'])}" if os.path.exists(audio_paths["isolated"]["wav"]) else None,
                "mp3_available": os.path.exists(audio_paths["isolated"]["mp3"]),
                "mp3_url": f"/media/accessible/{os.path.basename(audio_paths['isolated']['mp3'])}" if os.path.exists(audio_paths["isolated"]["mp3"]) else None
            },
            "mixed": {
                "wav_available": os.path.exists(audio_paths["mixed"]["wav"]),
                "wav_url": f"/media/accessible/{os.path.basename(audio_paths['mixed']['wav'])}" if os.path.exists(audio_paths["mixed"]["wav"]) else None,
                "mp3_available": os.path.exists(audio_paths["mixed"]["mp3"]),
                "mp3_url": f"/media/accessible/{os.path.basename(audio_paths['mixed']['mp3'])}" if os.path.exists(audio_paths["mixed"]["mp3"]) else None
            }
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

def perform_video_deletion(filename: str):
    matching_video = None
    for v in list_available_videos():
        if v["filename"] == filename:
            matching_video = v
            break

    if not matching_video:
        raise HTTPException(status_code=404, detail=f"El vídeo '{filename}' no existe en el sistema.")

    video_path = matching_video["path"]
    is_default = matching_video["is_default"]

    if is_default:
        raise HTTPException(
            status_code=400,
            detail="El vídeo de muestra predeterminado está protegido como plantilla del sistema y no puede eliminarse. Puedes eliminar cualquier otro vídeo subido."
        )

    usage = get_video_disk_usage(video_path)
    freed_mb = usage["total_mb"]
    safe_name = get_video_safe_name(video_path)

    # 1. Clean cues and referenced TTS files
    cues_file = get_cues_filepath(video_path)
    if os.path.exists(cues_file):
        try:
            with open(cues_file, "r", encoding="utf-8") as f:
                cues_data = json.load(f)
                for c in cues_data:
                    af = c.get("audio_file")
                    if af and os.path.exists(af):
                        try:
                            os.remove(af)
                        except Exception:
                            pass
        except Exception:
            pass
        try:
            os.remove(cues_file)
        except Exception:
            pass

    # 2. Clean TTS files matching safe_name
    if os.path.exists(TTS_DIR):
        for f in os.listdir(TTS_DIR):
            if f.startswith(f"cue_{safe_name}_"):
                try:
                    os.remove(os.path.join(TTS_DIR, f))
                except Exception:
                    pass

    # 3. Clean output files matching safe_name
    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            p = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(p):
                if f.startswith(safe_name) or (safe_name != "ad" and safe_name in f):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    # 4. Remove source video file
    if os.path.exists(video_path):
        try:
            os.remove(video_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al eliminar archivo del vídeo: {str(e)}")

    # 5. Switch current video if active was deleted
    if state["current_video"] == video_path:
        remaining = list_available_videos()
        if remaining:
            state["current_video"] = remaining[0]["path"]
            state["status_message"] = f"Vídeo '{filename}' eliminado con éxito. Liberados {freed_mb} MB."
        else:
            state["current_video"] = ""
            state["status_message"] = f"Vídeo '{filename}' eliminado. Liberados {freed_mb} MB."

    return {
        "success": True,
        "freed_mb": freed_mb,
        "deleted_filename": filename,
        "project": get_project_data()
    }

@app.post("/api/delete_video")
def delete_video_post(filename: str = Form(...)):
    return perform_video_deletion(filename)

@app.delete("/api/video/{filename}")
def delete_video_delete(filename: str):
    return perform_video_deletion(filename)

@app.post("/api/clean_video_exports")
def clean_video_exports_endpoint(filename: str = Form(...)):
    matching_video = None
    for v in list_available_videos():
        if v["filename"] == filename:
            matching_video = v
            break

    if not matching_video:
        raise HTTPException(status_code=404, detail="El vídeo especificado no existe.")

    video_path = matching_video["path"]
    safe_name = get_video_safe_name(video_path)
    freed_bytes = 0

    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            p = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(p):
                if f.startswith(safe_name) or (safe_name != "ad" and safe_name in f):
                    try:
                        freed_bytes += os.path.getsize(p)
                        os.remove(p)
                    except Exception:
                        pass

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    state["status_message"] = f"Archivos exportados de '{filename}' eliminados ({freed_mb} MB liberados)."
    return {"success": True, "freed_mb": freed_mb, "project": get_project_data()}

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
            prefix = get_video_safe_name(video_path)
            cues = asyncio.run(synthesize_all_cues(cues, voice=state["selected_voice"], output_dir=TTS_DIR, prefix=prefix))
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
    prefix = get_video_safe_name(state["current_video"])
    updated = await synthesize_cue_audio(cue_dict, voice=chosen_voice, output_dir=TTS_DIR, prefix=prefix)

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
        prefix = get_video_safe_name(state["current_video"])
        updated_cues = await synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR, prefix=prefix)
        save_cues_to_disk(updated_cues)
        state["status_message"] = "Síntesis completada."
        return {"status": "ok", "cues": updated_cues}
    finally:
        state["is_synthesizing"] = False

@app.post("/api/export_audio_track")
def export_audio_track_endpoint(background_tasks: BackgroundTasks, format: str = Form("wav"), mode: str = Form("isolated")):
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
                prefix = get_video_safe_name(video_path)
                asyncio.run(synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR, prefix=prefix))
                save_cues_to_disk(cues)

            info = get_video_info(video_path)
            target_ext = "wav" if format.lower() == "wav" else "mp3"
            is_isolated = (mode.lower() == "isolated")
            audio_paths = get_audio_track_paths(video_path)
            target_path = audio_paths["isolated"][target_ext] if is_isolated else audio_paths["mixed"][target_ext]

            desc = "AISLADA (solo voz sincro)" if is_isolated else "MEZCLA COMPLETA (con fondo y ducking)"
            state["status_message"] = f"Generando pista {target_ext.upper()} {desc}..."

            if is_isolated:
                export_ad_only_audio_track(
                    video_duration=info["duration"],
                    cues=cues,
                    output_audio_path=target_path
                )
            else:
                export_full_mixed_audio_track(
                    video_path=video_path,
                    cues=cues,
                    output_audio_path=target_path
                )

            state["status_message"] = f"Pista {target_ext.upper()} {desc} generada con éxito."
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
                prefix = get_video_safe_name(video_path)
                asyncio.run(synthesize_all_cues(cues, voice=chosen_voice, output_dir=TTS_DIR, prefix=prefix))
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
                export_ad_only_audio_track(info["duration"], cues, tracks["isolated"]["wav"])
                export_ad_only_audio_track(info["duration"], cues, tracks["isolated"]["mp3"])
                export_full_mixed_audio_track(video_path, cues, tracks["mixed"]["wav"])
                export_full_mixed_audio_track(video_path, cues, tracks["mixed"]["mp3"])
            except Exception as ex:
                print("Info post-exportación audio:", ex)

            state["status_message"] = "Vídeo final para el museo renderizado con éxito."
        except Exception as e:
            state["status_message"] = f"Error en exportación: {str(e)}"
        finally:
            state["is_exporting"] = False

    background_tasks.add_task(run_export)
    return {"status": "started", "message": "Renderizado de vídeo iniciado en segundo plano."}

# Direct Download Endpoints with Attachment Headers
@app.get("/api/download/video")
def download_video():
    video_path = state["current_video"]
    target_video = get_accessible_video_path(video_path)
    if os.path.exists(target_video):
        filename = os.path.basename(target_video)
        return FileResponse(
            target_video,
            media_type="video/mp4",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    raise HTTPException(status_code=404, detail="El vídeo renderizado no está disponible aún.")

@app.get("/api/download/audio")
def download_audio(format: str = "wav", mode: str = "isolated"):
    video_path = state["current_video"]
    tracks = get_audio_track_paths(video_path)
    ext = "wav" if format.lower() == "wav" else "mp3"
    is_isolated = (mode.lower() == "isolated")
    target_audio = tracks["isolated"][ext] if is_isolated else tracks["mixed"][ext]
    if os.path.exists(target_audio):
        filename = os.path.basename(target_audio)
        media_type = "audio/wav" if ext == "wav" else "audio/mpeg"
        return FileResponse(
            target_audio,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    raise HTTPException(status_code=404, detail=f"La pista {ext.upper()} no está disponible aún.")

# Media routes
app.mount("/media/accessible", StaticFiles(directory=OUTPUT_DIR), name="accessible_media")
app.mount("/media/tts", StaticFiles(directory=TTS_DIR), name="tts_media")
app.mount("/media/video", StaticFiles(directory=BASE_DIR), name="video_media")
app.mount("/media/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads_media")

# Frontends - La aplicación principal es el Estudio Profesional de Audiodescripción
@app.get("/")
def home_page():
    return FileResponse(os.path.join(BASE_DIR, "static", "editor.html"))

@app.get("/editor")
def editor_page():
    return FileResponse(os.path.join(BASE_DIR, "static", "editor.html"))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
