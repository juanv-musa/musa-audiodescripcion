// ==========================================================================
// MUSA · GESTOR UNIVERSAL DE AUDIODESCRIPCIÓN · LÓGICA DE CONTROL (MUSARAÑA)
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("editor-video");
  const slotsContainer = document.getElementById("timeline-slots-container");
  const timelinePlayhead = document.getElementById("timeline-playhead");
  const liveTime = document.getElementById("live-time");
  const btnPlay = document.getElementById("btn-play");
  const btnPause = document.getElementById("btn-pause");
  const checkLivePreview = document.getElementById("check-live-preview");
  const liveAdIndicator = document.getElementById("live-ad-indicator");
  const liveAdText = document.getElementById("live-ad-text");
  const scrubberCueStatus = document.getElementById("scrubber-cue-status");

  const cuesContainer = document.getElementById("cues-container");
  const btnAiGenerate = document.getElementById("btn-ai-generate");
  const btnExportFinal = document.getElementById("btn-export-final");
  const btnDownloadWav = document.getElementById("btn-download-wav");
  const btnDownloadMp3 = document.getElementById("btn-download-mp3");
  const btnAddCue = document.getElementById("btn-add-cue");
  const btnSaveCues = document.getElementById("btn-save-cues");
  const btnSaveCuesTop = document.getElementById("btn-save-cues-top");
  const selectVoice = document.getElementById("select-voice");
  const selectVideo = document.getElementById("select-video");
  const statusMessage = document.getElementById("status-message");

  // Meta fields
  const infoFilename = document.getElementById("info-filename");
  const infoDuration = document.getElementById("info-duration");
  const infoResolution = document.getElementById("info-resolution");
  const infoSize = document.getElementById("info-size");
  const infoFps = document.getElementById("info-fps");

  // Upload modal elements
  const btnOpenUpload = document.getElementById("btn-open-upload");
  const modalUpload = document.getElementById("modal-upload");
  const btnModalClose = document.getElementById("btn-modal-close");
  const dropzone = document.getElementById("dropzone");
  const inputFileVideo = document.getElementById("input-file-video");
  const uploadProgressWrap = document.getElementById("upload-progress-wrap");
  const uploadProgressBar = document.getElementById("upload-progress-bar");
  const uploadProgressText = document.getElementById("upload-progress-text");

  let cues = [];
  let pollInterval = null;
  let activeAudio = new Audio();
  let sampleAudio = new Audio();
  let currentlyPlayingCueId = null;
  let videoOriginalVolume = 1.0;

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

      // Populate video select
      if (data.available_videos) {
        selectVideo.innerHTML = "";
        data.available_videos.forEach(v => {
          const opt = document.createElement("option");
          opt.value = v.filename;
          opt.textContent = v.filename + (v.is_default ? " (Muestra inicial)" : "");
          if (data.video && v.filename === data.video.filename) {
            opt.selected = true;
          }
          selectVideo.appendChild(opt);
        });
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
      renderTimelineSlots();
      updateStatus(data.state.status_message);

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

  // 1. Render Timeline Slots (Visual spaces on scrubber)
  function renderTimelineSlots() {
    // Keep only playhead
    slotsContainer.innerHTML = '<div id="timeline-playhead" class="timeline-playhead"></div>';
    const dur = video.duration || 115;
    if (dur <= 0) return;

    cues.forEach(cue => {
      const slot = document.createElement("div");
      slot.className = "slot-block";
      slot.id = `timeline-slot-${cue.id}`;
      
      const leftPct = (cue.start_seconds / dur) * 100;
      const widthPct = Math.max(0.8, ((cue.end_seconds - cue.start_seconds) / dur) * 100);

      slot.style.left = `${leftPct}%`;
      slot.style.width = `${widthPct}%`;
      slot.title = `Cue #${cue.id} [${cue.start} - ${cue.end}]: ${cue.text.substring(0, 40)}...`;

      slotsContainer.appendChild(slot);
    });
  }

  // 2. Render cue cards
  function renderCues() {
    cuesContainer.innerHTML = "";
    if (cues.length === 0) {
      cuesContainer.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--tv-text-muted);">
          <p style="font-size: 15px; margin-bottom: 8px;">No hay intervenciones de audiodescripción registradas para este vídeo.</p>
          <p style="font-size: 13px;">Haz clic en <strong>⚡ Generar con IA (Gemini)</strong> o pulsa <strong>+ Añadir Marca</strong>.</p>
        </div>
      `;
      return;
    }

    cues.forEach((cue) => {
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
            <button type="button" class="btn-cue-tool btn-resynth" data-id="${cue.id}" title="Sintetizar locución">
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
          <span style="color: var(--musa-green); font-size: 11px; cursor: pointer;" class="btn-jump-cue" data-jump="${cue.start_seconds}">Ir al segundo ⏱️</span>
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
        renderTimelineSlots();
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
          sampleAudio.src = `${cue.audio_url}?t=${Date.now()}`;
          sampleAudio.play().catch(console.warn);
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
          renderTimelineSlots();
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
          renderTimelineSlots();
        }
      });
    });
  }

  // 3. Live Audio Sync & Slot Illumination Engine
  video.addEventListener("timeupdate", () => {
    const cur = video.currentTime || 0;
    const dur = video.duration || 1;
    const pct = (cur / dur) * 100;
    
    // Move playhead
    const playhead = document.getElementById("timeline-playhead");
    if (playhead) playhead.style.left = `${pct}%`;

    liveTime.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;

    // Check active cue
    const activeCue = cues.find(c => cur >= c.start_seconds && cur < c.end_seconds);

    // Update slots and cards
    cues.forEach(c => {
      const slot = document.getElementById(`timeline-slot-${c.id}`);
      const card = document.getElementById(`cue-card-${c.id}`);

      if (activeCue && c.id === activeCue.id) {
        if (slot) slot.classList.add("active-slot");
        if (card) {
          if (!card.classList.contains("active-playhead")) {
            card.classList.add("active-playhead");
            card.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        }
      } else {
        if (slot) slot.classList.remove("active-slot");
        if (card) card.classList.remove("active-playhead");
      }
    });

    if (activeCue) {
      scrubberCueStatus.textContent = `En reproducción: Cue #${activeCue.id} (${activeCue.start} -> ${activeCue.end})`;
      liveAdText.textContent = `Voz en off: #${activeCue.id}`;
      liveAdIndicator.classList.add("active");

      // Live Audio Preview & Ducking
      if (checkLivePreview.checked && !video.paused) {
        if (currentlyPlayingCueId !== activeCue.id) {
          currentlyPlayingCueId = activeCue.id;
          if (activeCue.audio_url) {
            activeAudio.src = `${activeCue.audio_url}?t=${Date.now()}`;
            // Duck video volume
            video.volume = 0.25;
            activeAudio.play().catch(console.warn);

            activeAudio.onended = () => {
              video.volume = 1.0;
            };
          }
        }
      }
    } else {
      scrubberCueStatus.textContent = "Reproduciendo sin audiodescripción";
      liveAdIndicator.classList.remove("active");
      if (currentlyPlayingCueId !== null) {
        currentlyPlayingCueId = null;
        activeAudio.pause();
        video.volume = 1.0;
      }
    }
  });

  video.addEventListener("loadedmetadata", () => {
    renderTimelineSlots();
  });

  video.addEventListener("pause", () => {
    activeAudio.pause();
    video.volume = 1.0;
  });

  video.addEventListener("seeked", () => {
    currentlyPlayingCueId = null;
    activeAudio.pause();
    video.volume = 1.0;
  });

  // Timeline scrub click
  slotsContainer.addEventListener("click", (e) => {
    const rect = slotsContainer.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    const dur = video.duration || 0;
    if (dur > 0) video.currentTime = pos * dur;
  });

  // 4. Video Selection Dropdown
  selectVideo.addEventListener("change", async (e) => {
    const filename = e.target.value;
    updateStatus(`Cambiando a proyecto: ${filename}...`);
    try {
      const formData = new FormData();
      formData.append("filename", filename);
      const res = await fetch("/api/select_video", { method: "POST", body: formData });
      if (!res.ok) throw new Error("Error al cambiar vídeo.");
      await loadProject();
      updateStatus(`Proyecto activo: ${filename}`);
    } catch (err) {
      console.error(err);
      updateStatus("Error al cambiar de vídeo.");
    }
  });

  // 5. Upload Modal & File Handling
  btnOpenUpload.addEventListener("click", () => {
    modalUpload.classList.add("active");
  });

  btnModalClose.addEventListener("click", () => {
    modalUpload.classList.remove("active");
  });

  modalUpload.addEventListener("click", (e) => {
    if (e.target === modalUpload) modalUpload.classList.remove("active");
  });

  dropzone.addEventListener("click", () => inputFileVideo.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.style.background = "rgba(140, 198, 63, 0.2)";
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.style.background = "rgba(140, 198, 63, 0.05)";
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.style.background = "rgba(140, 198, 63, 0.05)";
    if (e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files[0]);
    }
  });

  inputFileVideo.addEventListener("change", () => {
    if (inputFileVideo.files.length > 0) {
      handleUpload(inputFileVideo.files[0]);
    }
  });

  async function handleUpload(file) {
    if (!file) return;
    uploadProgressWrap.style.display = "flex";
    uploadProgressText.textContent = `Subiendo ${file.name}...`;
    uploadProgressBar.style.width = "40%";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload_video", {
        method: "POST",
        body: formData
      });
      uploadProgressBar.style.width = "100%";
      if (!res.ok) throw new Error("Error al subir archivo.");

      uploadProgressText.textContent = "¡Vídeo cargado con éxito!";
      setTimeout(() => {
        modalUpload.classList.remove("active");
        uploadProgressWrap.style.display = "none";
        uploadProgressBar.style.width = "0%";
        loadProject();
      }, 800);
    } catch (err) {
      console.error(err);
      uploadProgressText.textContent = "Error al subir el vídeo.";
    }
  }

  // 6. Professional Audio Downloads (WAV & MP3)
  async function triggerAudioExport(format) {
    updateStatus(`Preparando exportación de pista ${format.toUpperCase()} sincronizada para Premiere/DaVinci...`);
    const formData = new FormData();
    formData.append("format", format);

    try {
      const res = await fetch("/api/export_audio_track", {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error("Error al solicitar pista de audio.");
      startPolling(async () => {
        // Trigger download
        const pRes = await fetch("/api/project");
        const pData = await pRes.json();
        const url = format === "wav" ? pData.audio_tracks?.wav_url : pData.audio_tracks?.mp3_url;
        if (url) {
          const a = document.createElement("a");
          a.href = url;
          a.download = url.split("/").pop();
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          updateStatus(`Pista ${format.toUpperCase()} descargada correctamente.`);
        }
      });
    } catch (err) {
      console.error(err);
      updateStatus(err.message || "Error al exportar audio.");
    }
  }

  btnDownloadWav.addEventListener("click", () => triggerAudioExport("wav"));
  btnDownloadMp3.addEventListener("click", () => triggerAudioExport("mp3"));

  // 7. Export Final Video (MP4)
  btnExportFinal.addEventListener("click", async () => {
    try {
      updateStatus("Guardando cambios y preparando exportación de vídeo final...");
      await fetch("/api/save_cues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cues: cues, voice: selectVoice.value })
      });

      updateStatus("Renderizando vídeo final accesible con audio ducking...");
      const res = await fetch("/api/export", { method: "POST" });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Error al solicitar exportación.");
      }
      startPolling();
    } catch (e) {
      console.error(e);
      updateStatus(e.message || "Error al exportar vídeo final.");
    }
  });

  // 8. Polling Background Status
  function startPolling(onDoneCallback) {
    if (pollInterval) return;
    btnAiGenerate.disabled = true;
    btnExportFinal.disabled = true;
    btnDownloadWav.disabled = true;
    btnDownloadMp3.disabled = true;

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch("/api/project");
        const data = await res.json();
        updateStatus(data.state.status_message);

        if (data.state.is_exporting) {
          btnExportFinal.innerHTML = "⏳ Renderizando vídeo...";
          btnDownloadWav.innerHTML = "⏳ Procesando audio...";
        } else if (data.state.is_synthesizing) {
          btnExportFinal.innerHTML = "🎙️ Sintetizando locuciones...";
        } else if (data.state.is_analyzing) {
          btnAiGenerate.innerHTML = "⚡ Analizando con Gemini...";
        }

        if (!data.state.is_analyzing && !data.state.is_exporting && !data.state.is_synthesizing) {
          clearInterval(pollInterval);
          pollInterval = null;
          btnAiGenerate.disabled = false;
          btnAiGenerate.innerHTML = "<span>⚡ Generar con IA (Gemini)</span>";
          btnExportFinal.disabled = false;
          btnExportFinal.innerHTML = "<span>🎬 Renderizar Vídeo Final</span>";
          btnDownloadWav.disabled = false;
          btnDownloadWav.innerHTML = "<span>⬇️ Pista WAV (Premiere / DaVinci)</span>";
          btnDownloadMp3.disabled = false;
          btnDownloadMp3.innerHTML = "<span>⬇️ MP3</span>";

          cues = data.cues || [];
          renderCues();
          renderTimelineSlots();

          if (onDoneCallback) onDoneCallback();
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 1500);
  }

  // 9. Standard Actions
  btnPlay.addEventListener("click", () => video.play());
  btnPause.addEventListener("click", () => video.pause());

  btnAddCue.addEventListener("click", () => {
    const cur = video.currentTime || 0;
    const newId = cues.length > 0 ? Math.max(...cues.map(c => c.id)) + 1 : 1;
    const newCue = {
      id: newId,
      start: formatTime(cur),
      end: formatTime(cur + 5),
      start_seconds: Math.round(cur * 10) / 10,
      end_seconds: Math.round((cur + 5) * 10) / 10,
      text: "Descripción visual aquí...",
      audio_url: null,
      audio_duration: 0
    };
    cues.push(newCue);
    cues.sort((a, b) => a.start_seconds - b.start_seconds);
    renderCues();
    renderTimelineSlots();
    
    const card = document.getElementById(`cue-card-${newId}`);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  btnSaveCues.addEventListener("click", performSaveCues);
  if (btnSaveCuesTop) {
    btnSaveCuesTop.addEventListener("click", performSaveCues);
  }

  async function performSaveCues() {
    btnSaveCues.textContent = "Guardando...";
    if (btnSaveCuesTop) btnSaveCuesTop.innerHTML = "<span>⏳ Guardando...</span>";
    try {
      const res = await fetch("/api/save_cues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cues: cues, voice: selectVoice.value })
      });
      const data = await res.json();
      btnSaveCues.textContent = "💾 Guardar";
      if (btnSaveCuesTop) btnSaveCuesTop.innerHTML = "<span>💾 Guardar Cambios</span>";
      updateStatus(`Cambios guardados con éxito (${data.count} intervenciones).`);
      renderTimelineSlots();
    } catch (e) {
      console.error(e);
      btnSaveCues.textContent = "💾 Guardar";
      if (btnSaveCuesTop) btnSaveCuesTop.innerHTML = "<span>💾 Guardar Cambios</span>";
      updateStatus("Error al guardar cambios.");
    }
  }

  btnAiGenerate.addEventListener("click", async () => {
    if (!confirm("¿Deseas que Gemini analice el vídeo seleccionado y genere automáticamente las marcas de audiodescripción?")) {
      return;
    }
    try {
      updateStatus("Iniciando análisis multimodal con Gemini...");
      await fetch("/api/generate", { method: "POST" });
      startPolling();
    } catch (e) {
      console.error(e);
      updateStatus("Error al solicitar análisis de IA.");
    }
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
