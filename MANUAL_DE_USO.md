# Manual de Uso · MUSA Audiodescripción
### Guía Rápida para el Equipo de Trabajo

Bienvenido/a al gestor de audiodescripción **MUSA**. Esta herramienta permite generar, revisar, sincronizar y exportar vídeos y pistas de audiodescripción accesibles para personas con discapacidad visual en exposiciones y salas de museo.

---

## 1. Acceso a la Plataforma

Puedes acceder desde cualquier navegador web moderno (Chrome, Firefox, Safari, Edge):
- **En la nube (Render)**: Utiliza el enlace web proporcionado para el proyecto.
- **En local**: `http://localhost:8000/`

> [!TIP]
> Si alguna vez no ves los cambios más recientes tras una actualización, haz una recarga forzada de caché: **`Ctrl + F5`** (Windows) o **`Cmd + Shift + R`** (Mac).

---

## 2. Gestión de Vídeos (Carga, Cambio y Borrado)

En la barra superior tienes las opciones para gestionar los archivos audiovisuales:

### A. Subir un nuevo vídeo
1. Haz clic en el botón superior **`+ Cargar / Gestionar Vídeos`**.
2. Arrastra tu archivo de vídeo al recuadro o haz clic para seleccionarlo de tu ordenador.
3. Formatos soportados: **MP4, MOV, WEBM, M4V**.
4. Una vez completada la subida, el vídeo se configurará automáticamente como el proyecto activo.

### B. Cambiar entre vídeos existentes
- Usa el desplegable **"Vídeo en edición"** en la barra superior, o abre la ventana **`+ Cargar / Gestionar Vídeos`** y pulsa en **"Cargar"** junto al vídeo que desees.

### C. Borrar vídeos para no saturar espacio en disco
Para mantener el servidor limpio y evitar consumir el almacenamiento:
1. Haz clic en el botón **`🗑️ Borrar Vídeo`** de la barra superior (o pulsa **"🗑️ Borrar"** en la lista de vídeos del gestor).
2. Verás una ventana de confirmación indicando el vídeo a eliminar.
3. Pulsa **`Sí, Eliminar Definitivamente`**.
4. **¿Qué se elimina automáticamente?**
   - El archivo de vídeo original subido.
   - Todas las locuciones de voz TTS generadas.
   - El guion de marcas de tiempo guardado.
   - Los vídeos renderizados y las pistas exportadas asociadas.
   - La barra de estado te informará de cuántos **MB exactos** se han liberado en el servidor.

*(Nota: El documental demo inicial está protegido como plantilla base para garantizar que el sistema nunca quede vacío).*

---

## 3. Proceso de Audiodescripción (Paso a Paso)

Una vez seleccionado tu vídeo, el flujo de trabajo recomendado es:

### Paso 1: Generación Automática con IA
- En la columna izquierda, pulsa el botón **`Generar Audiodescripción con IA`**.
- El motor (Gemini Multimodal) analiza la imagen y el audio del vídeo, localiza los silencios o fondos musicales donde no hay diálogo y redacta automáticamente las descripciones visuales en español neutro.
- Las locuciones se sintetizan automáticamente en la voz seleccionada.

### Paso 2: Revisión y Edición Fina
En la columna derecha tienes el listado de intervenciones:
- **Reproducción sincronizada**: Al dar al Play al vídeo, el sistema reproduce en tiempo real las voces de audiodescripción en sus segundos exactos bajando sutilmente el audio de fondo (*ducking*).
- **Modificar textos**: Puedes corregir o ampliar el texto descriptivo de cualquier tarjeta.
- **Ajustar tiempos**: Si una locución empieza antes o después, modifica los campos de **Inicio** y **Fin** (`MM:SS.mmm`).
- **Escuchar audio individual**: Pulsa el botón **`🔊 Escuchar`** en cualquier tarjeta para oír cómo suena esa intervención.
- **Regenerar voz de una tarjeta**: Si cambias el texto de una tarjeta, pulsa **`Sintetizar Voz`** en esa tarjeta para actualizar su locución.
- **Añadir intervención manual**: Pulsa **`+ Añadir Intervención`** para insertar una marca en el punto temporal que desees.
- **Eliminar tarjeta**: Si una intervención no es necesaria, haz clic en el icono de papelera de esa tarjeta.
- **Guardar**: Pulsa en **`💾 Guardar Cambios`** para conservar todo en el servidor.

### Paso 3: Selección de Voz
Puedes elegir entre dos voces neurales ultra naturales de alta calidad:
- **Álvaro** (Voz española masculina)
- **Elvira** (Voz española femenina)
*(Si cambias de voz para todo el proyecto, pulsa el botón **"Sintetizar Todas las Voces"** para regenerar todas las pistas en bloque).*

---

## 4. Exportación y Entregables para el Museo

En la parte inferior de la columna izquierda dispones de la sección de **Exportación**:

### Opción A: Vídeo Final Accesible (MP4)
- Pulsa **`Renderizar Vídeo Accesible con Ducking`**.
- El servidor mezcla el vídeo con la audiodescripción, aplicando atenuación automática de fondo y generando subtítulos descriptivos estandarizados (`.vtt`).
- Al finalizar, pulsa **`Descargar Vídeo Accesible (.mp4)`**.

### Opción B: Pistas de Audio Profesionales
Ideales para sistemas de audioguías de sala o postproducción:
1. **Pista Aislada (Solo Voz AD sincro)**:
   - Archivo con la voz descriptiva en sus tiempos exactos y silencios en el resto.
   - Disponible en **WAV** (máxima calidad sin compresión) o **MP3**.
2. **Pista de Mezcla Completa**:
   - Audio íntegro del documental + voz de audiodescripción con ducking aplicado.
   - Disponible en **WAV** o **MP3**.

---

## 5. Atajos y Consejos Rápidos

- `Espacio`: Pausar / Reanudar el vídeo.
- `Clic en la barra de tiempo`: Salta directamente a ese momento del vídeo.
- Para verificar el espacio ocupado, abre **`+ Cargar / Gestionar Vídeos`** y observa la etiqueta superior que muestra el peso total acumulado en disco.
