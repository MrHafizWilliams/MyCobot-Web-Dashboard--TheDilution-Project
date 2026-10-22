import time
import json
import ssl
import threading

from wisepaasdatahubedgesdk.EdgeAgent import EdgeAgent
import wisepaasdatahubedgesdk.Common.Constants as constant
from wisepaasdatahubedgesdk.Model.Edge import (
    EdgeAgentOptions,
    DCCSOptions,
    EdgeData,
    EdgeTag,
    EdgeConfig,
    DeviceConfig,
    AnalogTagConfig,
    DiscreteTagConfig,
    TextTagConfig
)
import paho.mqtt.client as mqtt

# =========================================================
# =============== WISE-PAAS SETUP ========================
# =========================================================

_edgeAgent = None

def on_connected(edgeAgent, isConnected):
    print("✔ Wise-PaaS connected")
    config = __generateConfig()
    edgeAgent.uploadConfig(action=constant.ActionType['Create'], edgeConfig=config)

def on_disconnected(edgeAgent, isDisconnected):
    print("✔ Wise-PaaS disconnected")

def edgeAgent_on_message(agent, messageReceivedEventArgs):
    print("✔ Wise-PaaS message received")

# =========================================================
# =============== CONFIG GENERATION ======================
# =========================================================

def __generateConfig():
    config = EdgeConfig()
    deviceConfig = DeviceConfig(
        id='Device1',
        name='Device1',
        description='Device1',
        deviceType='Smart Device1',
        retentionPolicyName=''
    )

    # Analog tags (Loadcells + Temperature + Humidity)
    for name in ['LC1', 'LC2', 'LC3', 'Temperature', 'Humidity']:
        deviceConfig.analogTagList.append(
            AnalogTagConfig(
                name=name,
                description=name,
                readOnly=False,
                arraySize=0,
                spanHigh=1000,
                spanLow=0,
                engineerUnit='',
                integerDisplayFormat=4,
                fractionDisplayFormat=2
            )
        )

    # Discrete / text example
    deviceConfig.discreteTagList.append(
        DiscreteTagConfig(
            name='DTag1',
            description='DTag1',
            readOnly=False,
            arraySize=0,
            state0='Stop',
            state1='Start'
        )
    )
    deviceConfig.textTagList.append(
        TextTagConfig(
            name='SystemEvent',
            description='SystemEvent',
            readOnly=False,
            arraySize=0
        )
    )

    config.node.deviceList.append(deviceConfig)
    return config

# =========================================================
# =============== EDGE AGENT INIT ========================
# =========================================================

edgeAgentOptions = EdgeAgentOptions(nodeId='9a52456d-04bf-4905-bea0-557c74531bf8')
edgeAgentOptions.connectType = constant.ConnectType['DCCS']
dccsOptions = DCCSOptions(
    apiUrl='https://api-dccs-ensaas.education.wise-paas.com/',
    credentialKey='f497ae3affd76a250448d707c96da7z6'
)
edgeAgentOptions.DCCS = dccsOptions

_edgeAgent = EdgeAgent(edgeAgentOptions)
_edgeAgent.on_connected = on_connected
_edgeAgent.on_disconnected = on_disconnected
_edgeAgent.on_message = edgeAgent_on_message

_edgeAgent.connect()
time.sleep(5)  # wait for connection

# =========================================================
# =============== MQTT SETUP =============================
# =========================================================

MQTT_BROKER = "mqtt-dashboard.com"
MQTT_PORT = 8884
MQTT_TOPICS = [
    ("thedilution/loadcell", 1),
    ("thedilution/environment", 1),
    ("thedilution/system", 1)
]

def on_mqtt_connect(client, userdata, flags, rc):
    print("✔ MQTT connected")
    for topic in MQTT_TOPICS:
        client.subscribe(topic)

def on_mqtt_message(client, userdata, msg):
    payload = msg.payload.decode(errors='ignore')
    topic = msg.topic
    print(f"[MQTT] {topic} -> {payload}")

    try:
        data = json.loads(payload)
        __sendData(data)
    except Exception as e:
        print("❌ MQTT payload error:", e)

mqtt_client = mqtt.Client(transport="websockets")
mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
mqtt_client.tls_insecure_set(True)
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()

# =========================================================
# =============== SEND DATA TO WISE-PAAS =================
# =========================================================

def __sendData(payload):
    edgeData = EdgeData()
    # Analog tags
    for tag in ['LC1', 'LC2', 'LC3', 'Temperature', 'Humidity']:
        if tag in payload:
            edgeData.tagList.append(EdgeTag('Device1', tag, payload[tag]))

    # Example discrete / system event
    if 'DTag1' in payload:
        edgeData.tagList.append(EdgeTag('Device1', 'DTag1', payload['DTag1']))
    if 'SystemEvent' in payload:
        edgeData.tagList.append(EdgeTag('Device1', 'SystemEvent', payload['SystemEvent']))

    if edgeData.tagList:
        _edgeAgent.sendData(edgeData)
        print("✔ Data sent to Wise-PaaS")

# =========================================================
# =============== MAIN LOOP ==============================
# =========================================================

print("Subscriber running, waiting for MQTT data...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping subscriber...")
