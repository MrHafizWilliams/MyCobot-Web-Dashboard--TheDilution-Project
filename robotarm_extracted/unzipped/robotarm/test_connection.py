from pymycobot.mycobotsocket import MyCobotSocket
import time

# Connect to the Pi's IP address and listening port
mc = MyCobotSocket("10.212.42.168", 9000)
mc.connect()

print("Connection successful! Moving Joint 1...")
# Move Joint 1 to 0 degrees at 50% speed
mc.send_angle(1, 0, 50)
time.sleep(2)

print("Test complete.")