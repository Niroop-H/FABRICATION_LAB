"""Durable session storage with capability authentication and optimistic writes."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class StoreError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status=status


class Store:
    def __init__(self):
        self.url=os.environ.get('DATABASE_URL','')
        self.path=os.environ.get('FAB_DB_PATH','.local-data/fab.sqlite3')

    @contextmanager
    def connect(self):
        if self.url:
            import psycopg
            connection=psycopg.connect(self.url,connect_timeout=8)
        else:
            if os.environ.get('VERCEL'):
                raise StoreError('Add DATABASE_URL for a persistent PostgreSQL database in Vercel, then redeploy. The calculator remains available at /calculator.')
            Path(self.path).parent.mkdir(parents=True,exist_ok=True)
            connection=sqlite3.connect(self.path,timeout=10)
        try:
            connection.execute('CREATE TABLE IF NOT EXISTS fab_sessions (id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL)')
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def sql(self, query):
        return query.replace('?', '%s') if self.url else query

    def create(self,state):
        sid=uuid.uuid4().hex; secret=secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute(self.sql('INSERT INTO fab_sessions VALUES (?, ?, ?, ?)'),
                (sid,hashlib.sha256(secret.encode()).hexdigest(),state['revision'],json.dumps(state,allow_nan=False)))
        return sid,secret

    def read(self,sid,secret):
        with self.connect() as db:
            row=db.execute(self.sql('SELECT secret_hash, state FROM fab_sessions WHERE id=?'),(sid,)).fetchone()
        if not row or not hmac.compare_digest(row[0],hashlib.sha256(secret.encode()).hexdigest()):
            raise StoreError('Session not found or access token invalid.',404)
        return json.loads(row[1])

    def save(self,sid,previous,state):
        with self.connect() as db:
            result=db.execute(self.sql('UPDATE fab_sessions SET revision=?, state=? WHERE id=? AND revision=?'),
                (state['revision'],json.dumps(state,allow_nan=False),sid,previous))
            if result.rowcount!=1:
                raise StoreError('Session changed in another tab. Refresh and retry.',409)
