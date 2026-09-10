"""Transactional local job repository. Workers may share one local database."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflict(ValueError):
    """A request conflicts with the current incident revision."""


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "application.db"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL REFERENCES incidents(id),
                    number INTEGER NOT NULL, fingerprint TEXT UNIQUE NOT NULL,
                    state TEXT NOT NULL, stage TEXT NOT NULL, metadata TEXT NOT NULL,
                    files TEXT NOT NULL, bundle TEXT, result TEXT, error TEXT NOT NULL DEFAULT '',
                    owner TEXT, lease REAL, attempts INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    UNIQUE(incident_id, number));
                CREATE INDEX IF NOT EXISTS revision_queue ON revisions(state, lease, id);
                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY, incident_id TEXT, revision INTEGER,
                    at REAL NOT NULL, message TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts (
                    path TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, state TEXT NOT NULL,
                    message TEXT NOT NULL, updated REAL NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(row)
        for key in ("metadata", "files", "bundle", "result"):
            if key in result and result[key] is not None:
                result[key] = json.loads(result[key])
        return result

    def get(self, incident_id: str, number: int | None = None):
        with self.connect() as db:
            sql = """SELECT r.*, i.name, i.source FROM revisions r
                     JOIN incidents i ON i.id=r.incident_id WHERE i.id=?"""
            params = [incident_id]
            if number is not None:
                sql += " AND r.number=?"
                params.append(number)
            row = db.execute(sql + " ORDER BY r.number DESC LIMIT 1", params).fetchone()
            return self.decode(row)

    def list(self, limit=50, offset=0, query="", state=""):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT i.id, i.name, i.source, i.created, r.number, r.state, r.updated,
                       r.error, json_extract(r.metadata, '$.line_id') AS line_id
                FROM incidents i JOIN revisions r ON r.incident_id=i.id
                WHERE r.number=(SELECT MAX(number) FROM revisions WHERE incident_id=i.id)
                  AND (?='' OR instr(lower(i.name || ' ' || i.id), lower(?))>0)
                  AND (?='' OR r.state=?)
                ORDER BY r.updated DESC LIMIT ? OFFSET ?
            """, (query, query, state, state, limit, offset))]

    def summary(self):
        with self.connect() as db:
            return dict(db.execute("""SELECT state, COUNT(*) FROM revisions r
                WHERE number=(SELECT MAX(number) FROM revisions WHERE incident_id=r.incident_id)
                GROUP BY state""").fetchall())

    def submit(self, *, name, source, files, metadata, fingerprint, incident_id=None,
               expected=None):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM revisions WHERE fingerprint=?", (fingerprint,)).fetchone()
            if prior:
                return self.decode(prior), True
            if incident_id:
                current = db.execute("SELECT MAX(number) FROM revisions WHERE incident_id=?",
                                     (incident_id,)).fetchone()[0]
                if current is None:
                    raise KeyError(incident_id)
                if expected != current:
                    raise Conflict("This incident changed. Refresh before submitting another revision.")
                number = current + 1
            else:
                incident_id, number = uuid.uuid4().hex, 1
                db.execute("INSERT INTO incidents VALUES (?,?,?,?)", (incident_id, name, source, now))
            cursor = db.execute("""INSERT INTO revisions
                (incident_id,number,fingerprint,state,stage,metadata,files,created,updated)
                VALUES (?,?,?,'queued','inspect',?,?,?,?)""",
                (incident_id, number, fingerprint, json.dumps(metadata), json.dumps(files), now, now))
            db.execute("INSERT INTO activity(incident_id,revision,at,message) VALUES (?,?,?,?)",
                       (incident_id, number, now, f"Received through {source}; queued for inspection"))
            return self.decode(db.execute("SELECT * FROM revisions WHERE id=?",
                                         (cursor.lastrowid,)).fetchone()), False

    def review(self, incident_id, number, metadata):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM revisions WHERE incident_id=? ORDER BY number DESC LIMIT 1",
                             (incident_id,)).fetchone()
            if not row:
                raise KeyError(incident_id)
            if row["number"] != number or row["state"] != "needs_review":
                raise Conflict("Only the latest revision awaiting review can be assigned.")
            db.execute("UPDATE revisions SET metadata=?,state='queued',stage='analyse',error='',updated=? WHERE id=?",
                       (json.dumps(metadata), time.time(), row["id"]))
            db.execute("INSERT INTO activity(incident_id,revision,at,message) VALUES (?,?,?,?)",
                       (incident_id, number, time.time(), "Assignments confirmed; analysis queued"))

    def claim(self, lease_seconds=60):
        now, owner = time.time(), uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT * FROM revisions WHERE state='queued'
                OR (state='running' AND lease<?) ORDER BY id LIMIT 1""", (now,)).fetchone()
            if not row:
                return None
            db.execute("""UPDATE revisions SET state='running',owner=?,lease=?,attempts=attempts+1,
                       updated=? WHERE id=?""", (owner, now + lease_seconds, now, row["id"]))
            return self.decode(db.execute("SELECT * FROM revisions WHERE id=?", (row["id"],)).fetchone())

    def heartbeat(self, job):
        with self.connect() as db:
            return db.execute("UPDATE revisions SET lease=? WHERE id=? AND owner=? AND state='running'",
                              (time.time() + 60, job["id"], job["owner"])).rowcount == 1

    def finish(self, job, state, *, bundle=None, result=None, error=""):
        with self.connect() as db:
            changed = db.execute("""UPDATE revisions SET state=?,bundle=COALESCE(?,bundle),result=?,
                error=?,owner=NULL,lease=NULL,updated=? WHERE id=? AND owner=? AND state='running'""",
                (state, json.dumps(bundle) if bundle is not None else None,
                 json.dumps(result, allow_nan=False) if result is not None else None,
                 error, time.time(), job["id"], job["owner"])).rowcount
            if changed:
                db.execute("INSERT INTO activity(incident_id,revision,at,message) VALUES (?,?,?,?)",
                           (job["incident_id"], job["number"], time.time(), error or state.replace('_', ' ')))
            return bool(changed)

    def retry(self, incident_id, number):
        with self.connect() as db:
            count = db.execute("""UPDATE revisions SET state='queued',error='',updated=?
                WHERE incident_id=? AND number=? AND state='failed'""",
                (time.time(), incident_id, number)).rowcount
            if not count:
                raise Conflict("Only a failed job can be retried.")

    def history(self, incident_id):
        with self.connect() as db:
            return {"revisions": [dict(r) for r in db.execute(
                "SELECT number,state,stage,error,created,updated FROM revisions WHERE incident_id=? ORDER BY number DESC",
                (incident_id,))], "activity": [dict(r) for r in db.execute(
                "SELECT at,revision,message FROM activity WHERE incident_id=? ORDER BY id DESC LIMIT 100",
                (incident_id,))]}

    def receipt(self, path, fingerprint, state, message):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO receipts VALUES (?,?,?,?,?)",
                       (str(path), fingerprint, state, message, time.time()))

    def receipts(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM receipts ORDER BY updated DESC LIMIT 100")]

    def received(self, path, fingerprint):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM receipts WHERE path=? AND fingerprint=?',
                              (str(path), fingerprint)).fetchone() is not None
