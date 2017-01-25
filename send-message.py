import lcm
import time

from bot_core import *

lc = lcm.LCM()

#msg = example_t()
#msg.timestamp = int(time.time() * 1000000)
#msg.position = (1, 2, 3)
#msg.orientation = (1, 0, 0, 0)
#msg.ranges = range(15)
#msg.num_ranges = len(msg.ranges)
#msg.name = "example string"
#msg.enabled = True

for i in [1, 2, 3, 4, 5, 6, 7]:
    msg = robot_state_t();
    msg.utime = i
    msg.pose.translation.x = i + 1
    msg.pose.translation.y = i + 2
    msg.pose.translation.z = i + 3

    msg.num_joints = 1
    msg.joint_name = ["j1"]
    msg.joint_position = [i]
    msg.joint_velocity = [0]
    msg.joint_effort = [0]

    lc.publish("EXAMPLE", msg.encode())
