"""Versioned teaching routes, not foundry recipes or qualified process flows."""
from copy import deepcopy

TOOLS = {
 'clean': ('Wet preparation', 'WET-01', -9, 6),
 'oxidation': ('Thermal oxidation', 'FURN-01', -9, 0),
 'deposition': ('Thin-film deposition', 'CVD-01', -9, -6),
 'lithography': ('Lithography', 'LITH-01', 0, -9),
 'etch': ('Plasma etch', 'ETCH-01', 9, -6),
 'implant': ('Ion implantation', 'IMP-01', 9, 0),
 'anneal': ('Rapid thermal anneal', 'RTA-01', 9, 6),
 'cmp': ('Planarization', 'CMP-01', 0, 7),
 'metrology': ('Metrology & inspection', 'MET-01', -5, -10),
 'stock': ('Carrier stocker', 'STOCK-01', -5, 10),
 'facilities': ('Subfab utilities', 'UTIL-01', 5, 10),
 'gown': ('Gowning & entry', 'ENTRY-01', 0, 12),
}
PROFILES = {
 '180': dict(name='180 nm planar', diameter=200, carrier='SMIF', substrate='Bulk silicon', lithography='KrF 248 nm', metal='Al', cd_nm=180, overlay_nm=35, gate_nm=150, oxide_temp=900),
 '130': dict(name='130 nm planar', diameter=200, carrier='SMIF', substrate='Bulk silicon', lithography='KrF 248 nm', metal='Cu', cd_nm=130, overlay_nm=25, gate_nm=120, oxide_temp=875),
 '65': dict(name='65 nm planar', diameter=300, carrier='FOUP', substrate='Bulk silicon', lithography='ArF dry 193 nm', metal='Cu', cd_nm=65, overlay_nm=12, gate_nm=80, oxide_temp=850),
 '22fdsoi': dict(name='22 nm FD-SOI', diameter=300, carrier='FOUP', substrate='FD-SOI: 6 nm body / 20 nm BOX (illustrative)', lithography='ArF immersion 193 nm / split pattern', metal='Cu', cd_nm=22, overlay_nm=5, gate_nm=50, oxide_temp=825),
}

def param(label, unit, value, low, high):
    return dict(label=label, unit=unit, default=value, min=low, max=high,
                provenance='Teaching envelope v1; not OEM-qualified', calibration='unvalidated')


def route(node, version='training-v2'):
    p = PROFILES[node]
    steps = []
    def add(kind, name, seconds=60, params=None, model='procedure'):
        steps.append(dict(id=f'{node}-{len(steps)+1:02}', tool=kind, name=name,
                          seconds=seconds, params=params or {}, model=model))
    add('clean', 'Incoming inspection & surface clean', 120)
    if node == '22fdsoi':
        add('metrology', 'Verify SOI body and buried oxide', model='substrate inspection')
        add('deposition', 'Representative high-k gate dielectric', 60,
            {'thickness_nm':param('Dielectric target','nm',2,1,4)}, 'target-controlled film')
    else:
        add('oxidation', 'Representative gate dielectric growth', 600,
            {'temperature_c':param('Temperature','°C',p['oxide_temp'],800,1100),
             'duration_s':param('Duration','s',600,60,1800)}, 'Deal–Grove')
    add('deposition', 'Gate electrode deposition', 120,
        {'thickness_nm':param('Film target','nm',p['gate_nm'],p['gate_nm']*.8,p['gate_nm']*1.2)}, 'target-controlled film')
    if version == 'training-v2' and node != '22fdsoi':
        from src.fab.deposition import growth_rate
        nominal = {'temperature_c':650, 'pressure_torr':0.5, 'flow_sccm':100}
        seconds = round(p['gate_nm'] / growth_rate(nominal) * 60, 2)
        steps[-1].update(seconds=seconds, model='time-integrated LPCVD',
            target_nm=p['gate_nm'], tolerance_pct=10,
            params={
                'temperature_c':param('Temperature','°C',650,600,720),
                'pressure_torr':param('Chamber pressure','Torr',0.5,0.1,1.0),
                'flow_sccm':param('Precursor flow','sccm',100,50,200),
                'duration_s':param('Duration','s',seconds,60,7200),
            })
    add('lithography', 'Coat, align, expose & develop', 90,
        {'overlay_nm':param('Overlay offset','nm',0,-p['overlay_nm']*2,p['overlay_nm']*2)}, 'overlay teaching model')
    if node == '22fdsoi':
        add('lithography', 'Second pattern alignment demonstration', 90,
            {'overlay_nm':param('Overlay offset','nm',0,-10,10)}, 'split-pattern teaching model')
    add('etch', 'Pattern transfer into gate electrode', 60,
        {'source_w':param('Source RF','W',800,400,1200),
         'bias_w':param('Bias RF','W',100,50,200)}, 'existing plasma model')
    add('clean', 'Resist strip & post-etch clean', 90)
    if node != '22fdsoi':
        add('implant', 'Representative source/drain implant', 90,
            {'energy_kev':param('Ion energy','keV',30 if node=='180' else 15,5,80)}, 'existing range model')
    else:
        add('deposition', 'Raised source/drain concept demonstration', 90,
            {'thickness_nm':param('Epitaxial region target','nm',15,10,20)}, 'regional bookkeeping; not epitaxy physics')
    add('anneal', 'Thermal activation / recovery checkpoint', 30)
    add('deposition', 'Interlayer dielectric deposition', 120,
        {'thickness_nm':param('Dielectric target','nm',400,300,500)}, 'target-controlled film')
    add('cmp', 'Dielectric planarization', 90,
        {'removal_nm':param('Removal target','nm',100,50,150)}, 'thickness bookkeeping')
    if node != '180':
        add('lithography', 'Damascene interconnect pattern', 90,
            {'overlay_nm':param('Overlay offset','nm',0,-p['overlay_nm']*2,p['overlay_nm']*2)}, 'overlay teaching model')
        add('etch', 'Dielectric trench pattern transfer', 60,
            {'source_w':param('Source RF','W',800,400,1200),
             'bias_w':param('Bias RF','W',100,50,200)}, 'existing plasma model')
    add('deposition', f"{p['metal']} interconnect deposition", 120,
        {'thickness_nm':param('Metal target','nm',300,200,400)}, 'target-controlled film')
    if node != '180':
        add('cmp', 'Cu overburden polish', 90,
            {'removal_nm':param('Removal target','nm',100,50,150)}, 'thickness bookkeeping')
    add('metrology', 'Final thickness, CD & defect inspection', 60, model='deterministic teaching measurement')
    return steps


def catalog():
    return {'version':'training-v2', 'profiles':deepcopy(PROFILES),
            'tools':{k:dict(name=v[0],id=v[1],x=v[2],z=v[3]) for k,v in TOOLS.items()},
            'routes':{k:route(k) for k in PROFILES},
            'legacy_routes':{k:route(k,'training-v1') for k in PROFILES},
            'limitations':'Condensed teaching routes; no foundry qualification, real equipment control, or certification.'}
