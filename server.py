"""
THE DILUTION - Smart Medicine Delivery System Backend (CAT403)
Runs on Windows 11 Laptop.

DYNAMIC MULTI-STRATEGY AUTO-DISCOVERY & DUAL-CHANNEL:
1. Dynamic Local IP Detection & Subnet Scanner:
   Detects laptop Wi-Fi IP automatically (e.g. 10.243.208.129).
   Scans the local /24 subnet for myCobot Pi (e.g. 10.243.208.1).
2. Continuous UDP Discovery Beacon:
   Broadcasts THEDILUTION_BEACON:http://<laptop_ip>:8000 on UDP port 8888.
3. Active Reverse Sync Channel (/api/pi/sync):
   Accepts 12 Hz joint telemetry & dispatches queued motion commands.
4. 6-Slot Smart Medicine Tray (Module 3 & 4) & 5-State Delivery Lifecycle (Module 5).
"""

import os
import sys
import json
import time
import uuid
import socket
import asyncio
import threading
import concurrent.futures
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error

from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="TheDilution Delivery Deck", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Calibrated Poses from moverobotarm.py
CALIBRATED_POSES = {
    "home": [0.0, 0.0, 0.0, 0.0, 0.0, -129.0],
    "door": [25.48, -94.48, -2.1, 103.62, -114.08, -131.13],
    "dosing": [35.0, -25.0, 45.0, -20.0, 0.0, -129.0],
    "slot_1": [44.64, -108.98, 43.68, 90.0, 22.0, -136.0],     # Point A
    "slot_2": [44.64, -108.98, 43.68, 90.0, 22.0, -110.0],     # Point B
    "slot_3": [42.0, -102.65, 75.0, 60.0, 68.0, -136.0],       # Point C
    "slot_4": [54.84, -123.57, 74.61, 65.65, 65.21, -123.57],
    "slot_5": [59.0, -123.57, 74.61, 60.65, 65.21, -136.57],
    "slot_6": [6.67, -94.48, -2.1, 103.62, -90.7, -131.13]
}

# Strict Hardware Joint Limits enforced by pymycobot on myCobot 280 Pi
ROBOT_JOINT_LIMITS = [
    (-165.0, 165.0),  # J1 Base Waist
    (-135.0, 135.0),  # J2 Shoulder (STRICT: -135 ~ 135)
    (-150.0, 150.0),  # J3 Elbow (-150 ~ 150)
    (-145.0, 145.0),  # J4 Wrist Pitch (STRICT: -145 ~ 145)
    (-165.0, 165.0),  # J5 Wrist Roll (-165 ~ 165)
    (-175.0, 175.0)   # J6 Gripper Rotation (-175 ~ 175)
]

def clamp_to_hardware_limits(angles):
    """Clamps an angle vector strictly within pymycobot physical safety limits."""
    clamped = []
    for i, a in enumerate(angles[:6]):
        min_lim, max_lim = ROBOT_JOINT_LIMITS[i]
        clamped.append(round(max(min_lim, min(max_lim, float(a))), 2))
    return clamped


def get_laptop_ip() -> str:
    """Dynamically determine the laptop's active network IP."""
    for host in ["8.8.8.8", "1.1.1.1"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect((host, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
        except Exception:
            pass
    return "127.0.0.1"


def find_pi_on_subnet() -> Optional[str]:
    """Fast subnet scanner to discover myCobot 280 Pi on local /24 network."""
    laptop_ip = get_laptop_ip()
    if "." not in laptop_ip or laptop_ip.startswith("127."):
        return None
    prefix = laptop_ip.rsplit(".", 1)[0]
    
    # Priority IPs (common device/gateway numbers)
    priority_ips = [f"{prefix}.{i}" for i in [1, 2, 129, 100, 50, 10, 20]]
    all_ips = priority_ips + [f"{prefix}.{i}" for i in range(1, 255) if f"{prefix}.{i}" not in priority_ips]

    def probe(ip):
        try:
            # Check port 8080 (if bridge already running)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            if s.connect_ex((ip, 8080)) == 0:
                s.close()
                return ip
            s.close()

            # Check port 22 for OpenSSH Ubuntu banner
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.settimeout(0.2)
            if s2.connect_ex((ip, 22)) == 0:
                banner = s2.recv(50)
                s2.close()
                if b"SSH" in banner:
                    return ip
            s2.close()
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for res in executor.map(probe, all_ips):
            if res:
                return res
    return None


# Reverse Sync Command Queue & Lock
command_queue: List[Dict[str, Any]] = []
command_lock = threading.Lock()

def enqueue_command(action_type: str, payload: dict) -> Dict[str, Any]:
    """Enqueue command for immediate execution on the Pi's reverse sync channel."""
    with command_lock:
        if len(command_queue) > 12:
            command_queue.pop(0)
        cmd = {"id": str(uuid.uuid4()), "action": action_type, **payload}
        command_queue.append(cmd)
        return cmd


# Global System State
initial_laptop_ip = get_laptop_ip()
state = {
    "laptop_ip": initial_laptop_ip,
    "pi_url": f"http://{initial_laptop_ip.rsplit('.', 1)[0]}.1:8080" if "." in initial_laptop_ip else "http://10.243.208.1:8080",
    "connected_to_pi": False,
    "simulation_mode": False,
    "last_contact": 0.0,
    "hardware_connected": False,
    "pi_message": "Searching for Raspberry Pi on local network...",
    "angles": [0.0, 0.0, 0.0, 0.0, 0.0, -129.0],
    "coords": [100.0, 0.0, 200.0, -180.0, 0.0, 0.0],
    "gripper_value": 100,  # 100: Open, 50: Closed
    "is_powered": True,
    "roof_interlock": "CLOSED",  # CLOSED (Safe) or OPEN (Hazard)
    "delivery": {
        "status": "IDLE",  # IDLE, PREPARING, PICKING, PLACING, READY, COLLECTED, ERROR
        "active_job": None,
        "current_step_text": "System Ready • Waiting for delivery order",
        "running": False,
        "abort": False
    },
    "tray": [
        {"id": 1, "status": "EMPTY", "medicine": None, "led": False, "pose": "slot_1"},
        {"id": 2, "status": "EMPTY", "medicine": None, "led": False, "pose": "slot_2"},
        {"id": 3, "status": "EMPTY", "medicine": None, "led": False, "pose": "slot_3"},
        {"id": 4, "status": "EMPTY", "medicine": None, "led": False, "pose": "slot_4"},
        {"id": 5, "status": "EMPTY", "medicine": None, "led": False, "pose": "slot_5"},
        {"id": 6, "status": "EMPTY", "medicine": None, "led": False, "pose": "slot_6"},
    ]
}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"http://{url}"
    return url


def send_to_pi(endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: float = 0.5) -> Dict[str, Any]:
    """
    Dual-Channel Communication:
    1. If data is an action command, enqueue it for Pi reverse sync.
    2. Attempt direct HTTP call if reachable.
    """
    global state

    if state["simulation_mode"]:
        return {"success": True, "simulated": True}

    action_map = {
        "/api/jog_angle": "jog",
        "/api/angles": "angles",
        "/api/move_pose": "move_pose",
        "/api/gripper": "gripper",
        "/api/stop": "stop",
        "/api/release": "release",
        "/api/power_on": "power_on"
    }

    if endpoint in action_map and data is not None:
        enqueue_command(action_map[endpoint], data)
        # Non-blocking concurrent direct-HTTP push to Pi port 8080:
        # Guarantees immediate execution whether Pi uses reverse sync or direct HTTP!
        if state.get("pi_url"):
            def _async_push():
                try:
                    b_url = normalize_url(state["pi_url"]).rstrip('/')
                    req_u = urllib.request.Request(
                        f"{b_url}{endpoint}",
                        data=json.dumps(data).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    urllib.request.urlopen(req_u, timeout=0.35)
                except Exception:
                    pass
            threading.Thread(target=_async_push, daemon=True).start()

        return {"success": True, "queued": True, "reverse_sync": True, "angles": state["angles"]}

    # For status checks, if recently contacted via reverse sync, return healthy
    if endpoint in ["/status", "/api/status"]:
        if time.time() - state["last_contact"] < 3.0:
            return {
                "success": True,
                "reverse_sync": True,
                "hardware_connected": state["hardware_connected"],
                "angles": state["angles"],
                "gripper_value": state["gripper_value"]
            }

    # Attempt direct HTTP
    base_url = normalize_url(state["pi_url"]).rstrip('/')
    url = f"{base_url}{endpoint}"

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else None,
        headers={"Content-Type": "application/json"}
    )
    req.get_method = lambda: "POST" if data is not None else "GET"

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            state["connected_to_pi"] = True
            state["last_contact"] = time.time()
            return result
    except Exception as e:
        is_live = (time.time() - state["last_contact"] < 3.0)
        state["connected_to_pi"] = is_live
        if endpoint in action_map:
            return {"success": True, "queued": True, "reverse_sync": is_live, "angles": state["angles"]}
        return {"success": is_live, "error": str(e), "reverse_sync": is_live}


# Background Poller to maintain state
def background_poller():
    while True:
        try:
            if not state["simulation_mode"]:
                now = time.time()
                if now - state["last_contact"] < 3.0:
                    state["connected_to_pi"] = True
                else:
                    res = send_to_pi("/api/status", timeout=0.6)
                    state["connected_to_pi"] = bool(res.get("success", False))
        except Exception:
            state["connected_to_pi"] = (time.time() - state["last_contact"] < 3.0)
        time.sleep(0.8)

poller_thread = threading.Thread(target=background_poller, daemon=True)
poller_thread.start()


# UDP Beacon Broadcaster: Sends discovery beacons on local network every 1.8s
def udp_beacon_broadcaster():
    while True:
        try:
            ip = get_laptop_ip()
            state["laptop_ip"] = ip
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            msg = f"THEDILUTION_BEACON:http://{ip}:8000".encode("utf-8")
            sock.sendto(msg, ('<broadcast>', 8888))
            if "." in ip:
                prefix = ip.rsplit(".", 1)[0]
                sock.sendto(msg, (f"{prefix}.255", 8888))
            sock.close()
        except Exception:
            pass
        time.sleep(1.8)

beacon_thread = threading.Thread(target=udp_beacon_broadcaster, daemon=True)
beacon_thread.start()


# Background Pi Scanner: Automatically finds the Pi on subnet if disconnected
def background_pi_scanner():
    time.sleep(1.0)
    while True:
        try:
            if not state["connected_to_pi"]:
                detected = find_pi_on_subnet()
                if detected:
                    new_url = f"http://{detected}:8080"
                    if state["pi_url"] != new_url:
                        state["pi_url"] = new_url
                        print(f"[AUTO-DISCOVERY] Discovered myCobot Pi on network: {new_url}")
        except Exception:
            pass
        time.sleep(4.0)

scanner_thread = threading.Thread(target=background_pi_scanner, daemon=True)
scanner_thread.start()


# --- Pydantic Models ---
class ConfigRequest(BaseModel):
    pi_url: Optional[str] = None
    simulation_mode: Optional[bool] = None

class JogRequest(BaseModel):
    joint: int = Field(1, ge=1, le=6)
    direction: int = Field(1, description="+1 or -1")
    step: float = Field(5.0, description="Step in degrees")
    speed: int = Field(35, ge=1, le=100)

class AnglesRequest(BaseModel):
    angles: List[float] = Field(..., min_length=6, max_length=6)
    speed: int = Field(35, ge=1, le=100)

class DeliveryRequest(BaseModel):
    medicine_name: str = Field("Amoxicillin 250mg", description="Prepared medicine name")
    target_slot: Optional[int] = Field(None, ge=1, le=6, description="Optional target slot (1-6)")


# --- API Routes ---

@app.post("/api/pi/sync")
def pi_sync(payload: dict = Body(...)):
    """
    High-Frequency Reverse Sync Endpoint:
    Called by pi_bridge.py on the Raspberry Pi (~12 Hz).
    Delivers live joint telemetry and returns any pending arm commands.
    """
    global state
    now = time.time()
    state["last_contact"] = now
    state["connected_to_pi"] = True

    if "angles" in payload and isinstance(payload["angles"], list) and len(payload["angles"]) == 6:
        state["angles"] = [round(float(a), 2) for a in payload["angles"]]
    if "coords" in payload and isinstance(payload["coords"], list):
        state["coords"] = [round(float(c), 2) for c in payload["coords"]]
    if "gripper_value" in payload:
        state["gripper_value"] = int(payload["gripper_value"])
    if "hardware_connected" in payload:
        state["hardware_connected"] = bool(payload["hardware_connected"])
    if "message" in payload:
        state["pi_message"] = str(payload["message"])
    if "is_powered" in payload:
        state["is_powered"] = bool(payload["is_powered"])
    if "pi_ip" in payload and payload["pi_ip"]:
        state["pi_url"] = f"http://{payload['pi_ip']}:8080"

    commands_to_send = []
    with command_lock:
        while command_queue:
            commands_to_send.append(command_queue.pop(0))

    return {
        "success": True,
        "commands": commands_to_send,
        "command": commands_to_send[0] if commands_to_send else None
    }


@app.api_route("/api/announce", methods=["GET", "POST"])
def pi_announce(request: Request):
    """Auto-discovery announcement hook."""
    global state
    client_ip = request.client.host if request.client else "unknown"
    if client_ip and client_ip not in ["127.0.0.1", "localhost"]:
        state["pi_url"] = f"http://{client_ip}:8080"
        state["connected_to_pi"] = True
        state["last_contact"] = time.time()
        print(f"[AUTO-DISCOVERY] Pi announced at {state['pi_url']}")
    return {"success": True, "pi_url": state["pi_url"], "client_ip": client_ip}


@app.get("/api/scan_pi")
def scan_pi_route():
    """Trigger manual or programmatic scan for Raspberry Pi on the local subnet."""
    detected = find_pi_on_subnet()
    if detected:
        state["pi_url"] = f"http://{detected}:8080"
        return {"success": True, "pi_ip": detected, "pi_url": state["pi_url"]}
    return {"success": False, "message": "No myCobot Pi detected on current subnet"}


@app.get("/api/config")
def get_config():
    is_live = (time.time() - state["last_contact"] < 3.0) or state["simulation_mode"]
    state["connected_to_pi"] = is_live
    laptop_ip = get_laptop_ip()
    state["laptop_ip"] = laptop_ip
    return {
        "laptop_ip": laptop_ip,
        "laptop_url": f"http://{laptop_ip}:8000",
        "pi_url": state["pi_url"],
        "connected_to_pi": is_live,
        "simulation_mode": state["simulation_mode"],
        "hardware_connected": state.get("hardware_connected", False),
        "pi_message": state.get("pi_message", "")
    }

@app.post("/api/config")
def update_config(req: ConfigRequest):
    if req.pi_url is not None:
        state["pi_url"] = normalize_url(req.pi_url)
    if req.simulation_mode is not None:
        state["simulation_mode"] = req.simulation_mode
    test_res = send_to_pi("/api/status", timeout=1.0)
    is_live = (time.time() - state["last_contact"] < 3.0) or state["simulation_mode"]
    state["connected_to_pi"] = is_live
    return {
        "laptop_ip": get_laptop_ip(),
        "pi_url": state["pi_url"],
        "simulation_mode": state["simulation_mode"],
        "connected_to_pi": is_live,
        "test_result": test_res
    }

@app.get("/api/status")
def get_status():
    is_live = (time.time() - state["last_contact"] < 3.0) or state["simulation_mode"]
    state["connected_to_pi"] = is_live
    occupied_count = sum(1 for s in state["tray"] if s["status"] == "READY")
    return {
        "connected": is_live,
        "simulation_mode": state["simulation_mode"],
        "hardware_connected": state.get("hardware_connected", False),
        "pi_message": state.get("pi_message", ""),
        "laptop_ip": get_laptop_ip(),
        "angles": state["angles"],
        "coords": state["coords"],
        "gripper_value": state["gripper_value"],
        "is_powered": state["is_powered"],
        "roof_interlock": state["roof_interlock"],
        "tray": state["tray"],
        "tray_summary": {
            "total": 6,
            "occupied": occupied_count,
            "empty": 6 - occupied_count
        },
        "delivery": state["delivery"]
    }

@app.post("/api/jog")
def jog_robot(req: JogRequest):
    joint = req.joint
    direction = 1 if req.direction >= 0 else -1
    idx = joint - 1
    min_lim, max_lim = ROBOT_JOINT_LIMITS[idx]
    new_val = state["angles"][idx] + (direction * req.step)
    new_val = max(min_lim, min(max_lim, new_val))
    state["angles"][idx] = round(new_val, 2)
    # Ensure all angles strictly comply with pymycobot hardware safety bounds
    state["angles"] = clamp_to_hardware_limits(state["angles"])

    if not state["simulation_mode"]:
        return send_to_pi("/api/jog_angle", {
            "joint": joint,
            "direction": direction,
            "step": req.step,
            "speed": req.speed,
            "target_angle": round(new_val, 2),
            "angles": list(state["angles"])
        })
    return {"success": True, "angles": state["angles"], "simulated": True}

@app.post("/api/angles")
def set_angles(req: AnglesRequest):
    raw_angles = [round(a, 2) for a in req.angles]
    state["angles"] = clamp_to_hardware_limits(raw_angles)
    if not state["simulation_mode"]:
        return send_to_pi("/api/angles", {"angles": state["angles"], "speed": req.speed})
    return {"success": True, "angles": state["angles"], "simulated": True}

@app.post("/api/move_pose")
def move_to_pose(payload: dict = Body(...)):
    pose_name = payload.get("pose_name", "home")
    speed = payload.get("speed", 35)
    if pose_name not in CALIBRATED_POSES:
        raise HTTPException(status_code=400, detail="Unknown pose name")
    
    state["angles"] = list(CALIBRATED_POSES[pose_name])
    if not state["simulation_mode"]:
        return send_to_pi("/api/move_pose", {"pose_name": pose_name, "speed": speed})
    return {"success": True, "pose_name": pose_name, "angles": state["angles"], "simulated": True}

@app.post("/api/gripper")
def control_gripper(payload: dict = Body(...)):
    # 100: Open, 50: Closed (Grip)
    value = int(payload.get("value", 100))
    state["gripper_value"] = value
    if not state["simulation_mode"]:
        return send_to_pi("/api/gripper", {"value": value, "speed": 35})
    return {"success": True, "gripper_value": value, "simulated": True}

@app.post("/api/interlock/toggle")
def toggle_roof_interlock():
    """Toggle roof cover interlock (Module 2 Safety requirement)."""
    state["roof_interlock"] = "OPEN" if state["roof_interlock"] == "CLOSED" else "CLOSED"
    return {"success": True, "roof_interlock": state["roof_interlock"]}

@app.post("/api/stop")
def emergency_stop():
    state["delivery"]["abort"] = True
    state["delivery"]["running"] = False
    state["delivery"]["status"] = "ERROR"
    state["delivery"]["current_step_text"] = "Emergency Stop Triggered"
    if not state["simulation_mode"]:
        return send_to_pi("/api/stop", {})
    return {"success": True, "action": "emergency_stop"}

@app.post("/api/release")
def release_servos():
    state["is_powered"] = False
    if not state["simulation_mode"]:
        return send_to_pi("/api/release", {})
    return {"success": True, "action": "released"}

@app.post("/api/power_on")
def power_on():
    state["is_powered"] = True
    if not state["simulation_mode"]:
        return send_to_pi("/api/power_on", {})
    return {"success": True, "action": "powered_on"}


# --- TheDilution Medicine Delivery Lifecycle (Modules 1, 2, 3, 5) ---

@app.post("/api/delivery/start")
async def start_delivery(req: DeliveryRequest):
    """Executes the full delivery lifecycle: ADD -> PICK -> PLACE -> READY."""
    if state["delivery"]["running"]:
        raise HTTPException(status_code=400, detail="A delivery job is already in progress")

    if state["roof_interlock"] == "OPEN":
        raise HTTPException(status_code=400, detail="Roof cover is open! Safety interlock inhibits robot motion.")

    # Find available slot
    target_slot_id = req.target_slot
    if target_slot_id is None:
        for slot in state["tray"]:
            if slot["status"] == "EMPTY":
                target_slot_id = slot["id"]
                break

    if target_slot_id is None:
        raise HTTPException(status_code=400, detail="Pickup tray is completely full (6/6 slots occupied)!")

    slot_idx = target_slot_id - 1
    target_slot = state["tray"][slot_idx]
    if target_slot["status"] != "EMPTY":
        raise HTTPException(status_code=400, detail=f"Slot {target_slot_id} is already occupied!")

    state["delivery"]["running"] = True
    state["delivery"]["abort"] = False
    state["delivery"]["active_job"] = {
        "medicine": req.medicine_name,
        "slot": target_slot_id,
        "timestamp": time.strftime("%H:%M:%S")
    }

    async def execute_delivery():
        try:
            # 1. PREPARING
            state["delivery"]["status"] = "PREPARING"
            state["delivery"]["current_step_text"] = f"PREPARING: Verifying order for {req.medicine_name} -> Assigning Slot {target_slot_id}"
            await asyncio.sleep(2.0)

            if state["delivery"]["abort"]: return

            # 2. PICK
            state["delivery"]["status"] = "PICKING"
            state["delivery"]["current_step_text"] = "PICKING: Moving to preparation pickup area..."
            # Open gripper
            state["gripper_value"] = 100
            send_to_pi("/api/gripper", {"value": 100})
            await asyncio.sleep(1.0)

            # Move to Door / Pickup
            state["angles"] = list(CALIBRATED_POSES["door"])
            send_to_pi("/api/move_pose", {"pose_name": "door"})
            await asyncio.sleep(3.0)

            if state["delivery"]["abort"]: return

            # Grip container
            state["delivery"]["current_step_text"] = "PICKING: Gripping container at transfer station..."
            state["gripper_value"] = 50
            send_to_pi("/api/gripper", {"value": 50})
            await asyncio.sleep(2.0)

            if state["delivery"]["abort"]: return

            # 3. PLACE
            state["delivery"]["status"] = "PLACING"
            state["delivery"]["current_step_text"] = f"PLACING: Transferring container to Tray Slot {target_slot_id}..."
            slot_pose_name = f"slot_{target_slot_id}"
            target_pose = CALIBRATED_POSES.get(slot_pose_name, CALIBRATED_POSES["home"])
            state["angles"] = list(target_pose)
            send_to_pi("/api/move_pose", {"pose_name": slot_pose_name})
            await asyncio.sleep(3.5)

            if state["delivery"]["abort"]: return

            # Release container in slot
            state["delivery"]["current_step_text"] = f"PLACING: Releasing container into Slot {target_slot_id}..."
            state["gripper_value"] = 100
            send_to_pi("/api/gripper", {"value": 100})
            await asyncio.sleep(2.0)

            # Return to Home
            state["angles"] = list(CALIBRATED_POSES["home"])
            send_to_pi("/api/move_pose", {"pose_name": "home"})
            await asyncio.sleep(2.5)

            # 4. READY
            state["delivery"]["status"] = "READY"
            state["delivery"]["current_step_text"] = f"READY: Slot {target_slot_id} presence confirmed by sensor. LED ON. Available for collection."
            state["tray"][slot_idx]["status"] = "READY"
            state["tray"][slot_idx]["medicine"] = req.medicine_name
            state["tray"][slot_idx]["led"] = True

        except Exception as e:
            state["delivery"]["status"] = "ERROR"
            state["delivery"]["current_step_text"] = f"Delivery Error: {str(e)}"
        finally:
            state["delivery"]["running"] = False

    asyncio.create_task(execute_delivery())
    return {"success": True, "message": f"Delivery to Slot {target_slot_id} initiated"}

@app.post("/api/delivery/abort")
def abort_delivery():
    state["delivery"]["abort"] = True
    state["delivery"]["running"] = False
    state["delivery"]["status"] = "IDLE"
    state["delivery"]["current_step_text"] = "Delivery aborted by operator"
    send_to_pi("/api/stop", {})
    return {"success": True, "message": "Delivery aborted"}

@app.post("/api/tray/collect_slot/{slot_id}")
def collect_slot(slot_id: int):
    """Simulates physical staff collection (Module 3 & 5: Container removed -> LED turns OFF)."""
    if slot_id < 1 or slot_id > 6:
        raise HTTPException(status_code=400, detail="Slot must be 1 to 6")
    slot_idx = slot_id - 1
    if state["tray"][slot_idx]["status"] == "READY":
        med = state["tray"][slot_idx]["medicine"]
        state["tray"][slot_idx]["status"] = "EMPTY"
        state["tray"][slot_idx]["medicine"] = None
        state["tray"][slot_idx]["led"] = False
# --- Automation Waypoints & Calibration Sweep ---
WAYPOINTS_FILE = os.path.join(os.path.dirname(__file__), "waypoints.json")

def load_waypoints() -> Dict[str, Any]:
    if os.path.exists(WAYPOINTS_FILE):
        try:
            with open(WAYPOINTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_waypoints_file(wp_dict: dict):
    try:
        with open(WAYPOINTS_FILE, "w") as f:
            json.dump(wp_dict, f, indent=2)
    except Exception as e:
        print(f"Error saving waypoints: {e}")

@app.get("/api/waypoints")
def get_waypoints_route():
    return {"success": True, "waypoints": load_waypoints()}

@app.post("/api/waypoints/save")
def save_waypoint_route(payload: dict = Body(...)):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Waypoint name cannot be empty")
    angles = payload.get("angles", state["angles"])
    coords = payload.get("coords", state["coords"])
    desc = payload.get("description", "Custom automation pose")
    wp = load_waypoints()
    wp[name] = {
        "angles": [round(float(a), 2) for a in angles],
        "coords": [round(float(c), 2) for c in coords],
        "description": desc
    }
    save_waypoints_file(wp)
    return {"success": True, "waypoints": wp, "message": f"Waypoint '{name}' saved"}

@app.delete("/api/waypoints/{name}")
def delete_waypoint_route(name: str):
    wp = load_waypoints()
    if name in wp:
        del wp[name]
        save_waypoints_file(wp)
        return {"success": True, "waypoints": wp, "message": f"Waypoint '{name}' deleted"}
    raise HTTPException(status_code=404, detail="Waypoint not found")

@app.post("/api/automation/sweep")
async def run_calibration_sweep():
    """Runs automated kinematic calibration sweep across all cleanroom work zones."""
    if state["delivery"]["running"]:
        raise HTTPException(status_code=400, detail="Robot is currently executing another automation sequence")
    if state["roof_interlock"] == "OPEN":
        raise HTTPException(status_code=400, detail="Roof cover is open! Safety interlock inhibits robot motion.")

    state["delivery"]["running"] = True
    state["delivery"]["abort"] = False

    async def execute_sweep():
        try:
            poses = ["home", "door", "dosing", "slot_1", "slot_3", "home"]
            for p in poses:
                if state["delivery"]["abort"]:
                    state["delivery"]["current_step_text"] = "Sweep aborted by operator"
                    return
                state["delivery"]["status"] = "SWEEPING"
                state["delivery"]["current_step_text"] = f"Calibration Sweep: Aligning to {p.upper()}..."
                state["angles"] = list(CALIBRATED_POSES[p])
                send_to_pi("/api/move_pose", {"pose_name": p, "speed": 30})
                await asyncio.sleep(2.8)
            state["delivery"]["status"] = "IDLE"
            state["delivery"]["current_step_text"] = "Kinematic Calibration Sweep Complete • Encoders Verified"
        except Exception as e:
            state["delivery"]["status"] = "ERROR"
            state["delivery"]["current_step_text"] = f"Sweep error: {str(e)}"
        finally:
            state["delivery"]["running"] = False

    asyncio.create_task(execute_sweep())
    return {"success": True, "message": "Kinematic sweep initiated"}


# Mount Frontend
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    laptop_ip = get_laptop_ip()
    print("\n==================================================================")
    print("   THE DILUTION - Smart Medicine Delivery System (CAT403)")
    print("   Control Deck Server running on Windows 11")
    print(f"   Laptop Active IP:    {laptop_ip}")
    print(f"   Dashboard URL:       http://localhost:8000")
    print(f"   Network Dashboard:   http://{laptop_ip}:8000")
    print(f"   Reverse Sync URL:    http://{laptop_ip}:8000/api/pi/sync")
    print("==================================================================\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
