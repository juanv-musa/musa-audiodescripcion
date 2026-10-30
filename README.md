# MUSA · Gestor Universal de Audiodescripción Accesible
### Musaraña · Accesibilidad Audiovisual para Museos y Espacios Culturales

Sistema integral de accesibilidad audiovisual para personas con discapacidad visual o baja visión. Permite analizar vídeos con inteligencia artificial multimodal, redactar y sincronizar descripciones visuales en los silencios del contenido, sintetizar voces neurales de alta naturalidad y exportar vídeos y pistas de audio listas para emisión o sala expositiva.

---

## 📖 Manual de Uso para el Equipo

Para una guía paso a paso pensada para operadores y compañeros de equipo, consulta el archivo:
👉 **[MANUAL_DE_USO.md](./MANUAL_DE_USO.md)**

---

## 🚀 Capacidades Principales

1. **Gestión Multivídeo y Almacenamiento**:
   - Subida y gestión de cualquier vídeo expositivo (**MP4, MOV, WEBM, M4V**).
   - Panel de gestión de almacenamiento con cálculo en tiempo real de los MB ocupados.
   - **Herramienta de borrado seguro (`🗑️ Borrar Vídeo`)**: elimina el vídeo fuente, sus pistas de voz, guiones y renders exportados para no saturar el servidor ni la nube.

2. **Detección y Redacción Asistida por IA**:
   - Análisis con Gemini Multimodal para detectar momentos libres de diálogo y narrar los elementos visuales clave en español (norma UNE 153020).

3. **Locución Neural de Alta Naturalidad (Edge-TTS)**:
   - Voces naturales en español de España: **Álvaro** (masculina) y **Elvira** (femenina).
   - Síntesis inmediata por intervención o en lote para todo el proyecto.

4. **Estudio de Edición y Línea de Tiempo**:
   - Reproductor sincronizado con slots visuales en la línea de tiempo.
   - Edición de texto y ajuste de tiempos de inicio/fin en milisegundos.
   - Preescucha individual de audios.

5. **Exportación Multipropósito**:
   - **Vídeo final accesible (MP4)**: renderizado con *audio ducking* (atenuación automática de la música durante la voz) y subtítulos `.vtt`.
   - **Pistas de audio profesionales**:
     - *Pista Aislada (Solo Voz AD sincronizada)* en WAV o MP3 para sistemas de audio inalámbrico de museo o edición en DAW.
     - *Pista con Mezcla Completa* en WAV o MP3 con ducking integrado.

---

## 🛠️ Puesta en Marcha en Local

Para arrancar el servidor en local:

```bash
./iniciar.sh
```

O directamente mediante el entorno virtual:

```bash
source .venv/bin/activate
python app.py
```

La aplicación estará accesible en:
- `http://localhost:8000/`

---

## ☁️ Despliegue en la Nube (Render / Docker)

El proyecto incluye configuración nativa para Render (`render.yaml` y `Dockerfile`):
- Se despliega automáticamente mediante Webhook con cada `git push origin main`.
- Utiliza FastAPI, Uvicorn y FFmpeg para el procesamiento de medios.

---

## 📁 Estructura del Proyecto

- `app.py`: Servidor backend en FastAPI (API REST, gestión de vídeos, streaming y descargas).
- `core/ad_engine.py`: Motor de audiodescripción, Gemini Multimodal, Edge-TTS y renderizado FFmpeg.
- `static/`:
  - `editor.html`: Interfaz del Estudio Universal de Audiodescripción.
  - `css/editor.css`: Estilos visuales con identidad Musaraña.
  - `js/editor.js`: Lógica interactiva del reproductor, timeline y llamadas a API.
- `uploads/`: Directorio donde se almacenan los vídeos subidos por los usuarios.
- `data/`: Guiones JSON con las marcas de tiempo y textos de audiodescripción.
- `output/`:
  - `tts/`: Archivos MP3 de las intervenciones sintetizadas.
  - Vídeos y pistas de audio exportadas (`.mp4`, `.wav`, `.mp3`, `.vtt`).
- `MANUAL_DE_USO.md`: Manual operativo para el equipo.
