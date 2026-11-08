"""Connected route, safety, persistence and concurrency regression tests."""
import copy
import os
import tempfile
import unittest
from unittest.mock import patch
from app import app
from src.fab.engine import new_session, apply, current_step
from src.fab.catalog import PROFILES
from src.fab.store import Store, StoreError


def command(s,action,**kwargs):
    state,ok,message=apply(s,dict(action=action,**kwargs))
    if not ok: raise AssertionError(message)
    return state


def prepare(s):
    step=current_step(s); tool=step['tool']
    s=command(s,'load',tool=tool,carrier=s['carrier'])
    s=command(s,'recipe',tool=tool)
    return command(s,'start',tool=tool)


class TestFabEngine(unittest.TestCase):
    def test_all_routes_complete_and_keep_wafer_identity(self):
        for node in PROFILES:
            with self.subTest(node=node):
                s=new_session(node); identity=copy.deepcopy(s['wafer']['wafer_id'])
                s=command(s,'gown',checks=['apparel','gloves','carrier'])
                while current_step(s):
                    s=prepare(s); tool=current_step(s)['tool']
                    while s['tools'][tool]['state']=='RUNNING':
                        s=command(s,'advance',tool=tool,seconds=3600)
                    s=command(s,'unload',tool=tool)
                self.assertEqual(s['status'],'complete')
                self.assertEqual(s['wafer']['wafer_id'],identity)
                self.assertEqual(len(s['completed']),len(s['results']))
                self.assertTrue(all(r['pass'] for r in s['results']))

    def test_invalid_commands_do_not_change_wafer(self):
        s=new_session(); after,ok,_=apply(s,dict(action='load',tool='clean',carrier='SMIF'))
        self.assertFalse(ok); self.assertEqual(after['wafer'],s['wafer'])
        self.assertEqual(after['mistakes'],1)
        s=command(s,'gown',checks=['apparel','gloves','carrier'])
        for c in [dict(action='load',tool='etch',carrier='SMIF'),dict(action='load',tool='clean',carrier='FOUP')]:
            self.assertFalse(apply(s,c)[1])

    def test_fault_holds_wafer_and_acknowledgement_does_not_reset(self):
        s=prepare(command(new_session(),'gown',checks=['apparel','gloves','carrier']))
        s=command(s,'fault',utility='exhaust')
        self.assertFalse(s['tools']['clean']['outputs']); self.assertIsNotNone(s['hold'])
        s=command(s,'acknowledge',tool='clean')
        self.assertEqual(s['tools']['clean']['state'],'FAULT')
        self.assertFalse(apply(s,dict(action='reset',tool='clean'))[1])
        s=command(s,'restore',utility='exhaust'); s=command(s,'reset',tool='clean')
        self.assertFalse(apply(s,dict(action='start',tool='clean'))[1])
        s=command(s,'disposition',tool='clean',decision='scrap')
        self.assertEqual(s['status'],'scrapped')

    def test_out_of_spec_overlay_holds_route(self):
        s=command(new_session(),'gown',checks=['apparel','gloves','carrier'])
        while current_step(s)['tool']!='lithography':
            s=prepare(s); tool=current_step(s)['tool']
            while s['tools'][tool]['state']=='RUNNING':
                s=command(s,'advance',tool=tool,seconds=3600)
            s=command(s,'unload',tool=tool)
        s=command(s,'load',tool='lithography',carrier=s['carrier'])
        s=command(s,'recipe',tool='lithography',parameters={'overlay_nm':60})
        s=command(s,'start',tool='lithography'); s=command(s,'advance',tool='lithography',seconds=3600)
        self.assertIsNotNone(s['hold']); self.assertFalse(s['results'][-1]['pass'])
        self.assertFalse(apply(s,dict(action='unload',tool='lithography'))[1])


class TestFabStorage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'FAB_DB_PATH':self.temp.name+'/fab.db','DATABASE_URL':'','VERCEL':''})
        self.env.start(); self.client=app.test_client()
    def tearDown(self):
        self.env.stop(); self.temp.cleanup()
    def test_api_persistence_authentication_and_stale_version(self):
        r=self.client.post('/api/fab/sessions',json={'node':'65'}); self.assertEqual(r.status_code,201)
        data=r.json; path='/api/fab/sessions/'+data['id']; headers={'Authorization':'Bearer '+data['token']}
        self.assertEqual(self.client.get(path).status_code,401)
        self.assertEqual(self.client.get(path,headers={'Authorization':'Bearer wrong'}).status_code,404)
        command_data=dict(revision=0,action='gown',checks=['apparel','gloves','carrier'])
        self.assertEqual(self.client.post(path+'/commands',json=command_data,headers=headers).status_code,200)
        self.assertEqual(self.client.post(path+'/commands',json=command_data,headers=headers).status_code,409)
        self.assertTrue(Store().read(data['id'],data['token'])['gowned'])
    def test_authenticated_report_contains_evidence_without_secret(self):
        data=self.client.post('/api/fab/sessions',json={'mode':'assessment'}).json
        path='/api/fab/sessions/'+data['id']+'/report'
        self.assertEqual(self.client.get(path).status_code,401)
        response=self.client.get(path,headers={'Authorization':'Bearer '+data['token']})
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json['assessment']['certification'])
        self.assertNotIn(data['token'],response.get_data(as_text=True))
        self.assertEqual(len(self.client.get('/api/fab/handbook').json['modules']),12)

    def test_compare_and_swap_rejects_concurrent_write(self):
        store=Store(); state=new_session(); sid,token=store.create(state)
        changed=command(state,'gown',checks=['apparel','gloves','carrier']); store.save(sid,0,changed)
        with self.assertRaises(StoreError): store.save(sid,0,changed)
    def test_vercel_requires_durable_storage(self):
        with patch.dict(os.environ,{'VERCEL':'1'}):
            self.assertEqual(self.client.post('/api/fab/sessions',json={}).status_code,503)


class TestTraining(unittest.TestCase):
    def test_first_answer_is_retained(self):
        from src.fab.training import assessment, handbook
        s=command(new_session(mode='assessment'),'answer',question='alarm',choice=0)
        self.assertFalse(apply(s,dict(action='answer',question='alarm',choice=1))[1])
        report=assessment(s)
        self.assertEqual(report['knowledge_correct'],0)
        self.assertFalse(report['certification'])
        self.assertNotIn('answer',handbook()['questions'][0])

    def test_all_correct_is_not_route_completion(self):
        from src.fab.training import assessment, QUESTIONS
        s=new_session(mode='assessment')
        for q in QUESTIONS:
            s=command(s,'answer',question=q['id'],choice=q['answer'])
        report=assessment(s)
        self.assertEqual(report['knowledge_correct'],3)
        self.assertFalse(report['route_complete'])

    def test_invalid_types_are_rejected(self):
        from src.fab.engine import Rejected
        with self.assertRaises(Rejected):new_session(node=[])
        for c in ({'action':'load','tool':[]},{'action':'fault','utility':{}}):
            self.assertFalse(apply(new_session(),c)[1])
