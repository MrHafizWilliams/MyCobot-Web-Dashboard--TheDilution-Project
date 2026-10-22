from pymycobot.mycobot import MyCobot
import time

mc= MyCobot('/dev/ttyAMA0', 1000000)
#mc.release_all_servos()
time.sleep(1)
mc.send_angles([0,0,0,-90,0,-129],35)
