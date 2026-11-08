"""Test integrated growth, quality holds and immutable session route versions."""
import copy
import unittest
from src.fab.engine import new_session, current_step, apply
from src.fab.deposition import growth_rate


def cmd(state,action,**kwargs):
    result,ok,message=apply(state,dict(action=action,**kwargs))
    if not ok:raise AssertionError(message)
    return result


def ready_gate():
    state=cmd(new_session(),'gown',checks=['apparel','gloves','carrier'])
    while current_step(state)['name']!='Gate electrode deposition':
        tool=current_step(state)['tool']
        for action in ('load','recipe','start','advance','unload'):
            state=cmd(state,action,tool=tool,carrier=state['carrier'],seconds=3600)
    return cmd(state,'load',tool='deposition',carrier=state['carrier'])


def film(state):
    return next(l for l in state['wafer']['layer_stack']['layers'] if l['layer_id']==current_step(state)['id'])['thickness']['value']


class TestIntegratedDeposition(unittest.TestCase):
    def test_time_step_partition_preserves_growth(self):
        state=cmd(cmd(ready_gate(),'recipe',tool='deposition'),'start',tool='deposition')
        one=cmd(state,'advance',tool='deposition',seconds=120)
        two=cmd(cmd(state,'advance',tool='deposition',seconds=60),'advance',tool='deposition',seconds=60)
        self.assertAlmostEqual(film(one),film(two),places=10)
        self.assertAlmostEqual(film(one),growth_rate(state['tools']['deposition']['recipe'])*2)
        self.assertEqual(one['tools']['deposition']['state'],'RUNNING')
        self.assertEqual(len(one['results']),len(state['results']))

    def test_under_deposition_is_held_and_has_only_one_film(self):
        state=ready_gate(); step=current_step(state)
        state=cmd(state,'recipe',tool='deposition',parameters={'duration_s':step['seconds']/2})
        state=cmd(state,'start',tool='deposition')
        state=cmd(state,'advance',tool='deposition',seconds=3600)
        self.assertEqual(state['tools']['deposition']['state'],'FAULT')
        self.assertIsNotNone(state['hold'])
        self.assertFalse(state['results'][-1]['pass'])
        self.assertAlmostEqual(film(state),75,places=3)
        self.assertEqual(sum(l['layer_id']==step['id'] for l in state['wafer']['layer_stack']['layers']),1)

    def test_abort_retains_partial_film(self):
        state=cmd(cmd(ready_gate(),'recipe',tool='deposition'),'start',tool='deposition')
        state=cmd(state,'advance',tool='deposition',seconds=60)
        thickness=film(state)
        state=cmd(state,'abort',tool='deposition')
        self.assertEqual(film(state),thickness)
        self.assertGreater(thickness,0)
        self.assertFalse(state['tools']['deposition']['outputs'])
        self.assertIsNotNone(state['hold'])

    def test_recipe_response_and_invalid_numbers(self):
        baseline={'temperature_c':650,'pressure_torr':.5,'flow_sccm':100}
        self.assertGreater(growth_rate({**baseline,'temperature_c':680}),growth_rate(baseline))
        self.assertGreater(growth_rate({**baseline,'flow_sccm':150}),growth_rate(baseline))
        state=ready_gate()
        for value in (float('nan'),float('inf'),True,0):
            result,ok,_=apply(state,dict(action='recipe',tool='deposition',parameters={'pressure_torr':value}))
            self.assertFalse(ok); self.assertEqual(result['wafer'],state['wafer'])

    def test_existing_session_keeps_legacy_recipe(self):
        legacy=copy.deepcopy(new_session()); legacy.pop('route'); legacy.pop('route_version')
        legacy['step']=2
        self.assertIn('thickness_nm',current_step(legacy)['params'])
        modern=new_session(); modern['step']=2
        self.assertIn('duration_s',current_step(modern)['params'])
        modern['route'][2]['params']['duration_s']['default']=123
        self.assertEqual(current_step(modern)['params']['duration_s']['default'],123)
