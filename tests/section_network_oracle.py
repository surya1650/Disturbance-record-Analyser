"""Independent phase nodal admittance network, with explicit section junctions.

Each line branch is stamped into a nodal matrix; fault node is inserted at its
physical chainage. No locator, registry, or synthetic generator is imported.
Optional pi shunts support omitted-physics counterexamples, not distributed EMT.
"""
import numpy as np


def impedance(z1, z0):
    matrix = np.full((3,3), (z0-z1)/3, complex)
    np.fill_diagonal(matrix, (z0+2*z1)/3)
    return matrix


def solve(sections, fault_km, phase=0, resistance=4.0, charging=0.0, reverse_sources=False):
    """sections = (length km, Z1/km, Z0/km); charging is shunt S/km/phase."""
    junctions=np.r_[0,np.cumsum([s[0] for s in sections])]
    nodes=np.unique(np.r_[junctions,fault_km])
    assert 0 <= fault_km <= junctions[-1]
    n=len(nodes)
    matrix=np.zeros((3*n,3*n),complex)
    rhs=np.zeros(3*n,complex)
    branches=[]
    for j,(lo,hi) in enumerate(zip(nodes[:-1],nodes[1:],strict=True)):
        sec=sections[np.searchsorted(junctions,(lo+hi)/2)-1]
        z=impedance(sec[1],sec[2])*(hi-lo)
        y=np.linalg.inv(z)
        shunt=np.eye(3)*.5j*charging*(hi-lo)
        a,b=slice(3*j,3*j+3),slice(3*j+3,3*j+6)
        matrix[a,a]+=y+shunt
        matrix[b,b]+=y+shunt
        matrix[a,b]-=y
        matrix[b,a]-=y
        branches.append((y,shunt))
    sources=[impedance(3+12j,6+21j),impedance(5+18j,11+33j)]
    emf=220000/np.sqrt(3)*np.exp(1j*np.array([0,-2*np.pi/3,2*np.pi/3]))
    emfs=[emf,.99*emf*np.exp(-.1j)]
    if reverse_sources:
        sources.reverse()
        emfs.reverse()
    for block,z,e in [(slice(0,3),sources[0],emfs[0]),(slice(-3,None),sources[1],emfs[1])]:
        y=np.linalg.inv(z)
        matrix[block,block]+=y
        rhs[block]+=y@e
    fault_node=int(np.where(nodes==fault_km)[0][0])
    matrix[3*fault_node+phase,3*fault_node+phase]+=1/resistance
    voltages=np.linalg.solve(matrix,rhs).reshape(n,3)
    residual=float(np.max(abs(matrix@voltages.ravel()-rhs)))
    assert residual < 1e-6
    ys,bs=branches[0]
    yr,br=branches[-1]
    return dict(VS=voltages[0],VR=voltages[-1],IS=ys@(voltages[0]-voltages[1])+bs@voltages[0],
                IR=yr@(voltages[-1]-voltages[-2])+br@voltages[-1],nodes=nodes,
                voltages=voltages,branches=branches,fault_node=fault_node,residual=residual)


def negative(value):
    a=np.exp(2j*np.pi/3)
    return (value[0]+a*a*value[1]+a*value[2])/3
