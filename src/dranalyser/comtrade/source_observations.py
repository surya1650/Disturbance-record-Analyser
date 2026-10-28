"""Bounded read-only source acquisition, separate from strict byte decoding."""
from pathlib import Path

from .source_decode import _number as _number
from .source_decode import decode_source


def _read(path, limit):
    with path.open('rb') as stream:
        raw=stream.read(limit+1)
    if len(raw)>limit:
        raise ValueError(f'{path.suffix.upper().lstrip(".")} source byte budget exceeded ({limit} bytes).')
    return raw


def load_source(cfg_path, dat_path=None):
    path=Path(cfg_path)
    out=dict(status='unsupported',issues=[],channels=[],digital=[],sample_count=0,
        axis=dict(status='withheld',elapsed_s=[],reason='Source decode unavailable.'),
        content_hash='',source_sha256={},authorizes_location=False,alignment_eligible=False)
    try:
        if path.suffix.lower()!='.cfg':
            raise ValueError('Unsupported source container; explicit CFG/DAT required.')
        cfg=_read(path,1048576)
        # Decode CFG before touching DAT, retaining independently readable metadata.
        out=decode_source(cfg,cfg_name=path.name)
        if out['status']=='unsupported':
            return out
        data=Path(dat_path) if dat_path else next((p for p in
            (path.with_suffix('.DAT'),path.with_suffix('.dat'),path.with_suffix('.Dat')) if p.is_file()),
            path.with_suffix('.dat'))
        if not data.is_file():
            return out
        return decode_source(cfg,_read(data,64*1024*1024),cfg_name=path.name,dat_name=data.resolve().name)
    except (ValueError,OSError) as exc:
        out.update(status='unsupported',channels=[],digital=[],sample_count=0,
            axis=dict(status='withheld',elapsed_s=[],reason='Source decode unavailable.'))
        out['issues'].append(str(exc))
        return out

