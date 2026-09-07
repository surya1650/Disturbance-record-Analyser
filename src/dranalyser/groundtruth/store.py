"""Storage for patrol-confirmed fault locations.

This is the scarcest and most valuable data in the system, and the reason to
build it on day one rather than in year two: a confirmation can only be
captured in the days after the incident, while the patrol team still
remembers. Retrofitting the capture later does not retrofit the history.

SQLite and the standard library only. The brief targets PostgreSQL for the
production registry, and the schema here is written to lift across
unchanged, but nothing about capturing a tower number justifies standing up
a database server before the first confirmation exists.

Two things this deliberately does NOT do:

  * it never overwrites a confirmation. A correction is a new row with a new
    timestamp, and the accuracy figures use the latest. Ground truth that
    can be edited in place is ground truth nobody can audit.
  * it does not compute an error when the incident carries no estimate. A
    confirmed tower with no corresponding estimate is still worth storing;
    it just cannot score the locator.
"""
from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS incident (
    incident_id   TEXT PRIMARY KEY,
    line_id       TEXT NOT NULL,
    fault_time    TEXT,
    fault_type    TEXT,
    m             REAL,
    km_from_S     REAL,
    line_km       REAL,
    method        TEXT,
    mode          TEXT,
    verdict       TEXT,
    report_path   TEXT,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ground_truth (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id   TEXT NOT NULL,
    tower_no      TEXT,
    chainage_km   REAL,
    cause         TEXT,
    confirmed_by  TEXT,
    confirmed_at  TEXT NOT NULL,
    confidence    TEXT,
    notes         TEXT,
    FOREIGN KEY (incident_id) REFERENCES incident (incident_id)
);
CREATE INDEX IF NOT EXISTS gt_incident ON ground_truth (incident_id);
CREATE INDEX IF NOT EXISTS inc_line ON incident (line_id);
"""

CAUSES = ("lightning", "tree or vegetation", "bird or animal", "pollution flashover",
          "insulator failure", "conductor failure", "hardware or fitting",
          "external interference", "not found", "other")
CONFIDENCE = ("confirmed at tower", "narrowed to a span", "approximate", "unknown")


def _now() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


@dataclass
class Confirmation:
    incident_id: str
    tower_no: Optional[str] = None
    chainage_km: Optional[float] = None
    cause: str = ""
    confirmed_by: str = ""
    confirmed_at: str = ""
    confidence: str = ""
    notes: str = ""


@dataclass
class Scored:
    """One incident with an estimate and a confirmation, ready to grade."""

    incident_id: str
    line_id: str
    line_km: Optional[float]
    km_estimated: Optional[float]
    km_actual: Optional[float]
    mode: str = ""
    method: str = ""
    fault_type: str = ""
    tower_no: str = ""
    cause: str = ""

    @property
    def error_km(self) -> Optional[float]:
        if self.km_estimated is None or self.km_actual is None:
            return None
        return self.km_estimated - self.km_actual

    @property
    def error_pct(self) -> Optional[float]:
        e = self.error_km
        if e is None or not self.line_km:
            return None
        return 100.0 * e / self.line_km


class Store:
    def __init__(self, path: str = "dranalyser.db"):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        # The capture form serves requests from worker threads while the
        # store is created on the main thread, so the connection is shared
        # across threads and every access is serialised by this lock. SQLite
        # itself refuses cross-thread use by default, and the failure only
        # appears once a second person opens the form.
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def _query(self, sql: str, args: Sequence[Any] = ()) -> List[sqlite3.Row]:
        with self._lock:
            return list(self.conn.execute(sql, args))

    def _write(self, sql: str, args: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- incidents -------------------------------------------------------
    def record_incident(self, incident_id: str, line_id: str, **kw) -> None:
        """Register an incident so it can be confirmed later.

        Re-running the analyser on the same record must update the estimate
        without disturbing any confirmation already attached to it.
        """
        cols = ("fault_time", "fault_type", "m", "km_from_S", "line_km",
                "method", "mode", "verdict", "report_path")
        vals = {c: kw.get(c) for c in cols}
        self._write(
            "INSERT INTO incident (incident_id, line_id, " + ", ".join(cols)
            + ", created_at) VALUES (?, ?, " + ", ".join("?" * len(cols)) + ", ?)"
            " ON CONFLICT(incident_id) DO UPDATE SET "
            + ", ".join(c + "=excluded." + c for c in cols),
            [incident_id, line_id] + [vals[c] for c in cols] + [_now()])

    def incident(self, incident_id: str) -> Optional[sqlite3.Row]:
        rows = self._query("SELECT * FROM incident WHERE incident_id = ?",
                           (incident_id,))
        return rows[0] if rows else None

    def incidents(self, line_id: Optional[str] = None) -> List[sqlite3.Row]:
        q = "SELECT * FROM incident"
        args: List[Any] = []
        if line_id:
            q += " WHERE line_id = ?"
            args.append(line_id)
        return self._query(q + " ORDER BY fault_time DESC", args)

    # ---- confirmations ---------------------------------------------------
    def confirm(self, c: Confirmation) -> int:
        if not c.incident_id:
            raise ValueError("a confirmation must name its incident")
        if c.tower_no is None and c.chainage_km is None and c.cause != "not found":
            raise ValueError("give a tower number, a chainage, or record it as not found")
        cur = self._write(
            "INSERT INTO ground_truth (incident_id, tower_no, chainage_km, cause,"
            " confirmed_by, confirmed_at, confidence, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (c.incident_id, c.tower_no, c.chainage_km, c.cause, c.confirmed_by,
             c.confirmed_at or _now(), c.confidence, c.notes))
        return int(cur.lastrowid)

    def latest_confirmation(self, incident_id: str) -> Optional[sqlite3.Row]:
        rows = self._query(
            "SELECT * FROM ground_truth WHERE incident_id = ?"
            " ORDER BY confirmed_at DESC, id DESC LIMIT 1", (incident_id,))
        return rows[0] if rows else None

    def pending(self, line_id: Optional[str] = None) -> List[sqlite3.Row]:
        """Incidents with no confirmation yet -- the chase list."""
        q = ("SELECT i.* FROM incident i LEFT JOIN ground_truth g"
             " ON g.incident_id = i.incident_id WHERE g.id IS NULL")
        args: List[Any] = []
        if line_id:
            q += " AND i.line_id = ?"
            args.append(line_id)
        return self._query(q + " ORDER BY i.fault_time DESC", args)

    # ---- scoring ---------------------------------------------------------
    def scored(self, line_id: Optional[str] = None) -> List[Scored]:
        out: List[Scored] = []
        for inc in self.incidents(line_id):
            g = self.latest_confirmation(inc["incident_id"])
            if g is None:
                continue
            km_actual = g["chainage_km"]
            out.append(Scored(
                incident_id=inc["incident_id"], line_id=inc["line_id"],
                line_km=inc["line_km"], km_estimated=inc["km_from_S"],
                km_actual=km_actual, mode=inc["mode"] or "", method=inc["method"] or "",
                fault_type=inc["fault_type"] or "", tower_no=g["tower_no"] or "",
                cause=g["cause"] or ""))
        return out

    def accuracy(self, line_id: Optional[str] = None) -> Dict[str, Any]:
        """Measured accuracy against confirmations, and the Tier-2 gate.

        Reports the 90th percentile as well as the mean, because the tail is
        what destroys credibility with the patrol team: a locator averaging
        0.4 % with occasional 15 % excursions gets abandoned after the second
        wasted patrol.
        """
        rows = [s for s in self.scored(line_id) if s.error_km is not None]
        n_conf = len([s for s in self.scored(line_id)])
        out: Dict[str, Any] = {
            "confirmations": n_conf,
            "scorable": len(rows),
            "tier2_gate": 100,
            "tier2_ready": n_conf >= 100,
            "by_mode": {},
        }
        if not rows:
            return out
        errs = sorted(abs(s.error_km) for s in rows)
        pct = sorted(abs(s.error_pct) for s in rows if s.error_pct is not None)
        out["mae_km"] = sum(errs) / len(errs)
        out["p90_km"] = errs[min(int(0.9 * len(errs)), len(errs) - 1)]
        out["max_km"] = errs[-1]
        if pct:
            out["mae_pct"] = sum(pct) / len(pct)
            out["p90_pct"] = pct[min(int(0.9 * len(pct)), len(pct) - 1)]
            out["max_pct"] = pct[-1]
        for mode in sorted({s.mode for s in rows}):
            sub = sorted(abs(s.error_km) for s in rows if s.mode == mode)
            out["by_mode"][mode] = {
                "n": len(sub), "mae_km": sum(sub) / len(sub),
                "p90_km": sub[min(int(0.9 * len(sub)), len(sub) - 1)]}
        return out

    def accuracy_report(self, line_id: Optional[str] = None) -> str:
        a = self.accuracy(line_id)
        rows = ["ACCURACY against patrol confirmations",
                "  confirmations : " + str(a["confirmations"])
                + "   scorable against an estimate: " + str(a["scorable"])]
        if a["scorable"]:
            rows.append("  error, km     : mean " + format(a["mae_km"], ".3f")
                        + "   p90 " + format(a["p90_km"], ".3f")
                        + "   max " + format(a["max_km"], ".3f"))
            if "mae_pct" in a:
                rows.append("  error, % line : mean " + format(a["mae_pct"], ".3f")
                            + "   p90 " + format(a["p90_pct"], ".3f")
                            + "   max " + format(a["max_pct"], ".3f"))
            for mode, d in a["by_mode"].items():
                rows.append("     " + format(mode, "<14") + "n=" + format(d["n"], "<4")
                            + " mean " + format(d["mae_km"], ".3f")
                            + " km   p90 " + format(d["p90_km"], ".3f") + " km")
        rows.append("  Tier 2 gate   : " + str(a["confirmations"]) + "/"
                    + str(a["tier2_gate"]) + " confirmed events"
                    + ("  READY" if a["tier2_ready"]
                       else "  not yet -- the residual model stays gated off"))
        return "\n".join(rows)
