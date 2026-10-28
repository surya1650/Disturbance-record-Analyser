"""Bounded declared header facts, independent of source analysis eligibility."""


def header_information(raw):
    if len(raw)>1048576:
        return {}
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin1')
    lines = [line.strip() for line in text.replace('\x1a', '').splitlines() if line.strip()]
    try:
        counts = lines[1].split(',')
        na, nd = int(counts[1][:-1]), int(counts[2][:-1])
        if (counts[1][-1:] != 'A' or counts[2][-1:] != 'D' or not 0 <= na <= 64
                or not 0 <= nd <= 256 or int(counts[0]) != na+nd or len(lines) < 2+na+nd):
            return {}
        inventory = []
        for i, line in enumerate(lines[2:2+na+nd]):
            fields = line.split(',')
            analog = i < na
            inventory.append(dict(id=f'A{i+1}' if analog else f'D{i-na+1}',
                source_id=fields[0], kind='analog' if analog else 'digital', label=fields[1],
                phase=fields[2] if analog and len(fields)>2 else '',
                normal_state=fields[4] if not analog and len(fields)>4 else None,
                **({key: fields[pos] if len(fields)>pos else '' for key,pos in
                    [('a',5),('b',6),('primary',10),('secondary',11),('primary_secondary',12)]} if analog else {}),
                declared_units=fields[4] if analog and len(fields) > 4 else 'state' if not analog else 'Not available'))
        times=dict(start=None,trigger=None,basis='CFG recorded strings; timezone and trigger semantics are unverified.')
        try:
            j=2+na+nd
            rates=int(lines[j+1])
            index=j+2+max(rates,1)
            if 0<=rates<=8 and len(lines)>index+1:
                times.update(start=lines[index],trigger=lines[index+1])
        except (ValueError,IndexError):
            pass
        return dict(inventory=inventory,recorded_times=times)
    except (ValueError, IndexError):
        return {}
