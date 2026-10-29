"""Run the current checkout in an isolated preview, including Codespaces forwarding."""
import json
import os
import re
import shutil
import sys
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')


def main():
    import uvicorn
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from dranalyser.application.api import create_app
    from dranalyser.application.worker import Worker
    from scripts.create_demo import create_demo

    port = int(os.environ.get('DR_PREVIEW_PORT', '8098'))
    if not 1 <= port <= 65535:
        raise ValueError('DR_PREVIEW_PORT must be between 1 and 65535.')
    codespace = os.environ.get('CODESPACE_NAME', '')
    domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')
    hostname = f'{codespace}-{port}.{domain}' if codespace else ''
    if hostname and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', hostname):
        raise ValueError('Codespaces forwarding hostname is invalid.')
    preview = ROOT / 'out' / 'web-preview'
    registry = preview / 'registry'
    registry.mkdir(parents=True, exist_ok=True)
    synthetic = create_demo(preview / 'synthetic-demo')
    shutil.copyfile(synthetic / 'synthetic-line.yaml', registry / 'synthetic-demo.yaml')
    app = create_app(preview / 'application', registry, workers=1)
    receipt = preview / 'demo-receipt.json'
    if not receipt.exists():
        with ExitStack() as stack:
            streams = [(f'{end}/{path.name}', stack.enter_context(path.open('rb')))
                       for end in ('S', 'R') for path in sorted((synthetic / end).iterdir())]
            row, _duplicate = app.state.intake.ingest(streams, name='Synthetic two-record demonstration')
        Worker(app.state.store, registry).once()
        with receipt.open('x') as stream:
            json.dump({'incident_id': row['incident_id']}, stream)
    for middleware in app.user_middleware:
        if hostname and middleware.cls is TrustedHostMiddleware:
            middleware.kwargs['allowed_hosts'] = [*middleware.kwargs['allowed_hosts'], hostname]
    url = f'https://{hostname}' if hostname else f'http://127.0.0.1:{port}'
    print('\nLatest checkout preview: ' + url, flush=True)
    print(f'Codespaces: Ports -> {port} -> Open in Browser. Keep visibility Private.', flush=True)
    print('Preview data: ' + str(preview), flush=True)
    uvicorn.run(app, host='0.0.0.0' if hostname else '127.0.0.1', port=port)


if __name__ == '__main__':
    main()
