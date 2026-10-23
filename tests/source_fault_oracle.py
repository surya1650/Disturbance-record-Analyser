"""Independent phase nodal network with explicit source/fault contact circuits.

No locator, registry or production synthetic-generator imports. Z2=Z1 on line
branches only; source phase matrices and EMFs can be asymmetric/unbalanced.
"""
import numpy as np

FAULTS = ('AG', 'BG', 'CG', 'AB', 'BC', 'CA', 'ABG', 'BCG', 'CAG', 'ABC', 'ABCG')
PROFILES = ('baseline', 'weak_S_100', 'weak_S_10000', 'weak_R_100', 'weak_R_10000',
            'voltage_angle', 'voltage_unbalance', 'phase_impedance')


def phase_impedance(z1, z0):
    matrix = np.full((3, 3), (z0-z1)/3, complex)
    np.fill_diagonal(matrix, (z0+2*z1)/3)
    return matrix


def sequence(phases, order):
    if order not in (0, 1, 2):
        raise ValueError('Sequence order must be 0, 1 or 2.')
    a = np.exp(2j*np.pi/3)
    return complex((phases[0]+a**order*phases[1]+a**(2*order)*phases[2])/3)


def source_pair(profile='baseline'):
    if profile not in PROFILES:
        raise ValueError('Unknown source profile.')
    positive = 220000/np.sqrt(3)*np.exp(1j*np.array([0, -2*np.pi/3, 2*np.pi/3]))
    sources = [dict(z=phase_impedance(3+12j, 6+21j), emf=positive.copy()),
               dict(z=phase_impedance(5+18j, 11+33j), emf=.99*positive*np.exp(-.1j))]
    if profile.startswith('weak_'):
        _, end, scale = profile.split('_')
        sources[0 if end == 'S' else 1]['z'] *= float(scale)
    elif profile == 'voltage_angle':
        sources[1]['emf'] = .85*positive*np.exp(-.35j)
    elif profile == 'voltage_unbalance':
        sources[0]['emf'] += .03*positive.conjugate()+.01*positive[0]
        sources[1]['emf'] += .05*positive.conjugate()*np.exp(.4j)
    elif profile == 'phase_impedance':
        for source, factors in zip(sources, ([1.2, .8, 1.1], [.65, 1, 1.4]), strict=True):
            d = np.diag(factors)
            source['z'] = d@source['z']@d
    return sources


def solve(sections, fault_km, fault='AG', resistance=4, *, sources=None, reverse_sources=False):
    """SLG R to earth; LL R phase-phase; DLG R/2 legs + earth R;
    ABC/ABCG three R legs to a floating/common-earth-R node. NONE is healthy.
    Source facts are supplied in physical forward orientation, reversed here.
    """
    if fault not in (*FAULTS, 'NONE') or not np.isfinite(resistance) or resistance <= 0:
        raise ValueError('Unknown fault connection or nonpositive/nonfinite contact resistance.')
    if not sections or not np.isfinite(fault_km):
        raise ValueError('Finite physical geometry is required.')
    for length, z1, z0 in sections:
        if (not np.all(np.isfinite([length, z1, z0])) or length <= 0 or
                min(z1.real, z0.real) < 0 or min(z1.imag, z0.imag) <= 0):
            raise ValueError('Finite passive invertible phase branches are required.')
    sources = source_pair() if sources is None else list(sources)
    if len(sources) != 2:
        raise ValueError('Two Thevenin sources required.')
    for source in sources:
        z, emf = source['z'], source['emf']
        if (np.shape(z) != (3, 3) or np.shape(emf) != (3,) or not np.all(np.isfinite(z)) or
                not np.all(np.isfinite(emf)) or not np.allclose(z, z.T) or
                min(np.linalg.eigvalsh(z.real)) <= 0 or min(np.linalg.eigvalsh(z.imag)) <= 0):
            raise ValueError('Finite reciprocal passive source matrix and phase EMF required.')
    if reverse_sources:
        sources.reverse()
    junctions = np.r_[0, np.cumsum([s[0] for s in sections])]
    if not 0 < fault_km < junctions[-1]:
        raise ValueError('Interior fault node required; terminal/bus faults need an explicit CT-zone model.')
    nodes = np.unique(np.r_[junctions, fault_km])
    n = len(nodes)
    phases = [i for i, p in enumerate('ABC') if p in fault] if fault != 'NONE' else []
    common = len(phases) > 2 or len(phases) == 2 and 'G' in fault
    size = 3*n+int(common)
    matrix, rhs = np.zeros((size, size), complex), np.zeros(size, complex)
    branches = []
    for j, (lo, hi) in enumerate(zip(nodes[:-1], nodes[1:], strict=True)):
        _, z1, z0 = sections[np.searchsorted(junctions, (lo+hi)/2)-1]
        y = np.linalg.inv(phase_impedance(z1, z0)*(hi-lo))
        a, b = slice(3*j, 3*j+3), slice(3*j+3, 3*j+6)
        matrix[a, a] += y
        matrix[b, b] += y
        matrix[a, b] -= y
        matrix[b, a] -= y
        branches.append(y)
    for block, source in zip((slice(0, 3), slice(3*n-3, 3*n)), sources, strict=True):
        y = np.linalg.inv(source['z'])
        matrix[block, block] += y
        rhs[block] += y@source['emf']
    fault_node = int(np.where(nodes == fault_km)[0][0])
    at = [3*fault_node+p for p in phases]
    if len(phases) == 1:
        matrix[at[0], at[0]] += 1/resistance
    elif len(phases) == 2 and not common:
        a, b = at
        matrix[a, a] += 1/resistance
        matrix[b, b] += 1/resistance
        matrix[a, b] -= 1/resistance
        matrix[b, a] -= 1/resistance
    elif common:
        contact = resistance/2 if len(phases) == 2 else resistance
        for a in at:
            matrix[a, a] += 1/contact
            matrix[-1, -1] += 1/contact
            matrix[a, -1] -= 1/contact
            matrix[-1, a] -= 1/contact
        if 'G' in fault:
            matrix[-1, -1] += 1/resistance
    solution = np.linalg.solve(matrix, rhs)
    residual = float(np.max(abs(matrix@solution-rhs)))
    if not np.all(np.isfinite(solution)) or residual >= 1e-6:
        raise ArithmeticError('Nodal network failed the absolute 1e-6 A KCL residual screen.')
    voltages = solution[:3*n].reshape(n, 3)
    currents = np.zeros(3, complex)
    vf = voltages[fault_node]
    q = complex(solution[-1]) if common else None
    if len(phases) == 1:
        currents[phases[0]] = vf[phases[0]]/resistance
    elif len(phases) == 2 and not common:
        a, b = phases
        currents[a] = (vf[a]-vf[b])/resistance
        currents[b] = -currents[a]
    elif common:
        currents[phases] = (vf[phases]-q)/(resistance/2 if len(phases) == 2 else resistance)
    return dict(VS=voltages[0], VR=voltages[-1], IS=branches[0]@(voltages[0]-voltages[1]),
                IR=branches[-1]@(voltages[-1]-voltages[-2]), nodes=nodes, voltages=voltages,
                branches=branches, fault_node=fault_node, fault_currents=currents,
                fault_bus_voltage=q, residual=residual)
