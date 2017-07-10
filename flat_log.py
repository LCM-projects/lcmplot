import lcm
import numbers
import numpy as np
import pkgutil
import importlib

try:
    import cStringIO.StringIO as BytesIO
except ImportError:
    from io import BytesIO

# gets the time stamp for this lcm message if it containts 'utime' or
# 'timestamp', else 0.
def g_get_time(msg):
    if hasattr(msg, 'utime'):
        return msg.utime / 1e6
    elif hasattr(msg, 'timestamp'):
        return msg.timestamp / 1e6
    else:
        return 0

# This class represents a "flattened" version of a potentially nested LCM
# message. It has a map from string to int, where keys (strings) are the
# nested variable names, and values (int) are the corresponding index after
# "flattening".
#
# A tree like representation of this data will also be constructed. The tree
# has the following recursive format:
# [(var0, var0_s_children), (var1, var1_s_children), ...], where children is
# a list of the same form. Leaf variable's children will be an empty list
#
# If the LCM msg struct looks like this:
# msg:
#   int num
#   my_other_msg stuff
# and
# my_other_msg:
#   int data[3]
#
# The signature looks like this:
# sign.trace_names_to_idx = {'num' : 0, 'stuff.0' : 1, 'stuff.1' : 2, 'stuff.2' : 3}
# sign.tree = [(num, []), (stuff, [(0, []), (1, []), (2, [])])]
#
class DataPointSignature:
    def __init__(self, channel_name, data):
        self.channel_name = channel_name
        self.trace_names_to_idx = {}
        self.tree = self._recursive_flatten(data, '')

        self.trace_names_to_idx['dt'] = len(self.trace_names_to_idx)
        self.tree.append(('dt', []))

    def _recursive_flatten(self, data, current_path):
        children = []
        # nested, keep crawling down
        if (hasattr(data, '__slots__')):
            for attr_name in data.__slots__:
                attr = data.__getattribute__(attr_name)
                if (len(current_path) == 0):
                    my_child = self._recursive_flatten(attr, attr_name)
                else:
                    my_child = self._recursive_flatten(attr, current_path + "." + attr_name)
                children.append((attr_name, my_child))
        # not nested
        else:
            # data is single numerical
            if isinstance(data, numbers.Number):
                self.trace_names_to_idx[current_path] = len(self.trace_names_to_idx)
            # data is a list / tuple of numerical
            elif all(isinstance(x, numbers.Number) for x in data):
                for i in range(0, len(data)):
                    self.trace_names_to_idx[current_path + '.' + str(i)] = len(self.trace_names_to_idx)
                    children.append((str(i), []))
            # data is a list / tuple of strings
            elif all(isinstance(x, (str, unicode)) for x in data):
                for i, string in enumerate(data):
                    children.append((str(i) + " : " + str(string), []))
        return children

# This class just contains the data part of a message, the semantics are
# captured in the signature class.
# Following the previous example, suppose:
# msg.num = 6;
# msg.stuff[0] = 1;
# msg.stuff[1] = 2;
# msg.stuff[2] = 3;
#
# It's flat data is be:
# self.trace_data = [6, 1, 2, 3]
class DataPoint:
    def __init__(self, data, signature, time):
        self.data = []
        self.time = time
        self._recursive_flatten(data, signature, '')

    def _recursive_flatten(self, data, signature, current_path):
        # nested
        if (hasattr(data, '__slots__')):
            for attr_name in data.__slots__:
                attr = data.__getattribute__(attr_name)
                if (len(current_path) == 0):
                    self._recursive_flatten(attr, signature, attr_name)
                else:
                    self._recursive_flatten(attr, signature, current_path + "." + attr_name)
        # leaf
        else:
            if isinstance(data, numbers.Number):
                self.data.append(data)
            elif all(isinstance(x, numbers.Number) for x in data):
                map(self.data.append, data)

# A channel contains a list of timestamps and a list of list of data.
# when finalize() is called, the list of time and list of list of data will be
# converted into np arrays.
# data should be indexed by data[time_idx, trace_idx]
# Should not attempt to access data before finalize() is called.
class Channel:
    def __init__(self, channel_name):
        self.channel_name = channel_name
        self.signature = None
        self.times = []
        self.data_points = []
        self.is_final = False

    def add_data_point(self, msg):
        if (self.is_final):
            return

        if self.signature is None:
            self.signature = DataPointSignature(self.channel_name, msg)

        time = g_get_time(msg)

        flat_data_point = DataPoint(msg, self.signature, time)
        dt = 0
        if len(self.times) > 0:
            dt = time - self.times[-1]
        flat_data_point.data.append(dt)

        self.times.append(flat_data_point.time)
        self.data_points.append(flat_data_point.data)

    def finalize(self):
        if (self.is_final):
            return

        self.times = np.array(self.times)
        self.data_points = np.array(self.data_points)
        self.is_final = True

    def has_trace(self, trace_name):
        return trace_name in self.signature.trace_names_to_idx

    def slice_at_time(self, time_idx):
        return self.data_points[time_idx, :]

    def slice_at_trace(self, trace_name):
        trace_idx = self.signature.trace_names_to_idx[trace_name]
        return self.data_points[:, trace_idx]

# Holds a collection of channels.
class FlatLog:
    def __init__(self):
        self.channels = {}
        self.is_final = False

    def add_data_point(self, channel_name, msg):
        if (self.is_final):
            return

        if channel_name not in self.channels:
            self.channels[channel_name] = Channel(channel_name)

        channel = self.channels[channel_name]
        channel.add_data_point(msg)

    def finalize(self):
        if (self.is_final):
            return

        for channel_name, channel in self.channels.iteritems():
            channel.finalize()

        self.is_final = True

    def has_channel(self, channel_name):
        return channel_name in self.channels

    def get_channel(self, channel_name):
        return self.channels[channel_name]

#############################################################################
class Parser:
    def __init__(self, pkg_names):
        self.hash_to_decoder = {}
        for name in pkg_names:
            self.load_msg_types_from_package(name)

    def load_msg_types_from_package(self, pkg_name):
        pkg = importlib.import_module(pkg_name)
        msgs_list = [name for _, name, _ in pkgutil.iter_modules([pkg.__name__])]
        # for every message in the package, store its hash -> decode function.
        for name in msgs_list:
            module = getattr(pkg, name)
            self.hash_to_decoder[module._get_packed_fingerprint()] = module.decode

    def _get_msg_hash(self, event):
        if hasattr(event.data, 'read'):
            buf = event.data
        else:
            buf = BytesIO(event.data)
        return buf.read(8)

    def load_log(self, log_name):
        log = lcm.EventLog(log_name, "r")
        flat_log = FlatLog()

        # parse log
        for event in log:
            msg_hash = self._get_msg_hash(event)
            if msg_hash in self.hash_to_decoder:
                decoder = self.hash_to_decoder[msg_hash]
                msg = decoder(event.data)
                flat_log.add_data_point(event.channel, msg)

        flat_log.finalize()
        return flat_log
