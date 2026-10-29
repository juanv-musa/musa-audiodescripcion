// ==========================================================================
// ESTUDIO DE AUDIODESCRIPCIÓN IA · LÓGICA DE CONTROL Y EDICIÓN
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("editor-video");
  const scrubberTrack = document.getElementById("scrubber-track");
  const scrubberFill = document.getElementById("scrubber-fill");
  const liveTime = document.getElementById("live-time");
  const btnPlay = document.getElementById("btn-play");
  const btnPause = document.getElementById("btn-pause");
  const cuesContainer = document.getElementById("cues-container");
  const btnAiGenerate = document.getElementById("btn-ai-generate");
  const btnExportFinal = document.getElementById("btn-export-final");
  const btnAddCue = document.getElementById("btn-add-cue");
  const btnSaveCues = document.getElementById("btn-save-cues");
  const selectVoice = document.getElementById("select-voice");
  const statusMessage = document.getElementById("status-message");

  // Meta fields
  const infoFilename = document.getElementById("info-filename");
  const infoDuration = document.getElementById("info-duration");
  const infoResolution = document.getElementById("info-resolution");
  const infoSize = document.getElementById("info-size");
  const infoFps = document.getElementById("info-fps");

  let cues = [];
  let pollInterval = null;
  let previewAudio = new Audio();

  async function loadProject() {
    try {
      const res = await fetch("/api/project");
      const data = await res.json();
      
      // Update video metadata
      if (data.video) {
        infoFilename.textContent = data.video.filename || "-";
        infoDuration.textContent = data.video.duration_formatted || "-";
        infoResolution.textContent = `${data.video.width}x${data.video.height}`;
        infoSize.textContent = `${data.video.size_mb} MB`;
        infoFps.textContent = `${data.video.fps} fps`;

        if (!video.src.endsWith(data.video.url)) {
          video.src = data.video.url;
        }
      }

      // Populate voices
      if (data.voices && selectVoice.children.length === 0) {
        selectVoice.innerHTML = "";
        data.voices.forEach(v => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = v.name;
          if (v.id === data.state.selected_voice) opt.selected = true;
          selectVoice.appendChild(opt);
        });
      }

      cues = data.cues || [];
      renderCues();
      updateStatus(data.state.status_message);

      // Check if background task is running
      if (data.state.is_analyzing || data.state.is_exporting || data.state.is_synthesizing) {
        startPolling();
      }
    } catch (e) {
      console.error("Error al cargar proyecto:", e);
      updateStatus("Error de conexión al cargar datos.");
    }
  }

  function updateStatus(msg) {
    statusMessage.textContent = msg || "Listo";
  }

  function startPolling() {
    if (pollInterval) return;
    btnAiGenerate.disabled = true;
    btnExportFinal.disabled = true;

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch("/api/project");
        const data = await res.json();
        updateStatus(data.state.status_message);

        if (data.state.is_exporting) {
          btnExportFinal.innerHTML = "⏳ Renderizando vídeo final...";
          btnExportFinal.disabled = true;
        } else if (data.state.is_synthesizing) {
          btnExportFinal.innerHTML = "🎙️ Sintetizando locuciones...";
          btnExportFinal.disabled = true;
        } else if (data.state.is_analyzing) {
          btnAiGenerate.innerHTML = "⚡ Analizando con Gemini...";
          btnAiGenerate.disabled = true;
        }
        
        if (!data.state.is_analyzing && !data.state.is_exporting && !data.state.is_synthesizing) {
          clearInterval(pollInterval);
          pollInterval = null;
          btnAiGenerate.disabled = false;
          btnAiGenerate.innerHTML = "<span>⚡ Generar con IA (Gemini)</span>";
          btnExportFinal.disabled = false;
          btnExportFinal.innerHTML = "<span>🎬 Renderizar Vídeo Final</span>";
          cues = data.cues || [];
          renderCues();
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 1500);
  }

  // Render cue cards
  function renderCues() {
    cuesContainer.innerHTML = "";
    if (cues.length === 0) {
      cuesContainer.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--tv-text-muted);">
          <p style="font-size: 16px; margin-bottom: 8px;">No hay intervenciones de audiodescripción registradas.</p>
          <p style="font-size: 13px;">Haz clic en <strong>⚡ Generar con IA (Gemini)</strong> o añade marcas manualmente.</p>
        </div>
      `;
      return;
    }

    cues.forEach((cue, index) => {
      const card = document.createElement("div");
      card.className = "cue-card";
      card.id = `cue-card-${cue.id}`;

      const durSlot = (cue.end_seconds - cue.start_seconds).toFixed(1);
      const audioDur = cue.audio_duration ? `${cue.audio_duration}s` : "No generado";
      const hasAudio = !!cue.audio_url;

      card.innerHTML = `
        <div class="cue-header" data-jump="${cue.start_seconds}">
          <div class="cue-time-inputs">
            <span class="cue-badge">#${cue.id}</span>
            <input type="text" class="input-time start-time" value="${cue.start}" data-id="${cue.id}">
            <span class="time-sep-card">➔</span>
            <input type="text" class="input-time end-time" value="${cue.end}" data-id="${cue.id}">
          </div>

          <div class="cue-card-actions">
            <button type="button" class="btn-cue-tool btn-play-sample" data-id="${cue.id}" title="Escuchar locución">
              🔊 Probar Voz
            </button>
            <button type="button" class="btn-cue-tool btn-resynth" data-id="${cue.id}" title="Volver a generar voz">
              🎙️ Sintetizar
            </button>
            <button type="button" class="btn-cue-tool delete-btn" data-id="${cue.id}" title="Eliminar marca">
              ✕
            </button>
          </div>
        </div>

        <textarea class="cue-textarea" data-id="${cue.id}">${cue.text}</textarea>

        <div class="cue-footer">
          <div class="cue-audio-status">
            <span class="${hasAudio ? 'audio-ready-dot' : 'audio-missing-dot'}"></span>
            <span>Hueco en vídeo: <strong>${durSlot}s</strong> · Voz locutada: <strong>${audioDur}</strong></span>
          </div>
          <span style="color: var(--tv-accent-gold); font-size: 11px; cursor: pointer;" class="btn-jump-cue" data-jump="${cue.start_seconds}">Ir al segundo ⏱️</span>
        </div>
      `;

      cuesContainer.appendChild(card);
    });

    attachCueEvents();
  }

  function attachCueEvents() {
    // Jump to timestamp
    document.querySelectorAll("[data-jump]").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "BUTTON") return;
        const sec = parseFloat(el.getAttribute("data-jump"));
        if (!isNaN(sec)) {
          video.currentTime = sec;
          video.play().catch(console.warn);
        }
      });
    });

    // Time input updates
    document.querySelectorAll(".input-time").forEach(inp => {
      inp.addEventListener("change", (e) => {
        const id = parseInt(e.target.dataset.id);
        const cue = cues.find(c => c.id === id);
        if (!cue) return;
        if (e.target.classList.contains("start-time")) {
          cue.start = e.target.value;
          cue.start_seconds = parseTime(e.target.value);
        } else {
          cue.end = e.target.value;
          cue.end_seconds = parseTime(e.target.value);
        }
      });
    });

    // Text update
    document.querySelectorAll(".cue-textarea").forEach(txt => {
      txt.addEventListener("input", (e) => {
        const id = parseInt(e.target.dataset.id);
        const cue = cues.find(c => c.id === id);
        if (cue) {
          cue.text = e.target.value;
        }
      });
    });

    // Play TTS sample
    document.querySelectorAll(".btn-play-sample").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        const cue = cues.find(c => c.id === id);
        if (cue && cue.audio_url) {
          previewAudio.src = `${cue.audio_url}?t=${Date.now()}`;
          previewAudio.play().catch(console.warn);
        } else {
          updateStatus(`Cue #${id} no tiene audio sintetizado. Haz clic en 'Sintetizar'.`);
        }
      });
    });

    // Re-synthesize single cue
    document.querySelectorAll(".btn-resynth").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        const cue = cues.find(c => c.id === id);
        if (!cue) return;

        btn.textContent = "⏳...";
        btn.disabled = true;
        try {
          const res = await fetch("/api/synthesize_cue", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cue)
          });
          const updated = await res.json();
          const idx = cues.findIndex(c => c.id === id);
          if (idx !== -1) cues[idx] = updated;
          renderCues();
          updateStatus(`Cue #${id} sintetizado (${updated.audio_duration}s).`);
        } catch (err) {
          console.error(err);
          updateStatus("Error al sintetizar audio.");
        }
      });
    });

    // Delete cue
    document.querySelectorAll(".delete-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        if (confirm(`¿Eliminar la intervención #${id}?`)) {
          cues = cues.filter(c => c.id !== id);
          renderCues();
        }
      });
    });
  }

  // Add new cue at current playhead
  btnAddCue.addEventListener("click", () => {
    const cur = video.currentTime || 0;
    const newId = cues.length > 0 ? Math.max(...cues.map(c => c.id)) + 1 : 1;
    const newCue = {
      id: newId,
      start: formatTime(cur),
      end: formatTime(cur + 5),
      start_seconds: Math.round(cur * 10) / 10,
      end_seconds: Math.round((cur + 5) * 10) / 10,
      text: "Nueva descripción visual aquí...",
      audio_url: null,
      audio_duration: 0
    };
    cues.push(newCue);
    cues.sort((a, b) => a.start_seconds - b.start_seconds);
    renderCues();
    
    const card = document.getElementById(`cue-card-${newId}`);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  // Save cues to server
  btnSaveCues.addEventListener("click", async () => {
    btnSaveCues.textContent = "Guardando...";
    try {
      const res = await fetch("/api/save_cues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cues: cues, voice: selectVoice.value })
      });
      const data = await res.json();
      btnSaveCues.textContent = "💾 Guardar Cambios";
      updateStatus(`Cambios guardados con éxito (${data.count} intervenciones).`);
    } catch (e) {
      console.error(e);
      btnSaveCues.textContent = "💾 Guardar Cambios";
      updateStatus("Error al guardar cambios.");
    }
  });

  // Generate with Gemini AI
  btnAiGenerate.addEventListener("click", async () => {
    if (!confirm("¿Deseas que Gemini analice el vídeo y genere automáticamente la audiodescripción completa? Esto reemplazará las marcas actuales.")) {
      return;
    }

    try {
      updateStatus("Iniciando análisis multimodal con Gemini...");
      const res = await fetch("/api/generate", { method: "POST" });
      const data = await res.json();
      startPolling();
    } catch (e) {
      console.error(e);
      updateStatus("Error al solicitar análisis de IA.");
    }
  });

  // Export final video
  btnExportFinal.addEventListener("click", async () => {
    try {
      // 1. Automatically save any edited text first
      updateStatus("Guardando cambios y preparando exportación...");
      await fetch("/api/save_cues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cues: cues, voice: selectVoice.value })
      });

      // 2. Trigger export endpoint
      updateStatus("Iniciando renderizado con FFmpeg y audio ducking...");
      const res = await fetch("/api/export", { method: "POST" });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Error al solicitar exportación.");
      }
      const data = await res.json();
      startPolling();
    } catch (e) {
      console.error(e);
      updateStatus(e.message || "Error al exportar vídeo final.");
      btnExportFinal.disabled = false;
      btnExportFinal.innerHTML = "<span>🎬 Renderizar Vídeo Final</span>";
    }
  });

  // Video Scrubber & Playback Sync
  btnPlay.addEventListener("click", () => video.play());
  btnPause.addEventListener("click", () => video.pause());

  video.addEventListener("timeupdate", () => {
    const cur = video.currentTime || 0;
    const dur = video.duration || 1;
    const pct = (cur / dur) * 100;
    scrubberFill.style.width = `${pct}%`;
    liveTime.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;

    // Highlight active cue in list
    cues.forEach(c => {
      const card = document.getElementById(`cue-card-${c.id}`);
      if (card) {
        if (cur >= c.start_seconds && cur <= c.end_seconds) {
          card.classList.add("active-playhead");
        } else {
          card.classList.remove("active-playhead");
        }
      }
    });
  });

  scrubberTrack.addEventListener("click", (e) => {
    const rect = scrubberTrack.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    const dur = video.duration || 0;
    if (dur > 0) video.currentTime = pos * dur;
  });

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  function parseTime(str) {
    const parts = str.trim().split(":");
    if (parts.length === 2) return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
    return parseFloat(str) || 0;
  }

  loadProject();
});
