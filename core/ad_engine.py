import os
import json
import re
import asyncio
import subprocess
import shutil
from typing import List, Dict, Any, Optional
import static_ffmpeg
import edge_tts
from dotenv import load_dotenv

# Ensure ffmpeg/ffprobe from static_ffmpeg are available in PATH
static_ffmpeg.add_paths()

load_dotenv()

DEFAULT_VOICE = "es-ES-AlvaroNeural"  # Natural male Spanish voice
ALT_VOICE = "es-ES-ElviraNeural"     # Natural female Spanish voice

def get_ffmpeg_binaries():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        static_ffmpeg.add_paths()
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
    return ffmpeg, ffprobe

def get_video_info(video_path: str) -> Dict[str, Any]:
    _, ffprobe = get_ffmpeg_binaries()
    if not ffprobe:
        raise RuntimeError("ffprobe no está disponible.")
    
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    
    duration = float(data.get("format", {}).get("duration", 0.0))
    size = int(data.get("format", {}).get("size", 0))
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    
    width = video_stream.get("width") if video_stream else 0
    height = video_stream.get("height") if video_stream else 0
    fps_str = video_stream.get("r_frame_rate", "25/1") if video_stream else "25/1"
    try:
        num, den = map(int, fps_str.split("/"))
        fps = round(num / den, 2)
    except Exception:
        fps = 25.0
        
    return {
        "filename": os.path.basename(video_path),
        "duration": duration,
        "duration_formatted": format_time(duration),
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": audio_stream is not None
    }

def format_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def parse_time_to_seconds(time_str: str) -> float:
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(time_str)

def get_audio_duration(audio_path: str) -> float:
    _, ffprobe = get_ffmpeg_binaries()
    cmd = [
        ffprobe, "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 0.0

async def synthesize_cue_audio(cue: Dict[str, Any], voice: str = DEFAULT_VOICE, output_dir: str = "output/tts", prefix: Optional[str] = None) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    cue_id = cue.get("id", 1)
    if prefix:
        safe_prefix = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in prefix)
        filename = f"cue_{safe_prefix}_{cue_id}_{voice}.mp3"
    else:
        filename = f"cue_{cue_id}_{voice}.mp3"
    filepath = os.path.join(output_dir, filename)
    
    text = cue.get("text", "").strip()
    if not text:
        cue["audio_url"] = None
        cue["audio_duration"] = 0.0
        cue["audio_file"] = None
        return cue

    # Remove old/corrupted file if exists
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filepath)
        
        # Verify file was written properly and has non-zero size
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 200:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise RuntimeError(f"Error generando audio para la intervención #{cue_id}: archivo generado vacío o incompleto.")

        audio_dur = get_audio_duration(filepath)
        cue["audio_url"] = f"/media/tts/{filename}"
        cue["audio_duration"] = round(audio_dur, 2)
        cue["audio_file"] = filepath
        return cue
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        cue["audio_url"] = None
        cue["audio_duration"] = 0.0
        cue["audio_file"] = None
        raise RuntimeError(f"Fallo en síntesis de voz para #{cue_id}: {str(e)}")

async def synthesize_all_cues(cues: List[Dict[str, Any]], voice: str = DEFAULT_VOICE, output_dir: str = "output/tts", prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    tasks = [synthesize_cue_audio(c, voice, output_dir, prefix=prefix) for c in cues]
    return await asyncio.gather(*tasks)

def generate_ad_cues_with_gemini(video_path: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    from google import genai
    
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY no encontrada. Configúrala en el archivo .env.")
    
    client = genai.Client(api_key=key)
    
    # Check if this video has already been uploaded to Gemini File API
    base_name = os.path.basename(video_path)
    file_ref = None
    try:
        for f in client.files.list():
            if f.display_name == base_name and f.state.name == "ACTIVE":
                file_ref = f
                break
    except Exception:
        pass
    
    if not file_ref:
        print(f"Subiendo {video_path} a Gemini Files API...")
        file_ref = client.files.upload(file=video_path, config={"display_name": base_name})
        import time
        while file_ref.state.name == "PROCESSING":
            time.sleep(2)
            file_ref = client.files.get(name=file_ref.name)
        
        if file_ref.state.name == "FAILED":
            raise RuntimeError("El procesamiento del vídeo en Gemini falló.")

    is_pajarillo = "pajarillo" in base_name.lower()
    if is_pajarillo:
        specific_context = """Estás elaborando la audiodescripción completa para el documental audiovisual expuesto en el Centro de Interpretación Santuario Ibérico de El Pajarillo.
Describe los elementos visuales clave: planos aéreos del entorno, río Jandulilla, cerros, excavaciones históricas, reconstrucción virtual 3D del santuario, y las esculturas íberas (la cabeza de lobo, los leones, el guerrero, etc.)."""
    else:
        specific_context = f"""Estás elaborando la audiodescripción completa para el vídeo '{base_name}'.
Describe los elementos visuales clave: acciones de los personajes o presentadores, cambios de plano, escenarios, detalles narrativos y el contenido de rótulos o textos informativos en pantalla."""

    prompt = f"""Eres un especialista de referencia en Audiodescripción (AD) según la norma española UNE 153020 para personas ciegas en museos y centros de interpretación.
{specific_context}

Instrucciones precisas:
1. Analiza el audio y el vídeo con detalle a lo largo de toda la duración.
2. Identifica los momentos ideales para insertar audiodescripción:
   - Intervalos de música inicial y pausas entre intervenciones de los expertos o narradores.
   - En las apariciones de personas/entrevistados, describe quién aparece (rótulos con nombres y cargos).
   - Describe con objetividad y claridad lo que ocurre visualmente en pantalla en los huecos de voz disponibles.
3. Sé conciso, objetivo y natural. No pises la locución de los narradores si no hay espacio suficiente.
4. Para cada intervención, calcula con precisión el segundo de inicio y de fin.

Devuelve EXCLUSIVAMENTE un array JSON con esta estructura exacta (sin texto previo ni markdown):
[
  {{
    "id": 1,
    "start": "00:02",
    "end": "00:13",
    "start_seconds": 2.0,
    "end_seconds": 13.0,
    "text": "Descripción objetiva de lo que se ve en pantalla adaptada a la duración disponible."
  }}
]
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[file_ref, prompt]
    )
    
    raw = response.text or ""
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        raise ValueError(f"No se pudo extraer la lista de audiodescripción de la respuesta de Gemini: {raw[:300]}")
    
    cues = json.loads(match.group(0))
    # Normalize cues
    for idx, cue in enumerate(cues, 1):
        cue["id"] = idx
        if "start_seconds" not in cue and "start" in cue:
            cue["start_seconds"] = parse_time_to_seconds(cue["start"])
        if "end_seconds" not in cue and "end" in cue:
            cue["end_seconds"] = parse_time_to_seconds(cue["end"])
        if "start" not in cue:
            cue["start"] = format_time(cue.get("start_seconds", 0.0))
        if "end" not in cue:
            cue["end"] = format_time(cue.get("end_seconds", 0.0))
            
    return cues

def export_accessible_video(video_path: str, cues: List[Dict[str, Any]], output_video_path: str, ducking_attenuation_db: float = -12.0) -> str:
    ffmpeg, _ = get_ffmpeg_binaries()
    if not ffmpeg:
        raise RuntimeError("ffmpeg no está disponible.")
    
    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
    
    # Filter valid cues with existing and non-empty audio files
    valid_cues = []
    missing_cues = []
    for c in cues:
        f = c.get("audio_file")
        if f and os.path.exists(f) and os.path.getsize(f) > 500:
            valid_cues.append(c)
        else:
            missing_cues.append(str(c.get("id", "?")))

    if missing_cues:
        raise ValueError(
            f"Las siguientes intervenciones no tienen audio generado todavía: #{', #'.join(missing_cues)}. "
            "Por favor, espera a que termine de sintetizar la voz o pulsa 'Sintetizar' antes de exportar."
        )

    if not valid_cues:
        raise ValueError("No hay pistas de audio sintetizadas para mezclar.")

    # Build complex filter:
    # 1. Delay each cue to start_seconds in milliseconds
    # 2. amix all cues into single AD stream [ad_stream]
    # 3. Create ducking envelope on original audio [orig_ducked]
    # 4. Mix [orig_ducked] with [ad_stream]
    
    inputs = ["-i", video_path]
    filter_parts = []
    amix_inputs = []
    
    for i, cue in enumerate(valid_cues):
        inputs.extend(["-i", cue["audio_file"]])
        delay_ms = int(cue.get("start_seconds", 0.0) * 1000)
        input_idx = i + 1
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},volume=1.25[delayed_{i}]")
        amix_inputs.append(f"[delayed_{i}]")
    
    # Mix all delayed AD cues together
    if len(amix_inputs) == 1:
        filter_parts.append(f"{amix_inputs[0]}asplit=2[ad_sc][ad_mix]")
    else:
        joined = "".join(amix_inputs)
        filter_parts.append(f"{joined}amix=inputs={len(amix_inputs)}:dropout_transition=0:normalize=0,asplit=2[ad_sc][ad_mix]")
    
    # Audio ducking: duck original audio whenever AD voice is speaking
    filter_parts.append("[0:a][ad_sc]sidechaincompress=threshold=0.08:ratio=6:attack=30:release=400[orig_ducked]")
    filter_parts.append("[orig_ducked][ad_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[final_audio]")
    
    filter_str = ";".join(filter_parts)
    
    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "0:v",
        "-map", "[final_audio]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_video_path
    ]
    
    print("Ejecutando mezcla de audiodescripción con FFmpeg...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg error:", res.stderr)
        raise RuntimeError(f"Error al exportar vídeo con FFmpeg: {res.stderr[-500:]}")
        
    print(f"Vídeo accesible exportado con éxito en: {output_video_path}")
    
    # Also generate WebVTT file alongside the video
    vtt_path = output_video_path.rsplit(".", 1)[0] + ".vtt"
    generate_webvtt(cues, vtt_path)
    
    return output_video_path

def export_ad_only_audio_track(video_duration: float, cues: List[Dict[str, Any]], output_audio_path: str) -> str:
    """
    Genera una pista de audio única (Broadcast WAV/MP3) con la duración exacta del vídeo.
    Coloca cada intervención de audiodescripción en su segundo exacto y deja silencio en el resto.
    Lista para arrastrar y sincronizar a pista en Premiere Pro, DaVinci Resolve o Pro Tools.
    """
    ffmpeg, _ = get_ffmpeg_binaries()
    if not ffmpeg:
        raise RuntimeError("ffmpeg no está disponible.")

    os.makedirs(os.path.dirname(output_audio_path), exist_ok=True)

    valid_cues = []
    for c in cues:
        f = c.get("audio_file")
        if f and os.path.exists(f) and os.path.getsize(f) > 500:
            valid_cues.append(c)

    if not valid_cues:
        raise ValueError("No hay locuciones de audiodescripción sintetizadas para exportar.")

    # 1. Base input: silence generated with lavfi anullsrc matching video duration
    dur_str = f"{video_duration:.3f}"
    inputs = ["-f", "lavfi", "-t", dur_str, "-i", "anullsrc=r=48000:cl=stereo"]
    filter_parts = []
    amix_inputs = ["[0:a]"]

    for i, cue in enumerate(valid_cues):
        inputs.extend(["-i", cue["audio_file"]])
        delay_ms = int(cue.get("start_seconds", 0.0) * 1000)
        input_idx = i + 1
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},volume=1.0[delayed_{i}]")
        amix_inputs.append(f"[delayed_{i}]")

    joined = "".join(amix_inputs)
    filter_parts.append(f"{joined}amix=inputs={len(amix_inputs)}:duration=first:dropout_transition=0:normalize=0[audio_out]")

    filter_str = ";".join(filter_parts)

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[audio_out]"
    ]

    # Select codec based on extension
    if output_audio_path.lower().endswith(".wav"):
        cmd.extend(["-c:a", "pcm_s16le", "-ar", "48000"])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "48000"])

    cmd.append(output_audio_path)

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Error exportando pista de audio: {res.stderr[-500:]}")

    return output_audio_path

def generate_webvtt(cues: List[Dict[str, Any]], vtt_path: str):
    def vtt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    lines = ["WEBVTT - Audiodescripción Accesible · Musaraña Gestión Integral de Museos\n"]
    for cue in cues:
        start_sec = cue.get("start_seconds", 0.0)
        end_sec = cue.get("end_seconds", start_sec + 4.0)
        text = cue.get("text", "")
        lines.append(f"{cue.get('id', 1)}")
        lines.append(f"{vtt_time(start_sec)} --> {vtt_time(end_sec)}")
        lines.append(f"[AD]: {text}\n")
        
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def export_full_mixed_audio_track(video_path: str, cues: List[Dict[str, Any]], output_audio_path: str) -> str:
    """
    Genera la pista de audio con la MEZCLA COMPLETA:
    Audio original del vídeo + Voces de audiodescripción con atenuación automática (ducking).
    Ideal para escuchar el resultado sonoro completo o para audioguías.
    """
    ffmpeg, _ = get_ffmpeg_binaries()
    if not ffmpeg:
        raise RuntimeError("ffmpeg no está disponible.")

    os.makedirs(os.path.dirname(output_audio_path), exist_ok=True)

    valid_cues = []
    for c in cues:
        f = c.get("audio_file")
        if f and os.path.exists(f) and os.path.getsize(f) > 500:
            valid_cues.append(c)

    if not valid_cues:
        raise ValueError("No hay locuciones sintetizadas para mezclar.")

    inputs = ["-i", video_path]
    filter_parts = []
    amix_inputs = []

    for i, cue in enumerate(valid_cues):
        inputs.extend(["-i", cue["audio_file"]])
        delay_ms = int(cue.get("start_seconds", 0.0) * 1000)
        input_idx = i + 1
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},volume=1.25[delayed_{i}]")
        amix_inputs.append(f"[delayed_{i}]")

    if len(amix_inputs) == 1:
        filter_parts.append(f"{amix_inputs[0]}asplit=2[ad_sc][ad_mix]")
    else:
        joined = "".join(amix_inputs)
        filter_parts.append(f"{joined}amix=inputs={len(amix_inputs)}:dropout_transition=0:normalize=0,asplit=2[ad_sc][ad_mix]")

    filter_parts.append("[0:a][ad_sc]sidechaincompress=threshold=0.08:ratio=6:attack=30:release=400[orig_ducked]")
    filter_parts.append("[orig_ducked][ad_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[final_audio]")

    filter_str = ";".join(filter_parts)

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[final_audio]"
    ]

    if output_audio_path.lower().endswith(".wav"):
        cmd.extend(["-c:a", "pcm_s16le", "-ar", "48000"])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "48000"])

    cmd.append(output_audio_path)

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Error generando mezcla completa de audio: {res.stderr[-500:]}")

    return output_audio_path

def generate_webvtt(cues: List[Dict[str, Any]], vtt_path: str):
    def vtt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    lines = ["WEBVTT - Audiodescripción Accesible · Musaraña Gestión Integral de Museos\n"]
    for cue in cues:
        start_sec = cue.get("start_seconds", 0.0)
        end_sec = cue.get("end_seconds", start_sec + 4.0)
        text = cue.get("text", "")
        lines.append(f"{cue.get('id', 1)}")
        lines.append(f"{vtt_time(start_sec)} --> {vtt_time(end_sec)}")
        lines.append(f"[AD]: {text}\n")
        
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
