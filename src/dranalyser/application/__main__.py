"""python -m dranalyser.application [serve|worker]"""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main():
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    parser = argparse.ArgumentParser(description='Run the local DR Analyser application.')
    parser.add_argument('command', nargs='?', choices=['serve', 'worker'], default='serve')
    parser.add_argument('--root', default='out/application')
    parser.add_argument('--registry', default='data/registry')
    parser.add_argument('--inbox', help='Completed event folders and ZIPs to collect')
    parser.add_argument('--port', type=int, default=8091)
    parser.add_argument('--workers', type=int, default=2, help='Embedded analysis workers; 0 for separate workers')
    args = parser.parse_args()
    if not 0 <= args.workers <= 8:
        parser.error('--workers must be between 0 and 8')
    if args.command == 'worker':
        import threading
        from .store import Store
        from .worker import Worker
        try:
            Worker(Store(Path(args.root)), args.registry).run(threading.Event())
        except KeyboardInterrupt:
            pass
        return
    import uvicorn
    from .api import create_app
    app = create_app(args.root, args.registry, args.inbox, args.workers)
    print(f'DR Analyser: http://127.0.0.1:{args.port}')
    print(f'Data directory: {app.state.store.root}')
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
