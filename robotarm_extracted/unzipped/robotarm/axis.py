from pymycobot.mycobot import MyCobot
import time

# Initialize MyCobot
mc = MyCobot('/dev/ttyAMA0', 1000000)
mc.power_on()

# Check if connected
print("Is connected:", mc.is_controller_connected())

# Function to print the current joint angles
def print_current_angles():
    current_angles = mc.get_angles()
    print("Current Joint Angles:", current_angles)

# Call the function to see the current angles
print_current_angles()

# Sleep to allow time for reading
time.sleep(2)
