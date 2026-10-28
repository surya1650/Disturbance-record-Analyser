"""Explicit bounded CFF framing. Binary bytes are never searched for separators."""
import hashlib
import re

from .source_decode import decode_source

_MARKER=re.compile(rb'^---[ \t]*file type:[ \t]*(.*?)[ \t]*---[ \t]*(?:\r\n|\n|\r|$)',re.I|re.M)
_FORMATS=('ASCII','BINARY','BINARY32','FLOAT32')


def _tail(raw):
    """Only explicitly framed text metadata may follow the declared payload."""
    raw=raw.lstrip(b'\r\n')
    if not raw:
        return
    markers=list(_MARKER.finditer(raw))
    if not markers or markers[0].start()!=0:
        raise ValueError('Unsupported trailing CFF bytes outside declared DAT payload.')
    if any(m.group(1).strip().upper() not in (b'HDR',b'INF') for m in markers):
        raise ValueError('Unsupported trailing CFF section format; only HDR/INF text is supported.')


def _framed(raw):
    first=_MARKER.match(raw.removeprefix(b'\xef\xbb\xbf'))
    offset=3 if raw.startswith(b'\xef\xbb\xbf') else 0
    if first is None or first.group(1).strip().upper()!=b'CFG':
        raise ValueError('CFF requires an explicit initial CFG section marker.')
    begin=first.end()+offset
    # Only scan the bounded CFG region, before interpreting any DAT bytes.
    marker=_MARKER.search(raw,begin,min(len(raw),begin+1048576+128))
    cfg=raw[begin:marker.start()] if marker else raw[begin:]
    return cfg,marker


def decode_cff(raw,name):
    identity=hashlib.sha256(raw).hexdigest()
    out=dict(status='unsupported',issues=[],channels=[],digital=[],sample_count=0,
        axis=dict(status='withheld',elapsed_s=[],reason='Source container decode unavailable.'),
        authorizes_location=False,alignment_eligible=False)
    try:
        cfg,marker=_framed(raw)
        out=decode_source(cfg,cfg_name='container.cfg')
        if out['status']=='unsupported':
            return out
        if re.search(rb'^---[^\r\n]*file type:',cfg,re.I|re.M):
            out['issues']=[]
            raise ValueError('Malformed CFF section separator in CFG region.')
        if marker is None:
            return out
        out['issues']=[]
        words=marker.group(1).strip().upper().split()
        if len(words) not in (1,2) or words[0]!=b'DAT':
            raise ValueError('CFF requires an explicit supported DAT section format.')
        lines=[line.strip() for line in cfg.decode('latin1').replace('\x1a','').splitlines() if line.strip()]
        counts=lines[1].split(',')
        na,nd=int(counts[1][:-1]),int(counts[2][:-1])
        j=2+na+nd
        rates=int(lines[j+1])
        end=j+2+max(rates,1)
        kind=lines[end+2].upper()
        if kind not in _FORMATS or (len(words)==2 and words[1].decode('ascii')!=kind):
            raise ValueError('CFF DAT section format is unknown or conflicts with the explicit CFG format.')
        payload=raw[marker.end():]
        if kind=='ASCII':
            section=_MARKER.search(payload)
            if section:
                _tail(payload[section.start():])
                payload=payload[:section.start()]
            if re.search(rb'^---[^\r\n]*file type:',payload,re.I|re.M):
                raise ValueError('Malformed CFF DAT section separator.')
        else:
            declared=int(lines[end-1].split(',')[1])
            if not 1<=declared<=200000:
                raise ValueError('Unsupported CFF declared binary sample budget.')
            rowbytes=8+na*({'BINARY':2,'BINARY32':4,'FLOAT32':4}[kind])+2*((nd+15)//16)
            boundary=declared*rowbytes
            if len(payload)>boundary:
                _tail(payload[boundary:])
                payload=payload[:boundary]
        out=decode_source(cfg,payload,cfg_name='container.cfg',dat_name='container.dat')
        return out
    except (ValueError,IndexError,UnicodeError) as exc:
        out.update(status='unsupported',channels=[],digital=[],sample_count=0,
            axis=dict(status='withheld',elapsed_s=[],reason='Source container decode unavailable.'))
        out['issues'].append(str(exc))
        return out
    finally:
        # Virtual sections are not uploaded source files; retain only original bytes.
        out.update(source_sha256={name:identity},content_hash=identity,
            content_hash_basis='SHA256(original CFF container bytes); virtual sections are not source files')
