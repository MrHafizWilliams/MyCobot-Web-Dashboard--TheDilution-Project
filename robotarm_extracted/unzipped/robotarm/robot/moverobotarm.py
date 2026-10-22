from pymycobot.mycobot import MyCobot
import time

mc= MyCobot('/dev/ttyAMA0', 1000000)
mc.power_on()
#mc.set_color(255,0,0)
#time.sleep(2)
print("Is connected:", mc.is_controller_connected())

#home
mc.send_angles([0,0,0,0,0,-129],35)
time.sleep(1.5)

mc.set_gripper_value(50,35)
time.sleep(4)

#go to PointA
mc.send_angles([44.64, -108.98, 43.68, 90, 22, -136],35)
time.sleep(1.5)

mc.send_angles([44.56, -108.45, 44.03, 76, 22, -136],35)
time.sleep(1.5)

mc.set_gripper_value(100,35)
time.sleep(10)

mc.set_gripper_value(50,35)
time.sleep(4)

mc.send_angles([44.64, -108.98, 43.68, 90, 22, -136],35)
time.sleep(1.5)

#Point B
mc.send_angles([44.64, -108.98, 43.68, 90, 22, -110],35)
time.sleep(1.5)

mc.send_angles([42, -108.45, 44.03, 70, 64, -136],35)
time.sleep(1.5)

mc.set_gripper_value(100,35)
time.sleep(4)

mc.set_gripper_value(50,35)
time.sleep(4)

mc.send_angles([42, -102.65, 75, 60, 68, -136],35)
time.sleep(1.5)

mc.send_angles([59, -123.57, 74.61, 60.65, 65.21, -136.57],35)
time.sleep(1.5)

mc.set_gripper_value(100,35)
time.sleep(4)

mc.set_gripper_value(50,35)
time.sleep(4)

mc.send_angles([0,0,0,0,0,-129],35)
#time.sleep(7)
