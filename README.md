# MUSA · Sistema de Audiodescripción Accesible para Museos
### Centro de Interpretación Santuario Ibérico de “El Pajarillo” (Huelma)

Sistema integral de accesibilidad audiovisual para personas ciegas y con baja visión, diseñado específicamente para salas audiovisuales y pantallas interactivas de museos (Kioscos y TV 65").

---

## 🚀 ¿Cómo funciona?

El sistema cuenta con **dos interfaces**:

1. **Pantalla del Museo (`http://localhost:8000/`)**:
   - Diseñada para la televisión táctil de 65" o tótem de la sala del museo en servidor local.
   - Selector en pantalla gigante:
     - 🔊 **Versión Estándar**: Reproducción documental convencional con la locución original.
     - 👁️‍🗨️ **Con Audiodescripción (Accesible)**: Reproducción inclusiva con la capa de voz descriptiva sincronizada en los silencios, aplicando *audio ducking* sutil a la música de fondo.
   - Subtítulos descriptivos opcionales de alto contraste (norma UNE 153020).
   - Accesibilidad por teclado / pulsadores:
     - `Espacio`: Reproducir / Pausar
     - `Flechas izquierda/derecha`: Retroceder / Avanzar 5s
     - `Tecla A`: Conmutar modo Audiodescripción
     - `Tecla C`: Mostrar / Ocultar subtítulos
     - `Tecla F`: Pantalla completa

2. **Estudio de Audiodescripción IA (`http://localhost:8000/editor`)**:
   - Diseñado para ti y tu equipo técnico para revisar, ajustar y dar el visto bueno:
     - **Análisis con Gemini**: Escucha el vídeo, detecta los momentos de pausa o música y redacta las descripciones visuales exactas en español de España.
     - **Síntesis Neural Edge-TTS**: Voces ultra naturales sin coste de API (Álvaro o Elvira).
     - **Editor interactivo**: Puedes retocar cualquier palabra, ajustar segundos de inicio/fin y escuchar la muestra con un solo clic.
     - **Renderizado Final FFmpeg**: Genera el vídeo final accesible con ducking automático de audio y el archivo de subtítulos `.vtt`.

---

## 🛠️ Puesta en Marcha en el Servidor Local

Para arrancar el servidor en cualquier momento:

```bash
./iniciar.sh
```

El servidor quedará disponible en la red local del museo (por ejemplo: `http://192.168.1.X:8000`).

---

## 📁 Estructura del Proyecto

- `app.py`: Servidor backend en FastAPI con soporte de streaming HTTP Range (206 Partial Content).
- `core/ad_engine.py`: Motor de audiodescripción, conexión con Gemini, síntesis de voz y filtros complejos de mezcla FFmpeg.
- `static/`:
  - `index.html` & `css/museum.css` & `js/museum.js`: Reproductor accesible del museo con la identidad gráfica corporativa del Santuario de El Pajarillo.
  - `editor.html` & `css/editor.css` & `js/editor.js`: Panel de validación y autoría.
- `data/ad_cues.json`: Registro de marcas de tiempo y textos de audiodescripción.
- `output/`:
  - `DOCUMENTAL_EL_PAJARILLO_accesible.mp4`: Vídeo final renderizado para la pantalla del museo.
  - `DOCUMENTAL_EL_PAJARILLO_accesible.vtt`: Subtítulos accesibles estandarizados.
  - `tts/`: Archivos de voz sintetizada.
