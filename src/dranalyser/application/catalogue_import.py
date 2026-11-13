"""Upload, preview and explicitly activate retained Excel source evidence."""
from typing import Annotated

from anyio import CapacityLimiter, to_thread
from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from ..registry.catalogue import build_catalogue, digest
from ..registry.catalogue_store import (
    ActivationConflict,
    activate_import,
    import_preview,
    list_imports,
    original_import,
    save_import,
)
from ..registry.xlsx_catalogue import read_workbook

MAX_WORKBOOK_BYTES = 16 * 1024 * 1024


class CatalogueActivation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_active_hash: str | None = Field(..., strict=True, pattern=r'^[0-9a-f]{64}$')


def install_catalogue_import(app, root):
    """Install under the application's existing token and origin middleware."""
    parsing = CapacityLimiter(2)

    def prepare(original, filename):
        snapshot = read_workbook(original, filename)
        catalogue = build_catalogue(snapshot)
        return save_import(root, original, snapshot,
                           {'catalogue_hash': digest(catalogue), 'catalogue': catalogue})

    def known(action, import_id, *args):
        try:
            return action(root, import_id, *args)
        except KeyError as exc:
            raise HTTPException(404, 'Source catalogue import not found.') from exc

    @app.post('/api/catalogue/imports')
    async def upload(file: Annotated[UploadFile, File()]):
        try:
            original = await file.read(MAX_WORKBOOK_BYTES + 1)
        finally:
            await file.close()
        if len(original) > MAX_WORKBOOK_BYTES:
            raise HTTPException(413, 'Excel workbook exceeds the 16 MiB upload limit.')
        return await to_thread.run_sync(prepare, original, file.filename or 'original.xlsx', limiter=parsing)

    @app.get('/api/catalogue/imports')
    def history():
        return list_imports(root)

    @app.get('/api/catalogue/imports/{import_id}')
    def preview(import_id: str):
        return known(import_preview, import_id)

    @app.post('/api/catalogue/imports/{import_id}/activate')
    def activate(import_id: str, body: CatalogueActivation):
        try:
            return known(activate_import, import_id, body.expected_active_hash)
        except ActivationConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/catalogue/imports/{import_id}/original')
    def original(import_id: str):
        return FileResponse(known(original_import, import_id), filename='original.xlsx',
                            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
