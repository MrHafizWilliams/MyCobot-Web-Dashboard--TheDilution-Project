import datetime
import time
import string
import random
import threading
import serial 

from wisepaasdatahubedgesdk.EdgeAgent import EdgeAgent
import wisepaasdatahubedgesdk.Common.Constants as constant
from wisepaasdatahubedgesdk.Model.Edge import EdgeAgentOptions, MQTTOptions, DCCSOptions, EdgeData, EdgeTag, EdgeStatus, EdgeDeviceStatus, EdgeConfig, NodeConfig, DeviceConfig, AnalogTagConfig, DiscreteTagConfig, TextTagConfig
from wisepaasdatahubedgesdk.Common.Utils import RepeatedTimer

# =========================================================================
# ⚙️ CONFIGURATION SECTION: WISE-PAAS AND SERIAL
# =========================================================================

# --- WISE-PAAS DCCS Credentials ---
WISEPAAS_NODE_ID = '9a52456d-04bf-4905-bea0-557c74531bf8'  # <-- YOUR Node ID
WISEPAAS_API_URL = 'https://api-dccs-ensaas.education.wise-paas.com/' # <-- YOUR API URL
WISEPAAS_CREDENTIAL_KEY = 'f497ae3affd76a250448d707c96da7z6' # <-- YOUR Credential Key

# --- Serial Port Settings ---
# *** IMPORTANT: Change the serial port to match your Arduino connection ***
SERIAL_PORT = '/dev/ttyUSB0' 
SERIAL_BAUD_RATE = 9600 # Must match Arduino's Serial.begin(9600)
# =========================================================================


# --- GLOBAL SENSOR DATA STORAGE ---
latest_sensor_data = {
    'LC1': 0.0,
    'LC2': 0.0,
    'LC3': 0.0,
    'T': 0.0,
    'H': 0.0
}
ser = None 
# -------------------------------------

def on_connected(edgeAgent, isConnected):
    print("connected !")
    config = __generateConfig()
    _edgeAgent.uploadConfig(action = constant.ActionType['Create'], edgeConfig = config)
    

def on_disconnected(edgeAgent, isDisconnected):
    print("disconnected !")

def edgeAgent_on_message(agent, messageReceivedEventArgs):
    global ser
    print("edgeAgent_on_message: Received command from cloud")
    print(f"Topic: {messageReceivedEventArgs.topic}, Message: {messageReceivedEventArgs.message}")
    
    command_str = messageReceivedEventArgs.message
    if ser and command_str:
        print(f"Sending command to Arduino: {command_str}")
        try:
            # The Arduino expects a newline/carriage return
            ser.write(f"{command_str}\n".encode())
        except Exception as e:
            print(f"Error writing to serial: {e}")

def read_serial_data():
    global latest_sensor_data
    global ser
    
    try:
        # Initialize serial connection using constants
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD_RATE, timeout=1) 
        print(f"Serial port {SERIAL_PORT} opened successfully.")
        time.sleep(2) 
        
    except serial.SerialException as e:
        print(f"Could not open serial port {SERIAL_PORT}: {e}")
        return

    while True:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if line:
                if line.startswith("LC1:"):
                    parts = line.split('|')
                    new_data = {}
                    
                    for part in parts:
                        part = part.strip()
                        if ':' in part:
                            tag_part, val_unit_part = part.split(':', 1)
                            tag = tag_part.strip()
                            value_str = val_unit_part.strip().split(' ')[0] 
                            
                            try:
                                if tag.startswith('LC'):
                                    new_data[tag] = float(value_str)
                                elif tag == 'T':
                                    new_data[tag] = float(value_str)
                                elif tag == 'H':
                                    new_data[tag] = float(value_str)
                                
                            except ValueError:
                                pass # Ignore non-numeric values like '---'
                                
                    if all(key in new_data for key in latest_sensor_data):
                        latest_sensor_data.update(new_data)
                
                elif line.endswith("DONE") or line.startswith("!!!") or line.startswith("---") or line.startswith("BATCH"):
                    print(f"[Arduino Status] {line}")
                
        except serial.SerialTimeoutException:
            pass
        except Exception as e:
            print(f"Error reading from serial: {e}")
            time.sleep(1)
            
# -------------------------------------------------------------------------


def __sendData():
    global latest_sensor_data
    
    edgeData = EdgeData()
    deviceId = 'Device1' 
    
    # Analog Tags (Load Cells and Temp/Humidity)
    edgeData.tagList.append(EdgeTag(deviceId, 'LC1_Weight', latest_sensor_data.get('LC1', 0.0)))
    edgeData.tagList.append(EdgeTag(deviceId, 'LC2_Weight', latest_sensor_data.get('LC2', 0.0)))
    edgeData.tagList.append(EdgeTag(deviceId, 'LC3_Weight', latest_sensor_data.get('LC3', 0.0)))
    edgeData.tagList.append(EdgeTag(deviceId, 'Temperature', latest_sensor_data.get('T', 0.0)))
    edgeData.tagList.append(EdgeTag(deviceId, 'Humidity', latest_sensor_data.get('H', 0.0)))

    _edgeAgent.sendData(edgeData)


def __generateConfig():
    config = EdgeConfig()
    deviceConfig = DeviceConfig(id = 'Device1',
        name = 'MixingStation',
        description = 'Three-Pump Mixing/Weighing Station',
        deviceType = 'Smart Mixer',
        retentionPolicyName = '')
    
    # Load Cell 1
    analog1 = AnalogTagConfig(name = 'LC1_Weight', description = 'Load Cell 1 Weight', readOnly = False, arraySize = 0, spanHigh = 1000, spanLow = 0, engineerUnit = 'g', integerDisplayFormat = 4, fractionDisplayFormat = 2)
    deviceConfig.analogTagList.append(analog1)
    
    # Load Cell 2
    analog2 = AnalogTagConfig(name = 'LC2_Weight', description = 'Load Cell 2 Weight', readOnly = False, arraySize = 0, spanHigh = 1000, spanLow = 0, engineerUnit = 'g', integerDisplayFormat = 4, fractionDisplayFormat = 2)
    deviceConfig.analogTagList.append(analog2)
    
    # Load Cell 3
    analog3 = AnalogTagConfig(name = 'LC3_Weight', description = 'Load Cell 3 Weight', readOnly = False, arraySize = 0, spanHigh = 1000, spanLow = 0, engineerUnit = 'g', integerDisplayFormat = 4, fractionDisplayFormat = 2)
    deviceConfig.analogTagList.append(analog3)
    
    # Temperature
    temp = AnalogTagConfig(name = 'Temperature', description = 'DHT11 Temperature', readOnly = False, arraySize = 0, spanHigh = 50, spanLow = 0, engineerUnit = 'C', integerDisplayFormat = 2, fractionDisplayFormat = 1)
    deviceConfig.analogTagList.append(temp)
    
    # Humidity
    humidity = AnalogTagConfig(name = 'Humidity', description = 'DHT11 Humidity', readOnly = False, arraySize = 0, spanHigh = 100, spanLow = 0, engineerUnit = '%', integerDisplayFormat = 3, fractionDisplayFormat = 1)
    deviceConfig.analogTagList.append(humidity)
    
    config.node.deviceList.append(deviceConfig)
    return config


# --- AGENT INITIALIZATION USING CONFIGURATION VARIABLES ---
_edgeAgent = None
edgeAgentOptions = EdgeAgentOptions(nodeId = WISEPAAS_NODE_ID)
edgeAgentOptions.connectType = constant.ConnectType['DCCS']
dccsOptions = DCCSOptions(apiUrl = WISEPAAS_API_URL, credentialKey = WISEPAAS_CREDENTIAL_KEY)
edgeAgentOptions.DCCS = dccsOptions
_edgeAgent = EdgeAgent(edgeAgentOptions)
_edgeAgent.on_connected = on_connected
_edgeAgent.on_disconnected = on_disconnected
_edgeAgent.on_message = edgeAgent_on_message

# Start the serial reader thread
serial_thread = threading.Thread(target=read_serial_data, daemon=True)
serial_thread.start()

_edgeAgent.connect()

time.sleep(5) 

# Start sending data
for i in range(1, 60):
    __sendData()
    time.sleep(1)
