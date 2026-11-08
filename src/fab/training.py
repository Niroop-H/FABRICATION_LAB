"""Evidence-based training review, never real-equipment certification."""
from src.fab.catalog import route
from src.fab.manuals import manuals, references

QUESTIONS = [
    {'id':'alarm', 'prompt':'Does acknowledging an alarm restore the equipment?',
     'options':['Yes, acknowledgement clears the cause','No, the cause must be corrected and reset permitted'],
     'answer':1, 'explanation':'Acknowledgement records awareness. Utility restoration and a permitted reset are separate actions.'},
    {'id':'carrier', 'prompt':'Which carrier belongs to this session?',
     'options':['SMIF for the 200 mm reference; FOUP for the 300 mm reference','Every carrier can be loaded into every tool'],
     'answer':0, 'explanation':'The selected reference profile fixes wafer diameter and carrier compatibility.'},
    {'id':'hold', 'prompt':'What happens to an interrupted wafer after tool reset?',
     'options':['It automatically returns to the route','It stays on hold until disposition'],
     'answer':1, 'explanation':'Tool recovery does not establish wafer quality. The teaching release supports scrap disposition.'},
]


def handbook():
    modules={
        'gown':('Entry protocol','Verify simulated apparel, gloves and carrier before accessing process controls.'),
        'stock':('Wafer handling','Confirm the laser mark, diameter and carrier. A wafer is either at the stocker or one tool; never both.'),
        'clean':('Wet preparation','Surface preparation removes contamination. This module records a procedural clean; no chemical mixing or wet kinetics are modeled.'),
        'oxidation':('Thermal growth','The existing Deal–Grove engine predicts silicon dioxide growth. Thin-oxide corrections are disabled. Real ultrathin gate dielectrics need validated models.'),
        'deposition':('Thin films','New bulk-planar gate recipes integrate the existing LPCVD growth model over time. Other depositions remain target bookkeeping. Gas consumption, stress and physical uncertainties are not validated.'),
        'lithography':('Patterning','Review the profile-specific scanner choice and overlay window. Overlay excursions hold the wafer. Resist chemistry and optical imaging are not simulated.'),
        'etch':('Pattern transfer','The existing plasma model estimates rate and anisotropy. An endpoint bookkeeping step marks the protected film patterned; full 3D etch evolution is not simulated.'),
        'implant':('Doping','Projected range and straggle are estimated by the existing range table. The route does not calculate complete transistor doping or electrical characteristics.'),
        'anneal':('Activation checkpoint','This is a procedural checkpoint. The connected route does not apply diffusion, thermal budget or activation physics.'),
        'cmp':('Planarization','The requested removal is subtracted from the film stack. Slurry selectivity, dishing and erosion are not modeled.'),
        'metrology':('Inspection','Inspect model-derived film thickness, particles and SOI dimensions. These are deterministic simulated values, not an independent measurement or calibration.'),
        'facilities':('Utilities and recovery','Inject utility loss only in the simulator. Outputs are inhibited and running wafers held. Restore the utility, acknowledge, reset and disposition. Actual equipment-specific emergency behavior requires expert review.'),
    }
    return {'manuals':manuals(), 'references':references(), 'version':'training-v2','modules':{k:{'title':v[0],'principle':v[1]} for k,v in modules.items()},
            'sequence':['Verify entry and wafer identity','Load the released tool','Review parameters and select recipe','Check interlocks and start','Advance simulated time; inspect results','Unload to release the next route step'],
            'questions':[{k:v for k,v in q.items() if k not in ('answer','explanation')} for q in QUESTIONS],
            'limitations':'Demonstrates simulator procedure only. No OEM approval, industrial compliance, or real-equipment authorization.'}


def assessment(state):
    audit=state['audit']; completed=len(state['completed']); total=len(state.get('route') or route(state['node'],'training-v1'))
    failed=[e for e in audit if not e['ok']]
    answers=state.get('answers',{})
    correct=sum(a['correct'] for a in answers.values())
    had_fault=any(e['ok'] and e['action'] in ('fault','emergency','abort') for e in audit)
    disposed=any(e['ok'] and e['action']=='disposition' for e in audit)
    criteria=[
        {'name':'Entry checks','status':'demonstrated' if state['gowned'] else 'pending'},
        {'name':'Route completion','status':'demonstrated' if state['status']=='complete' else 'incomplete','evidence':f'{completed}/{total} steps'},
        {'name':'Command sequencing','status':'review required' if failed else 'no violations observed','evidence':f'{len(failed)} rejected commands'},
        {'name':'Knowledge checks','status':'demonstrated' if correct==len(QUESTIONS) else 'pending' if not answers else 'review required','evidence':f'{correct}/{len(QUESTIONS)} correct on first submission'},
        {'name':'Fault disposition','status':'demonstrated' if disposed else 'pending' if had_fault else 'not exercised'},
    ]
    return {'criteria':criteria, 'mode':state['mode'], 'route_complete':state['status']=='complete',
            'knowledge_correct':correct,'knowledge_total':len(QUESTIONS),
            'rejected_actions':len(failed),'certification':False,
            'conclusion':'Instructor review required. This report is evidence of simulator activity, not certification.'}
