import serial
import time
import json
import ssl
import paho.mqtt.client as mqtt

# -----------------------------
# SERIAL CONFIG
# -----------------------------
SERIAL_PORT = "/dev/ttyUSB0"      # Linux/Mac: /dev/ttyUSB0
BAUD_RATE = 9600

# -----------------------------
# MQTT CONFIG (mqtt-dashboard.com)
# -----------------------------
BROKER = "mqtt-dashboard.com"
PORT = 8884               # WSS PORT
CLIENT_ID = "arduino-serial-bridge"

TOPIC_LC = "thedilution/loadcell"
TOPIC_ENV = "thedilution/environment"
TOPIC_SYS = "thedilution/system"

# -----------------------------
# MQTT SETUP (WebSocket Secure)
# -----------------------------
client = mqtt.Client(
    client_id=CLIENT_ID,
    transport="websockets"
)

client.tls_set(
    cert_reqs=ssl.CERT_NONE,
    tls_version=ssl.PROTOCOL_TLS
)
client.tls_insecure_set(True)

client.connect(BROKER, PORT, keepalive=60)
client.loop_start()

print("MQTT connected to mqtt-dashboard.com (WSS)")

# -----------------------------
# SERIAL SETUP
# -----------------------------
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)
print("Serial connected")

# -----------------------------
# PARSER FUNCTION
# -----------------------------
def parse_line(line):
    try:
        parts = line.split("|")

        lc = {
            "LC1": float(parts[0].split(":")[1].replace("g", "")),
            "LC2": float(parts[1].split(":")[1].replace("g", "")),
            "LC3": float(parts[2].split(":")[1].replace("g", ""))
        }

        env = {
            "temperature": float(parts[3].split(":")[1].replace("C", "")),
            "humidity": float(parts[4].split(":")[1].replace("%", ""))
        }

        return lc, env
    except:
        return None, None

# -----------------------------
# MAIN LOOP
# -----------------------------
while True:
    try:
        if ser.in_waiting:
            line = ser.readline().decode(errors="ignore").strip()
            print("SERIAL:", line)

            if "LC1" in line:
                lc, env = parse_line(line)

                if lc:
                    client.publish(TOPIC_LC, json.dumps(lc), qos=1)
                    client.publish(TOPIC_ENV, json.dumps(env), qos=1)

            if "EMERGENCY" in line:
                client.publish(
                    TOPIC_SYS,
                    json.dumps({"event": line}),
                    qos=1
                )

    except KeyboardInterrupt:
        print("Exiting...")
        break
    except Exception as e:
        print("Error:", e)

ser.close()
client.loop_stop()
