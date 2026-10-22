# myCobot 280 Pi - Medicine Control Deck & Automation Dashboard

This project provides a real-time web dashboard running on your Windows 11 laptop to control the **Elephant Robotics myCobot 280 Pi** over your local Wi-Fi network (`10.29.95.1`), featuring:
* **Interactive Keyboard Teleoperation** (Jog joints or Cartesian axes live).
* **Visual HUD Keycaps** (Lights up on-screen keys when pressed).
* **6-DOF Joint Angles Controls** (Sliders from -165° to +165°).
* **Cartesian Pose Control** (Millimeter-level XYZ movements).
* **Medicine Waypoint Recorder** (Save pick, drop, and home positions).
* **Automated Cycle Sequencer** (Execute multi-step pick & place routines).
* **Simulation Mode** (Test all controls and sequences offline).
* **Emergency Stop (`Esc`)**.

---

## 1. Quick Start: Raspberry Pi Setup (`10.29.95.1`)

The Raspberry Pi inside the robot base needs to run `pi_bridge.py` to route network commands to the internal serial port (`/dev/ttyAMA0`).

### Step A: Ensure Hardware Power
1. Plug the **8.4V / 12V 5A power adapter** into the base of the myCobot.
2. Turn the green power switch on the base to **ON** (confirm green LED is lit).

### Step B: Copy `pi_bridge.py` to the Pi
From your Windows laptop PowerShell, you can copy `pi_bridge.py` directly to the Pi via SCP:
```powershell
scp pi_bridge.py er@10.29.95.1:~/pi_bridge.py
```
*(Or use `pi@10.29.95.1` depending on your Pi username. Default password is usually `Elephant` or `raspberry`).*

### Step C: Run Diagnostic Test on Pi
In the Raspberry Pi terminal (via SSH or connected monitor):
```bash
python3 pi_bridge.py --test
```
This will test the `/dev/ttyAMA0` serial link and wiggle Joint 1 by $10^\circ$ to verify hardware.

### Step D: Start the Bridge Server on Pi
```bash
python3 pi_bridge.py
```
You will see:
`[Ready] Pi Bridge listening at http://0.0.0.0:8080/`

*(Optional: To run it automatically every time the Pi boots up, add `@reboot python3 /home/er/pi_bridge.py &` to your crontab using `crontab -e`)*.

---

## 2. Quick Start: Windows 11 Laptop

Simply double-click:
```
start_dashboard.bat
```
This launches the server and opens your browser to:
**`http://localhost:8000`**

---

## 3. Keyboard Teleoperation Controls

Click anywhere on the dashboard and use your keyboard:

### Joint Mode (Angles)
| Key | Joint | Action |
|:---:|:---:|:---|
| **A / D** | Joint 1 | Base Rotate Left / Right |
| **W / S** | Joint 2 | Shoulder Forward / Back |
| **Q / E** | Joint 3 | Elbow Up / Down |
| **R / F** | Joint 4 | Wrist 1 Pitch Up / Down |
| **T / G** | Joint 5 | Wrist 2 Roll CW / CCW |
| **Y / H** | Joint 6 | Tool Rotation CW / CCW |

### Cartesian Mode (XYZ Millimeters)
Click the **"Cartesian (XYZ)"** toggle pill on the HUD:
| Key | Axis | Action |
|:---:|:---:|:---|
| **W / S** | X Axis | Forward / Backward |
| **A / D** | Y Axis | Left / Right |
| **Q / E** | Z Axis | Up / Down |

### Universal Controls
| Key | Action |
|:---:|:---|
| **Spacebar** | Toggle Gripper / Suction Pump |
| **Escape (Esc)** | **EMERGENCY STOP** (Halts motion immediately) |

---

## 4. Medicine Pick-and-Place Automation

1. **Jog the arm to your medicine dispenser/tray** using the keyboard or sliders.
2. In the **Medicine Waypoints** panel, type a name (e.g. `Medicine Pick 1`) and click **Save Current Pose**.
3. **Jog the arm to your drop destination** (e.g. customer dispensing box).
4. Save the waypoint as `Medicine Drop 1`.
5. Under **Automated Medicine Cycle**, click **Run Medicine Automation**. The robot will:
   1. Move to Home.
   2. Move to Medicine Pick.
   3. Activate Suction Pump.
   4. Transfer to Medicine Drop.
   5. Release Suction Pump.
   6. Return safely to Home.
6. Click **Abort Cycle** or hit **Esc** at any point to stop instantly.

---

## 5. Offline Simulation Mode
If the robot is turned off or you want to demonstrate the interface, toggle the **"Simulation Mode"** switch in the top navigation bar. You can test all keyboard bindings, angle sliders, and sequences offline.
