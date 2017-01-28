import sys
import lcm
import numbers
import decimal

from PyQt4.uic import loadUiType
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

Ui_MainWindow, QMainWindow = loadUiType('lcmplot.ui')

from flat_log import *

class Subplot:
    def __init__(self, mpl_axes, idx, selector):
        # [(channel_name, trace_name), ... ]
        self.contents = []
        self.mpl_axes = mpl_axes
        self.idx = idx
        self.selector = selector

    def clear(self):
        self.contents = []
        del self.mpl_axes.lines[:]
        self.mpl_axes.legend()

class Main(QMainWindow, Ui_MainWindow):

    def __init__(self, ):
        super(Main, self).__init__()
        self.proc_log(sys.argv[1])

        self.setupUi(self)

        self.build_log_menu(self.flat_log)
        self.traceTree.doubleClicked.connect(self.double_clicked)

        # make mpl fig
        self.fig = Figure()
        self.fig.subplots_adjust(left = 0.02, right = 0.99,
                                bottom = 0.03, top = 0.99,
                                wspace = 0.0, hspace = 0.1)
        self.add_mpl(self.fig)

        # connect buttons
        self.clear_all_button.clicked.connect(self.clear_all_button_handler)
        self.clear_last_button.clicked.connect(self.clear_last_button_handler)
        self.add_figure_button.clicked.connect(self.add_figure_button_handler)
        self.remove_figure_button.clicked.connect(self.remove_figure_button_handler)

        self.subplot_selector_group = QtGui.QButtonGroup()
        self.subplot_selector_group.setExclusive(True)

        self.idx_to_subplot = {}
        self.alive_subplot_idx = []

        self.new_subplot_idx = 1
        self.num_subplots = 0

        self.add_subplot()

    def add_subplot(self):
        new_idx = self.new_subplot_idx
        # always add a new one to the bottom
        new_position = self.num_subplots + 1

        # add a new radio button for this plot and add it to the radio button group
        new_selector = QtGui.QRadioButton(str(new_idx))
        self.subplot_selector_group.addButton(new_selector)
        new_selector.setChecked(True)
        self.mpl_figure_selector_layout.addWidget(new_selector)

        new_subplot = Subplot(self.fig.add_subplot(self.num_subplots + 1, 1, new_position), new_idx, new_selector)
        self.idx_to_subplot[new_idx] = new_subplot

        # increment counters
        self.new_subplot_idx += 1
        self.num_subplots += 1

        self.alive_subplot_idx.append(new_idx)
        self.alive_subplot_idx.sort()

        return new_idx

    def get_subplot_position(self, idx):
        return self.alive_subplot_idx.index(idx)

    def get_selected_subplot(self):
        for button in self.subplot_selector_group.buttons():
            if (button.isChecked()):
                active_idx = int(str(button.text()))
                print "current subplto: " + str(active_idx)
                return active_idx

    def remove_subplot(self):
        to_be_removed = self.idx_to_subplot[self.get_selected_subplot()]
        # remove subplot's axes from fig
        self.fig.delaxes(to_be_removed.mpl_axes)
        # delete the radion button
        self.mpl_figure_selector_layout.removeWidget(to_be_removed.selector)
        self.subplot_selector_group.removeButton(to_be_removed.selector)
        to_be_removed.selector.deleteLater()
        to_be_removed.selector = None

        # delete entry
        self.alive_subplot_idx.remove(to_be_removed.idx)
        self.alive_subplot_idx.sort()
        del self.idx_to_subplot[to_be_removed.idx]

        self.num_subplots -= 1

        # the first subplot to be active
        self.idx_to_subplot[self.alive_subplot_idx[0]].selector.setChecked(True)

    def update_subplot_position(self):
        # update the subplots' locations
        gs = gridspec.GridSpec(self.num_subplots, 1)
        for idx in self.alive_subplot_idx:
            position = self.get_subplot_position(idx)
            print("idx, pos, num_plots: " + str(idx) + " " + str(position) + " " + str(self.num_subplots))
            #self.idx_to_subplot[idx].mpl_axes.change_geometry(self.num_subplots, 1, position)
            self.idx_to_subplot[idx].mpl_axes.set_subplotspec(gs[position, 0])

        self.fig.canvas.draw()

    def remove_figure_button_handler(self):
        if self.num_subplots == 1:
            return

        self.remove_subplot()
        self.update_subplot_position()

        print "================="
        print "alive: "
        print self.alive_subplot_idx
        print "stuff: "
        print self.idx_to_subplot

    def add_figure_button_handler(self):
        self.add_subplot()
        self.update_subplot_position()

        print "================="
        print "alive: "
        print self.alive_subplot_idx
        print "stuff: "
        print self.idx_to_subplot

    def clear_all_button_handler(self):
        for idx in self.alive_subplot_idx:
            self.idx_to_subplot[idx].clear()

        self.fig.canvas.draw()

    def clear_last_button_handler(self):
        subplot = self.idx_to_subplot[self.get_selected_subplot()]
        subplot.contents.pop(-1)
        subplot.mpl_axes.lines.pop(-1)
        subplot.mpl_axes.legend()
        self.fig.canvas.draw()

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

    def build_log_menu(self, log):
        for channel_name, channel in log.channel_name_to_data.iteritems():
            item = QTreeWidgetItem()
            item.setText(0, channel_name)
            self.build_tree_menu(item, channel.tree)
            self.traceTree.addTopLevelItem(item)

    def build_tree_menu(self, parent, tree):
        for me, children in tree:
            item = QTreeWidgetItem()
            item.setText(0, me)
            if children:
                self.build_tree_menu(item, children)
            parent.addChild(item)

    def double_clicked(self, index):
        item = self.traceTree.selectedItems()[0]
        # has children, should keep expanding
        if item.childCount():
            ############# TODO THIS DOESN'T EXPAND
            is_expand = self.traceTree.expand(index)
            #self.traceTree.setExpanded(index, not(is_expand))
        else:
            path = str(item.text(0))
            while(True):
                if not(item.parent()):
                    channel_name = str(item.text(0))
                    break
                item = item.parent()
                path = str(item.text(0)) + "." + path

            trace_name = path[len(channel_name) + 1 :]

            self.add_trace_to_subplot(self.idx_to_subplot[self.get_selected_subplot()],
                                      channel_name, trace_name)

    def add_trace_to_subplot(self, subplot, channel_name, trace_name):
        channel = self.flat_log.get_channel(channel_name)
        if not (channel.has_trace(trace_name)):
            return

        subplot.contents.append((channel_name, trace_name))

        data = channel.slice_at_trace(channel.trace_names_to_idx[trace_name])
        subplot.mpl_axes.plot(channel.times, data, label = channel_name + "/" + trace_name)
        subplot.mpl_axes.legend()
        self.fig.canvas.draw()

    def add_mpl(self, fig):
        self.canvas = FigureCanvas(fig)
        self.mpl_figure_layout.addWidget(self.canvas)
        self.canvas.draw()
        self.toolbar = NavigationToolbar(self.canvas,
                self.matplotlib_widget, coordinates=True)
        self.mpl_toolbar_layout.addWidget(self.toolbar)

if __name__ == '__main__':
    import sys
    from PyQt4 import QtGui
    import numpy as np

    app = QtGui.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())

