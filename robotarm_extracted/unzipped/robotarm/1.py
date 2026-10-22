from pymycobot.mycobot import MyCobot
import time

mc= MyCobot('/dev/ttyAMA0', 1000000)
mc.power_on()
#mc.set_color(255,0,0)
#time.sleep(2)
print("Is connected:", mc.is_controller_connected())

#home
mc.send_angles([0,0,0,0,0,-129],35)
time.sleep(7)

mc.set_gripper_value(50,35)
time.sleep(7)

#go to PointA
mc.send_angles([44.64, -108.98, 43.68, 90, 22, -136],35)
time.sleep(7)

mc.send_angles([44.56, -108.45, 44.03, 76, 22, -136],35)
time.sleep(7)

mc.set_gripper_value(100,35)
time.sleep(7)

mc.set_gripper_value(50,35)
time.sleep(7)

mc.send_angles([44.64, -108.98, 43.68, 90, 22, -136],35)
time.sleep(7)

#Point B
mc.send_angles([44.64, -108.98, 43.68, 90, 22, -110],35)
time.sleep(7)

mc.send_angles([42, -108.45, 44.03, 70, 64, -136],35)
time.sleep(7)

mc.set_gripper_value(100,35)
time.sleep(7)

mc.set_gripper_value(50,35)
time.sleep(7)

mc.send_angles([42, -102.65, 75, 60, 68, -136],35)
time.sleep(7)


mc.send_angles([54.84, -123.57, 74.61, 65.65, 65.21, -123.57],35)
time.sleep(7)


mc.set_gripper_value(100,35)
time.sleep(7)

mc.set_gripper_value(50,35)
time.sleep(7)

mc.send_angles([0,0,0,0,0,-129],35)
time.sleep(7)
#mc.send_angles([44.64, -108.98, 43.68, 75.21, 15.34, -136.31],35)
#time.sleep(7)

#mc.send_angles([45.0, -108.8, 44.12, 88.22, 47.72, -121.99],35)
#time.sleep(7)


#mc.send_angles([45.0, -108.8, 44.12, 83.22, 47.72, -121.99],35)
#time.sleep(7)



#Open Gripper
#mc.set_gripper_value(100,35)
#time.sleep(7)


