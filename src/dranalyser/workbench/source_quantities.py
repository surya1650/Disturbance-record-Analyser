"""Conditional export-phasor quantities; never an operational location authority."""
import math

TINY=2.2250738585072014e-308
CONDITION_FLOOR=1e-8


def _real(value):
    try:
        if isinstance(value,bool) or not isinstance(value,(int,float)):
            return None
        value=float(value)
        return value if math.isfinite(value) else None
    except (ValueError,OverflowError):
        return None


def _finite_complex(value):
    return math.isfinite(value.real) and math.isfinite(value.imag)


def _pair(value):
    return [float(value.real),float(value.imag)]


def _unavailable(reason,**fields):
    return dict(status='Not available',reason=reason,authorizes_location=False,**fields)


def _phasors(channels,window,roles):
    frequency=window.get('frequency') or {}
    if frequency.get('status')!='estimated' or (_real(frequency.get('frequency_hz')) or 0)<=0:
        return None,'An estimated finite source-window frequency is required.'
    if window.get('coverage_status')!='covered':
        return None,'The requested source support is not covered.'
    values={}
    centres=[]
    for role in roles:
        matches=[c for c in channels if c.get('meaning')==role]
        if len(matches)!=1:
            return None,'Assign exactly one source channel to '+role+'; missing, ignored and duplicate meanings stay unavailable.'
        channel=matches[0]
        unit=str(channel.get('units','')).split(' ',1)[0]
        if unit!=('V' if role.startswith('V') else 'A'):
            return None,role+' requires corresponding V/A source scaling; raw counts or incompatible units cannot form this quantity.'
        fit=window.get('channels',{}).get(channel['id'],{})
        phasor=fit.get('phasor')
        centre=_real(fit.get('centre_s'))
        if fit.get('status')!='model_consistent' or not isinstance(phasor,(list,tuple)) or len(phasor)!=2 or centre is None:
            return None,role+': a supported source fit and explicit common source-time centre are required.'
        parts=[_real(v) for v in phasor]
        if any(v is None for v in parts):
            return None,role+': finite real and imaginary phasor components are required.'
        values[role]=complex(*parts)
        centres.append(centre)
    if max(centres)-min(centres)>max(1e-12,max(abs(c) for c in centres)*32*2.220446049250313e-16):
        return None,'Phasors do not share a corresponding source-time centre.'
    return values,''


def _sequence(channels,window,prefix):
    roles=[prefix+p for p in ('A','B','C')]
    phasors,reason=_phasors(channels,window,roles)
    if phasors is None:
        return _unavailable(reason,zero=None,positive=None,negative=None)
    values=[phasors[k] for k in roles]
    scale=max(max(abs(v.real),abs(v.imag)) for v in values)
    scale=scale or 1.
    va,vb,vc=[v/scale for v in values]
    a=complex(-.5,math.sqrt(3)/2)
    components=[(va+vb+vc)/3,(va+a*vb+a*a*vc)/3,(va+a*a*vb+a*vc)/3]
    components=[v*scale for v in components]
    if not all(_finite_complex(v) for v in components):
        return _unavailable('Sequence conversion exceeds representable numeric range.',zero=None,positive=None,negative=None)
    return dict(status='Conditional source quantity',zero=_pair(components[0]),positive=_pair(components[1]),
        negative=_pair(components[2]),units='V' if prefix=='V' else 'A',method='Fortescue ABC RMS phasor components',
        source_roles=roles,authorizes_location=False,
        basis='Corresponding declared/assumed source scaling and assigned phase meanings; wiring/physical sequence is unverified.')


def _loop(channels,window,name):
    x,y=name
    roles=['V'+x,'V'+y,'I'+x,'I'+y]
    phasors,reason=_phasors(channels,window,roles)
    if phasors is None:
        return _unavailable(reason,impedance_ohm=None)
    vx,vy,ix,iy=[phasors[k] for k in roles]
    vs=max(abs(vx.real),abs(vx.imag),abs(vy.real),abs(vy.imag))
    cs=max(abs(ix.real),abs(ix.imag),abs(iy.real),abs(iy.imag))
    if not vs or not cs:
        return _unavailable('Nonzero corresponding voltage and current loop excitation is required.',impedance_ohm=None)
    dv=vx/vs-vy/vs
    di=ix/cs-iy/cs
    if abs(di)<=CONDITION_FLOOR*max(abs(ix/cs),abs(iy/cs)):
        return _unavailable('Phase-current loop is cancelled or numerically ill-conditioned.',impedance_ohm=None)
    if abs(dv)<=CONDITION_FLOOR*max(abs(vx/vs),abs(vy/vs)):
        return _unavailable('Phase-voltage loop is cancelled or numerically ill-conditioned.',impedance_ohm=None)
    ratio=vs/cs
    if not math.isfinite(ratio) or ratio<TINY:
        return _unavailable('Voltage/current scale ratio exceeds representable numeric range.',impedance_ohm=None)
    relative=dv/di
    z=relative*ratio
    if not _finite_complex(z) or any(a!=0 and (b==0 or abs(b)<TINY) for a,b in ((relative.real,z.real),(relative.imag,z.imag))):
        return _unavailable('Loop impedance conversion overflows or underflows; no zero is substituted.',impedance_ohm=None)
    return dict(status='Conditional source quantity',impedance_ohm=_pair(z),units='ohm (conditional source scaling)',
        method='Phase-phase apparent impedance (Vx-Vy)/(Ix-Iy)',source_roles=roles,authorizes_location=False,
        basis='Assigned source phases and corresponding fits; this apparent impedance does not identify a fault or physical distance.')


def _line_sections(line):
    length=_real(line.get('length_km')) if isinstance(line,dict) else None
    if length is None or length<=0:
        return None,'Supply an explicit finite positive line length.'
    sections=line.get('sections') or [dict(from_km=0.,to_km=length,
        x1_ohm_per_km=line.get('x1_ohm_per_km'),r1_ohm_per_km=line.get('r1_ohm_per_km'))]
    if not isinstance(sections,list) or not 1<=len(sections)<=128:
        return None,'Supply one to128 explicit contiguous line sections.'
    parts=[]
    previous=0.
    total=0.
    for section in sections:
        if not isinstance(section,dict):
            return None,'Each supplied line section must contain explicit coordinates and reactance.'
        lo,hi,x,r=(_real(section.get(k)) for k in ('from_km','to_km','x1_ohm_per_km','r1_ohm_per_km'))
        if (lo is None or hi is None or x is None or x<=0 or hi<=lo
                or abs(lo-previous)>max(1e-8,length*1e-10)):
            return None,'Sections require contiguous increasing kilometre coordinates and positive known X1 in ohm/km.'
        amount=(hi-lo)*x
        updated=total+amount
        if not math.isfinite(updated) or amount<TINY or updated<=total:
            return None,'Section reactance accumulation exceeds representable numeric range.'
        parts.append(dict(lo=lo,hi=hi,x=x,r=r,x_before=total,x_after=updated))
        previous,total=hi,updated
    if abs(previous-length)>max(1e-8,length*1e-10):
        return None,'Supplied sections do not cover the supplied full line length.'
    return parts,''


def _projection(loops,line,name):
    empty=dict(distance_km=None,fraction=None,residual=None,eligible_overlay=False)
    if name not in ('AB','BC','CA'):
        return _unavailable('Choose an explicit phase-phase fault-loop assumption; ground loops require a separate compensation contract.',**empty)
    loop=loops[name]
    if loop['status']!='Conditional source quantity':
        return _unavailable('Selected loop is unavailable: '+loop['reason'],**empty)
    parts,reason=_line_sections(line)
    if parts is None:
        return _unavailable(reason,**empty)
    z=complex(*loop['impedance_ohm'])
    target=z.imag
    chosen=next((i for i,p in enumerate(parts) if target<=p['x_after']),len(parts)-1)
    part=parts[chosen]
    delta=target-part['x_before']
    step=delta/part['x']
    if delta!=0 and (step==0 or abs(step)<TINY):
        return _unavailable('Projection conversion underflows; no zero kilometre coordinate is substituted.',**empty)
    distance=part['lo']+step
    length=parts[-1]['hi']
    fraction=distance/length
    if (distance!=0 and (abs(distance)<TINY or fraction==0 or abs(fraction)<TINY)) or (step!=0 and distance==part['lo']):
        return _unavailable('Projection coordinate/fraction underflows or collapses; no terminal marker is substituted.',**empty)
    if not math.isfinite(distance) or not math.isfinite(fraction):
        return _unavailable('Model projection exceeds representable numeric range.',**empty)
    inside=0<=target<=parts[-1]['x_after']
    residual=None
    residual_reason='Supplied R1 is required for a complex model mismatch; no confidence is inferred.'
    if inside and all(p['r'] is not None for p in parts[:chosen+1]):
        predicted_r=sum((p['hi']-p['lo'])*p['r'] for p in parts[:chosen])+(distance-part['lo'])*part['r']
        if math.isfinite(predicted_r):
            scale=max(abs(z.real),abs(z.imag),abs(predicted_r),abs(target),TINY)
            actual=complex(z.real/scale,z.imag/scale)
            predicted=complex(predicted_r/scale,target/scale)
            magnitude=max(math.hypot(actual.real,actual.imag),math.hypot(predicted.real,predicted.imag),TINY)
            value=math.hypot(actual.real-predicted.real,actual.imag-predicted.imag)/magnitude
            if math.isfinite(value):
                residual=value
                residual_reason='Scaled complex line-impedance mismatch; not uncertainty or confidence.'
        else:
            residual_reason='Supplied resistance prediction exceeds numeric range; residual remains unavailable.'
    return dict(status='Conditional model projection' if inside else 'Outside supplied line',
        distance_km=distance,fraction=fraction,residual=residual,residual_reason=residual_reason,section_index=chosen if inside else None,
        eligible_overlay=inside,authorizes_location=False,method='Selected phase-loop reactance projection on supplied positive-X1 sections',
        reason='' if inside else 'Projection lies outside the supplied line; it is not clipped to a plausible location.',
        assumptions=['Selected phase-phase fault loop; corresponding stationary source fits and assigned V/A phases.',
            'Supplied line length/X1 model and declared or assumed CT/VT scaling; no field verification.',
            'Load, infeed, fault-resistance reactance bias, mutual coupling and recorder/alias errors are not bounded.'],
        basis='A conditional line-model projection, not a verified fault location. Outside-line distances extrapolate the boundary section only.',
        residual_basis='Complex line-impedance mismatch where supplied R1 is available; not uncertainty or confidence.',
        line_provenance=line.get('provenance','Explicit supplied model'))


def _numeric_quantity(operation,**empty):
    try:
        return operation()
    except ArithmeticError:
        return _unavailable('Numerical range exceeded for this quantity; no fabricated value is substituted.',**empty)


def compose_source_quantities(channels,windows,line_model=None,fault_loop=''):
    rows=[]
    for window in windows:
        loops={name:_numeric_quantity(lambda name=name,window=window:_loop(channels,window,name),impedance_ohm=None) for name in ('AB','BC','CA')}
        rows.append(dict(index=window['index'],support_s=window.get('support_s'),
            sequence={kind:_numeric_quantity(lambda prefix=prefix,window=window:_sequence(channels,window,prefix),zero=None,positive=None,negative=None) for kind,prefix in [('voltage','V'),('current','I')]},
            loops=loops,projection=_numeric_quantity(lambda loops=loops:_projection(loops,line_model,fault_loop),distance_km=None,fraction=None,residual=None,eligible_overlay=False)))
    return dict(windows=rows,authorizes_location=False,alignment_eligible=False,
        basis='Conditional export-coordinate quantities only; no physical event, clock, wiring, line or location authority.')
