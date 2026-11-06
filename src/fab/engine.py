"""Deterministic command reducer. Rendering never owns wafer or equipment state."""
import copy
import math
import uuid

from src.fab.catalog import PROFILES, TOOLS, route
from src.simulation.core.wafer import Wafer, WaferID, WaferSubstrate, Layer, ProcessStepRecord
from src.simulation.core.units import wafer_diameter, film_thickness
from src.simulation.process.thermal_oxidation import ThermalOxidationModel
from src.simulation.process.etch_models import PlasmaEtchModel, SubstrateMaterial, EtchGasChemistry
from src.simulation.process.implant_models import IonImplantModel, ImplantSpecies


class Rejected(ValueError):
    """An operation was rejected without changing physical state."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


def new_session(node='180', mode='guided'):
    require(node in PROFILES, 'Unknown technology profile.')
    require(mode in ('guided','independent','assessment'), 'Unknown training mode.')
    lot = 'LOT-' + uuid.uuid4().hex[:8].upper()
    if node == '22fdsoi':
        wafer = Wafer.create_22nm_fdsoi_wafer(lot, 1)
    else:
        wafer = Wafer(WaferID(lot, 1, lot+'-01'), WaferSubstrate(diameter=wafer_diameter(PROFILES[node]['diameter'])))
    wafer.state.particle_count = 12
    return dict(schema=1, node=node, mode=mode, revision=0, clock=0, step=0,
                gowned=False, wafer=wafer.to_dict(), carrier=PROFILES[node]['carrier'],
                location='stock', status='active', tools={k:dict(state='IDLE', recipe=None,
                remaining=0, alarm=None, acknowledged=False, outputs=False) for k in TOOLS},
                utilities={'exhaust':True,'cooling':True,'vacuum':True}, audit=[], results=[],
                mistakes=0, completed=[], hold=None, contamination=12)


def current_step(state):
    steps = route(state['node'])
    return steps[state['step']] if state['step'] < len(steps) else None


def record(state, action, ok, message):
    state['audit'].append(dict(sequence=len(state['audit'])+1, time_s=state['clock'],
                               action=action, ok=ok, message=message))
    # Bounded sessions keep DB/response growth under control; no silent audit truncation.


def apply(state, command):
    require(isinstance(command, dict), 'Command must be an object.')
    require(len(state['audit']) < 2000, 'Session action limit reached; export and start a new session.')
    result = copy.deepcopy(state)
    action = command.get('action', '')
    require(isinstance(action,str), 'Action must be text.')
    try:
        message = operate(result, command)
        record(result, action, True, message)
        ok = True
    except Rejected as exc:
        result = copy.deepcopy(state)
        result['mistakes'] += 1
        message = str(exc)
        record(result, action, False, message)
        ok = False
    result['revision'] += 1
    return result, ok, message


def operate(s, c):
    action, tool = c.get('action'), c.get('tool')
    if action == 'gown':
        require(not s['gowned'], 'Entry checks already complete.')
        require(c.get('checks') == ['apparel','gloves','carrier'], 'Confirm apparel, gloves and carrier checks in order.')
        s['gowned'] = True
        return 'Entry checks recorded. Cleanroom access enabled.'
    if action in ('fault','restore'):
        utility = c.get('utility')
        require(utility in s['utilities'], 'Unknown facility utility.')
        s['utilities'][utility] = action == 'restore'
        if action == 'fault':
            for name,t in s['tools'].items():
                if t['state'] == 'RUNNING':
                    t.update(state='FAULT', outputs=False, alarm=f'{utility} lost', acknowledged=False)
                    s['hold'] = 'Interrupted process: wafer held for disposition.'
        return f'{utility}: '+('available; acknowledge and reset affected tools' if action=='restore' else 'lost; active tool outputs inhibited')
    require(tool in s['tools'], 'Select a known machine.')
    t = s['tools'][tool]
    step = current_step(s)
    if action == 'acknowledge':
        require(t['alarm'] is not None, 'No alarm to acknowledge.')
        t['acknowledged'] = True
        return 'Alarm acknowledged. The fault is still active until reset.'
    if action == 'reset':
        require(t['state']=='FAULT' and t['acknowledged'], 'Acknowledge the alarm before reset.')
        require(all(s['utilities'].values()), 'Restore all required utilities before reset.')
        t.update(state='LOADED' if s['location']==tool else 'IDLE', alarm=None, outputs=False, recipe=None, remaining=0)
        return 'Tool reset. Interrupted wafer remains on hold; use disposition before processing.'
    if action in ('emergency','abort'):
        require(t['state'] in ('RUNNING','LOADED','COMPLETE'), 'No active or loaded operation to stop.')
        t.update(state='FAULT', alarm='Emergency stop' if action=='emergency' else 'Operator abort', acknowledged=False, outputs=False)
        s['hold'] = 'Interrupted process: wafer held for disposition.'
        return 'Energy and gas commands inhibited in this representative model. Restore, acknowledge, reset, then disposition the wafer.'
    if action == 'disposition':
        require(s['hold'] is not None, 'Wafer is not on hold.')
        require(t['state']=='LOADED' and s['location']==tool and all(s['utilities'].values()), 'Reset the loaded tool and restore utilities first.')
        require(c.get('decision')=='scrap', 'Interrupted/failed wafers may only be scrapped in this teaching release.')
        wafer = Wafer.from_dict(s['wafer']); wafer.mark_scrapped(s['hold']); s['wafer']=wafer.to_dict()
        s['status']='scrapped'; s['location']='stock'; t.update(state='IDLE', recipe=None, outputs=False)
        return 'Wafer scrapped; history retained. Start a new lot to repeat training.'
    require(s['status']=='active' and step is not None, 'This lot is no longer active.')
    require(s['gowned'], 'Complete gowning and entry checks first.')
    require(s['hold'] is None, 'Wafer is on hold. Review and disposition before continuing.')
    require(tool==step['tool'], 'Route mismatch: next operation is '+step['name']+'.')
    if action == 'load':
        require(s['location']=='stock' and t['state']=='IDLE', 'Wafer must be at the stocker and tool idle.')
        require(c.get('carrier')==s['carrier'], 'Carrier incompatible with this reference fab.')
        s['location']=tool; t['state']='LOADED'
        return f"{s['wafer']['wafer_id']['laser_mark']} loaded into {TOOLS[tool][1]}."
    if action == 'recipe':
        require(t['state']=='LOADED', 'Load the wafer before selecting a recipe.')
        values = c.get('parameters', {})
        require(isinstance(values,dict) and not (set(values)-set(step['params'])), 'Unknown recipe parameter.')
        checked = {}
        for name,p in step['params'].items():
            value = values.get(name,p['default'])
            require(type(value) in (int,float) and math.isfinite(value) and p['min']<=value<=p['max'], f"{p['label']} must be {p['min']}–{p['max']} {p['unit']}.")
            checked[name]=value
        t['recipe']=checked
        return 'Recipe selected and teaching-envelope limits checked.'
    if action == 'start':
        require(t['state']=='LOADED' and t['recipe'] is not None, 'Load a wafer and select the route recipe first.')
        require(all(s['utilities'].values()), 'Interlock: exhaust, cooling and vacuum must be available.')
        t.update(state='RUNNING', remaining=t['recipe'].get('duration_s',step['seconds']), outputs=True, started=s['clock'])
        return 'Process started. Wafer movement is locked until completion.'
    if action == 'advance':
        require(t['state']=='RUNNING', 'Tool is not processing.')
        seconds=c.get('seconds',30)
        require(type(seconds) in (int,float) and math.isfinite(seconds) and 0<seconds<=3600, 'Advance must be 1–3600 simulated seconds.')
        elapsed=min(seconds,t['remaining']); s['clock']+=elapsed; t['remaining']-=elapsed
        if t['remaining']==0:
            output = process(s,step,t['recipe'])
            output.update(step_id=step['id'], name=step['name'], time_s=s['clock'])
            s['results'].append(output)
            t.update(state='COMPLETE', outputs=False)
            if not output['pass']:
                s['hold']='Quality excursion: '+output['summary']; t.update(state='FAULT',alarm=s['hold'],acknowledged=False)
            return output['summary']
        return f"{t['remaining']:.0f} simulated seconds remain."
    if action == 'unload':
        require(t['state']=='COMPLETE', 'Complete processing before unloading.')
        s['completed'].append(step['id']); s['step']+=1; s['location']='stock'
        t.update(state='IDLE',recipe=None,remaining=0,outputs=False)
        if current_step(s) is None: s['status']='complete'
        return 'Carrier returned to stocker. '+('Training route complete.' if s['status']=='complete' else 'Next route step released.')
    raise Rejected('Unknown command.')


def process(s, step, params):
    wafer = Wafer.from_dict(s['wafer'])
    kind, name = step['tool'], step['name']
    profile = PROFILES[s['node']]
    output = dict(model=step['model'], provenance='Repository teaching model v1; unvalidated',
                  uncertainty='Not characterized unless explicitly supplied', measurements={}, **{'pass':True})
    def measure(key,value,unit):
        output['measurements'][key]={'value':round(value,5),'unit':unit}
    def film(material, thickness):
        wafer.layer_stack.add_layer(Layer(step['id'],name,material,film_thickness(thickness,'nm'),deposition_method=kind,process_step_id=step['id']))
    if kind=='clean':
        wafer.state.particle_count=0; s['contamination']=0
        measure('particles',0,'count')
    elif kind=='oxidation':
        r=ThermalOxidationModel().simulate_oxidation(params['temperature_c'],params['duration_s'],initial_thickness_nm=0,enable_thin_oxide_enhancement=False)
        film('SiO2',r.final_thickness.value)
        measure('oxide',r.final_thickness.value,'nm'); measure('uncertainty',r.final_thickness.uncertainty,'nm')
    elif kind=='deposition':
        material = 'HfO2' if 'high-k' in name else ('SiO2' if 'dielectric' in name else (profile['metal'] if 'interconnect' in name else 'Si'))
        if 'source/drain' in name:
            measure('raised_region_height',params['thickness_nm'],'nm')
        else:
            film(material,params['thickness_nm']); measure('film',params['thickness_nm'],'nm')
    elif kind=='lithography':
        offset=abs(params['overlay_nm']); measure('overlay',offset,'nm')
        measure('overlay_limit',profile['overlay_nm'],'nm'); measure('nominal_cd',profile['cd_nm'],'nm')
        output['pass']=offset<=profile['overlay_nm']
        s['pattern']={'cd_nm':profile['cd_nm'],'overlay_nm':offset}
    elif kind=='etch':
        top=wafer.layer_stack.get_top_layer()
        require(top is not None and s.get('pattern'), 'A deposited film and developed pattern are required.')
        model=PlasmaEtchModel()
        dielectric=top.material=='SiO2'
        plasma=model.compute_plasma_state(params['source_w'],params['bias_w'],15,
            EtchGasChemistry.CHF3_CF4 if dielectric else EtchGasChemistry.HBR_CL2_O2,100)
        result=model.simulate_profile(SubstrateMaterial.SILICON_DIOXIDE if dielectric else SubstrateMaterial.POLYSILICON,
                                       plasma,top.thickness.value,profile['cd_nm'])
        # Patterned field clears to an endpoint; protected feature height is retained.
        top.is_patterned=True
        measure('vertical_rate',result.vertical_etch_rate.value,'nm/min')
        measure('anisotropy',result.anisotropy,'ratio'); measure('feature_height',top.thickness.value,'nm')
        output['model']='Existing plasma rate estimate; endpoint depth bookkeeping (not timed etch integration)'
        s.pop('pattern',None)
    elif kind=='implant':
        stats=IonImplantModel().get_range_statistics(ImplantSpecies.ARSENIC,params['energy_kev'])
        measure('projected_range',stats.rp_nm,'nm'); measure('straggle',stats.delta_rp_nm,'nm')
    elif kind=='cmp':
        top=wafer.layer_stack.get_top_layer(); require(top is not None,'No film to planarize.')
        removed=min(params['removal_nm'],top.thickness.value)
        wafer.layer_stack.etch_top_layer(film_thickness(removed,'nm'))
        measure('removed',removed,'nm')
    elif kind=='metrology':
        measure('total_film',sum(l.thickness.value for l in wafer.layer_stack.layers),'nm')
        measure('particles',wafer.state.particle_count,'count')
        if wafer.substrate.is_soi:
            measure('body',wafer.substrate.device_layer_thickness.value,'nm')
            measure('BOX',wafer.substrate.box_thickness.value,'nm')
    elif kind=='anneal':
        output['model']='Procedure checkpoint only; no activation physics applied'
    output['summary']=('PASS: ' if output['pass'] else 'HOLD: ')+name
    wafer.history.record_step(ProcessStepRecord(s['step']+1,step['id'],TOOLS[kind][1],step['id']+'-R1',
        s['tools'][kind]['started'],s['clock'],'SUCCESS' if output['pass'] else 'EXCURSION',operator_notes=output['model']))
    s['wafer']=wafer.to_dict()
    return output
