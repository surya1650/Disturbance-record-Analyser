"""Explicit derived COMTRADE export with round-trip checks and provenance."""
import io
import json
import math
import zipfile

from ..comtrade.source_decode import decode_source


def export_join(source):
    if not source.get('join'):
        raise ValueError('Select a joined recording before exporting combined COMTRADE.')
    channels, digitals = source['channels'], source['digital']
    if not isinstance(source.get('nominal_frequency_hz'), (float, int)) or not 0 < source['nominal_frequency_hz'] <= 1000:
        raise ValueError('A valid declared nominal frequency is required for COMTRADE export.')
    if any(v is None for c in channels+digitals for v in c.get('values', c.get('states', []))):
        raise ValueError('COMTRADE export cannot represent unknown amplitudes or digital states without inventing data. Keep the original files and joined inspection.')
    headers = {h['id']: h for h in source['header_inventory']}
    analog_lines, raw_columns, errors = [], [], {}
    for number, channel in enumerate(channels, 1):
        h = headers[channel['key']]
        unit, a, b = h['declared_units'], float(h['a']), float(h['b'])
        primary, secondary, ps = float(h['primary']), float(h['secondary']), h['primary_secondary'].upper()
        if not all(math.isfinite(v) for v in (a, b, primary, secondary)):
            raise ValueError('Incomplete or nonfinite calibration fields cannot be exported safely.')
        skew = channel.get('skew_us')
        if skew is None or not math.isfinite(skew):
            raise ValueError('Declared analog sample skew is unavailable; no zero skew is invented for export.')
        ratio = primary/secondary if ps == 'S' and primary > 0 and secondary > 0 else 1
        multiplier = ratio*(1000 if unit.upper() in ('KV', 'KA') else 1)
        scaled = channel['units'] != 'raw counts'
        values = [(v/multiplier-b)/a for v in channel['values']] if scaled else channel['values']
        if any(not math.isfinite(v) for v in values):
            raise ValueError('Source calibration cannot be represented in the export.')
        integer = all(abs(v-round(v)) <= 1e-7 and abs(round(v)) <= 2147483647 for v in values)
        scale = 1. if integer else max(abs(v) for v in values)/2147480000
        if not integer and (not scaled or not scale or not math.isfinite(a*scale)):
            raise ValueError('Unknown-unit fractional counts or extreme scaling cannot be exported safely as integer COMTRADE. Original recordings remain available.')
        raw = [round(v/scale) for v in values]
        new_a = a*scale
        raw_columns.append(raw)
        reconstructed = [(v*new_a+b)*multiplier for v in raw] if scaled else raw
        errors[channel['key']] = max(abs(v-w) for v, w in zip(channel['values'], reconstructed, strict=True))
        # ASCII has integer analog samples. Floating sources are explicitly quantized to 32-bit counts.
        label = channel['label'].replace(',', ' ').replace('\r', ' ').replace('\n', ' ')
        analog_lines.append(f'{number},{label},{h.get("phase", "")},,{unit},{new_a:.17g},{b:.17g},{skew:.17g},-2147483648,2147483647,{primary:.17g},{secondary:.17g},{ps}')
    times = source['axis']['elapsed_s']
    multiplier = next((m for m in (.001, .01, .1, 1., 10.) if times[-1]*1e6/m <= 4294967295), None)
    if multiplier is None:
        raise ValueError('Joined time range exceeds the supported COMTRADE timestamp budget.')
    stamps = [round(t*1e6/multiplier) for t in times]
    if any(b <= a for a, b in zip(stamps, stamps[1:], strict=False)):
        raise ValueError('Export timestamp resolution would collapse distinct samples; keep separate original recordings.')
    if any(headers[c['key']].get('normal_state') not in ('0', '1') for c in digitals):
        raise ValueError('A declared digital normal state is required for export; polarity is not invented.')
    digital_lines = [f'{i},{c["label"].replace(",", " ")},,,{headers[c["key"]]["normal_state"]}'
                     for i, c in enumerate(digitals, 1)]
    lines = [f'{source["station"]},{source["device"]} [DERIVED JOIN],1999', f'{len(channels)+len(digitals)},{len(channels)}A,{len(digitals)}D',
             *analog_lines, *digital_lines, str(source['nominal_frequency_hz']), '0', f'0,{len(times)}',
             source['recorded_times']['start'], source['recorded_times']['trigger'], 'ASCII', str(multiplier)]
    cfg = ('\r\n'.join(lines)+'\r\n').encode('utf-8')
    dat = ('\r\n'.join(','.join(map(str, [i+1, stamps[i], *(c[i] for c in raw_columns),
                       *(c['states'][i] for c in digitals)])) for i in range(len(times)))+'\r\n').encode('ascii')
    decoded = decode_source(cfg, dat, cfg_name='joined.cfg', dat_name='joined.dat')
    if decoded['sample_count'] != len(times) or decoded['axis']['status'] != 'source_time_inspection':
        raise ValueError('Derived COMTRADE round-trip verification failed; no export published.')
    if any(a['states'] != b['states'] for a, b in zip(digitals, decoded['digital'], strict=True)):
        raise ValueError('Derived digital-state round-trip verification failed.')
    for before, after in zip(channels, decoded['channels'], strict=True):
        if before['units'] != after['units'] or any(v is None for v in after['values']):
            raise ValueError('Derived export would change source-unit interpretation; keep the originals.')
        actual = max(abs(v-w) for v, w in zip(before['values'], after['values'], strict=True))
        if actual > errors[before['key']]+max(max(map(abs, before['values'])), 1.)*1e-12:
            raise ValueError('Derived export amplitude round-trip verification failed.')
    source_names = [entry['file'] for entry in source['join']['sources']]
    source_ids = {name: i for i, name in enumerate(source_names)}
    manifest = dict(source['join'], source_sha256=source['source_sha256'], source_names=source_names,
        source_samples=[[source_ids[name], i] for name, i in source['_origins']],
        sample_origin_encoding='Each row is [index into source_names, zero-based original sample index].',
        original_channel_inventory=source['header_inventory'],
        original_relay=dict(station=source['station'], device=source['device']),
        amplitude_max_absolute_error=errors, timestamp_resolution_s=multiplier*1e-6,
        maximum_timestamp_error_s=max(abs(t-stamp*multiplier*1e-6) for t, stamp in zip(times, stamps, strict=True)),
        derived=True, operationally_validated=False,
        note='Derived viewing export, not relay-original evidence. Overlap samples retained. First capture supplies CFG trigger; all capture triggers are in sources. Integer-compatible source counts are retained; floating sources use explicit 32-bit count quantization.')
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('joined.cfg', cfg)
        bundle.writestr('joined.dat', dat)
        bundle.writestr('joined.hdr', 'DERIVED JOIN: not relay-original evidence.\n'
                        'Original capture checksums, all trigger times, sample origins, overlaps/gaps, and export errors are in provenance.json.\n'
                        'Do not infer clock synchronization, physical calibration, or fault-location eligibility from this export.\n')
        bundle.writestr('provenance.json', json.dumps(manifest, indent=2))
    return archive.getvalue()
