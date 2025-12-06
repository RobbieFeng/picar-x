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
};

const STORAGE_KEY = "petFollowerDashboard";
let config = {
  deviceAddress: "",
};
let pollTimer = null;
let eventSource = null;
let resolvedBaseUrl = "";
const LEGACY_MESSAGE_MAP = {
  "未检测到宠物，执行搜索模式": "No target; searching",
  "执行强制搜索": "Executing forced search",
  "安全检查限制移动": "Stop by safety check",
  "检测到宠物，正在跟随": "Target acquired; following",
  "保持最后方向，继续搜索": "Holding last heading, continuing search",
  "正在进入跟随模式": "Entering follow mode",
  "已启动宠物跟随": "Following started",
  "已停止": "Stopped",
  "宠物跟随已停止": "Following stopped",
  "状态已重置": "State reset",
  "触发庆祝动作": "Celebration requested",
  "庆祝动作已触发": "Celebration triggered",
  "已请求搜索动作": "Search command queued",
  "搜索动作已触发": "Search triggered",
  "当前无法获取画面": "Unable to capture frame",
  "已上传单帧到云端": "Snapshot uploaded to cloud",
  "快照已发送": "Snapshot sent",
  "当前处于自动模式，请先停止跟随": "Follower is active; stop it before manual drive",
  "未知方向，允许 forward/backward/left/right/stop":
    "Unknown direction; allowed forward/backward/left/right/stop",
  "手动驾驶 完成": "Manual drive complete",
  "事件已记录": "Event recorded",
};

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
  els.targetStatus.textContent = translateLegacyText(payload.message || payload.note || "");

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
  els.statusList.lastMessage.textContent = translateLegacyText(msg);

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

function setupButtons() {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (!action) return;
      if (action === "snapshot") {
        sendAction("capture_frame");
      } else if (action === "search") {
        sendAction("force_search");
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

function logEvent(level, text) {
  const translated = translateLegacyText(text);
  const li = document.createElement("li");
  const time = document.createElement("time");
  time.dateTime = new Date().toISOString();
  time.textContent = new Date().toLocaleTimeString();
  const span = document.createElement("span");
  span.textContent = `[${level}] ${translated}`;
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

function init() {
  loadConfig();
  setupButtons();
  setupSliders();
  setupLogControls();
  setupConfigButtons();
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

function translateLegacyText(text) {
  if (!text) return text;
  const trimmed = text.trim();
  if (trimmed.startsWith("手动驾驶")) {
    const direction = trimmed.replace("手动驾驶", "").trim();
    return direction ? `Manual drive ${direction}` : "Manual drive";
  }
  if (trimmed.startsWith("事件：")) {
    return `Event: ${trimmed.replace("事件：", "").trim()}`;
  }
  return LEGACY_MESSAGE_MAP[trimmed] || trimmed;
}
