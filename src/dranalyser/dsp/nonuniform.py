"""Direct declared-time signal models; never acquisition or CT certification."""
import math

import numpy as np
from scipy.optimize import minimize_scalar


def withheld(reason):
    return dict(status='withheld',reason=reason,authorizes_location=False,
                alignment_eligible=False,authorizes_production_dsp=False)


def numeric(values):
    if np.ma.isMaskedArray(values) and np.any(np.ma.getmaskarray(values)):
        raise ValueError('Missing masked observations.')
    a=np.asarray(values)
    if any(isinstance(v,(bool,np.bool_)) for v in np.asarray(values,dtype=object).flat):
        raise ValueError('Boolean observations are not measured values.')
    if a.dtype.kind not in 'iuf' or not np.all(np.isfinite(a)):
        raise ValueError('Finite real numeric observations required.')
    if a.size and np.max(abs(a))>1e100:
        raise ValueError('Unsupported numeric range.')
    return a.astype(float)


def _prepare(t,y):
    t,y=numeric(t),numeric(y)
    if y.ndim==1:
        y=y[:,None]
    if t.ndim!=1 or y.ndim!=2 or y.shape[0]!=len(t) or not 24<=len(t)<=4096 or not 1<=y.shape[1]<=64:
        raise ValueError('Require24..4096 matching observations and1..64 channels.')
    dt=np.diff(t)
    if np.any(dt<=0) or not 1e-5<=t[-1]-t[0]<=1:
        raise ValueError('Unsupported or nonincreasing time support.')
    scale=np.max(abs(y),axis=0)
    if np.any((scale>0)&(scale<1e-100)):
        raise ValueError('Unsupported tiny signal scale.')
    scale=np.where(scale==0,1,scale)
    weights=np.r_[dt[0]/2,(dt[:-1]+dt[1:])/2,dt[-1]/2]
    weights=weights/np.sum(weights)
    return t,y/scale,scale,weights


def _solve(t,y,weights,f):
    if not isinstance(f,(float,int,np.floating)) or isinstance(f,(bool,np.bool_)) or not 20<=f<=100:
        raise ValueError('Frequency must be explicitly20..100Hz.')
    if np.max(np.diff(t))>1/(12*f):
        raise ValueError('Insufficient time-coordinate coverage; no alias guarantee is implied.')
    u=(t-t[0])-(t[-1]-t[0])/2
    phase=2*np.pi*f*u
    design=np.column_stack([np.ones(len(t)),2*u/(t[-1]-t[0]),
        *[v for h in (1,2,3) for v in (np.cos(h*phase),np.sin(h*phase))]])
    weighted=design*np.sqrt(weights[:,None])
    coefficients,_,rank,singular=np.linalg.lstsq(weighted,y*np.sqrt(weights[:,None]),rcond=None)
    condition=float(singular[0]/singular[-1]) if singular[-1]>0 else float('inf')
    if rank!=8 or not math.isfinite(condition) or condition>1e4:
        raise ValueError('Ill-conditioned direct-time basis.')
    errors=y-design@coefficients
    residual=np.sqrt(weights@(errors*errors))
    phasor=(coefficients[2]-1j*coefficients[3])/np.sqrt(2)
    return coefficients,phasor,residual,condition


def fit_source_window(t,y,frequency):
    """RMS coefficients at support centre; conditional on the exported coordinates."""
    try:
        t,values,scale,weights=_prepare(t,y)
        if values.shape[1]!=1:
            raise ValueError('Fit one measurement channel at a time.')
        coefficients,phasor,residual,condition=_solve(t,values,weights,frequency)
        raw_rms=float(np.sqrt(weights@(values[:,0]**2))*scale[0])
        amp=float(abs(phasor[0])*scale[0])
        relative=float(residual[0]/max(abs(phasor[0]),1e-100))
        if amp<=1e-6*max(raw_rms,1e-100):
            return withheld('Fundamental unobservable in this model.')
        if relative>.03:
            return withheld('Residual exceeds the stationary signal-model policy.')
        p=phasor[0]*scale[0]
        out=withheld('Conditional exported-signal model; no physical accuracy guarantee.')
        out.update(status='model_consistent',rms=amp,phasor=[float(p.real),float(p.imag)],
            relative_residual=relative,raw_rms=raw_rms,condition=condition,
            centre_s=float(t[0]+(t[-1]-t[0])/2),
            harmonic_rms=[float(np.hypot(coefficients[2*h,0],coefficients[2*h+1,0])*scale[0]/np.sqrt(2))
                          for h in (1,2,3)])
        if not all(math.isfinite(v) for v in [amp,relative,raw_rms,*out['phasor'],*out['harmonic_rms']]):
            return withheld('Unrepresentable fitted values.')
        return out
    except (ValueError,TypeError,OverflowError,np.linalg.LinAlgError):
        return withheld('Unsupported observations, coverage or numeric signal model.')


def source_frequency(t,values,nominal):
    """Profile a joint harmonic model; no fixed-rate crossing or nominal fallback."""
    try:
        if isinstance(nominal,(bool,np.bool_)) or not isinstance(nominal,(int,float)) or not 40<=nominal<=70:
            raise ValueError('Explicit nominal40..70Hz required.')
        t,y,_,weights=_prepare(t,values)
        y=y-np.sum(weights[:,None]*y,axis=0)
        energy=weights@(y*y)
        if np.any(energy<1e-12):
            raise ValueError('Uninformative frequency reference.')
        y=y/np.sqrt(energy)
        def loss(f):
            return float(np.mean(_solve(t,y,weights,f)[2]**2))
        grid=np.linspace(.9*nominal,1.1*nominal,41)
        scores=np.array([loss(f) for f in grid])
        best=int(np.argmin(scores))
        if best in (0,40):
            raise ValueError('Frequency at or beyond the search boundary.')
        minima=[i for i in range(1,40) if scores[i]<=scores[i-1] and scores[i]<=scores[i+1]]
        if any(abs(i-best)>2 and scores[i]<=scores[best]+max(1e-8,.05*scores[best]) for i in minima):
            raise ValueError('Ambiguous separated frequency minima.')
        result=minimize_scalar(loss,bounds=(grid[best-1],grid[best+1]),method='bounded',options={'xatol':1e-8})
        if not result.success or not math.isfinite(result.x):
            raise ValueError('Frequency search did not converge.')
        fundamental=_solve(t,y,weights,float(result.x))[1]
        if not np.any(abs(fundamental)>1e-6):
            raise ValueError('Fundamental is unobservable in the frequency references.')
        out=withheld('Fitted export-coordinate frequency; not a calibrated clock measurement.')
        out.update(status='estimated',frequency_hz=float(result.x),loss=float(result.fun),
                   search_hz=[float(grid[0]),float(grid[-1])])
        return out
    except (ValueError,TypeError,OverflowError,np.linalg.LinAlgError):
        return withheld('Frequency unobservable, outside supported domain or unsupported input.')
