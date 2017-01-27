import sys
import lcm
import numbers
import decimal

from PyQt4.uic import loadUiType
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

Ui_MainWindow, QMainWindow = loadUiType('lcmplot.ui')

from flat_log import *

class Main(QMainWindow, Ui_MainWindow):
    def __init__(self, ):
        super(Main, self).__init__()
        self.proc_log(sys.argv[1])

        self.setupUi(self)

        self.build_log_menu(self.flat_log)
        self.traceTree.doubleClicked.connect(self.double_clicked)

        # connect buttons
        self.clear_all_button.clicked.connect(self.clear_all_button_handler)
        self.clear_last_button.clicked.connect(self.clear_last_button_handler)
        self.add_figure_button.clicked.connect(self.add_figure_button_handler)
        self.remove_figure_button.clicked.connect(self.remove_figure_button_handler)

        self.fig = Figure()
        self.idx_to_content = {}
        self.idx_to_axe = {}

        self.fig.subplots_adjust(left = 0.02, right = 0.99,
                                bottom = 0.03, top = 0.99,
                                wspace = 0.0, hspace = 0.1)

        self.subplot_selector_group = QtGui.QButtonGroup()
        self.subplot_selector_group.setExclusive(True)

        self.current_subplot_idx = self.add_subplot()

        self.add_mpl(self.fig)

    def num_of_subplots(self):
        return len(self.idx_to_content)

    def add_subplot(self):
        new_subplot_idx = self.num_of_subplots() + 1
        self.idx_to_content[new_subplot_idx] = []
        self.idx_to_axe[new_subplot_idx] = self.fig.add_subplot(new_subplot_idx, 1, 1)

        new_selector = QtGui.QRadioButton(str(new_subplot_idx))
        self.subplot_selector_group.addButton(new_selector)
        new_selector.setChecked(True)
        new_selector.clicked.connect(self.subplot_selector_handler)
        self.mpl_figure_selector_layout.addWidget(new_selector)

        return new_subplot_idx

    def subplot_selector_handler(self):
        for button in self.subplot_selector_group.buttons():
            if (button.isChecked()):
                print button.text()
                self.current_subplot_idx = int(str(button.text()))

    def remove_figure_button_handler(self):
        if self.current_subplot_idx == 1:
            return

        del_subplot_idx = self.current_subplot_idx
        del self.idx_to_content[del_subplot_idx]
        self.fig.delaxes(self.idx_to_axe[del_subplot_idx])
        del self.idx_to_axe[del_subplot_idx]
        num_subplots = self.num_of_subplots()

        for subplot_idx in self.idx_to_axe:
            self.idx_to_axe[subplot_idx].change_geometry(num_subplots, 1, subplot_idx)

        self.current_subplot_idx = num_subplots
        self.fig.canvas.draw()

    def add_figure_button_handler(self):
        self.add_subplot()
        num_subplots = self.num_of_subplots()
        for subplot_idx in self.idx_to_axe:
            self.idx_to_axe[subplot_idx].change_geometry(num_subplots, 1, subplot_idx)

        self.current_subplot_idx = num_subplots
        self.fig.canvas.draw()

    def clear_all_button_handler(self):
        for subplot_idx in self.idx_to_content:
            while self.idx_to_content[subplot_idx]:
                self.remove_last_trace_from_subplot(subplot_idx)

    def clear_last_button_handler(self):
        self.remove_last_trace_from_subplot(self.current_subplot_idx)

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

            self.add_trace_to_subplot(self.current_subplot_idx, channel_name, trace_name)

    def add_trace_to_subplot(self, subplot_idx, channel_name, trace_name):
        channel = self.flat_log.get_channel(channel_name)
        if not (channel.has_trace(trace_name)):
            return

        axe = self.idx_to_axe[subplot_idx]
        self.idx_to_content[subplot_idx].append((channel_name, trace_name))

        data = channel.slice_at_trace(channel.trace_names_to_idx[trace_name])
        axe.plot(channel.times, data, label = channel_name + "/" + trace_name)
        axe.legend()
        self.fig.canvas.draw()

    def remove_last_trace_from_subplot(self, subplot_idx):
        axe = self.idx_to_axe[subplot_idx]
        axe.lines.pop(-1)
        self.idx_to_content[subplot_idx].pop(-1)
        axe.legend()
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

