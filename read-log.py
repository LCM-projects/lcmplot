import sys
import lcm
import numbers
import decimal
import matplotlib.pyplot as plt

try:
  import cStringIO.StringIO as BytesIO
except ImportError:
  from io import BytesIO

from bot_core import *
import numpy as np

# gets the fingerprint for a lcm income message or a log event. should match
# lcm_msg._get_packed_fingerprint()
def get_finger_print(data):
  if hasattr(data, 'read'):
    buf = data
  else:
    buf = BytesIO(data)
  return buf.read(8)

# gets the time stamp for this lcm message if it containts 'utime' or 'timestamp', else 0.
def get_time(msg):
  if hasattr(msg, 'utime'):
    return msg.utime
  elif hasattr(msg, 'timetamp'):
    return msg.timestamp
  else:
    return 0

def access_all(data, my_path, flat_data):
  if (hasattr(data, '__slots__')):
    for attr_name in data.__slots__:
      attr = data.__getattribute__(attr_name)
      access_all(attr, my_path + "." + attr_name, flat_data)
  else:
    # not nested datatype
    if (isinstance(data, numbers.Number)):
      flat_data[my_path] = data

if len(sys.argv) < 2:
    sys.stderr.write("usage: read-log <logfile>\n")
    sys.exit(1)

log = lcm.EventLog(sys.argv[1], "r")

# {channel_name : ({trace_name : idx}, [time], [trace_data])}, trace_data is a list
all_data = {}

for event in log:
  if event.channel == "EXAMPLE":
    msg = robot_state_t.decode(event.data)

    time = get_time(msg)
    flat_data = {}

    access_all(msg, event.channel, flat_data)

    trace_name_to_idx = {}
    trace_data = []
    for key, val in flat_data.iteritems():
      trace_name_to_idx[key] = len(trace_data)
      trace_data.append(val)

    if (event.channel in all_data):
      # append time
      all_data[event.channel][1].append(time)
      # append data
      all_data[event.channel][2].append(trace_data)
    else:
      all_data[event.channel] = (trace_name_to_idx, [time], [trace_data])

# post process [trace_data] to 2d numpy array
for channel_name, channel_data in all_data.iteritems():
  all_data[channel_name] = (channel_data[0], np.array(channel_data[1]), np.array(channel_data[2]))

# test EXAMPLE channel
channel_data = all_data['EXAMPLE']
trace_name_to_idx = channel_data[0]

plt.figure(1)
plt.hold(True)
ln1 = plt.plot(channel_data[1], channel_data[2][:, trace_name_to_idx['EXAMPLE.pose.translation.x']], label = 'EXAMPLE.pose.translation.x')
ln2 = plt.plot(channel_data[1], channel_data[2][:, trace_name_to_idx['EXAMPLE.pose.translation.y']], label = 'EXAMPLE.pose.translation.y')
plt.xlabel('time')
plt.legend()

plt.show()

