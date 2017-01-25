import lcm

try:
  import cStringIO.StringIO as BytesIO
except ImportError:
  from io import BytesIO

from bot_core import *

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
    flat_data[my_path] = data

def my_handler(channel, data):
    fingerprint = get_finger_print(data)
    print(fingerprint)

    msg = robot_state_t.decode(data)

    flat_data = {}
    access_all(msg, "robot_state_t", flat_data)
    print(flat_data)

lc = lcm.LCM()
subscription = lc.subscribe("EXAMPLE", my_handler)

try:
    while True:
        lc.handle()
except KeyboardInterrupt:
    pass

lc.unsubscribe(subscription)
