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

from PyQt4.QtCore import *
from PyQt4.QtGui import *

# gets the time stamp for this lcm message if it containts 'utime' or 'timestamp', else 0.
def get_time(msg):
  if hasattr(msg, 'utime'):
    return msg.utime
  elif hasattr(msg, 'timetamp'):
    return msg.timestamp
  else:
    return 0

class DataPoint:
  def __init__(self, channel_name, time):
    self.channel_name = channel_name
    self.trace_names_to_idx = {}
    self.trace_data = []
    self.time = time

  def _recursive_flatten(self, data, current_path):
    if (hasattr(data, '__slots__')):
      # nested, keep crawling down
      for attr_name in data.__slots__:
        attr = data.__getattribute__(attr_name)
        if (len(current_path) == 0):
          self._recursive_flatten(attr, attr_name)
        else:
          self._recursive_flatten(attr, current_path + "." + attr_name)
    else:
      # not nested
      if (isinstance(data, numbers.Number)):
        self.trace_names_to_idx[current_path] = len(self.trace_data)
        self.trace_data.append(data)

  def flatten(self, data):
    self._recursive_flatten(data, '')
    self.trace_data = np.array(self.trace_data)

class Channel:
  def __init__(self, data_point):
    self.channel_name = data_point.channel_name
    self.times = [data_point.time]
    self.data_points = [data_point.trace_data]
    self.trace_names_to_idx = data_point.trace_names_to_idx
    self.is_final = False

  def add_data_point(self, data_point):
    if (self.is_final):
      return

    self.times.append(data_point.time)
    self.data_points.append(data_point.trace_data)

  def finalize(self):
    if (self.is_final):
      return

    self.times = np.array(self.times)
    self.data_points = np.array(self.data_points)
    self.is_final = True

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

  def get_channel(self, channel_name):
    return self.channel_name_to_data[channel_name]

class Window(QWidget):
  def __init__(self):
    self.proc_log(sys.argv[1])

    QWidget.__init__(self)
    self.treeView = QTreeView()
    self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
    #self.treeView.customContextMenuRequested.connect(self.openMenu)
    #self.treeVeiw.expandsOnDoubleClick()

    self.model = QStandardItemModel()
    self._build_tree_menu(self.model, self.flat_log.channel_name_to_data)
    self.treeView.setModel(self.model)

    self.model.setHorizontalHeaderLabels([self.tr("Object")])
    layout = QVBoxLayout()
    layout.addWidget(self.treeView)
    self.setLayout(layout)

  def proc_log(self, log_name):
    log = lcm.EventLog(log_name, "r")
    self.flat_log = FlatLog()

    # parse log
    for event in log:
      if event.channel == "EXAMPLE":
        msg = robot_state_t.decode(event.data)
        data_point = DataPoint(event.channel, get_time(msg))
        data_point.flatten(msg)
        self.flat_log.add_data_point(data_point)

    self.flat_log.finalize()

  def _build_tree_menu(self, parent, channels):
    for channel_name, channel in channels.iteritems():
      item = QStandardItem(channel_name)
      parent.appendRow(item)
      self._build_tree_menu_channel(item, channel)

  def _build_tree_menu_channel(self, parent, channel):
    for trace_name, trace_idx in channel.trace_names_to_idx.iteritems():
      item = QStandardItem(trace_name)
      parent.appendRow(item)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())

#channel_name = 'EXAMPLE'
#trace_names = ['pose.translation.x', 'pose.translation.y']
#channel = flat_log.get_channel(channel_name)

#plt.figure(1)
#plt.hold(True)
#for trace_name in trace_names:
#  idx = channel.trace_names_to_idx[trace_name]
#  plt.plot(channel.times, channel.slice_at_trace(idx) , label = channel_name + "/" + trace_name)
#plt.xlabel('time')
#plt.legend()

#plt.show()

