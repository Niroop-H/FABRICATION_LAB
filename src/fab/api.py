"""Browser API; all mutations are authenticated and version checked."""
from flask import Blueprint, request, jsonify
from src.fab.catalog import catalog
from src.fab.engine import new_session, apply, Rejected
from src.fab.store import Store, StoreError

fab=Blueprint('fab',__name__,url_prefix='/api/fab')

@fab.get('/catalog')
def get_catalog():
    return catalog()

@fab.post('/sessions')
def create_session():
    data=request.get_json()
    if not isinstance(data,dict): return {'error':'Provide a JSON object.'},400
    state=new_session(data.get('node','180'),data.get('mode','guided'))
    sid,secret=Store().create(state)
    return {'id':sid,'token':secret,'state':state},201

def load(sid):
    authorization=request.headers.get('Authorization','')
    if not authorization.startswith('Bearer '): raise StoreError('Session token required.',401)
    return Store().read(sid,authorization[7:])

@fab.get('/sessions/<sid>')
def get_session(sid):
    return {'state':load(sid)}

@fab.post('/sessions/<sid>/commands')
def command(sid):
    state=load(sid); data=request.get_json()
    if not isinstance(data,dict): return {'error':'Provide a command object.'},400
    if type(data.get('revision')) is not int or data['revision']!=state['revision']:
        raise StoreError('Session changed. Refresh before sending another command.',409)
    updated,ok,message=apply(state,data)
    Store().save(sid,state['revision'],updated)
    return jsonify(state=updated,ok=ok,message=message)

@fab.errorhandler(Rejected)
def rejected(error):
    return {'error':str(error)},400

@fab.errorhandler(StoreError)
def storage_error(error):
    return {'error':str(error)},error.status
