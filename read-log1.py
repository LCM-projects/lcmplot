import sys
import lcm
import numbers
import decimal
import matplotlib.pyplot as plt
import threading

try:
  import cStringIO.StringIO as BytesIO
except ImportError:
  from io import BytesIO

from bot_core import *
import numpy as np

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from multiprocessing import Process, Pipe

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
    self.tree = []

  def _recursive_flatten(self, data, current_path):
    if (hasattr(data, '__slots__')):
      # nested, keep crawling down
      children = []
      for attr_name in data.__slots__:
        attr = data.__getattribute__(attr_name)
        if (len(current_path) == 0):
          my_child = self._recursive_flatten(attr, attr_name)
        else:
          my_child = self._recursive_flatten(attr, current_path + "." + attr_name)
        children.append((attr_name, my_child))
      return children
    else:
      # not nested
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

class ProcessPlotter(object):
  def poll_draw(self):
    while True:
      if not self.pipe.poll():
        continue

      command = self.pipe.recv()
      fig_num = command[0]
      times = command[1]
      data = command[2]
      legend = command[3]

      print fig_num
      print times

      plt.figure(fig_num)
      plt.plot(times, data, label = legend)
      plt.xlabel('time')
      plt.legend()
      plt.show(block=False)

  def __call__(self, pipe):
    print('starting plotter...')
    self.pipe = pipe
    self.poll_draw()

    print('plotter died...')

class Window(QWidget):
  def __init__(self):
    self.proc_log(sys.argv[1])

    QWidget.__init__(self)
    self.treeView = QTreeView()
    self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
    #self.treeView.customContextMenuRequested.connect(self.openMenu)
    #self.treeVeiw.expandsOnDoubleClick()

    self.model = QStandardItemModel()
    self._build_log_menu(self.model, self.flat_log)
    self.treeView.setModel(self.model)
    self.treeView.doubleClicked.connect(self._double_clicked)

    self.model.setHorizontalHeaderLabels([self.tr("Object")])
    layout = QVBoxLayout()
    layout.addWidget(self.treeView)
    self.setLayout(layout)

    # multi processing
    self.plot_pipe, plotter_pipe = Pipe()
    self.plotter = ProcessPlotter()
    self.plot_process = Process(target=self.plotter,
                                args=(plotter_pipe,))
    self.plot_process.start()

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

  def _build_log_menu(self, parent, log):
    for channel_name, channel in log.channel_name_to_data.iteritems():
      item = QStandardItem(channel_name)
      parent.appendRow(item)
      self._build_tree_menu(item, channel.tree)

  def _build_tree_menu(self, parent, tree):
    for me, children in tree:
      item = QStandardItem(me)
      parent.appendRow(item)
      if children:
        self._build_tree_menu(item, children)

  def _double_clicked(self, index):
    model_idx = self.treeView.selectedIndexes()[0]
    item = model_idx.model().itemFromIndex(index)

    if (item.hasChildren()):
      is_expand = self.treeView.isExpanded(index)
      self.treeView.setExpanded(index, not(is_expand))
    else:
      path = item.text()
      while(True):
        if not(item.parent()):
          channel_name = str(item.text())
          break
        item = item.parent()
        path = item.text() + "." + path

      trace_name = str(path[len(channel_name) + 1 :])
      self.plot_trace(channel_name, trace_name)

  def plot_trace(self, channel_name, trace_name):
    channel = self.flat_log.get_channel(channel_name)
    if not (channel.has_trace(trace_name)):
      return
    data = channel.slice_at_trace(channel.trace_names_to_idx[trace_name])
#    from PyQt4.QtCore import pyqtRemoveInputHook
#    pyqtRemoveInputHook()
#    import IPython; IPython.embed()
#    plt.figure(1)
#    plt.hold(True)
#    plt.plot(channel.times, data, label = channel_name + "/" + trace_name)
#    plt.xlabel('time')
#    plt.legend()
#    plt.show()
    send = self.plot_pipe.send
    send((1, channel.times, data, channel_name + "/" + trace_name))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())

