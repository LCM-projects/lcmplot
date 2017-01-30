import sys
import lcm
import numbers
import decimal
from bot_core import *
import numpy as np
import pkgutil
import importlib

try:
  import cStringIO.StringIO as BytesIO
except ImportError:
  from io import BytesIO

class DataPoint:
  def __init__(self, channel_name, time):
    self.channel_name = channel_name
    self.trace_names_to_idx = {}
    self.trace_data = []
    self.time = time
    self.tree = []

  def _recursive_flatten(self, data, current_path):
    # nested, keep crawling down
    if (hasattr(data, '__slots__')):
      children = []
      for attr_name in data.__slots__:
        attr = data.__getattribute__(attr_name)
        if (len(current_path) == 0):
          my_child = self._recursive_flatten(attr, attr_name)
        else:
          my_child = self._recursive_flatten(attr, current_path + "." + attr_name)
        children.append((attr_name, my_child))
      return children
    # not nested
    else:
      children = []
      # data is single numerical
      if isinstance(data, numbers.Number):
        self.trace_names_to_idx[current_path] = len(self.trace_data)
        self.trace_data.append(data)
      # data is a list / tuple of numerical
      elif all(isinstance(x, numbers.Number) for x in data):
        for i, x in enumerate(data):
          self.trace_names_to_idx[current_path + '.' + str(i)] = len(self.trace_data)
          self.trace_data.append(x)
          children.append((str(i), []))
      # data is a list / tuple of strings
      elif all(isinstance(x, (str, unicode)) for x in data):
        for i, string in enumerate(data):
          children.append((str(i) + " : " + str(string), []))
      return children

  def flatten(self, data):
    self.tree = self._recursive_flatten(data, '')
    self.trace_data = np.array(self.trace_data)

class Channel:
  def __init__(self, data_point):
    self.channel_name = data_point.channel_name
    self.times = [data_point.time]
    self.data_points = [data_point.trace_data]
    self.trace_names_to_idx = data_point.trace_names_to_idx
    self.is_final = False
    self.tree = []

  def add_data_point(self, data_point):
    if (self.is_final):
      return
    if not self.tree:
      self.tree = data_point.tree

    self.times.append(data_point.time)
    self.data_points.append(data_point.trace_data)

  def finalize(self):
    if (self.is_final):
      return

    self.times = np.array(self.times)
    self.data_points = np.array(self.data_points)
    self.is_final = True

  def has_trace(self, trace_name):
    return trace_name in self.trace_names_to_idx

  def slice_at_time(self, time_idx):
    return self.data_points[time_idx, :]

  def slice_at_trace(self, trace_idx):
    return self.data_points[:, trace_idx]


class FlatLog:
  def __init__(self):
    self.channel_name_to_data = {}
    self.is_final = False

  def add_data_point(self, data_point):
    if (self.is_final):
      return

    if data_point.channel_name in self.channel_name_to_data:
      channel = self.channel_name_to_data[data_point.channel_name]
      channel.add_data_point(data_point)
    else:
      self.channel_name_to_data[data_point.channel_name] = Channel(data_point)
      channel = self.channel_name_to_data[data_point.channel_name]

  def finalize(self):
    if (self.is_final):
      return

    for channel_name, channel in self.channel_name_to_data.iteritems():
      channel.finalize()
    self.is_final = True

  def has_channel(self, channel_name):
    return channel_name in self.channel_name_to_data

  def get_channel(self, channel_name):
    return self.channel_name_to_data[channel_name]

#############################################################################
# gets the time stamp for this lcm message if it containts 'utime' or 'timestamp', else 0.
class Parser:
  def __init__(self):
    self.hash_to_decoder = {}
    self.load_msg_types_from_package('bot_core')

  def load_msg_types_from_package(self, pkg_name):
    pkg = importlib.import_module(pkg_name)
    msgs_list = [name for _, name, _ in pkgutil.iter_modules([pkg.__name__])]
    for name in msgs_list:
      module = getattr(pkg, name)
      self.hash_to_decoder[module._get_packed_fingerprint()] = module.decode

  def _get_time(self, msg):
    if hasattr(msg, 'utime'):
      return msg.utime / 1e6
    elif hasattr(msg, 'timetamp'):
      return msg.timestamp / 1e6
    else:
      return 0

  def _get_msg_hash(self, event):
    if hasattr(event.data, 'read'):
      buf = event.data
    else:
      buf = BytesIO(event.data)
    return buf.read(8)

  def proc_log(self, log_name):
    log = lcm.EventLog(log_name, "r")
    flat_log = FlatLog()
    # parse log
    for event in log:
      msg_hash = self._get_msg_hash(event)
      if msg_hash in self.hash_to_decoder:
        decoder = self.hash_to_decoder[msg_hash]
        msg = decoder(event.data)
        data_point = DataPoint(event.channel, self._get_time(msg))
        data_point.flatten(msg)
        flat_log.add_data_point(data_point)

    flat_log.finalize()
    return flat_log
