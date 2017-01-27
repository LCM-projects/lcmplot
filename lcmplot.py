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

Ui_MainWindow, QMainWindow = loadUiType('window.ui')

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
        self.idx_to_content = {111 : []}
        self.idx_to_axe = {111 : self.fig.add_subplot(111)}

#        self.fig.subplots_adjust(left = 0.02, right = 0.99,
#                                bottom = 0.03, top = 0.99,
#                                wspace = 0.0, hspace = 0.03)
        self.addmpl(self.fig)

    def remove_figure_button_handler(self):
        print 'remove_figure_button'

    def add_figure_button_handler(self):
        print 'add_figure_button'

    def clear_all_button_handler(self):
        print 'clear_all_button'

    def clear_last_button_handler(self):
        print 'clear_last_button'
        subplot_idx = 111
        self.remove_last_trace_from_fig(subplot_idx)

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
            path = item.text(0)
            while(True):
                if not(item.parent()):
                    channel_name = str(item.text(0))
                    break
                item = item.parent()
                path = item.text(0) + "." + path

            trace_name = str(path[len(channel_name) + 1 :])

            subplot_idx = 111
            self.add_trace_to_fig(subplot_idx, channel_name, trace_name)

    def add_trace_to_fig(self, subplot_idx, channel_name, trace_name):
        channel = self.flat_log.get_channel(channel_name)
        if not (channel.has_trace(trace_name)):
            return

        axe = self.idx_to_axe[subplot_idx]
        self.idx_to_content[subplot_idx].append((channel_name, trace_name))

        data = channel.slice_at_trace(channel.trace_names_to_idx[trace_name])
        axe.plot(channel.times, data, label = channel_name + "/" + trace_name)
        axe.legend()
        self.fig.canvas.draw()

    def remove_last_trace_from_fig(self, subplot_idx):
        axe = self.idx_to_axe[subplot_idx]
        axe.lines.pop(-1)
        self.idx_to_content[subplot_idx].pop(-1)
        axe.legend()
        self.fig.canvas.draw()

    def addmpl(self, fig):
        self.canvas = FigureCanvas(fig)
        self.mplvl.addWidget(self.canvas)
        self.canvas.draw()
        self.toolbar = NavigationToolbar(self.canvas,
                self.mpl_widget, coordinates=True)
        self.mplvl.addWidget(self.toolbar)

if __name__ == '__main__':
    import sys
    from PyQt4 import QtGui
    import numpy as np

    fig1 = Figure()
    ax1f1 = fig1.add_subplot(111)
    ax1f1.plot(np.random.rand(5))

    app = QtGui.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())

