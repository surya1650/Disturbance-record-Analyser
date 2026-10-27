"""Bounded digital observations and possible trip/reclose explanations."""
from ..rules.signals import CANONICAL, map_signals


def digital_evidence(source, mappings, limit=512, *, mapping_sources=None, asserted_states=None):
    time=source['axis'].get('elapsed_s', [])
    result=[]
    remaining=4096
    asserted_states=asserted_states or {}
    headers={c['id']:c for c in source.get('header_inventory',[])}
    for c in source['digital']:
        key,label,bits=c['key'],c['label'],c['states']
        selected=mappings.get(key)
        automatic=map_signals([label])
        meanings=([selected] if selected!='ignore' else []) if selected else [m for m in CANONICAL if label in automatic.channels(m)]
        rising=[]
        falling=[]
        rising_count=falling_count=0
        asserted=asserted_states.get(key,1)
        raw_normal=headers.get(key,{}).get('normal_state')
        normal=int(raw_normal) if raw_normal in ('0','1') else None
        interpretation=key in asserted_states or normal!=asserted
        first=next((i for i,v in enumerate(bits) if v==asserted),None)
        for i in range(1,len(bits)):
            if bits[i-1] is None or bits[i] is None or bits[i-1]==bits[i]:
                continue
            edge=dict(index=i,sample_bracket=[i-1,i],source_s=time[i] if time else None,
                      source_bracket_s=[time[i-1],time[i]] if time else None)
            if bits[i]==1:
                rising_count+=1
                if len(rising)<limit and remaining>0:
                    rising.append(edge)
                    remaining-=1
            else:
                falling_count+=1
                if len(falling)<limit and remaining>0:
                    falling.append(edge)
                    remaining-=1
        result.append(dict(id=key,label=label,meanings=meanings,mapping_source=(mapping_sources or {}).get(key,'source-analysis choice' if selected else 'label suggestion'),
            first_active_index=first,first_active_source_s=time[first] if time and first is not None else None,
            unknown_samples=sum(v is None for v in bits),active_samples=sum(v==asserted for v in bits),
            asserted_state=asserted,assertion_source='source-analysis choice' if key in asserted_states else 'assumed high state',
            declared_normal_state=normal,interpretation_available=interpretation,
            assertion_note='CFG normal state is recorded metadata, not asserted-state authority; review polarity if the default equals the normal state.',
            rising_edges=rising,falling_edges=falling,rising_count=rising_count,falling_count=falling_count,
            omitted_edges=rising_count+falling_count-len(rising)-len(falling),
            note='Recorded indication only. Source sample brackets are not physical relay operating times.'))
    return result


def trip_ar(evidence):
    def active(meanings):
        return [c for c in evidence if c['first_active_index'] is not None and c.get('interpretation_available',True) and set(c['meanings']) & set(meanings)]
    trips=active(['TRIP','TRIP_A','TRIP_B','TRIP_C','TRIP_3P','TRIP_Z2','TRIP_Z3','TRIP_Z4'])
    trip=dict(status='Observed indication' if trips else 'Not available',evidence_ids=[c['id'] for c in trips],
        text='Trip indications recorded under stated polarity: '+', '.join(c['id']+' '+c['label']+' (state '+str(c.get('asserted_state',1))+'; '+c.get('assertion_source','assumed high state')+')' for c in trips) if trips else
             'No assigned trip assertion was observed. Check channel meanings and capture coverage; absence is not proof of no trip.')
    causes=[]
    ids=[]
    for meanings,text in [(['AR_BLOCK'],'AR blocking indication recorded; a close command may have been inhibited. Check scheme inputs and settings.'),
                         (['AR_LOCKOUT'],'AR lockout indication recorded. Shot/reclaim limits or scheme state may explain why no further close occurred.'),
                         (['AR_FAIL'],'AR failure indication recorded. The indication alone does not identify its physical cause.')]:
        matches=active(meanings)
        if matches:
            causes.append(text)
            ids.extend(c['id'] for c in matches)
    close=active(['AR_CLOSE'])
    init=active(['AR_INITIATE'])
    if init and not close:
        causes.append('AR initiation recorded; no assigned close assertion observed within this capture. Check inhibit/wait logic and capture duration.')
        ids.extend(c['id'] for c in init)
    def assertion_edges(channel):
        return channel['rising_edges'] if channel.get('asserted_state',1)==1 else channel['falling_edges']
    close_edges=[e['index'] for c in close for e in assertion_edges(c)]
    after=[c for c in trips if any(e['index']>lo for e in assertion_edges(c) for lo in close_edges)]
    if after:
        causes.append('A close indication is followed by a trip indication. A persistent or returning fault, or a breaker/close-path issue, is possible; inspect fault currents and pole states.')
        ids.extend(c['id'] for c in close+after)
    ar=dict(status='Possible explanation' if causes else 'Not available',evidence_ids=list(dict.fromkeys(ids)),
        text=' '.join(causes) if causes else 'No observed assigned AR assertions identify a failure mechanism in this capture. Review AR/pole indications, capture coverage and scheme settings; add any missing channels.')
    return trip,ar
