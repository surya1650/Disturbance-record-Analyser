"""Start the browser app with the exact GitHub Codespaces forwarded hostname."""
import argparse
import os
from pathlib import Path

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dranalyser.application.api import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8091)
    parser.add_argument('--root', default='out/browser-test')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    name = os.environ.get('CODESPACE_NAME')
    if not name:
        parser.error('Run this launcher inside GitHub Codespaces. For a local app use python -m dranalyser.application.')
    domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')
    hostname = f'{name}-{args.port}.{domain}'
    os.chdir(Path(__file__).resolve().parents[1])
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    app = create_app(root=args.root, workers=1)
    for middleware in app.user_middleware:
        if middleware.cls is TrustedHostMiddleware:
            middleware.kwargs['allowed_hosts'].append(hostname)
    print(f'Open port {args.port} from the Codespaces Ports tab. Keep it private for real DR files.')
    uvicorn.run(app, host='0.0.0.0', port=args.port)


if __name__ == '__main__':
    main()
