import sys

from PyQt4 import (QtGui, QtCore)
from PyQt4.QtCore import Qt
from PyQt4.QtGui import (QTreeWidgetItem, QMenu)
from PyQt4.uic import loadUiType

from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

Ui_MainWindow, QMainWindow = loadUiType('lcmplot.ui')

from flat_log import Parser

class Subplot:
    def __init__(self, mpl_axes, idx, selector):
        # [(channel_name, trace_name), ... ], the order should match
        # self.mpl_axes.lines, and self.mpl_axes.legend_.texts
        self.contents = []
        self.mpl_axes = mpl_axes
        self.idx = idx
        self.selector = selector

    def clear(self):
        self.contents = []
        del self.mpl_axes.lines[:]
        if self.mpl_axes.legend_ is not None:
            del self.mpl_axes.legend_.texts[:]
        self.mpl_axes.legend()

class Main(QMainWindow, Ui_MainWindow):

    def __init__(self, ):
        super(Main, self).__init__()
        # parses the log file, this takes a while..
        log_parser = Parser(['bot_core'])
        self.flat_log = log_parser.load_log(sys.argv[1])

        self.setupUi(self)

        # make mpl fig
        self.fig = Figure()
        # initial attempt to eliminate borders in the subplots
        self.fig.subplots_adjust(left = 0.02, right = 0.99,
                                bottom = 0.03, top = 0.99,
                                wspace = 0.0, hspace = 0.1)
        self.add_mpl(self.fig)

        # build the treeWidget
        self.build_log_menu(self.flat_log)
        # add right click menu stuff
        self.traceTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.traceTree.customContextMenuRequested.connect(self.open_menu)

        # connect buttons
        self.clear_all_button.clicked.connect(self.clear_all_button_handler)
        self.clear_last_button.clicked.connect(self.clear_last_button_handler)
        self.add_figure_button.clicked.connect(self.add_figure_button_handler)
        self.remove_figure_button.clicked.connect(self.remove_figure_button_handler)

        # make radio buttons / button group for the subplot selector
        self.subplot_selector_group = QtGui.QButtonGroup()
        self.subplot_selector_group.setExclusive(True)

        # init internal lookups
        # subplot index -> subplot, subplot index is stricted increasing
        self.idx_to_subplot = {}
        # list of present subplots, this list needs to be sorted. and it gives
        # the index that matplotlib uses for plotting.
        # e.g. self.alive_subplot_idx = [1, 3, 4, 5, 8] means subplot 1 3 4 5 8
        # are present, and
        # subplot 1 is plotted at (5, 1, 1),
        # subplot 3 is plotted at (5, 1, 2),
        # subplot 4 is plotted at (5, 1, 3),
        # subplot 5 is plotted at (5, 1, 4),
        # subplot 8 is plotted at (5, 1, 5),
        # where the 3 number tuple is (num_rows, num_cols, idx) for drawing
        # subplots in matplotlib
        self.alive_subplot_idx = []

        self.new_subplot_idx = 1
        self.num_subplots = 0

        # init to have 6 subplots by default
        for i in range(0, 6):
            self.add_subplot()

        # redraw
        self.update_subplot_position()

    # get the channel name, and trace name from a Qt something item
    def get_channel_and_trace_name_from_item(self, item):
        path = str(item.text(0))
        while(True):
            if not(item.parent()):
                channel_name = str(item.text(0))
                break
            item = item.parent()
            path = str(item.text(0)) + "." + path

        trace_name = path[len(channel_name) + 1 :]
        return (channel_name, trace_name)

    # make a right click menu only for leaf nodes.
    def open_menu(self, position):
        item = self.traceTree.selectedItems()[0]
        # leaf node
        if item.childCount() == 0:
            names = self.get_channel_and_trace_name_from_item(item)
            channel_name = names[0]
            trace_name = names[1]

            subplot = self.idx_to_subplot[self.get_selected_subplot()]

            # make a right click popup menu
            menu = QMenu()
            menu.addAction("Add trace", lambda: self.add_trace_to_subplot(subplot, channel_name, trace_name))
            menu.addAction("Remove trace", lambda: self.remove_trace_from_subplot(subplot, channel_name, trace_name))

            menu.exec_(self.traceTree.viewport().mapToGlobal(position))

    # button handler for "Remove Figure" button
    def remove_figure_button_handler(self):
        if self.num_subplots == 1:
            return

        self.remove_subplot()
        self.update_subplot_position()

    # button handler for "Add Figure" button
    def add_figure_button_handler(self):
        self.add_subplot()
        self.update_subplot_position()

    # button handler for "Clear All Traces" button
    def clear_all_button_handler(self):
        for idx in self.alive_subplot_idx:
            self.idx_to_subplot[idx].clear()

        self.fig.canvas.draw()

    # button handler for "Clear Last Trace" button
    def clear_last_button_handler(self):
        subplot = self.idx_to_subplot[self.get_selected_subplot()]
        subplot.contents.pop(-1)
        subplot.mpl_axes.lines.pop(-1)
        subplot.mpl_axes.legend_.texts.pop(-1)
        subplot.mpl_axes.legend()
        self.fig.canvas.draw()

    # add a subplot
    def add_subplot(self):
        new_idx = self.new_subplot_idx
        # always add a new one to the bottom
        new_position = self.num_subplots + 1

        # add a new radio button for this plot and add it to the radio button group
        new_selector = QtGui.QRadioButton(str(new_idx))
        self.subplot_selector_group.addButton(new_selector)
        new_selector.setChecked(True)
        self.mpl_figure_selector_layout.addWidget(new_selector)

        # forces matplotlib to give me a new axes with new_idx, because it's
        # always increasing. The actual subplot location doesn't matter, since
        # it will get reset later. I think if I use num_subplots, it gives me
        # back the handle to the last subplot being added.
        new_axes = self.fig.add_subplot(new_idx, 1, new_position)
        new_subplot = Subplot(new_axes, new_idx, new_selector)

        self.idx_to_subplot[new_idx] = new_subplot

        # increment counters
        self.new_subplot_idx += 1
        self.num_subplots += 1

        self.alive_subplot_idx.append(new_idx)
        self.alive_subplot_idx.sort()

        return new_idx

    # get the correct positioning index (index that we tell matplotlib where
    # to draw the subplot) from subplot index. Since subplot index is strictly
    # increasing, and we could have removed some subplot earlier, these two
    # indices are not necessarily the same all the time.
    def get_subplot_position(self, idx):
        return self.alive_subplot_idx.index(idx)

    # gets the current subplot index from the selector radio buttons.
    def get_selected_subplot(self):
        for button in self.subplot_selector_group.buttons():
            if (button.isChecked()):
                active_idx = int(str(button.text()))
                return active_idx

    # removes a subplot completely
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

    # updates the rendering of all subplots. should be called after add / remove subplot.
    def update_subplot_position(self):
        # update the subplots' locations
        gs = gridspec.GridSpec(self.num_subplots, 1)
        for idx in self.alive_subplot_idx:
            position = self.get_subplot_position(idx)
            axes = self.idx_to_subplot[idx].mpl_axes
            axes.set_position(gs[position].get_position(self.fig))
            axes.set_subplotspec(gs[position])

        self.fig.canvas.draw()

    # build the tree widget that corresponds to the log topology
    def build_log_menu(self, log):
        for channel_name, channel in log.channels.iteritems():
            item = QTreeWidgetItem()
            item.setText(0, channel_name)
            self.build_tree_menu(item, channel.signature.tree)
            self.traceTree.addTopLevelItem(item)

    # build the tree widget that corresponds to the log topology
    def build_tree_menu(self, parent, tree):
        for me, children in tree:
            item = QTreeWidgetItem()
            item.setText(0, me)
            if children:
                self.build_tree_menu(item, children)
            parent.addChild(item)

    # adds a trace to a specific subplot, calls redraw only for that subplot
    def add_trace_to_subplot(self, subplot, channel_name, trace_name):
        channel = self.flat_log.get_channel(channel_name)
        if not (channel.has_trace(trace_name)):
            return

        subplot.contents.append((channel_name, trace_name))

        data = channel.slice_at_trace(trace_name)
        subplot.mpl_axes.plot(channel.times, data, label = channel_name + "/" + trace_name)
        subplot.mpl_axes.legend()
        self.fig.canvas.draw()

    # removes a trace from a specific subplot, calls redraw only for that subplot
    def remove_trace_from_subplot(self, subplot, channel_name, trace_name):
        try:
            i = subplot.contents.index((channel_name, trace_name))
            ax = subplot.mpl_axes
            del subplot.contents[i]
            del ax.lines[i]
            del ax.legend_.texts[i]

            # recompute the ax.dataLim
            ax.relim()
            # update ax.viewLim using the new dataLim
            ax.autoscale_view()
            ax.legend()
            self.fig.canvas.draw()
        except:
            return

    # make the matplotlib widget in the main gui.
    def add_mpl(self, fig):
        self.canvas = FigureCanvas(fig)
        self.mpl_figure_layout.addWidget(self.canvas)
        self.canvas.draw()
        self.toolbar = NavigationToolbar(self.canvas,
                self.matplotlib_widget, coordinates=True)
        self.mpl_toolbar_layout.addWidget(self.toolbar)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())

