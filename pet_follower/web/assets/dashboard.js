const els = {
  deviceHost: document.getElementById("deviceHost"),
  video: document.getElementById("videoFeed"),
  modeLabel: document.getElementById("modeLabel"),
  followLabel: document.getElementById("followLabel"),
  confidenceLabel: document.getElementById("confidenceLabel"),
  distanceLabel: document.getElementById("distanceLabel"),
  targetStatus: document.getElementById("targetStatus"),
  statusList: {
    targetVisible: document.getElementById("targetVisible"),
    lastTargetTime: document.getElementById("lastTargetTime"),
    safetyDistance: document.getElementById("safetyDistance"),
    cliffStatus: document.getElementById("cliffStatus"),
    fpsLabel: document.getElementById("fpsLabel"),
    lastMessage: document.getElementById("lastMessage"),
  },
  connectionBadge: document.getElementById("connectionBadge"),
  logList: document.getElementById("logList"),
  autoScroll: document.getElementById("autoScroll"),
  clearLog: document.getElementById("clearLog"),
  refreshBtn: document.getElementById("refreshStatus"),
  testBtn: document.getElementById("testConnection"),
  saveBtn: document.getElementById("saveConfig"),
  stateOverlay: document.getElementById("stateOverlay"),
  speedSlider: document.getElementById("speedSlider"),
  durationSlider: document.getElementById("durationSlider"),
  speedValue: document.getElementById("speedValue"),
  durationValue: document.getElementById("durationValue"),
  consoleBody: document.getElementById("robotConsole"),
  consoleReload: document.getElementById("consoleReload"),
  consoleAutoScroll: document.getElementById("consoleAutoScroll"),
  autoRecordToggle: document.getElementById("autoRecordToggle"),
  autoRecordInterval: document.getElementById("autoRecordInterval"),
  autoRecordIntervalLabel: document.getElementById("autoRecordIntervalLabel"),
  autoRecordStatus: document.getElementById("autoRecordStatus"),
  applyAutoRecord: document.getElementById("applyAutoRecord"),
  autoRecordLast: document.getElementById("autoRecordLast"),
};

const STORAGE_KEY = "petFollowerDashboard";
let config = {
  deviceAddress: "",
};
let pollTimer = null;
let eventSource = null;
let consolePollTimer = null;
let resolvedBaseUrl = "";
const GCP_LOG_ENDPOINT = "/api/gcp-log";
const CONSOLE_POLL_INTERVAL = 10000; // 10 seconds

function loadConfig() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      config = { ...config, ...JSON.parse(saved) };
    }
  } catch (err) {
    console.warn("Failed to parse saved config", err);
  }
  els.deviceHost.value = config.deviceAddress || "";
  updateResolvedBaseUrl();
  setVideoSrc();
}

function saveConfig() {
  config.deviceAddress = els.deviceHost.value.trim();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  updateResolvedBaseUrl();
  if (!resolvedBaseUrl) {
    logEvent("warn", "Please enter a valid PiCar-X host or IP");
    return;
  }
  logEvent("system", `Target device: ${resolvedBaseUrl}`);
  setVideoSrc();
  connectStreams();
}

function setVideoSrc() {
  if (resolvedBaseUrl) {
    els.video.src = `${resolvedBaseUrl}/stream.mjpg`;
    els.video.alt = "pet follower live stream";
  } else {
    els.video.removeAttribute("src");
    els.video.alt = "Video stream not configured";
  }
}

function setConnectionState(state, message = "") {
  els.connectionBadge.textContent = state === "online" ? "Online" : "Offline";
  els.connectionBadge.classList.toggle("online", state === "online");
  els.connectionBadge.classList.toggle("offline", state === "offline");
  if (message) {
    els.targetStatus.textContent = message;
  }
}

async function fetchStatus(showToast = false) {
  if (!resolvedBaseUrl) {
    if (showToast) logEvent("warn", "Enter the PiCar-X API address first");
    return null;
  }
  try {
    const resp = await fetch(`${resolvedBaseUrl}/api/status`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    updateStatusUI(data);
    setConnectionState("online", "Syncing live data");
    if (showToast) logEvent("system", "Status refreshed");
    return data;
  } catch (err) {
    setConnectionState("offline", "Unable to reach PiCar-X");
    logEvent("error", `Failed to fetch status: ${err.message}`);
    return null;
  }
}

function updateStatusUI(payload = {}) {
  const mode = payload.mode || payload.state || "-";
  const detection = payload.detection || {};
  const safety = payload.safety || {};
  const motion = payload.motion || {};

  els.modeLabel.textContent = mode;
  const visible = detection.target_visible ?? payload.target_visible;
  els.followLabel.textContent = visible ? "Following target" : "No target";
  els.confidenceLabel.textContent = detection.confidence
    ? `${(detection.confidence * 100).toFixed(1)}%`
    : "-";
  const distance = detection.approx_distance_cm ?? payload.distance_cm;
  els.distanceLabel.textContent = distance ? `${distance.toFixed(1)} cm` : "-";
  els.targetStatus.textContent = payload.message || payload.note || "";

  els.statusList.targetVisible.textContent = visible ? "Yes" : "No";
  els.statusList.lastTargetTime.textContent = formatRelativeTime(
    detection.updated_at || payload.last_detection
  );
  const dist = safety.distance_cm ?? payload.obstacle_distance;
  els.statusList.safetyDistance.textContent = typeof dist === "number" ? `${dist} cm` : "Unknown";
  const cliff = safety.cliff_detected ?? false;
  els.statusList.cliffStatus.textContent = cliff ? "Warning" : "Normal";
  els.statusList.cliffStatus.style.color = cliff ? "var(--danger)" : "var(--muted)";
  const fps = payload.fps ?? payload.camera_fps;
  els.statusList.fpsLabel.textContent = fps ? fps.toFixed(1) : "-";
  const msg = payload.last_log || payload.message || "-";
  els.statusList.lastMessage.textContent = msg;
  if (payload.auto_recording) {
    updateAutoRecordUI(payload.auto_recording);
  }

  if (motion.safe_to_move === false) {
    els.stateOverlay.dataset.blocked = "true";
  } else {
    delete els.stateOverlay.dataset.blocked;
  }
}

function formatRelativeTime(value) {
  if (!value) return "-";
  try {
    const ts = typeof value === "number" ? value * 1000 : Date.parse(value);
    if (Number.isNaN(ts)) return value;
    const diff = Date.now() - ts;
    if (diff < 5000) return "just now";
    if (diff < 60000) return `${Math.round(diff / 1000)} sec ago`;
    if (diff < 3600000) return `${Math.round(diff / 60000)} min ago`;
    return new Date(ts).toLocaleTimeString();
  } catch (err) {
    return value;
  }
}

async function sendAction(action, extra = {}) {
  if (!resolvedBaseUrl) {
    logEvent("warn", "API address not configured");
    return;
  }
  try {
    const resp = await fetch(`${resolvedBaseUrl}/api/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...extra }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.status) logEvent("system", data.status);
    if (data.state) updateStatusUI(data.state);
  } catch (err) {
    logEvent("error", `Action ${action} failed: ${err.message}`);
  }
}

function setButtonActive(btn) {
  if (!btn || !btn.dataset || !btn.dataset.group) return;
  const group = btn.dataset.group;
  document.querySelectorAll(`[data-group="${group}"]`).forEach((el) => {
    el.classList.remove("is-active");
  });
  btn.classList.add("is-active");
}

function applyDefaultActiveStates() {
  document.querySelectorAll("[data-default-active]").forEach((btn) => {
    setButtonActive(btn);
  });
}

function setupButtons() {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (!action) return;
      setButtonActive(btn);
      if (action === "snapshot") {
        sendAction("capture_frame");
      } else if (action === "search") {
        sendAction("force_search");
      } else if (action === "record_video") {
        const duration = Number(btn.dataset.duration || 10);
        sendAction("record_video", { duration });
      } else if (action === "mark") {
        sendAction("mark_event", { note: prompt("Enter event note", "") });
      } else {
        sendAction(action);
      }
    });
  });

  document.querySelectorAll("[data-drive]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const direction = btn.dataset.drive;
      setButtonActive(btn);
      const payload = {
        direction,
        speed: Number(els.speedSlider.value),
        duration: Number(els.durationSlider.value),
      };
      sendAction("manual_drive", payload);
    });
  });
}

function setupSliders() {
  const sync = () => {
    els.speedValue.textContent = els.speedSlider.value;
    els.durationValue.textContent = Number(els.durationSlider.value).toFixed(1);
  };
  els.speedSlider.addEventListener("input", sync);
  els.durationSlider.addEventListener("input", sync);
  sync();
}

function setupAutoRecordControls() {
  if (!els.autoRecordInterval || !els.autoRecordIntervalLabel) return;
  const syncLabel = () => {
    els.autoRecordIntervalLabel.textContent = els.autoRecordInterval.value;
  };
  els.autoRecordInterval.addEventListener("input", syncLabel);
  syncLabel();
  if (els.applyAutoRecord) {
    els.applyAutoRecord.addEventListener("click", () => {
      const enabled = !!(els.autoRecordToggle && els.autoRecordToggle.checked);
      const minutes = Number(els.autoRecordInterval.value || 3);
      sendAction("auto_recording", { enabled, interval: minutes * 60 });
    });
  }
}

function updateAutoRecordUI(info) {
  if (!els.autoRecordToggle || !els.autoRecordInterval) return;
  const minutes = Math.round((info.interval || 180) / 60);
  els.autoRecordToggle.checked = !!info.enabled;
  els.autoRecordInterval.value = String(Math.max(1, Math.min(minutes, 10)));
  if (els.autoRecordIntervalLabel) {
    els.autoRecordIntervalLabel.textContent = els.autoRecordInterval.value;
  }
  let status = "Auto recording disabled";
  let lastText = "No clips yet";
  if (info.enabled) {
    const secondsUntil = info.seconds_until_next ?? 0;
    if (info.active) {
      status = "Recording clip...";
    } else if (!info.eligible) {
      const minutesLeft = secondsUntil / 60;
      status = `Ready in ${minutesLeft.toFixed(1)} min`;
    } else {
      status = "Ready to record on next detection";
    }
  }
  if (info.last_uploaded_at) {
    const lastDate = new Date(info.last_uploaded_at * 1000);
    const since = formatDurationSeconds(info.seconds_since_last);
    lastText = `Last clip: ${lastDate.toLocaleTimeString()}${since ? ` (${since} ago)` : ""}`;
  }
  if (els.autoRecordStatus) {
    els.autoRecordStatus.textContent = status;
  }
  if (els.autoRecordLast) {
    els.autoRecordLast.textContent = lastText;
  }
}

function logEvent(level, text) {
  const li = document.createElement("li");
  const time = document.createElement("time");
  time.dateTime = new Date().toISOString();
  time.textContent = new Date().toLocaleTimeString();
  const span = document.createElement("span");
  span.textContent = `[${level}] ${text}`;
  if (level === "error") {
    span.style.color = "var(--danger)";
  } else if (level === "warn") {
    span.style.color = "var(--warning)";
  }
  li.appendChild(time);
  li.appendChild(span);
  els.logList.prepend(li);
  const maxItems = 150;
  while (els.logList.children.length > maxItems) {
    els.logList.removeChild(els.logList.lastChild);
  }
  if (els.autoScroll.checked) {
    li.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function setupLogControls() {
  els.clearLog.addEventListener("click", () => {
    els.logList.innerHTML = "";
  });
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    fetchStatus();
  }, 5000);
}

function connectEventStream() {
  if (!window.EventSource || !resolvedBaseUrl) return;
  if (eventSource) {
    eventSource.close();
  }
  eventSource = new EventSource(`${resolvedBaseUrl}/api/events`);
  eventSource.onmessage = (event) => {
    if (!event.data) return;
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === "status") {
        updateStatusUI(payload.data);
      } else if (payload.type === "log") {
        logEvent(payload.level || "info", payload.message || "");
      }
    } catch (err) {
      console.warn("Failed to parse event", err);
    }
  };
  eventSource.onerror = () => {
    logEvent("warn", "Event stream interrupted, retrying in 5s");
    eventSource.close();
    setTimeout(connectEventStream, 5000);
  };
}

function connectStreams() {
  if (!resolvedBaseUrl) return;
  fetchStatus();
  startPolling();
  connectEventStream();
}

function setupConfigButtons() {
  els.saveBtn.addEventListener("click", saveConfig);
  els.testBtn.addEventListener("click", () => fetchStatus(true));
  els.refreshBtn.addEventListener("click", () => fetchStatus(true));
}

function setupConsole() {
  if (!els.consoleBody) return;
  if (els.consoleReload) {
    els.consoleReload.addEventListener("click", () => {
      loadLocalConsoleLog();
    });
  }
  // Load immediately
  loadLocalConsoleLog();
  // Start auto-polling
  startConsolePolling();
}

function startConsolePolling() {
  if (consolePollTimer) clearInterval(consolePollTimer);
  consolePollTimer = setInterval(() => {
    loadLocalConsoleLog();
  }, CONSOLE_POLL_INTERVAL);
}

async function loadLocalConsoleLog() {
  if (!els.consoleBody) return;
  try {
    const resp = await fetch(GCP_LOG_ENDPOINT, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    
    if (data.status === "ok") {
      // Use entries if available, otherwise parse content
      let entries = data.entries || [];
      if (!entries.length && data.content) {
        const lines = data.content.split(/\r?\n/).filter((line) => line.trim().length > 0);
        for (const line of lines) {
          try {
            entries.push(JSON.parse(line));
          } catch (err) {
            entries.push({
              ts: "",
              level: "error",
              source: "console",
              msg: "Invalid JSONL line",
              extra: { line },
            });
          }
        }
      }
      renderConsoleLog(entries);
    } else {
      throw new Error(data.error || "Unknown error");
    }
  } catch (err) {
    renderConsoleLog([
      {
        ts: "",
        level: "error",
        source: "console",
        msg: `Failed to load log from GCP: ${err.message}`,
      },
    ]);
  }
}

function renderConsoleLog(entries) {
  const container = els.consoleBody;
  if (!container) return;
  container.innerHTML = "";

  entries.forEach((entry) => {
    const level = (entry.level || "info").toLowerCase();
    const card = document.createElement("div");
    card.className = `console-entry level-${level}`;

    const ts = entry.ts || entry.time || "";
    const source = entry.source || entry.component || (entry.extra && entry.extra.source) || "";
    const description = entry.description || entry.msg || entry.message || "";
    const extra = entry.extra && typeof entry.extra === "object" ? entry.extra : null;

    const header = document.createElement("div");
    header.className = "console-entry-header";

    const meta = document.createElement("div");
    meta.className = "console-entry-meta";

    if (ts) {
      const timeEl = document.createElement("span");
      timeEl.className = "console-entry-time";
      timeEl.textContent = ts;
      meta.appendChild(timeEl);
    }

    if (source) {
      const sourceEl = document.createElement("span");
      sourceEl.className = "console-entry-source";
      sourceEl.textContent = source;
      meta.appendChild(sourceEl);
    }

    const levelEl = document.createElement("span");
    levelEl.className = "console-entry-level";
    levelEl.textContent = level;

    header.appendChild(meta);
    header.appendChild(levelEl);

    const descEl = document.createElement("div");
    descEl.className = "console-entry-description";
    descEl.textContent = description;

    card.appendChild(header);
    card.appendChild(descEl);

    if (extra && Object.keys(extra).length > 0) {
      const tags = document.createElement("div");
      tags.className = "console-tags";
      Object.entries(extra).forEach(([key, value]) => {
        const tag = document.createElement("span");
        tag.className = "console-tag";
        tag.textContent = `${key}: ${value}`;
        tags.appendChild(tag);
      });
      card.appendChild(tags);
    }

    container.appendChild(card);
  });

  if (els.consoleAutoScroll && els.consoleAutoScroll.checked) {
    container.scrollTop = container.scrollHeight;
  }
}

function init() {
  loadConfig();
  setupButtons();
  setupSliders();
  setupAutoRecordControls();
  setupLogControls();
  setupConfigButtons();
  setupConsole();
  applyDefaultActiveStates();
  if (resolvedBaseUrl) {
    connectStreams();
  } else {
    setConnectionState("offline", "Enter the device address");
  }
}

init();

function updateResolvedBaseUrl() {
  resolvedBaseUrl = normalizeBaseUrl(config.deviceAddress);
}

function normalizeBaseUrl(input) {
  if (!input) return "";
  let value = input.trim();
  if (!value) return "";
  if (!/^https?:\/\//i.test(value)) {
    value = `http://${value}`;
  }
  try {
    const url = new URL(value);
    if (!url.port) {
      url.port = "8000";
    }
    return url.origin;
  } catch (err) {
    logEvent("warn", `Invalid address: ${input}`);
    return "";
  }
}

function formatDurationSeconds(seconds) {
  if (seconds == null || seconds < 0) return "";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}
