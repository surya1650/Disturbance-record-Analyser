"""Canonical digital-signal mapping.

The digital timeline is often the most diagnostic graphic in the report, and
it is the only evidence for the highest-value rules in the catalogue -- did
the carrier arrive, did the breaker clear in spec, was the reclose correct.
None of that survives if every relay family spells the signals differently,
which they do. Two relays in the same bay of the source corpus:

    Main-1   Any Start   Any Trip   DIST Trip A   Z1   DIST. Chan Recv
             A/R Lockout   Any Pole Dead   L1-CB R-PH OPEN
    Main-2   Relay PICKUP   Dis.Gen. Trip   Dis.Trip 1pL1   Dis.TripZ2/1p
             Dis.T.SEND L1   >Dis Tel Rec.Ch1   1pole open L1   86A OPTD

So rules are written against canonical names and the vendor text is matched
here, once.

Matching is SCORED, not first-past-the-post. A 74-channel SIPROTEC offers
about ten candidates for "trip", and the first regex hit is "O/C TRIP 1p.L1"
-- the overcurrent element, not the distance element. Timing a distance
scheme off the overcurrent trip is a wrong answer that looks entirely
plausible. Each canonical name therefore carries what to prefer and what to
avoid, and every candidate is kept so a rule can ask for all carrier-receive
channels rather than one.

A signal that cannot be mapped is REPORTED, not ignored: a rule that
silently evaluates to false because its channel was never mapped reads as a
healthy result, which is the worst possible failure for this system.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

CANONICAL = (
    "START", "TRIP", "TRIP_A", "TRIP_B", "TRIP_C", "TRIP_3P",
    "Z1", "Z2", "Z3", "Z4", "ZONE_FWD", "ZONE_REV",
    "TRIP_Z2", "TRIP_Z3", "TRIP_Z4",
    "CARRIER_SEND", "CARRIER_RECV", "CARRIER_FAIL",
    "CB_OPEN_A", "CB_OPEN_B", "CB_OPEN_C", "ANY_POLE_DEAD", "ALL_POLE_DEAD",
    "AR_INITIATE", "AR_IN_PROGRESS", "AR_CLOSE", "AR_LOCKOUT", "AR_BLOCK",
    "AR_FAIL",
    "VT_FAIL", "SOTF", "POWER_SWING", "DEFINITIVE_TRIP", "LOCKOUT_86",
    "MANUAL_CLOSE", "BROKEN_CONDUCTOR", "EARTH_FAULT_TRIP",
)

# Function prefixes that mark a channel as belonging to a protection element
# other than distance. Timing a distance scheme off one of these is wrong.
OTHER_ELEMENT = r"O/?C\b|OVERCURRENT|\bE/?F\b|EARTH\s*FAULT|3I0|\bSOF\b|SOTF|\bBF\b"
# A leading > is a SIPROTEC binary INPUT. Correct for a carrier receive,
# wrong for anything the relay itself asserts.
INPUT_MARK = r"^\s*>"
DISTANCE = r"\bDIS\w*\b|\bDIST\b"
GENERAL = r"\bANY\b|\bGEN\w*\b|\bRELAY\b"
# E is the earth/residual element, not a phase, but for the purpose of
# picking a GENERAL start or trip channel it disqualifies a candidate in
# exactly the same way: "Dis.Pickup E" is the earth starter, not the relay's
# general pickup.
PER_PHASE = r"\b(L1|L2|L3|1P|3P)\b|\b[ABCE]\b"


@dataclass(frozen=True)
class SignalRule:
    canonical: str
    match: str
    prefer: Tuple[str, ...] = ()
    avoid: Tuple[str, ...] = ()


# Order matters only for which rule a channel is tested against first; within
# a canonical name the winner is chosen by score.
RULES: Tuple[SignalRule, ...] = (
    SignalRule("CARRIER_FAIL", r"(CARR|CHAN|TEL)\w*.*FAIL|CR\s*CH.*FAI"),
    SignalRule("CARRIER_SEND", r"T\.?\s*SEND|CARR\w*\s*SEND|SEND\s*(SIG|CARR)|PLCC.*SEND",
               prefer=(DISTANCE,), avoid=(OTHER_ELEMENT,)),
    SignalRule("CARRIER_RECV",
               r"TEL\w*\s*REC|\bT\.?\s*REC|CHAN\w*\s*RECV?|CARR\w*\s*REC|CR\s*CH|DT\s*REC"
               r"|PERM\w*\s*RECV?",
               prefer=(DISTANCE, r"CH-?\s*1|Ch1"), avoid=(r"FAIL",)),
    SignalRule("TRIP_Z2", r"TRIP\s*Z2|Z2\s*TRIP", avoid=(PER_PHASE,)),
    SignalRule("TRIP_Z3", r"TRIP\s*Z3|Z3\s*TRIP|TRIPZ3/T3"),
    SignalRule("TRIP_Z4", r"TRIP\s*3?\s*P?\.?\s*Z4|Z4\s*TRIP"),
    SignalRule("AR_LOCKOUT", r"(A/?R|RECLOS\w*).*(LOCKOUT|BLOCKED\s*OUT)|LOCKOUT\s*SHOT",
               avoid=(INPUT_MARK, r"SHOT",)),
    SignalRule("AR_BLOCK", r">?\s*A/?R\s*BLOCK|BLOCK\s*A/?R|RECLOSE\s*BLOCK"),
    SignalRule("AR_FAIL", r"(A/?R|RECLOS\w*).*FAIL"),
    SignalRule("AR_IN_PROGRESS", r"(A/?R|RECLOS\w*).*(IN\s*PROG|1P\s*IN)"),
    SignalRule("AR_CLOSE", r"(A/?R)\s*CLOSE|RECLOSE\s*(CMD|CLOSE)",
               prefer=(r"CMD",), avoid=(INPUT_MARK, r"^\s*I\s")),
    SignalRule("AR_INITIATE", r"(A/?R|RECLOS\w*).*(INIT|START)"),
    SignalRule("ALL_POLE_DEAD", r"ALL\s*POLE\s*DEAD"),
    SignalRule("ANY_POLE_DEAD", r"ANY\s*POLE\s*DEAD|\bPOLE\s*DEAD"),
    SignalRule("CB_OPEN_A", r"(L1|R)\s*[- ]?\s*PH\s*OPEN|1\s*POLE\s*OPEN\s*L1"
                            r"|CB.*R[- ]?PH.*OPEN|^\s*R\s*PH\s*OPEN",
               prefer=(r"1\s*POLE\s*OPEN|L1|CB",)),
    SignalRule("CB_OPEN_B", r"(L2|Y)\s*[- ]?\s*PH\s*OPEN|1\s*POLE\s*OPEN\s*L2"
                            r"|CB.*Y[- ]?PH.*OPEN|^\s*Y\s*PH\s*OPEN",
               prefer=(r"1\s*POLE\s*OPEN|L2|CB",)),
    SignalRule("CB_OPEN_C", r"(L3|B)\s*[- ]?\s*PH\s*OPEN|1\s*POLE\s*OPEN\s*L3"
                            r"|CB.*B[- ]?PH.*OPEN|^\s*B\s*PH\s*OPEN",
               prefer=(r"1\s*POLE\s*OPEN|L3|CB",)),
    SignalRule("LOCKOUT_86", r"^\s*86[AB]?\b|86\s*OPTD|MASTER\s*TRIP"),
    SignalRule("DEFINITIVE_TRIP", r"DEFINITIVE\s*TRIP|FINAL\s*TRIP"),
    SignalRule("TRIP_3P", r"TRIP\s*3\s*P|3\s*P(H|OLE)?\s*TRIP|TRIP\s*L123",
               prefer=(DISTANCE,), avoid=(OTHER_ELEMENT, r"Z[0-9]")),
    SignalRule("TRIP_A", r"TRIP\s*1?P?\s*(A|L1|R)\b|TRIP\s*A\b",
               prefer=(DISTANCE,), avoid=(OTHER_ELEMENT, INPUT_MARK)),
    SignalRule("TRIP_B", r"TRIP\s*1?P?\s*(B|L2|Y)\b|TRIP\s*B\b",
               prefer=(DISTANCE,), avoid=(OTHER_ELEMENT, INPUT_MARK)),
    SignalRule("TRIP_C", r"TRIP\s*1?P?\s*(C|L3|B)\b|TRIP\s*C\b",
               prefer=(DISTANCE,), avoid=(OTHER_ELEMENT, INPUT_MARK)),
    SignalRule("Z1", r"^\s*Z1\b|ZONE\s*1\b"),
    SignalRule("Z2", r"^\s*Z2\b|ZONE\s*2\b"),
    SignalRule("Z3", r"^\s*Z3\b|ZONE\s*3\b"),
    SignalRule("Z4", r"^\s*Z4\b|ZONE\s*4\b"),
    SignalRule("ZONE_REV", r"DIS\w*\.?\s*REV|REVERSE"),
    SignalRule("ZONE_FWD", r"DIS\w*\.?\s*(FWD|FORWARD)"),
    SignalRule("VT_FAIL", r"VT\s*(FAIL|FUSE)|FUSE\s*FAIL|MCB\s*TRIP|FAIL\s*U\s*ABSENT",
               prefer=(r"VT",)),
    SignalRule("POWER_SWING", r"POWER\s*SWING|OUT\s*OF\s*STEP|\bPSB\b"),
    SignalRule("SOTF", r"SOTF|SOFO|SWITCH\s*ON\s*TO\s*FAULT|TOR\s*TRIP"),
    SignalRule("MANUAL_CLOSE", r"MAN\w*\.?\s*CLOSE|LINE\s*CLOSURE", avoid=(INPUT_MARK,)),
    SignalRule("BROKEN_CONDUCTOR", r"BROK\w*\.?\s*COND|FAIL\s*CONDUCTOR"),
    SignalRule("EARTH_FAULT_TRIP", r"E/?F\s*\S*\s*TRIP|EARTH\s*FAULT\s*TRIP"),
    SignalRule("TRIP", r"\bTRIP\b",
               prefer=(DISTANCE, GENERAL),
               avoid=(OTHER_ELEMENT, INPUT_MARK, PER_PHASE, r"Z[0-9]", r"DEFINITIVE")),
    SignalRule("START", r"\b(START|PICKUP)\b",
               prefer=(DISTANCE, GENERAL),
               avoid=(OTHER_ELEMENT, INPUT_MARK, PER_PHASE)),
)

_COMPILED = tuple(
    (r, re.compile(r.match, re.I),
     tuple(re.compile(p, re.I) for p in r.prefer),
     tuple(re.compile(a, re.I) for a in r.avoid))
    for r in RULES
)

IGNORE = re.compile(
    r"TRIG\w*\.?\s*WAVE|FLAG\s*LOST|FLT?\s*REC|FAULT\s*REC|UNUSED|SPARE|NOT\s*USED",
    re.I,
)


@dataclass
class SignalMap:
    """Canonical name -> every vendor channel that matched, best first."""

    candidates: Dict[str, List[str]] = field(default_factory=dict)
    scores: Dict[str, List[float]] = field(default_factory=dict)
    unmapped: List[str] = field(default_factory=list)
    ignored: List[str] = field(default_factory=list)

    @property
    def mapping(self) -> Dict[str, str]:
        return {k: v[0] for k, v in self.candidates.items() if v}

    def channel(self, canonical: str) -> Optional[str]:
        c = self.candidates.get(canonical)
        return c[0] if c else None

    def channels(self, canonical: str) -> List[str]:
        return list(self.candidates.get(canonical, ()))

    def has(self, canonical: str) -> bool:
        return bool(self.candidates.get(canonical))

    def missing(self, *names: str) -> List[str]:
        return [n for n in names if not self.has(n)]

    def summary(self) -> str:
        rows = ["mapped " + str(len(self.candidates)) + " of " + str(len(CANONICAL))
                + " canonical signals"]
        for k in sorted(self.candidates):
            extra = self.candidates[k][1:]
            rows.append("   " + format(k, "<18") + " <- " + self.candidates[k][0]
                        + ("   (+" + str(len(extra)) + " more)" if extra else ""))
        if self.unmapped:
            rows.append("   unmapped: " + ", ".join(self.unmapped[:12])
                        + (" ..." if len(self.unmapped) > 12 else ""))
        return "\n".join(rows)


def _score(name: str, prefer, avoid) -> float:
    s = 0.0
    for rx in prefer:
        if rx.search(name):
            s += 10.0
    for rx in avoid:
        if rx.search(name):
            s -= 10.0
    return s - 0.01 * len(name)          # shorter names break ties


def map_signals(channel_names: Sequence[str]) -> SignalMap:
    """Map a record's digital channel names onto canonical signals."""
    out = SignalMap()
    scored: Dict[str, List[Tuple[float, str]]] = {}
    for raw in channel_names:
        name = " ".join(str(raw).split())
        if not name:
            continue
        if IGNORE.search(name):
            out.ignored.append(raw)
            continue
        hit = None
        for rule, rx, prefer, avoid in _COMPILED:
            if rx.search(name):
                hit = (rule.canonical, _score(name, prefer, avoid))
                break
        if hit is None:
            out.unmapped.append(raw)
            continue
        scored.setdefault(hit[0], []).append((hit[1], raw))
    for canonical, items in scored.items():
        items.sort(key=lambda t: -t[0])
        out.candidates[canonical] = [n for _, n in items]
        out.scores[canonical] = [s for s, _ in items]
    return out


def infer_zone_operated(
    asserts: Dict[str, Optional[float]], operate_s: Optional[float],
    z2_time_s: float = 0.35,
) -> Optional[str]:
    """Which zone actually tripped.

    Some relays assert an explicit zone-qualified trip; others assert only a
    general trip plus a zone pickup. Where the qualifier exists it wins.
    Otherwise a trip faster than the Zone 2 timer is a Zone 1 trip OR an aided
    Zone 2 trip, and timing alone genuinely cannot separate those -- so the
    result is reported as Z1_OR_AIDED rather than asserted to be Zone 1. The
    carrier channels are what settle it, and rule CR-01 uses them.
    """
    for zone, sig in (("Z4", "TRIP_Z4"), ("Z3", "TRIP_Z3"), ("Z2", "TRIP_Z2")):
        if asserts.get(sig) is not None:
            return zone
    if operate_s is None:
        return None
    if operate_s < 0.75 * z2_time_s:
        return "Z1_OR_AIDED"
    if operate_s < 1.5 * z2_time_s:
        return "Z2"
    return "Z3_OR_SLOWER"
