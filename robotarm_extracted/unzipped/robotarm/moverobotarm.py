from pymycobot.mycobot import MyCobot
import time
import requests

# CONFIGURATION
API_URL = "http://localhost:5000/api/command"

def send_to_unity(payload_str):
    """
    Wraps the command with ANGLE: prefix so the Pi listener ignores it.
    """
    full_command = f"ANGLE:{payload_str}"

    try:
        # verify=False handles self-signed certificates
        r = requests.post(API_URL, data={'task_name': full_command}, verify=False)
        if r.status_code == 200:
            print(f" -> Sent to Unity: {full_command}")
        else:
            print(f" -> Server Error: {r.status_code}")
    except Exception as e:
        print(f" -> Connection Failed: {e}")

def sync_unity_arm(angles):
    """Sends joint angles to Unity."""
    # Format: "0,45,90,0,0,0"
    csv_angles = ",".join(map(str, angles[:6]))
    send_to_unity(csv_angles)

def sync_unity_gripper(action):
    """Sends GRIP or RELEASE command to Unity."""
    # action should be "GRIP" or "RELEASE"
    if action.upper() in ["GRIP", "RELEASE"]:
        send_to_unity(action.upper())

mc= MyCobot('/dev/ttyAMA0', 1000000)
mc.power_on()
#mc.set_color(255,0,0)
#time.sleep(2)
print("Is connected:", mc.is_controller_connected())

#home
mc.send_angles([0,0,0,0,0,-129],35)
time.sleep(1.5)

mc.set_gripper_value(100,35)
time.sleep(4)

######### DOOR UNITY #######################

#DOOR UNITY
# 1. Define Movements
target_angles = [22.64,-129.4,76.1,54.59,-20.97,0]

# 2. Move Physical Arm
print("Moving Physical Arm...")
# mc.send_angles(target_angles, 35)

# 3. Sync Unity Arm
sync_unity_arm(target_angles)
time.sleep(1)

# 4. Grip
print("Closing Gripper...")
# mc.send_gripper(1)
sync_unity_gripper("GRIP")

######### DOOR UNITY #######################


#goto Door
mc.send_angles([25.48, -94.48, -2.1, 103.62, -114.08, -131.13],35)
time.sleep(3)

mc.send_angles([6.67, -94.48, -2.1, 103.62, -90.7, -131.13],35)
time.sleep(3)

mc.set_gripper_value(50,35)
time.sleep(2)

######### POINT A UNITY######################

#POINT A UNITY
# 1. Define Movements
target_angles = [-72.8,-131.5,106.8,25.2,-91.2,0]

# 2. Move Physical Arm
print("Moving Physical Arm...")
# mc.send_angles(target_angles, 35)

# 3. Sync Unity Arm
sync_unity_arm(target_angles)

# 5. Release
print("Opening Gripper...")
# mc.send_gripper(0)
sync_unity_gripper("RELEASE")


######### POINT A UNITY ######################


#go to PointA
mc.send_angles([44.64, -108.98, 43.68, 90, 22, -136],35)
time.sleep(1.5)

mc.send_angles([44.56, -108.45, 44.03, 76, 22, -136],35)
time.sleep(5)

mc.set_gripper_value(100,35)
time.sleep(4)

mc.set_gripper_value(50,35)
time.sleep(4)

mc.send_angles([44.64, -108.98, 43.68, 90, 22, -136],35)
time.sleep(1.5)


####### POINT B UNITY ########################

#POINTB unity
# 1. Define Movements
print("Opening Gripper...")
# mc.send_gripper(0)
sync_unity_gripper("GRIP")
target_angles = [-72.8,-131.5,106.8,25.2,-126.7,0]

# 2. Move Physical Arm
print("Moving Physical A#POINTC")
# 1. Define Movements
target_angles = [-91.4, -136.1, 118.4, 18.3, -122, 0]

# 2. Move Physical Arm
print("Moving Physical Arm...")
# mc.send_angles(target_angles, 35)

# 3. Sync Unity Arm
sync_unity_arm(target_angles)

# 4. Grip
print("Closing Gripper...")
# mc.send_gripper(1)
sync_unity_gripper("GRIP")

# 5. Release
print("Opening Gripper...")
# mc.send_gripper(0)
sync_unity_gripper("RELEASE")

# mc.send_angles(target_angles, 35)

# 3. Sync Unity Arm
sync_unity_arm(target_angles)

# 4. Grip
print("Closing Gripper...")
# mc.send_gripper(1)
sync_unity_gripper("GRIP")
time.sleep(2)

# 5. Release
print("Opening Gripper...")
# mc.send_gripper(0)
sync_unity_gripper("RELEASE")


####### POINT B UNITY ########################

#Point B
mc.send_angles([44.64, -108.98, 43.68, 90, 22, -110],35)
time.sleep(1.5)

mc.send_angles([42, -108.45, 45.03, 71, 64, -136],35)
time.sleep(1.5)

mc.set_gripper_value(100,35)
time.sleep(4)

mc.set_gripper_value(50,35)
time.sleep(4)

mc.send_angles([42, -102.65, 75, 60, 68, -136],35)
time.sleep(1.5)


######### POINT C UNITY #################################

#POINTC
# 1. Define Movements
print("Opening Gripper...")
# mc.send_gripper(0)
sync_unity_gripper("GRIP")
target_angles = [-91.4, -136.1, 118.4, 18.3, -122, 0]

# 2. Move Physical Arm
print("Moving Physical Arm...")
# mc.send_angles(target_angles, 35)

# 3. Sync Unity Arm
sync_unity_arm(target_angles)

# 4. Grip
print("Closing Gripper...")
# mc.send_gripper(1)
sync_unity_gripper("GRIP")

######### POINT C UNITY #################################


#POINT C ROBOT
mc.send_angles([42, -102.65, 75, 60, 68, -136],35)
time.sleep(1.5)

mc.send_angles([59, -123.57, 74.61, 60.65, 65.21, -136.57],35)
time.sleep(1.5)

mc.set_gripper_value(100,35)
time.sleep(4)

mc.set_gripper_value(50,35)
time.sleep(4)

mc.send_angles([42, -102.65, 75, 60, 68, -136],35)
time.sleep(1.5)

mc.send_angles([0,-30,30,0,0,-129],35)

######### MIX UNITY #################################

#MIX UNITY
target_angles = [-72.4, -110.3, 112.6, 28.3, -130.1, 0]

# 3. Sync Unity Arm
sync_unity_arm(target_angles)

target_angles = [0,0,0,0,-90,0]

# 3. Sync Unity Arm
sync_unity_arm(target_angles)

######### POINT C UNITY #################################
#time.sleep(7)

target_angles = [22.64,-129.4,76.1,54.59,-20.97,0]

sync_unity_arm(target_angles)
sync_unity_gripper("RELEASE")


target_angles = [0,0,0,0,-90,0]

sync_unity_arm(target_angles)


i=0
while i < 10:
    mc.send_angles([0,-30,30,0,0,-84],35)
    mc.send_angles([0,-30,30,0,0,-174],35)
    i=i+1
    time.sleep(1)

time.sleep(3)

mc.send_angles([6.67, -94.48, -2.1, 103.62, -90.7, -131.13],35)
time.sleep(10)

mc.set_gripper_value(100,35)
time.sleep(10)

mc.send_angles([25.48, -94.48, -2.1, 103.62, -114.08, -131.13],35)
time.sleep(3)


mc.send_angles([0,0,0,-5,0,-129],35)
