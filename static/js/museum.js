// ==========================================================================
// SANTUARIO IBÉRICO DE EL PAJARILLO · LOGICA REPRODUCTOR KIOSCO ACCESIBLE
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const video = document.getElementById("kiosk-video");
  const playOverlay = document.getElementById("play-overlay");
  const btnGiantPlay = document.getElementById("btn-giant-play");
  const btnPlayPause = document.getElementById("btn-play-pause");
  const iconPlay = document.getElementById("icon-play");
  const iconPause = document.getElementById("icon-pause");
  const btnRewind = document.getElementById("btn-rewind");
  const btnForward = document.getElementById("btn-forward");
  const timelineWrap = document.getElementById("timeline-wrap");
  const timelineFill = document.getElementById("timeline-fill");
  const timeCurrent = document.getElementById("time-current");
  const timeTotal = document.getElementById("time-total");
  const btnModeStandard = document.getElementById("btn-mode-standard");
  const btnModeAD = document.getElementById("btn-mode-ad");
  const btnToggleSubtitles = document.getElementById("btn-toggle-subtitles");
  const btnFullscreen = document.getElementById("btn-fullscreen");
  const subtitleBanner = document.getElementById("ad-subtitle-banner");
  const subtitleText = document.getElementById("subtitle-text");
  const activeModeTag = document.getElementById("active-mode-tag");

  let projectData = null;
  let currentMode = "standard"; // 'standard' or 'ad'
  let showSubtitles = false;
  let cues = [];

  // 1. Load initial project information
  async function loadProject() {
    try {
      const res = await fetch("/api/project");
      projectData = await res.json();
      cues = projectData.cues || [];
      
      // Set initial video source
      setVideoSource(currentMode);
    } catch (e) {
      console.error("Error al cargar datos del proyecto:", e);
    }
  }

  function setVideoSource(mode) {
    const isPlaying = !video.paused && !video.ended && video.readyState > 2;
    const curTime = video.currentTime || 0;

    let targetUrl = "";
    if (mode === "ad" && projectData?.accessible_video?.url) {
      targetUrl = projectData.accessible_video.url;
      activeModeTag.textContent = "Audiodescripción para Personas Ciegas Activa";
    } else {
      targetUrl = projectData?.video?.url || "/media/video/DOCUMENTAL EL PAJARILLO_demo.mp4";
      activeModeTag.textContent = "Locución Original Estándar";
    }

    // Only update src if it changed
    if (!video.src.endsWith(targetUrl)) {
      video.src = targetUrl;
      video.load();
      video.currentTime = curTime;
      if (isPlaying) {
        video.play().catch(console.warn);
      }
    }
  }

  // 2. Mode Switching with seamless playback continuation
  function switchMode(newMode) {
    if (currentMode === newMode) return;
    currentMode = newMode;

    if (currentMode === "standard") {
      btnModeStandard.classList.add("active");
      btnModeAD.classList.remove("active");
    } else {
      btnModeStandard.classList.remove("active");
      btnModeAD.classList.add("active");
    }

    setVideoSource(currentMode);
  }

  btnModeStandard.addEventListener("click", () => switchMode("standard"));
  btnModeAD.addEventListener("click", () => switchMode("ad"));

  // 3. Playback controls
  function togglePlay() {
    if (video.paused || video.ended) {
      video.play().catch(console.warn);
    } else {
      video.pause();
    }
  }

  video.addEventListener("play", () => {
    playOverlay.classList.add("hidden");
    iconPlay.style.display = "none";
    iconPause.style.display = "block";
  });

  video.addEventListener("pause", () => {
    playOverlay.classList.remove("hidden");
    iconPlay.style.display = "block";
    iconPause.style.display = "none";
  });

  playOverlay.addEventListener("click", togglePlay);
  btnPlayPause.addEventListener("click", togglePlay);

  btnRewind.addEventListener("click", () => {
    video.currentTime = Math.max(0, video.currentTime - 10);
  });

  btnForward.addEventListener("click", () => {
    video.currentTime = Math.min(video.duration || 0, video.currentTime + 10);
  });

  // 4. Timeline update & Subtitle sync
  video.addEventListener("timeupdate", () => {
    const cur = video.currentTime || 0;
    const dur = video.duration || 1;
    const pct = Math.min(100, Math.max(0, (cur / dur) * 100));
    timelineFill.style.width = `${pct}%`;

    timeCurrent.textContent = formatTime(cur);
    if (!isNaN(dur) && dur > 0) {
      timeTotal.textContent = formatTime(dur);
    }

    // Subtitle / Banner Sync
    if (showSubtitles || currentMode === "ad") {
      const activeCue = cues.find(c => cur >= c.start_seconds && cur <= c.end_seconds);
      if (activeCue && showSubtitles) {
        subtitleText.textContent = activeCue.text;
        subtitleBanner.classList.add("active");
      } else {
        subtitleBanner.classList.remove("active");
      }
    } else {
      subtitleBanner.classList.remove("active");
    }
  });

  // Timeline click seeking
  timelineWrap.addEventListener("click", (e) => {
    const rect = timelineWrap.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    const dur = video.duration || 0;
    if (dur > 0) {
      video.currentTime = pos * dur;
    }
  });

  // 5. Subtitle Toggle
  btnToggleSubtitles.addEventListener("click", () => {
    showSubtitles = !showSubtitles;
    btnToggleSubtitles.classList.toggle("active", showSubtitles);
    if (!showSubtitles) {
      subtitleBanner.classList.remove("active");
    }
  });

  // 6. Fullscreen Toggle
  btnFullscreen.addEventListener("click", () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(console.warn);
    } else {
      document.exitFullscreen().catch(console.warn);
    }
  });

  // 7. Keyboard Accessibility Shortcuts (for visually impaired visitors or staff)
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    
    switch (e.key.toLowerCase()) {
      case " ":
      case "k":
        e.preventDefault();
        togglePlay();
        break;
      case "arrowleft":
      case "j":
        e.preventDefault();
        video.currentTime = Math.max(0, video.currentTime - 5);
        break;
      case "arrowright":
      case "l":
        e.preventDefault();
        video.currentTime = Math.min(video.duration || 0, video.currentTime + 5);
        break;
      case "a": // Toggle Audiodescripción
        e.preventDefault();
        switchMode(currentMode === "standard" ? "ad" : "standard");
        break;
      case "c": // Toggle Captions
        e.preventDefault();
        btnToggleSubtitles.click();
        break;
      case "f": // Fullscreen
        e.preventDefault();
        btnFullscreen.click();
        break;
      case "m": // Mute
        e.preventDefault();
        video.muted = !video.muted;
        break;
    }
  });

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  loadProject();
});
