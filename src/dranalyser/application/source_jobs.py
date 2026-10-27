"""Bounded read-only source diagnostic jobs; no revision/operational state writes."""
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from ..workbench.source_diagnostics import diagnose_source, diagnostic_identity


class SourceJobs:
    def __init__(self, root):
        self.root=root
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='source-diagnostics')
        self.jobs=OrderedDict()
        self.lock=threading.Lock()

    def request(self, revision, filename, options):
        # Verify immutable bytes/options on every poll, including completed jobs.
        identity=diagnostic_identity(self.root,revision,filename,options)
        key=identity['job_id']
        with self.lock:
            if key not in self.jobs:
                if len(self.jobs)>=2:
                    completed=next((k for k,f in self.jobs.items() if f.done()),None)
                    if completed is None:
                        return dict(status='busy',**identity,detail='Two source analyses are already pending. Waveform inspection remains available; retry shortly.')
                    del self.jobs[completed]
                self.jobs[key]=self.executor.submit(diagnose_source,self.root,revision,filename,identity['options'])
            future=self.jobs[key]
            self.jobs.move_to_end(key)
        if not future.done():
            return dict(status='pending',**identity,detail='Analysing source observations in the background. Waveforms remain available.')
        try:
            result=future.result()
            if result['job_id']!=key:
                raise ValueError('Source/options identity changed during analysis. Reopen this record.')
            return dict(status='ready',**identity,result=result)
        except Exception as exc:
            return dict(status='error',**identity,detail='Source diagnostics could not finish: '+str(exc)[:500])

    def close(self):
        self.executor.shutdown(wait=False,cancel_futures=True)
