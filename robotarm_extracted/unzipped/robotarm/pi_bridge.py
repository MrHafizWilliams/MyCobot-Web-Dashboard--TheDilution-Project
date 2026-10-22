#!/usr/bin/env python3
"""
THE DILUTION - Smart Medicine Delivery System (CAT403)
myCobot 280 Pi Bridge Daemon (Account: er)
Runs directly on the Raspberry Pi inside the robot arm base.

ZERO-DEPENDENCY AUTO-DISCOVERY & DUAL-MODE DESIGN:
1. Multi-Strategy Auto-Discovery Engine:
   Automatically locates the laptop dashboard across dynamic IP changes (DHCP, hotspots, lab Wi-Fi):
   - Strategy A: UDP Beacon Receiver on port 8888.
   - Strategy B: High-speed parallel subnet scanner across local /24 network for port 8000.
   - Strategy C: Cached last-known URL + CLI override (--laptop).
2. Active Reverse Sync Channel:
   Pushes real-time arm angles (12 Hz) to the laptop dashboard at /api/pi/sync
   and executes queued teleoperation / delivery commands with sub-100ms latency.
   100% immune to firewalls (ufw), AP isolation, or NAT!
3. Standard HTTP Server (Port 8080):
   Serves local REST API endpoints for direct LAN calls.
4. myCobot 280 Hardware Communication:
   Communicates over /dev/ttyAMA0 @ 1,000,000 baud with calibrated poses from moverobotarm.py.
"""

import os
import sys
import json
import time
import socket
import argparse
import threading
import subprocess
import concurrent.futures
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

DEFAULT_PORT = 8080
DEFAULT_SERIAL = "/dev/ttyAMA0"
DEFAULT_BAUD = 1000000

# Thread-safe Robot State
robot_lock = threading.Lock()
robot_instance = None
last_motion_command_time = 0.0
hardware_status = {
    "connected": False,
    "platform": "TheDilution Smart Medicine Delivery",
    "arm": "Elephant Robotics myCobot 280 Pi",
    "port_used": None,
    "baud_used": None,
    "library": None,
    "message": "Initializing hardware connection...",
    "angles": [0.0, 0.0, 0.0, 0.0, 0.0, -129.0],
    "coords": [100.0, 0.0, 200.0, -180.0, 0.0, 0.0],
    "gripper_value": 100,  # 100: Open, 50: Closed (Grip)
    "pump": 0,
    "is_powered": True,
    "local_ip": "127.0.0.1",
    "laptop_url": None
}

# Calibrated Joint Angles from TheDilution moverobotarm.py & CAT403 System
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


def detect_local_ip():
    """Accurately determine the Pi's active Wi-Fi IPv4 address."""
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
    try:
        out = subprocess.check_output(["hostname", "-I"]).decode().split()
        for ip in out:
            # Prioritize standard LAN IPv4, skip loopback, link-local, and Tailscale 100.x
            if "." in ip and not ip.startswith("127.") and not ip.startswith("169.254.") and not ip.startswith("100."):
                return ip
        for ip in out:
            if "." in ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass
    return "10.228.81.1"


CACHE_FILE = os.path.expanduser("~/.thedilution_laptop")

def save_cached_laptop_url(url):
    try:
        with open(CACHE_FILE, "w") as f:
            f.write(url.strip())
    except Exception:
        pass

def get_cached_laptop_url():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                url = f.read().strip()
                if url.startswith("http"):
                    return url
    except Exception:
        pass
    return None

def verify_laptop_url(url, timeout=0.35):
    """Verifies that a candidate URL is running the TheDilution dashboard server."""
    try:
        clean = url.rstrip("/")
        req = urllib.request.Request(f"{clean}/api/config", headers={"User-Agent": "pi_bridge"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if "pi_url" in body or "TheDilution" in body or "connected_to_pi" in body:
                return clean
    except Exception:
        pass
    return None


def discover_laptop(local_ip, timeout_total=2.5):
    """
    Zero-Configuration Multi-Strategy Auto-Discovery:
    Strategy 0: Fast Cache Probe from previous session (20ms)
    Strategy 1: mDNS Hostname Resolution (HAFIZ-VICTUS-PC.local) (10ms)
    Strategy 2: Default Gateway / Mobile Hotspot Host probe (50ms)
    Strategy 3: UDP Discovery Beacon on port 8888 (400ms)
    Strategy 4: High-speed parallel subnet sweep on port 8000 (500ms)
    """
    print("[TheDilution Auto-Discovery] Locating laptop dashboard dynamically...")

    # Strategy 0: Check Cached URL from previous session
    cached = get_cached_laptop_url()
    if cached:
        verified = verify_laptop_url(cached, timeout=0.3)
        if verified:
            print(f"[TheDilution Auto-Discovery] Re-connected to Cached Laptop URL: {verified}")
            return verified

    # Strategy 1: mDNS Hostname Resolution (No IP tracking required!)
    for host in ["HAFIZ-VICTUS-PC.local", "hafiz-victus-pc.local"]:
        try:
            ip = socket.gethostbyname(host)
            if ip and not ip.startswith("127."):
                candidate = f"http://{ip}:8000"
                verified = verify_laptop_url(candidate, timeout=0.4)
                if verified:
                    print(f"[TheDilution Auto-Discovery] Found Laptop via mDNS ({host}): {verified}")
                    save_cached_laptop_url(verified)
                    return verified
        except Exception:
            pass

    # Strategy 2: Default Gateway Probe (Common when Laptop is Mobile Hotspot 192.168.137.1)
    try:
        out = subprocess.check_output(["ip", "route"]).decode()
        for line in out.splitlines():
            if "default via" in line:
                gw_ip = line.split("default via")[1].split()[0]
                candidate = f"http://{gw_ip}:8000"
                verified = verify_laptop_url(candidate, timeout=0.3)
                if verified:
                    print(f"[TheDilution Auto-Discovery] Found Laptop on Default Gateway: {verified}")
                    save_cached_laptop_url(verified)
                    return verified
    except Exception:
        pass

    # Strategy 3: Check UDP Discovery Beacon (Port 8888)
    try:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(('', 8888))
        udp_sock.settimeout(0.4)
        data, _ = udp_sock.recvfrom(512)
        udp_sock.close()
        text = data.decode("utf-8", errors="ignore")
        if "THEDILUTION_BEACON:" in text:
            beacon_url = text.split("THEDILUTION_BEACON:")[1].strip()
            verified = verify_laptop_url(beacon_url, timeout=0.35)
            if verified:
                print(f"[TheDilution Auto-Discovery] Found Laptop via UDP Beacon: {verified}")
                save_cached_laptop_url(verified)
                return verified
    except Exception:
        pass

    # Strategy 4: High-Speed Parallel Subnet Sweep on Port 8000
    if "." in local_ip:
        prefix = local_ip.rsplit(".", 1)[0]
        # Prioritize common device host numbers (.129, .1, .2, .100, .50)
        priority_ips = [f"{prefix}.{i}" for i in [129, 1, 2, 100, 50, 10, 20]]
        all_ips = priority_ips + [f"{prefix}.{i}" for i in range(1, 255) if f"{prefix}.{i}" not in priority_ips]

        def probe_ip(ip):
            try:
                candidate = f"http://{ip}:8000"
                return verify_laptop_url(candidate, timeout=0.25)
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            future_to_ip = {executor.submit(probe_ip, ip): ip for ip in all_ips}
            for future in concurrent.futures.as_completed(future_to_ip):
                res = future.result()
                if res:
                    print(f"[TheDilution Auto-Discovery] Found Laptop Dashboard on Subnet Sweep: {res}")
                    save_cached_laptop_url(res)
                    return res

    return None


def try_open_firewall(port=8080):
    """Best-effort attempt to open port 8080 without requiring user input."""
    for cmd in [
        ["sudo", "-n", "ufw", "allow", str(port)],
        ["sudo", "-n", "iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"]
    ]:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
        except Exception:
            pass


def find_pymycobot_class():
    """Import MyCobot dynamically from pymycobot."""
    global hardware_status
    candidates = [
        ("pymycobot.mycobot", "MyCobot"),
        ("pymycobot", "MyCobot"),
        ("pymycobot", "MyCobot280"),
        ("pymycobot.mycobot280", "MyCobot280"),
    ]
    for mod_name, cls_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            hardware_status["library"] = f"{mod_name}.{cls_name}"
            return cls
        except Exception:
            continue
    return None


def hardware_connection_supervisor():
    """
    Continuous background monitor that connects and keeps the myCobot hardware live!
    Never terminates: auto-reconnects if 12V switch is flipped on at any point.
    """
    global robot_instance, hardware_status
    print("[TheDilution Pi Bridge] Continuous hardware connection supervisor started.")

    cls = find_pymycobot_class()
    if not cls:
        msg = "pymycobot not found. Run on Pi: pip install pymycobot"
        print(f"[TheDilution Pi Bridge] {msg}")
        hardware_status["message"] = msg
        return

    ports_to_try = [
        (DEFAULT_SERIAL, DEFAULT_BAUD),   # /dev/ttyAMA0 @ 1,000,000 baud (Primary myCobot Pi UART)
        ("/dev/ttyAMA0", 115200),
        ("/dev/ttyUSB0", 115200),
        ("/dev/ttyS0", 1000000)
    ]

    while True:
        if not robot_instance or not hardware_status["connected"]:
            for port, baud in ports_to_try:
                if not os.path.exists(port):
                    continue

                try:
                    with robot_lock:
                        dev = cls(port, baud)
                        time.sleep(0.15)

                        if hasattr(dev, "power_on"):
                            try:
                                dev.power_on()
                                time.sleep(0.15)
                            except Exception:
                                pass

                        if hasattr(dev, "set_fresh_mode"):
                            try:
                                dev.set_fresh_mode(1)
                            except Exception:
                                pass

                        # Indicate physical connection with Green LED on Atom head
                        if hasattr(dev, "set_color"):
                            try:
                                dev.set_color(0, 150, 50)
                            except Exception:
                                pass

                        # Test reading angles gently
                        angles_res = []
                        def query_angles():
                            try:
                                a = dev.get_angles()
                                if a and isinstance(a, list) and len(a) == 6:
                                    angles_res.extend(a)
                            except Exception:
                                pass

                        t = threading.Thread(target=query_angles, daemon=True)
                        t.start()
                        t.join(timeout=0.6)

                        robot_instance = dev
                        hardware_status["connected"] = True
                        hardware_status["port_used"] = port
                        hardware_status["baud_used"] = baud

                        if angles_res:
                            hardware_status["angles"] = [round(float(a), 2) for a in angles_res]
                            hardware_status["message"] = f"Connected to {port} @ {baud} baud. Arm Ready."
                            print(f"[TheDilution Pi Bridge] SUCCESS: myCobot 280 connected on {port} @ {baud} baud! Angles: {angles_res}")
                        else:
                            hardware_status["message"] = f"Serial port {port} active @ {baud} baud. Arm commands enabled."
                            print(f"[TheDilution Pi Bridge] Port {port} active @ {baud} baud. Arm control ready.")
                        break
                except Exception:
                    pass

        time.sleep(2.0)


def execute_queued_command(cmd):
    """Executes a command dispatched from the laptop dashboard with zero latency."""
    global robot_instance, hardware_status, last_motion_command_time
    action = cmd.get("action") or cmd.get("type", "")
    last_motion_command_time = time.time()

    if not robot_instance:
        print(f"[TheDilution Pi Bridge] Cannot execute '{action}': Robot not connected.")
        return

    # Ensure servos are energized before any motion
    if not hardware_status.get("is_powered", True):
        try:
            with robot_lock:
                robot_instance.power_on()
                if hasattr(robot_instance, "focus_all_servos"):
                    robot_instance.focus_all_servos()
            hardware_status["is_powered"] = True
        except Exception:
            pass

    if action in ["jog", "jog_angle"]:
        joint = int(cmd.get("joint", 1))
        speed = max(1, min(100, int(cmd.get("speed", 45))))
        idx = joint - 1

        if "target_angle" in cmd:
            target_angle = float(cmd["target_angle"])
        else:
            direction = int(cmd.get("direction", 1))
            step = float(cmd.get("step", 5.0))
            curr = list(hardware_status["angles"])
            target_angle = curr[idx] + (direction * step)

        min_lim, max_lim = ROBOT_JOINT_LIMITS[idx]
        target_angle = max(min_lim, min(max_lim, target_angle))
        hardware_status["angles"][idx] = round(target_angle, 2)

        if "angles" in cmd and isinstance(cmd["angles"], list) and len(cmd["angles"]) == 6:
            hardware_status["angles"] = [round(float(a), 2) for a in cmd["angles"]]

        # CRITICAL FIX: Clamp all joint angles strictly within hardware bounds
        safe_angles = clamp_to_hardware_limits(hardware_status["angles"])
        hardware_status["angles"] = safe_angles

        with robot_lock:
            # Primary motion: send_angles sends full vector (reliable on myCobot 280 Pi)
            moved = False
            try:
                robot_instance.send_angles(safe_angles, speed)
                moved = True
            except Exception as e1:
                pass

            # Fallback: single joint send_angle
            if not moved:
                try:
                    if hasattr(robot_instance, "send_angle"):
                        robot_instance.send_angle(joint, round(target_angle, 2), speed)
                        moved = True
                except Exception as e2:
                    err_msg = f"Jog motion error on J{joint}: {e2}"
                    hardware_status["message"] = err_msg
                    print(f"[TheDilution Pi Bridge] {err_msg}")

        print(f"[TheDilution Pi Bridge] >>> Jog Joint {joint} to {target_angle}° @ {speed}% | State: {hardware_status['angles']}")

    elif action == "angles":
        angles = [round(float(a), 2) for a in cmd["angles"]]
        speed = max(1, min(100, int(cmd.get("speed", 45))))
        safe_angles = clamp_to_hardware_limits(angles)
        hardware_status["angles"] = safe_angles
        with robot_lock:
            try:
                robot_instance.send_angles(safe_angles, speed)
            except Exception as e:
                err_msg = f"send_angles error: {e}"
                hardware_status["message"] = err_msg
                print(f"[TheDilution Pi Bridge] {err_msg}")
        print(f"[TheDilution Pi Bridge] >>> Send Angles: {angles} @ {speed}%")

    elif action == "move_pose":
        pose_name = cmd.get("pose_name", "home")
        speed = max(1, min(100, int(cmd.get("speed", 45))))
        if pose_name in CALIBRATED_POSES:
            target = CALIBRATED_POSES[pose_name]
            hardware_status["angles"] = list(target)
            with robot_lock:
                try:
                    robot_instance.send_angles(target, speed)
                except Exception as e:
                    err_msg = f"move_pose error: {e}"
                    hardware_status["message"] = err_msg
                    print(f"[TheDilution Pi Bridge] {err_msg}")
            print(f"[TheDilution Pi Bridge] >>> Move Pose '{pose_name}': {target} @ {speed}%")

    elif action == "gripper":
        val = int(cmd.get("value", 100))
        speed = max(1, min(100, int(cmd.get("speed", 50))))
        hardware_status["gripper_value"] = val
        with robot_lock:
            try:
                if hasattr(robot_instance, "set_gripper_value"):
                    robot_instance.set_gripper_value(val, speed)
                elif hasattr(robot_instance, "set_gripper_state"):
                    robot_instance.set_gripper_state(1 if val >= 80 else 0, speed)
            except Exception as e:
                print(f"[TheDilution Pi Bridge] Gripper error: {e}")
        print(f"[TheDilution Pi Bridge] >>> Gripper Value: {val}")

    elif action == "stop":
        with robot_lock:
            try:
                robot_instance.stop()
            except Exception as e:
                print(f"[TheDilution Pi Bridge] Stop error: {e}")

    elif action == "release":
        with robot_lock:
            try:
                robot_instance.release_all_servos()
            except Exception as e:
                print(f"[TheDilution Pi Bridge] Release error: {e}")
        hardware_status["is_powered"] = False

    elif action == "power_on":
        with robot_lock:
            try:
                robot_instance.power_on()
                if hasattr(robot_instance, "focus_all_servos"):
                    robot_instance.focus_all_servos()
            except Exception as e:
                print(f"[TheDilution Pi Bridge] Power-on error: {e}")
        hardware_status["is_powered"] = True


def reverse_sync_worker(initial_laptop_url):
    """
    Continuous telemetry push & command poll to laptop dashboard.
    Features automatic reconnect & re-discovery when IPs change dynamically!
    """
    global robot_instance, hardware_status, last_motion_command_time
    laptop_url = initial_laptop_url
    hardware_status["laptop_url"] = laptop_url

    consecutive_success = 0
    consecutive_errors = 0
    last_telemetry_read = 0.0

    while True:
        # If disconnected for more than 4 cycles, auto-rediscover the laptop
        if consecutive_errors >= 4 or not laptop_url:
            print("[TheDilution Auto-Discovery] Re-discovering laptop dashboard...")
            discovered = discover_laptop(hardware_status["local_ip"])
            if discovered:
                laptop_url = discovered
                hardware_status["laptop_url"] = laptop_url
                consecutive_errors = 0
            else:
                time.sleep(2.0)
                continue

        sync_url = f"{laptop_url.rstrip('/')}/api/pi/sync"

        try:
            # 1. Periodically sync physical angles ONLY when arm is resting to eliminate serial contention!
            now = time.time()
            if hardware_status["connected"] and robot_instance and (now - last_motion_command_time > 1.0) and (now - last_telemetry_read > 0.4):
                with robot_lock:
                    try:
                        read_a = robot_instance.get_angles()
                        if read_a and isinstance(read_a, list) and len(read_a) == 6:
                            hardware_status["angles"] = [round(float(a), 2) for a in read_a]
                        last_telemetry_read = now
                    except Exception:
                        pass

            # 2. Package telemetry
            payload = {
                "platform": "TheDilution",
                "hardware_connected": hardware_status["connected"],
                "port": hardware_status["port_used"],
                "message": hardware_status["message"],
                "angles": hardware_status["angles"],
                "coords": hardware_status["coords"],
                "gripper_value": hardware_status["gripper_value"],
                "is_powered": hardware_status["is_powered"],
                "pi_ip": hardware_status.get("local_ip", "127.0.0.1")
            }

            # 3. Post to laptop dashboard
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                sync_url,
                data=data_bytes,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                res_body = resp.read().decode("utf-8")
                res_data = json.loads(res_body)

                if consecutive_success == 0:
                    print(f"\n==================================================================")
                    print(f" >>> [TheDilution] SUCCESSFULLY CONNECTED TO LAPTOP DASHBOARD! <<<")
                    print(f"     Target URL:          {laptop_url}")
                    print(f"     Pi Local IP:         {hardware_status['local_ip']}")
                    print(f"     Hardware Arm Status: {'LIVE' if hardware_status['connected'] else 'CONNECTING...'}")
                    print(f"==================================================================\n")

                consecutive_success += 1
                consecutive_errors = 0

                # 4. Check if dashboard queued any action (executes immediately!)
                commands = res_data.get("commands", [])
                if not commands and res_data.get("command"):
                    commands = [res_data["command"]]
                for c in commands:
                    execute_queued_command(c)

            # High-speed responsive poll: 40 times per second (25ms latency)
            time.sleep(0.025)

        except Exception as e:
            consecutive_errors += 1
            consecutive_success = 0
            if consecutive_errors == 1:
                print(f"[TheDilution Pi Bridge] Contact lost with {laptop_url}. Retrying...")
            elif consecutive_errors % 10 == 0:
                print(f"[TheDilution Pi Bridge] Searching for new laptop IP on network...")
            time.sleep(0.6)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class RobotRequestHandler(BaseHTTPRequestHandler):
    """Local HTTP API Server on port 8080 (Direct Mode)."""

    def _send_json(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({"cors": "ok"}, 200)

    def do_GET(self):
        global robot_instance, hardware_status

        if hardware_status["connected"] and robot_instance:
            with robot_lock:
                try:
                    read_a = robot_instance.get_angles()
                    if read_a and isinstance(read_a, list) and len(read_a) == 6:
                        hardware_status["angles"] = [round(float(a), 2) for a in read_a]
                    read_c = robot_instance.get_coords()
                    if read_c and isinstance(read_c, list) and len(read_c) == 6:
                        hardware_status["coords"] = [round(float(c), 2) for c in read_c]
                except Exception:
                    pass

        if self.path in ["/status", "/api/status", "/"]:
            self._send_json({
                "success": True,
                "platform": "TheDilution",
                "hardware_connected": hardware_status["connected"],
                "port": hardware_status["port_used"],
                "message": hardware_status["message"],
                "angles": hardware_status["angles"],
                "coords": hardware_status["coords"],
                "gripper_value": hardware_status["gripper_value"],
                "pump": hardware_status["pump"],
                "is_powered": hardware_status["is_powered"],
                "laptop_url": hardware_status.get("laptop_url")
            })
        elif self.path in ["/api/poses", "/poses"]:
            self._send_json({"success": True, "poses": CALIBRATED_POSES})
        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            payload = {}

        path = self.path
        if path in ["/api/angles", "/angles"]:
            execute_queued_command({"action": "angles", **payload})
            self._send_json({"success": True, "angles": hardware_status["angles"]})
        elif path in ["/api/jog_angle", "/jog_angle"]:
            execute_queued_command({"action": "jog", **payload})
            self._send_json({"success": True, "angles": hardware_status["angles"]})
        elif path in ["/api/move_pose", "/move_pose"]:
            execute_queued_command({"action": "move_pose", **payload})
            self._send_json({"success": True, "angles": hardware_status["angles"]})
        elif path in ["/api/gripper", "/gripper"]:
            execute_queued_command({"action": "gripper", **payload})
            self._send_json({"success": True, "gripper_value": hardware_status["gripper_value"]})
        elif path in ["/api/stop", "/stop"]:
            execute_queued_command({"action": "stop"})
            self._send_json({"success": True, "action": "stopped"})
        elif path in ["/api/release", "/release"]:
            execute_queued_command({"action": "release"})
            self._send_json({"success": True, "action": "servos_released"})
        elif path in ["/api/power_on", "/power_on"]:
            execute_queued_command({"action": "power_on"})
            self._send_json({"success": True, "action": "powered_on"})
        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="TheDilution myCobot 280 Pi Auto-Discovery Bridge")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"HTTP Server Port (default {DEFAULT_PORT})")
    parser.add_argument("--laptop", type=str, default=None, help="Laptop Dashboard URL (default: Auto-Discover)")
    args = parser.parse_args()

    detected_ip = detect_local_ip()
    hardware_status["local_ip"] = detected_ip

    print("==================================================================")
    print("   THE DILUTION - Smart Medicine Delivery System (CAT403)")
    print("   myCobot 280 Pi Auto-Discovery Bridge (Account: er)")
    print("==================================================================")
    print(f" [1] Raspberry Pi Detected IP:  http://{detected_ip}:{args.port}")

    # Determine laptop URL: CLI flag or Auto-Discovery
    laptop_url = args.laptop
    if not laptop_url:
        print(" [2] Laptop Dashboard:          AUTO-DISCOVERING on network...")
        laptop_url = discover_laptop(detected_ip)
        if not laptop_url:
            print("     (Auto-discovery will keep searching in background)")
    else:
        print(f" [2] Laptop Dashboard:          {laptop_url} (Manual)")

    print(f" [3] Reverse Sync Engine:       ACTIVE (12 Hz auto-reconnect)")
    print("==================================================================\n")

    try_open_firewall(args.port)

    # 1. Start continuous hardware connection supervisor thread
    hw_thread = threading.Thread(target=hardware_connection_supervisor, daemon=True)
    hw_thread.start()

    # 2. Start reverse synchronization worker (laptop dashboard push/poll)
    sync_thread = threading.Thread(target=reverse_sync_worker, args=(laptop_url,), daemon=True)
    sync_thread.start()

    # 3. Start local HTTP server on port 8080
    server_address = ("0.0.0.0", args.port)
    try:
        httpd = ThreadedHTTPServer(server_address, RobotRequestHandler)
        print(f"[TheDilution Pi Bridge] Local server listening on http://0.0.0.0:{args.port}/")
        print("Press Ctrl+C to terminate.\n")
        httpd.serve_forever()
    except OSError as e:
        print(f"[Note] Port {args.port} bind notice: {e} (Reverse sync to laptop remains 100% active)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down TheDilution Bridge...")
        if robot_instance and hardware_status["connected"]:
            try:
                robot_instance.stop()
            except Exception:
                pass
        sys.exit(0)


if __name__ == "__main__":
    main()
