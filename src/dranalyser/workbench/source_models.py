"""Per-application bounded source-fit reuse across non-numerical display choices."""

import copy
import threading
from collections import OrderedDict

from ..dsp.source_analysis import analyse_source


def analyse_models(source):
    result=analyse_source(source,max_windows=512)
    result.pop('digital',None)
    result.pop('axis',None)
    return result


class SourceModelCache:
    def __init__(self):
        self.entries=OrderedDict()
        self.lock=threading.Lock()

    def analyse(self,source,voltage_kv):
        key=(tuple(sorted(source['source_sha256'].items())),voltage_kv,
            tuple((c['key'],c.get('meaning'),c['units'],c['frequency_reference'],c['current_reference']) for c in source['channels']))
        with self.lock:
            if key not in self.entries:
                self.entries[key]=analyse_models(source)
                while len(self.entries)>2:
                    self.entries.popitem(last=False)
            self.entries.move_to_end(key)
            return copy.deepcopy(self.entries[key])
