/**
 * THE DILUTION - Cleanroom Robot Controller & Automation Deck (CAT403 Biomedical Robotics)
 * 6-Axis Automation Sequences, Real-Time Teleoperation, Enlarged 3D Digital Twin & Clock
 */

// Calibrated Joint Angles (TheDilution cleanroom work envelope)
const CALIBRATED_POSES = {
  "home": [0.0, 0.0, 0.0, 0.0, 0.0, -129.0],
  "door": [25.48, -94.48, -2.1, 103.62, -114.08, -131.13],
  "dosing": [35.0, -25.0, 45.0, -20.0, 0.0, -129.0],
  "slot_1": [44.64, -108.98, 43.68, 90.0, 22.0, -136.0],     // Point A
  "slot_2": [44.64, -108.98, 43.68, 90.0, 22.0, -110.0],     // Point B
  "slot_3": [42.0, -102.65, 75.0, 60.0, 68.0, -136.0],       // Point C
  "slot_4": [54.84, -123.57, 74.61, 65.65, 65.21, -123.57],
  "slot_5": [59.0, -123.57, 74.61, 60.65, 65.21, -136.57],
  "slot_6": [6.67, -94.48, -2.1, 103.62, -90.7, -131.13]
};

// Application State
const state = {
  stepSize: 5.0,
  speed: 35,
  angles: [0.0, 0.0, 0.0, 0.0, 0.0, -129.0],
  coords: [100.0, 0.0, 200.0],
  connected: false,
  simulationMode: false,
  gripperValue: 100,
  roofInterlock: "CLOSED",
  tray: [],
  waypoints: {},
  delivery: { status: "IDLE", current_step_text: "Standby" },
  lastJogTime: 0,
  throttleMs: 35, // Ultra-low latency throttle (28 Hz)
  theme: localStorage.getItem('cleanroom_theme') || 'dark',
  currentPoseName: 'home'
};

// Comprehensive 6-Axis Key Mappings (Supports code, lower/upper key, and arrow keys)
const KEY_MAPPINGS = {
  // Letters by code
  'KeyA': { joint: 1, dir: -1 },
  'KeyD': { joint: 1, dir: 1 },
  'KeyS': { joint: 2, dir: -1 },
  'KeyW': { joint: 2, dir: 1 },
  'KeyE': { joint: 3, dir: -1 },
  'KeyQ': { joint: 3, dir: 1 },
  'KeyF': { joint: 4, dir: -1 },
  'KeyR': { joint: 4, dir: 1 },
  'KeyG': { joint: 5, dir: -1 },
  'KeyT': { joint: 5, dir: 1 },
  'KeyH': { joint: 6, dir: -1 },
  'KeyY': { joint: 6, dir: 1 },

  // Letters by key (case-insensitive fallback)
  'a': { joint: 1, dir: -1 }, 'A': { joint: 1, dir: -1 },
  'd': { joint: 1, dir: 1 },  'D': { joint: 1, dir: 1 },
  's': { joint: 2, dir: -1 }, 'S': { joint: 2, dir: -1 },
  'w': { joint: 2, dir: 1 },  'W': { joint: 2, dir: 1 },
  'e': { joint: 3, dir: -1 }, 'E': { joint: 3, dir: -1 },
  'q': { joint: 3, dir: 1 },  'Q': { joint: 3, dir: 1 },
  'f': { joint: 4, dir: -1 }, 'F': { joint: 4, dir: -1 },
  'r': { joint: 4, dir: 1 },  'R': { joint: 4, dir: 1 },
  'g': { joint: 5, dir: -1 }, 'G': { joint: 5, dir: -1 },
  't': { joint: 5, dir: 1 },  'T': { joint: 5, dir: 1 },
  'h': { joint: 6, dir: -1 }, 'H': { joint: 6, dir: -1 },
  'y': { joint: 6, dir: 1 },  'Y': { joint: 6, dir: 1 },

  // Intuitive Arrow Controls
  'ArrowLeft':  { joint: 1, dir: -1 },
  'ArrowRight': { joint: 1, dir: 1 },
  'ArrowDown':  { joint: 2, dir: -1 },
  'ArrowUp':    { joint: 2, dir: 1 },
  'PageDown':   { joint: 3, dir: -1 },
  'PageUp':     { joint: 3, dir: 1 }
};

// Hardware Joint Limits strictly enforced by pymycobot on myCobot 280 Pi
const JOINT_LIMITS = [
  [-165, 165], // J1 Base Waist
  [-135, 135], // J2 Shoulder (STRICT: -135 ~ 135)
  [-150, 150], // J3 Elbow (-150 ~ 150)
  [-145, 145], // J4 Wrist Pitch (STRICT: -145 ~ 145)
  [-165, 165], // J5 Wrist Roll (-165 ~ 165)
  [-175, 175]  // J6 Gripper Rotation (-175 ~ 175)
];

// DOM References
const piIpInput = document.getElementById('pi-ip');
const btnConnect = document.getElementById('btn-connect');
const btnAutoDetect = document.getElementById('btn-auto-detect');
const statusBadge = document.getElementById('status-badge');
const statusLabel = document.getElementById('status-label');
const btnEstop = document.getElementById('btn-estop');
const btnToggleInterlock = document.getElementById('btn-toggle-interlock');
const interlockIcon = document.getElementById('interlock-icon');
const interlockText = document.getElementById('interlock-text');

const trayCounterLabel = document.getElementById('tray-counter-label');
const trayGrid = document.getElementById('tray-grid');

const speedSlider = document.getElementById('speed-slider');
const speedLabel = document.getElementById('speed-label');
const footerText = document.getElementById('footer-text');
const footerDot = document.getElementById('footer-dot');
const simCheckbox = document.getElementById('sim-checkbox');

// Theme Switcher & Clock Elements
const themeToggleBtn = document.getElementById('theme-toggle');
const themeIcon = document.getElementById('theme-icon');
const themeText = document.getElementById('theme-text');
const themeToast = document.getElementById('theme-toast');

const digitalClockTime = document.getElementById('digital-clock-time');
const digitalClockAmpm = document.getElementById('digital-clock-ampm');
const digitalClockDate = document.getElementById('digital-clock-date');

// Automation Elements
const autoStatusPill = document.getElementById('auto-status-pill');
const autoStatusText = document.getElementById('auto-status-text');
const autoStepLiveText = document.getElementById('auto-step-live-text');
const autoTargetSlot = document.getElementById('auto-target-slot');
const btnRunTransfer = document.getElementById('btn-run-transfer');
const btnRunSweep = document.getElementById('btn-run-sweep');
const btnAbortAuto = document.getElementById('btn-abort-auto');
const customWpName = document.getElementById('custom-wp-name');
const btnSaveWp = document.getElementById('btn-save-wp');
const customWaypointsList = document.getElementById('custom-waypoints-list');


// --- API Helpers ---
async function apiPost(endpoint, data = {}) {
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await res.json();
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function apiGet(endpoint) {
  try {
    const res = await fetch(endpoint);
    return await res.json();
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function apiDelete(endpoint) {
  try {
    const res = await fetch(endpoint, { method: 'DELETE' });
    return await res.json();
  } catch (err) {
    return { success: false, error: err.message };
  }
}

function showStatus(msg, isSuccess = true) {
  if (!footerText) return;
  footerText.textContent = msg;
  if (footerDot) {
    footerDot.style.background = isSuccess ? 'var(--green)' : 'var(--amber)';
  }
}

let toastTimeout = null;
function showToast(message) {
  if (!themeToast) return;
  themeToast.textContent = message;
  themeToast.classList.add('show');
  if (toastTimeout) clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    themeToast.classList.remove('show');
  }, 2200);
}


// --- High-Precision Cleanroom Digital Clock ---
function updateCleanroomClock() {
  if (!digitalClockTime || !digitalClockAmpm || !digitalClockDate) return;

  const now = new Date();
  const hours = now.getHours();
  const mins = String(now.getMinutes()).padStart(2, '0');
  const secs = String(now.getSeconds()).padStart(2, '0');
  const h12 = String(hours % 12 || 12).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';

  digitalClockTime.textContent = `${h12}:${mins}:${secs}`;
  digitalClockAmpm.textContent = ampm;

  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  digitalClockDate.textContent = `${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
}


// --- Theme Engine (Dark & Light Mode) ---
function applyTheme(theme, notify = false) {
  state.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('cleanroom_theme', theme);

  if (theme === 'light') {
    if (themeIcon) themeIcon.textContent = '🌙';
    if (themeText) themeText.textContent = 'Dark';
    if (notify) showToast('Switched to Light Mode');
  } else {
    if (themeIcon) themeIcon.textContent = '☀️';
    if (themeText) themeText.textContent = 'Light';
    if (notify) showToast('Switched to Dark Mode');
  }

  // Synchronize 3D Digital Twin environment with theme
  applyThemeTo3D(theme);
}

function toggleTheme() {
  const newTheme = state.theme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme, true);
}


// --- Cleanroom Tab Navigation Engine ---
function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll('.cleanroom-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  // Update tab content panes
  document.querySelectorAll('.tab-content').forEach(pane => {
    pane.classList.toggle('active', pane.id === `tab-content-${tabName}`);
  });

  // If switching to teleop tab, ensure 3D twin canvas is properly sized
  if (tabName === 'teleop') {
    setTimeout(handleTwinResize, 60);
  }

  try {
    localStorage.setItem('cleanroom_active_tab', tabName);
  } catch (e) {}

  showStatus(tabName === 'teleop' ? "Manual Teleoperation & 3D Kinematics Active" : "Robot Automation Deck & Autonomous Routines Active");
}

function handleTwinResize() {
  const canvas = document.getElementById('twin-canvas');
  if (!canvas || !twinRenderer || !twinCamera) return;
  const container = canvas.parentElement;
  if (!container) return;
  const w = container.clientWidth;
  const h = container.clientHeight;
  if (w > 0 && h > 0) {
    twinCamera.aspect = w / h;
    twinCamera.updateProjectionMatrix();
    twinRenderer.setSize(w, h);
  }
}



// --- ENLARGED 3D Digital Twin Engine (Three.js) ---
let twinScene, twinCamera, twinRenderer, twinArm = {}, traySlotMeshes = [], cleanroomGrid, cleanroomTrayBase;
let isMouseDown = false, prevMousePos = { x: 0, y: 0 };

function initDigitalTwin() {
  const canvas = document.getElementById('twin-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const container = canvas.parentElement;
  const width = container.clientWidth || 600;
  const height = container.clientHeight || 520;

  twinScene = new THREE.Scene();
  const isLight = state.theme === 'light';
  twinScene.background = new THREE.Color(isLight ? 0xf0f7f7 : 0x070d18);

  // Perspective camera with clear field of view
  twinCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1200);
  setCameraView('iso');

  twinRenderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  twinRenderer.setSize(width, height);
  twinRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // Lighting
  const ambient = new THREE.AmbientLight(0xffffff, isLight ? 0.85 : 0.7);
  twinScene.add(ambient);
  const dir = new THREE.DirectionalLight(isLight ? 0x0284c7 : 0x38bdf8, 0.95);
  dir.position.set(100, 220, 120);
  twinScene.add(dir);

  // Cleanroom Base Grid (Extended grid for enlarged viewport)
  cleanroomGrid = new THREE.GridHelper(360, 24, isLight ? 0x0284c7 : 0x06b6d4, isLight ? 0x94a3b8 : 0x1e293b);
  twinScene.add(cleanroomGrid);

  // Preparation Window Platform (Left)
  const prepPlatform = new THREE.Mesh(
    new THREE.BoxGeometry(45, 6, 45),
    new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.3 })
  );
  prepPlatform.position.set(-65, 3, 40);
  twinScene.add(prepPlatform);

  // 6-Slot Medicine Pickup Tray (Right: 2 Rows x 3 Cols)
  cleanroomTrayBase = new THREE.Mesh(
    new THREE.BoxGeometry(115, 6, 80),
    new THREE.MeshStandardMaterial({ color: isLight ? 0xdbeafe : 0x131e33, roughness: 0.3 })
  );
  cleanroomTrayBase.position.set(50, 3, 50);
  twinScene.add(cleanroomTrayBase);

  // 6 Slot Cups on the Tray
  traySlotMeshes = [];
  const colXs = [20, 50, 80];
  const rowZs = [35, 65];
  for (let r = 0; r < 2; r++) {
    for (let c = 0; c < 3; c++) {
      const slotCup = new THREE.Mesh(
        new THREE.CylinderGeometry(8.5, 8.5, 14, 16),
        new THREE.MeshStandardMaterial({ color: isLight ? 0x94a3b8 : 0x1e293b, transparent: true, opacity: 0.88 })
      );
      slotCup.position.set(colXs[c], 10, rowZs[r]);
      twinScene.add(slotCup);
      traySlotMeshes.push(slotCup);
    }
  }

  // --- Hierarchical myCobot 280 Arm ---
  const metalMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.35, roughness: 0.25 });
  const blueJointMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.5, roughness: 0.2 });

  const base = new THREE.Mesh(new THREE.CylinderGeometry(20, 24, 16, 24), metalMat);
  base.position.y = 8;
  twinScene.add(base);

  // J1 Waist
  twinArm.j1 = new THREE.Group();
  twinArm.j1.position.y = 16;
  twinScene.add(twinArm.j1);
  twinArm.j1.add(new THREE.Mesh(new THREE.CylinderGeometry(15, 15, 18, 20), blueJointMat));

  // J2 Shoulder
  twinArm.j2 = new THREE.Group();
  twinArm.j2.position.set(0, 16, 0);
  twinArm.j1.add(twinArm.j2);
  const link1 = new THREE.Mesh(new THREE.CylinderGeometry(11, 11, 46, 20), metalMat);
  link1.position.y = 22;
  twinArm.j2.add(link1);

  // J3 Elbow
  twinArm.j3 = new THREE.Group();
  twinArm.j3.position.set(0, 46, 0);
  twinArm.j2.add(twinArm.j3);
  const link2 = new THREE.Mesh(new THREE.CylinderGeometry(10, 10, 42, 20), metalMat);
  link2.position.y = 20;
  twinArm.j3.add(link2);

  // J4 Wrist Pitch
  twinArm.j4 = new THREE.Group();
  twinArm.j4.position.set(0, 42, 0);
  twinArm.j3.add(twinArm.j4);
  const link3 = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 16, 16), blueJointMat);
  link3.position.y = 8;
  twinArm.j4.add(link3);

  // J5 Wrist Roll
  twinArm.j5 = new THREE.Group();
  twinArm.j5.position.set(0, 16, 0);
  twinArm.j4.add(twinArm.j5);
  const link4 = new THREE.Mesh(new THREE.CylinderGeometry(7, 7, 14, 16), metalMat);
  link4.position.y = 7;
  twinArm.j5.add(link4);

  // J6 Gripper Flange
  twinArm.j6 = new THREE.Group();
  twinArm.j6.position.set(0, 14, 0);
  twinArm.j5.add(twinArm.j6);
  const gripper = new THREE.Mesh(new THREE.BoxGeometry(16, 8, 10), blueJointMat);
  gripper.position.y = 5;
  twinArm.j6.add(gripper);

  // Initialize initial posture
  updateDigitalTwinAngles(state.angles);

  // Mouse orbit
  container.addEventListener('mousedown', (e) => { isMouseDown = true; prevMousePos = { x: e.clientX, y: e.clientY }; });
  window.addEventListener('mouseup', () => { isMouseDown = false; });
  window.addEventListener('mousemove', (e) => {
    if (!isMouseDown) return;
    twinCamera.position.x += (e.clientX - prevMousePos.x) * 0.45;
    twinCamera.position.y -= (e.clientY - prevMousePos.y) * 0.45;
    twinCamera.lookAt(0, 50, 0);
    prevMousePos = { x: e.clientX, y: e.clientY };
  });

  // Render loop
  function animate() {
    requestAnimationFrame(animate);
    twinRenderer.render(twinScene, twinCamera);
  }
  animate();

  // Responsive resize
  window.addEventListener('resize', () => {
    if (!container || !twinRenderer || !twinCamera) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    twinCamera.aspect = w / h;
    twinCamera.updateProjectionMatrix();
    twinRenderer.setSize(w, h);
  });
}

// Camera Angle Presets
function setCameraView(viewName) {
  if (!twinCamera) return;
  document.querySelectorAll('.btn-cam').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`.btn-cam[data-cam="${viewName}"]`);
  if (btn) btn.classList.add('active');

  switch (viewName) {
    case 'iso':
      twinCamera.position.set(0, 140, 290);
      twinCamera.lookAt(0, 50, 0);
      break;
    case 'top':
      twinCamera.position.set(0, 340, 40);
      twinCamera.lookAt(0, 0, 40);
      break;
    case 'front':
      twinCamera.position.set(0, 80, 320);
      twinCamera.lookAt(0, 60, 0);
      break;
    case 'side':
      twinCamera.position.set(330, 80, 40);
      twinCamera.lookAt(0, 60, 40);
      break;
  }
}

function applyThemeTo3D(theme) {
  if (!twinScene) return;
  const isLight = theme === 'light';
  twinScene.background = new THREE.Color(isLight ? 0xf0f7f7 : 0x070d18);

  if (cleanroomGrid) {
    twinScene.remove(cleanroomGrid);
    cleanroomGrid = new THREE.GridHelper(360, 24, isLight ? 0x0284c7 : 0x06b6d4, isLight ? 0x94a3b8 : 0x1e293b);
    twinScene.add(cleanroomGrid);
  }

  if (cleanroomTrayBase) {
    cleanroomTrayBase.material.color.setHex(isLight ? 0xdbeafe : 0x131e33);
  }

  // Update empty slot colors
  traySlotMeshes.forEach((mesh, idx) => {
    const isOccupied = state.tray[idx] && state.tray[idx].status === "READY";
    mesh.material.color.setHex(isOccupied ? 0x10b981 : (isLight ? 0x94a3b8 : 0x1e293b));
  });
}

function updateDigitalTwinAngles(angles) {
  if (!twinArm.j1 || !angles || angles.length !== 6) return;
  const toRad = deg => (deg * Math.PI) / 180;
  twinArm.j1.rotation.y = -toRad(angles[0]);
  twinArm.j2.rotation.z = toRad(angles[1]);
  twinArm.j3.rotation.z = toRad(angles[2]);
  twinArm.j4.rotation.z = toRad(angles[3]);
  twinArm.j5.rotation.y = toRad(angles[4]);
  twinArm.j6.rotation.z = toRad(angles[5]);

  // Update Joint Angles HUD in 3D Canvas
  const hud = document.getElementById('twin-angles-hud');
  if (hud) {
    hud.textContent = `J1: ${Math.round(angles[0])}° J2: ${Math.round(angles[1])}° J3: ${Math.round(angles[2])}° J4: ${Math.round(angles[3])}° J5: ${Math.round(angles[4])}° J6: ${Math.round(angles[5])}°`;
  }
}


// --- 6-Slot Smart Tray UI Renderer (Boxy Compartments) ---
function renderSmartTray(slots) {
  if (!trayGrid) return;
  trayGrid.innerHTML = '';
  const isLight = state.theme === 'light';

  slots.forEach(slot => {
    const isOccupied = slot.status === "READY";
    const box = document.createElement('div');
    box.className = `slot-box ${isOccupied ? 'occupied' : ''}`;
    box.innerHTML = `
      <div class="slot-top">
        <span class="slot-num-badge">SLOT ${slot.id}</span>
        <div class="slot-led-wrap ${slot.led ? 'led-active' : ''}">
          <span class="slot-led-dot"></span>
          <span>LED ${slot.led ? 'ON' : 'OFF'}</span>
        </div>
      </div>
      <div class="slot-center">
        <div class="slot-status-row">
          <span class="slot-status-badge ${isOccupied ? 'badge-ready' : 'badge-empty'}">${slot.status}</span>
        </div>
        ${isOccupied 
          ? `<span class="slot-medicine-name" title="${slot.medicine}">${slot.medicine}</span>` 
          : '<span class="slot-empty-sub">Ready for container</span>'}
      </div>
      ${isOccupied ? `
        <button class="btn-slot-collect" onclick="collectMedicineSlot(${slot.id})">
          <span>👋 Staff Collect</span>
        </button>
      ` : ''}
    `;
    trayGrid.appendChild(box);

    // Update 3D tray slot visual
    const slotIdx = slot.id - 1;
    if (traySlotMeshes[slotIdx]) {
      traySlotMeshes[slotIdx].material.color.setHex(isOccupied ? 0x10b981 : (isLight ? 0x94a3b8 : 0x1e293b));
    }
  });
}

// Staff collection handler
window.collectMedicineSlot = async function(slotId) {
  showStatus(`Simulating staff opening lid and removing medicine from Slot ${slotId}...`);
  const res = await apiPost(`/api/tray/collect_slot/${slotId}`);
  if (res.success) {
    showStatus(`Slot ${slotId} collected: LED turned OFF. Slot is now EMPTY.`);
  } else {
    showStatus(`Error: ${res.detail || res.error}`, false);
  }
};


// --- ROBOT AUTOMATION DECK ENGINE ---

// 1. Move to Calibrated Pose (One-Touch)
async function moveToPose(poseName) {
  state.currentPoseName = poseName;
  document.querySelectorAll('.auto-pose-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.pose === poseName);
  });

  const targetAngles = CALIBRATED_POSES[poseName];
  if (targetAngles) {
    // Optimistic UI & 3D update
    updateAnglesDisplay(targetAngles);
    if (autoStatusText) autoStatusText.textContent = `Aligning to ${poseName.toUpperCase()}`;
    if (autoStepLiveText) autoStepLiveText.textContent = `Automated motion: Moving arm to ${poseName.toUpperCase()} pose...`;
    showStatus(`Automated Pose: Moving to ${poseName.toUpperCase()}...`);
  }

  const res = await apiPost('/api/move_pose', { pose_name: poseName, speed: state.speed });
  if (res.angles) updateAnglesDisplay(res.angles);
  showToast(`Moved to ${poseName.toUpperCase()} Pose`);
}

// 2. Start Automated Delivery Sequence
async function startAutomatedTransfer() {
  const slotVal = autoTargetSlot ? autoTargetSlot.value : "auto";
  const targetSlot = slotVal === "auto" ? null : parseInt(slotVal);

  showStatus(`Initiating automated transfer sequence to ${slotVal === "auto" ? "next free slot" : `Slot ${slotVal}`}...`);
  if (autoStatusPill) {
    autoStatusPill.className = "badge badge-auto-running";
    if (autoStatusText) autoStatusText.textContent = "Executing";
  }

  const res = await apiPost('/api/delivery/start', {
    medicine_name: "Automated Compounding Container",
    target_slot: targetSlot
  });

  if (res.success) {
    showStatus(res.message);
    showToast(`Transfer Sequence Started: Slot ${targetSlot || 'Auto'}`);
  } else {
    showStatus(`Automation Error: ${res.detail || res.error}`, false);
    if (autoStatusPill) {
      autoStatusPill.className = "badge badge-auto-error";
      if (autoStatusText) autoStatusText.textContent = "Error";
    }
  }
}

// 3. Run Diagnostic Calibration Sweep
async function runDiagnosticSweep() {
  showStatus("Running kinematic diagnostic calibration sweep across work envelope...");
  if (autoStatusPill) {
    autoStatusPill.className = "badge badge-auto-running";
    if (autoStatusText) autoStatusText.textContent = "Diagnostic Sweep";
  }
  const res = await apiPost('/api/automation/sweep', {});
  if (res.success) {
    showToast("Kinematic Sweep Started");
  } else {
    showStatus(`Sweep Error: ${res.detail || res.error}`, false);
  }
}

// 4. Abort Active Automation
async function abortAutomation() {
  showStatus("⚠️ Aborting active automation routine...");
  await apiPost('/api/delivery/abort', {});
  if (autoStatusPill) {
    autoStatusPill.className = "badge badge-auto-standby";
    if (autoStatusText) autoStatusText.textContent = "Standby";
  }
  if (autoStepLiveText) autoStepLiveText.textContent = "Automation aborted by operator";
  updateStepperDisplay(null);
  showToast("Automation Aborted");
}

// 5. Update Sequence Stepper Visuals
function updateStepperDisplay(delivery) {
  if (!autoStepLiveText) return;
  const steps = ['home', 'pick', 'grip', 'place', 'release', 'ready'];
  const status = (delivery && delivery.status ? delivery.status : 'IDLE').toUpperCase();

  if (delivery && delivery.running) {
    if (autoStatusPill) {
      autoStatusPill.className = "badge badge-auto-running";
      if (autoStatusText) autoStatusText.textContent = `Running: ${status}`;
    }
    if (delivery.current_step_text) {
      autoStepLiveText.textContent = delivery.current_step_text;
    }
  } else {
    if (autoStatusPill && autoStatusText && autoStatusText.textContent !== "Standby") {
      autoStatusPill.className = "badge badge-auto-standby";
      autoStatusText.textContent = "Standby";
    }
  }

  // Active step index
  const activeIdxMap = {
    'PREPARING': 0,
    'PICKING': 1,
    'PLACING': 3,
    'READY': 5,
    'SWEEPING': 1
  };
  const activeIdx = activeIdxMap[status];

  steps.forEach((name, idx) => {
    const el = document.getElementById(`step-node-${name}`);
    if (el) {
      if (activeIdx !== undefined && idx === activeIdx) {
        el.className = "stepper-step active";
      } else if (activeIdx !== undefined && idx < activeIdx) {
        el.className = "stepper-step completed";
      } else {
        el.className = "stepper-step";
      }
    }
  });
}

// 6. Custom Waypoint Management (Teach & Save)
async function loadWaypoints() {
  const res = await apiGet('/api/waypoints');
  if (res.success && res.waypoints) {
    state.waypoints = res.waypoints;
    renderWaypointsList(res.waypoints);
  }
}

function renderWaypointsList(waypoints) {
  if (!customWaypointsList) return;
  customWaypointsList.innerHTML = '';
  const entries = Object.entries(waypoints);

  if (entries.length === 0) {
    customWaypointsList.innerHTML = '<div style="font-size:0.72rem; color:var(--text-dim); padding:4px;">No custom waypoints saved yet. Jog the arm and click Save.</div>';
    return;
  }

  entries.forEach(([name, data]) => {
    const item = document.createElement('div');
    item.className = 'wp-item';
    item.innerHTML = `
      <div class="wp-item-info">
        <span class="wp-item-name">📍 ${name}</span>
        <span class="wp-item-desc">[${data.angles ? data.angles.map(a => Math.round(a)).join('°, ') + '°' : ''}]</span>
      </div>
      <div class="wp-item-actions">
        <button class="btn-wp-run" onclick="runCustomWaypoint('${name}')">▶ Move</button>
        <button class="btn-wp-del" onclick="deleteCustomWaypoint('${name}')" title="Delete">✕</button>
      </div>
    `;
    customWaypointsList.appendChild(item);
  });
}

window.runCustomWaypoint = async function(name) {
  const wp = state.waypoints[name];
  if (wp && wp.angles) {
    showStatus(`Moving to custom waypoint: ${name}...`);
    updateAnglesDisplay(wp.angles);
    await apiPost('/api/angles', { angles: wp.angles, speed: state.speed });
    showToast(`Moved to Waypoint '${name}'`);
  }
};

window.deleteCustomWaypoint = async function(name) {
  const res = await apiDelete(`/api/waypoints/${encodeURIComponent(name)}`);
  if (res.success) {
    state.waypoints = res.waypoints;
    renderWaypointsList(res.waypoints);
    showToast(`Deleted Waypoint '${name}'`);
  }
};

async function saveCurrentAsWaypoint() {
  const name = customWpName ? customWpName.value.trim() : '';
  if (!name) {
    showToast("Please enter a waypoint name");
    return;
  }
  const res = await apiPost('/api/waypoints/save', {
    name: name,
    angles: state.angles,
    coords: state.coords,
    description: "Custom user-taught pose"
  });
  if (res.success) {
    state.waypoints = res.waypoints;
    renderWaypointsList(res.waypoints);
    if (customWpName) customWpName.value = '';
    showToast(`Saved Waypoint: '${name}'`);
  }
}


// --- Zero-Lag Manual Teleoperation Engine ---
async function jogJoint(joint, direction) {
  const now = Date.now();
  if (now - state.lastJogTime < state.throttleMs) return;
  state.lastJogTime = now;

  // 1. OPTIMISTIC UPDATE: Calculate and immediately render change without waiting for network!
  const idx = joint - 1;
  const currentAngle = state.angles[idx];
  const delta = direction * state.stepSize;
  const limits = JOINT_LIMITS[idx];
  const targetAngle = Math.min(Math.max(currentAngle + delta, limits[0]), limits[1]);

  state.angles[idx] = targetAngle;

  // Immediate UI & 3D update
  const disp = document.getElementById(`disp-j${joint}`);
  const slider = document.getElementById(`slider-j${joint}`);
  if (disp) disp.textContent = `${Math.round(targetAngle)}°`;
  if (slider && !slider.matches(':active')) slider.value = targetAngle;
  updateDigitalTwinAngles(state.angles);

  // 2. DISPATCH TO BACKEND IN BACKGROUND (Takes <0.2ms via reverse-sync)
  showStatus(`Jogging J${joint} ${direction > 0 ? '+' : ''}${state.stepSize}° → ${Math.round(targetAngle)}°`);
  apiPost('/api/jog', {
    joint: joint,
    direction: direction,
    step: state.stepSize,
    speed: state.speed
  }).then(res => {
    if (res.success && res.angles) {
      updateAnglesDisplay(res.angles);
    } else if (res.error) {
      showStatus(`Jog response: ${res.error}`, false);
    }
  }).catch(() => {});
}

function updateAnglesDisplay(angles) {
  if (!angles || angles.length !== 6) return;
  state.angles = angles;

  angles.forEach((angle, idx) => {
    const disp = document.getElementById(`disp-j${idx + 1}`);
    const slider = document.getElementById(`slider-j${idx + 1}`);
    if (disp) disp.textContent = `${Math.round(angle)}°`;
    if (slider && !slider.matches(':active')) slider.value = angle;

    // Update Tab 2 Live Telemetry HUD
    const autoDisp = document.getElementById(`disp-auto-j${idx + 1}`);
    if (autoDisp) autoDisp.textContent = `${Math.round(angle)}°`;
  });

  updateDigitalTwinAngles(angles);

  const coordsEl = document.getElementById('twin-coords-text');
  if (coordsEl && state.coords) {
    coordsEl.textContent = `Pose: X: ${Math.round(state.coords[0])}mm Y: ${Math.round(state.coords[1])}mm Z: ${Math.round(state.coords[2])}mm`;
  }

  // Update Tab 2 Cartesian Coordinates HUD
  const autoCoordsEl = document.getElementById('disp-auto-coords');
  if (autoCoordsEl && state.coords) {
    autoCoordsEl.textContent = `X: ${Math.round(state.coords[0])}mm Y: ${Math.round(state.coords[1])}mm Z: ${Math.round(state.coords[2])}mm`;
  }

  const autoSpeedEl = document.getElementById('auto-telemetry-speed');
  if (autoSpeedEl) {
    autoSpeedEl.textContent = `${state.speed}%`;
  }
}


// --- Emergency Stop & Interlock ---
async function triggerStop() {
  showStatus("⚠️ EMERGENCY STOP ACTIVATED: Robot motion inhibited immediately!", false);
  await apiPost('/api/stop', {});
  abortAutomation();
}

async function toggleRoofInterlock() {
  const res = await apiPost('/api/interlock/toggle', {});
  if (res.success) {
    state.roofInterlock = res.roof_interlock;
    const isClosed = state.roofInterlock === "CLOSED";
    if (btnToggleInterlock) btnToggleInterlock.className = `safety-interlock-btn ${isClosed ? '' : 'open'}`;
    if (interlockIcon) interlockIcon.textContent = isClosed ? '🔒' : '⚠️';
    if (interlockText) interlockText.textContent = `Roof Interlock: ${state.roofInterlock}`;
    showStatus(isClosed ? "Roof cover closed: Robot motion permitted." : "Roof cover OPEN: Robot motion inhibited for staff safety.", isClosed);
  }
}

async function setGripper(val) {
  // 100: Open, 50: Closed
  state.gripperValue = val;
  const btnOpen = document.getElementById('btn-gripper-open');
  const btnClose = document.getElementById('btn-gripper-close');
  if (btnOpen) btnOpen.classList.toggle('active', val === 100);
  if (btnClose) btnClose.classList.toggle('active', val === 50);
  showStatus(`Gripper set to ${val === 100 ? 'OPEN (100)' : 'GRIP (50)'}`);
  await apiPost('/api/gripper', { value: val });
}


// --- Keyboard Teleoperation Listener ---
window.addEventListener('keydown', (e) => {
  // If user is focused on an input, let ESC blur it out so controls work immediately
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
    if (e.key === 'Escape') {
      e.target.blur();
    }
    return;
  }

  if (e.key === 'Escape') {
    e.preventDefault();
    triggerStop();
    return;
  }

  // Spacebar toggles gripper
  if (e.code === 'Space' || e.key === ' ') {
    e.preventDefault();
    const nextVal = (state.gripperValue === 100) ? 50 : 100;
    setGripper(nextVal);
    return;
  }

  const map = KEY_MAPPINGS[e.code] || KEY_MAPPINGS[e.key];
  if (map) {
    e.preventDefault();
    const { joint, dir } = map;
    const btn = document.querySelector(`.btn-jog[data-key="${e.code}"]`) ||
                document.querySelector(`.btn-jog[data-joint="${joint}"][data-dir="${dir}"]`);
    if (btn) btn.classList.add('active');
    jogJoint(joint, dir);
  }
});

window.addEventListener('keyup', (e) => {
  const map = KEY_MAPPINGS[e.code] || KEY_MAPPINGS[e.key];
  if (map) {
    const { joint, dir } = map;
    const btn = document.querySelector(`.btn-jog[data-key="${e.code}"]`) ||
                document.querySelector(`.btn-jog[data-joint="${joint}"][data-dir="${dir}"]`);
    if (btn) btn.classList.remove('active');
  }
});

// Click handlers for Jog Buttons
document.querySelectorAll('.btn-jog').forEach(btn => {
  btn.addEventListener('click', () => {
    const joint = parseInt(btn.dataset.joint);
    const dir = parseInt(btn.dataset.dir);
    jogJoint(joint, dir);
  });
});

// Slider direct change with live dragging support
let sliderThrottleTimers = {};
for (let j = 1; j <= 6; j++) {
  const slider = document.getElementById(`slider-j${j}`);
  if (slider) {
    const handleSlider = (val) => {
      const newAngles = [...state.angles];
      newAngles[j - 1] = val;
      updateAnglesDisplay(newAngles);
      showStatus(`Moving J${j} to ${val}°`);
      apiPost('/api/angles', { angles: newAngles, speed: state.speed });
    };

    slider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      if (sliderThrottleTimers[j]) return;
      sliderThrottleTimers[j] = setTimeout(() => {
        sliderThrottleTimers[j] = null;
        handleSlider(val);
      }, 40);
    });

    slider.addEventListener('change', (e) => {
      const val = parseFloat(e.target.value);
      handleSlider(val);
    });
  }
}

// Step & Speed Buttons
document.querySelectorAll('.btn-step').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.btn-step').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.stepSize = parseFloat(btn.dataset.step);
    showStatus(`Step size: ${state.stepSize}°`);
  });
});

if (speedSlider && speedLabel) {
  speedSlider.addEventListener('input', (e) => {
    state.speed = parseInt(e.target.value);
    speedLabel.textContent = `${state.speed}%`;
    const autoSpeed = document.getElementById('auto-telemetry-speed');
    if (autoSpeed) autoSpeed.textContent = `${state.speed}%`;
  });
}

// Calibrated Pose One-Touch Buttons
document.querySelectorAll('.auto-pose-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const pose = btn.dataset.pose;
    if (pose) moveToPose(pose);
  });
});

// Automation Sequence Buttons
btnRunTransfer?.addEventListener('click', startAutomatedTransfer);
btnRunSweep?.addEventListener('click', runDiagnosticSweep);
btnAbortAuto?.addEventListener('click', abortAutomation);
btnSaveWp?.addEventListener('click', saveCurrentAsWaypoint);

// Gripper & Quick Standby Buttons
document.getElementById('btn-gripper-open')?.addEventListener('click', () => setGripper(100));
document.getElementById('btn-gripper-close')?.addEventListener('click', () => setGripper(50));
document.getElementById('btn-quick-home')?.addEventListener('click', () => moveToPose('home'));
document.getElementById('btn-quick-home-top')?.addEventListener('click', () => moveToPose('home'));

// Torque Management Buttons
document.getElementById('btn-torque-lock')?.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/power_on', { method: 'POST' });
    const data = await res.json();
    console.log('[TheDilution] Servos Powered & Locked:', data);
    alert('⚡ All joint servos ENERGIZED & LOCKED with torque!');
  } catch (err) {
    console.error('Failed to lock torque:', err);
  }
});

document.getElementById('btn-torque-release')?.addEventListener('click', async () => {
  if (confirm('Release all servos? The arm will become free/limp. Hold the arm so it does not drop hard!')) {
    try {
      const res = await fetch('/api/release', { method: 'POST' });
      const data = await res.json();
      console.log('[TheDilution] Servos Released:', data);
    } catch (err) {
      console.error('Failed to release servos:', err);
    }
  }
});

// Safety Listeners
btnEstop?.addEventListener('click', triggerStop);
btnToggleInterlock?.addEventListener('click', toggleRoofInterlock);

// Theme Toggle Listener
themeToggleBtn?.addEventListener('click', toggleTheme);

// Camera Angle Preset Buttons
document.querySelectorAll('.btn-cam').forEach(btn => {
  btn.addEventListener('click', () => {
    const cam = btn.dataset.cam;
    if (cam) setCameraView(cam);
  });
});

document.getElementById('btn-reset-cam')?.addEventListener('click', () => setCameraView('iso'));

// Connection Handling
if (btnConnect) {
  btnConnect.addEventListener('click', async () => {
    const ip = piIpInput.value.trim();
    showStatus(`Connecting to Pi at ${ip}...`);
    const res = await apiPost('/api/config', { pi_url: ip, simulation_mode: false });
    updateConnectionBadge(res.connected_to_pi, res.simulation_mode);
  });
}

if (btnAutoDetect) {
  btnAutoDetect.addEventListener('click', async () => {
    btnAutoDetect.textContent = '⏳ Scanning...';
    btnAutoDetect.disabled = true;
    showStatus('Scanning local subnet for myCobot 280 Pi...');
    const res = await apiGet('/api/scan_pi');
    btnAutoDetect.disabled = false;
    btnAutoDetect.textContent = '🔍 Auto-Detect';
    if (res.success && res.pi_url) {
      piIpInput.value = res.pi_url.replace('http://', '');
      showStatus(`Found myCobot Pi at ${res.pi_ip}! Connecting...`);
      const cfg = await apiPost('/api/config', { pi_url: res.pi_url, simulation_mode: false });
      updateConnectionBadge(cfg.connected_to_pi, cfg.simulation_mode);
    } else {
      showStatus('No myCobot Pi found on subnet. Verify Pi is powered and on same Wi-Fi.', false);
    }
  });
}

if (simCheckbox) {
  simCheckbox.addEventListener('change', async (e) => {
    const isSim = e.target.checked;
    await apiPost('/api/config', { simulation_mode: isSim });
    updateConnectionBadge(false, isSim);
    showStatus(isSim ? "Offline simulation mode active." : "Live hardware mode.");
  });
}

function updateConnectionBadge(connected, isSim) {
  if (!statusBadge || !statusLabel) return;
  if (isSim) {
    statusBadge.className = 'badge badge-simulated';
    statusLabel.textContent = 'Simulated';
  } else if (connected) {
    statusBadge.className = 'badge badge-connected';
    statusLabel.textContent = 'Live (Pi Connected)';
  } else {
    statusBadge.className = 'badge badge-disconnected';
    statusLabel.textContent = 'Disconnected';
  }
}


// --- Telemetry Sync Loop ---
async function syncTelemetry() {
  try {
    const data = await apiGet('/api/status');
    if (data) {
      updateConnectionBadge(data.connected, data.simulation_mode);
      if (data.angles && (Date.now() - state.lastJogTime > 500)) {
        // Only overwrite angles if not actively jogging
        updateAnglesDisplay(data.angles);
      }
      if (data.coords) state.coords = data.coords;

      // Update Tray
      if (data.tray) {
        state.tray = data.tray;
        renderSmartTray(data.tray);
      }
      if (data.tray_summary && trayCounterLabel) {
        trayCounterLabel.textContent = `Occupied: ${data.tray_summary.occupied} / 6`;
      }

      // Update Automation Stepper
      if (data.delivery) {
        state.delivery = data.delivery;
        updateStepperDisplay(data.delivery);
      }
    }
  } catch (e) {}
}


// --- Initializer ---
async function init() {
  // Apply initial theme from storage or default dark
  applyTheme(state.theme, false);

  // Initialize Real-Time Cleanroom Digital Clock and tick every 1000ms
  updateCleanroomClock();
  setInterval(updateCleanroomClock, 1000);

  // Initialize Cleanroom Tab Navigation (restore saved tab or hash)
  const savedTab = window.location.hash.includes('auto') ? 'automation' : (localStorage.getItem('cleanroom_active_tab') || 'teleop');
  switchTab(savedTab);

  // Tab button click listeners
  document.querySelectorAll('.cleanroom-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  const btnViewTwin = document.getElementById('btn-view-twin');
  if (btnViewTwin) {
    btnViewTwin.addEventListener('click', () => {
      switchTab('teleop');
    });
  }

  // Initialize ENLARGED 3D Digital Twin Engine
  initDigitalTwin();

  // Load custom automation waypoints
  await loadWaypoints();

  // Load backend configuration
  const config = await apiGet('/api/config');
  if (config && config.pi_url && piIpInput) {
    piIpInput.value = config.pi_url.replace('http://', '');
    if (simCheckbox) simCheckbox.checked = !!config.simulation_mode;
  }

  // Telemetry sync at 2 Hz
  setInterval(syncTelemetry, 500);
  showStatus("Cleanroom Robot Controller Ready • Automation Deck & 3D Kinematics Active");
}

document.addEventListener('DOMContentLoaded', init);
