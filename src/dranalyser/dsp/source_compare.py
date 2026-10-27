"""Independent local references are display aids, never synchronisation evidence."""


def _digital_intervals(record):
    time=record['axis'].get('elapsed_s',[])
    result=[]
    for channel in record['digital']:
        bits=channel['states']
        start=None
        active=bool(bits and bits[0]==1)
        def segment(start,end,channel=channel,bits=bits):
            known=start is not None and end is not None and len(time)==len(bits)
            return dict(key=channel['key'],label=channel['label'],start_index=start,end_index=end,
                source_span_s=float(time[end]-time[start]) if known else None,
                duration_sample_bracket_s=[max(0.,float(time[end-1]-time[start])),float(time[end]-time[start-1])]
                    if known else None)
        for index,bit in enumerate(bits):
            if index==0:
                continue
            if bit is None or bits[index-1] is None:
                if active:
                    result.append(segment(start,None))
                active=bit==1
                start=None
            elif bit==1 and bits[index-1]==0:
                start,active=index,True
            elif bit==0 and bits[index-1]==1:
                result.append(segment(start,index))
                start,active=None,False
        if active:
            result.append(segment(start,None))
    return result


def compare_sources(analyses,reference=None):
    """Caller-grouped views do not prove shared incident identity or physical ends."""
    rows=[]
    hashes={}
    for index,analysis in enumerate(analyses):
        row=dict(analysis)
        digest=row.get('content_hash')
        row['duplicate_of']=hashes.get(digest) if digest else None
        if digest:
            hashes.setdefault(digest,index)
        row['digital_intervals']=_digital_intervals(row)
        anchor=dict(status='record_start',sample_index=0,source_s=0.,label='First source sample; not fault inception')
        if reference:
            anchor=dict(status='unavailable',sample_index=None,source_s=None,label=reference)
            matches=[c for c in row['digital'] if c['label'].strip()==reference.strip()]
            time=row['axis'].get('elapsed_s',[])
            if len(matches)==1 and len(time)==len(matches[0]['states']):
                bits=matches[0]['states']
                edges=[i for i in range(1,len(bits)) if bits[i-1]==0 and bits[i]==1]
                if edges:
                    k=edges[0]
                    anchor.update(status='declared_local_edge',sample_index=k,source_s=float(time[k]),
                        sample_bracket_s=[float(time[k-1]),float(time[k])])
        row['local_reference']=anchor
        rows.append(row)
    return dict(records=rows,distinct_payloads=len(hashes),pairing_verified=False,
        alignment_eligible=False,authorizes_location=False,physical_timing_verified=False,
        basis='Independent source-coordinate views. Local references do not prove a common event or clock.',
        limitations=['No missing CT/VT ratios, wiring, line parameters or recorder timing are inferred.',
            'A consistent signal fit does not certify CT saturation absence, anti-alias filtering or physical accuracy.',
            'Fault classification, physical operating times and location remain subject to their own gates.'])
