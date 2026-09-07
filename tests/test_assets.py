"""Resolving a record to a line and a terminal, from evidence.

The rule these guard: nothing infers a terminal from the operator's argument
order, and ambiguity is refused rather than broken by ordering.
"""
from __future__ import annotations

import pytest

from dranalyser.registry.assets import (Ambiguous, Assignment, AssetResolver,
                                        RecordFacts, norm)
from dranalyser.registry.model import (InstrumentTransformer, Relay, Terminal,
                                       uniform_line)


def _line(lid, name, kv, a, b, *, aliases=(), path_rules=(),
          ct=(800.0, 800.0), vt=(2000.0, 2000.0), a_aliases=(), b_aliases=()):
    ln = uniform_line(lid, name, kv, 60.0, complex(0.03, 0.4), complex(0.25, 1.2))
    ln.aliases = list(aliases)
    ln.path_rules = list(path_rules)
    ln.terminals["S"] = Terminal(
        end="S", substation=a, aliases=list(a_aliases),
        it=InstrumentTransformer(ct_ratio=ct[0], vt_ratio=vt[0]),
        relays=[Relay(id=a + "-M1", model="7SA522", function="main1",
                      aliases=["Main-1"])])
    ln.terminals["R"] = Terminal(
        end="R", substation=b, aliases=list(b_aliases),
        it=InstrumentTransformer(ct_ratio=ct[1], vt_ratio=vt[1]),
        relays=[Relay(id=b + "-M1", model="P444", function="main1",
                      aliases=["Main-1"])])
    return ln


DHN = _line("DHN-NNR", "Dhone - Nandyal 220 kV", 220.0, "DHONE", "NANDYAL",
            aliases=["DHONE-NANDYAL", "220KV DHN NNR"],
            a_aliases=["DHONE(SWS)", "APTRANSCO_Dhone"])
GRV = _line("GRV-MRD-1", "Garividi - Maradam 1", 220.0, "GARIVIDI", "MARADAM",
            aliases=["LINE 205", "B205"])
GRV2 = _line("GRV-MRD-2", "Garividi - Maradam 2", 220.0, "GARIVIDI", "MARADAM",
             aliases=["LINE 206", "B206"])


def test_normalisation_lets_one_line_answer_to_several_written_forms():
    assert norm("220KV DHN-NNR 18-3-2026") == "220KVDHNNNR1832026"
    assert norm("DHN-NNR") in norm("220KV DHN-NNR 18-3-2026")


def test_the_real_dhone_header_names_the_line_but_not_the_end_so_it_refuses():
    """`220KV DHN-NNR ... 7SA522 V4.7` names the line and a relay MODEL, and
    a model is not an identifier -- half this fleet is 7SA522. The folder is
    `Main-2`, which is a relay function, not a terminal. So nothing here says
    which end, and the honest answer is to refuse."""
    r = AssetResolver([DHN]).resolve(RecordFacts(
        station="220KV DHN-NNR 18-3-2026  Folder  7SA522 V4.7 Var",
        path="DR & Events/Main-2/DR-1/DR-1.CFG"))
    assert isinstance(r, Ambiguous)
    assert {c.terminal_end for c in r.candidates} == {"S", "R"}
    assert all(c.line_id == "DHN-NNR" for c in r.candidates)


def test_the_sibling_rio_supplies_the_end_the_header_could_not():
    """Evidence layers: the header fixes the line, the settings export's
    SUBSTATION fixes the terminal. This is the real DHONE record."""
    r = AssetResolver([DHN]).resolve(RecordFacts(
        station="220KV DHN-NNR 18-3-2026  Folder  7SA522 V4.7 Var",
        path="DR & Events/Main-2/DR-1/DR-1.CFG",
        settings_substation="DHONE(SWS)"))
    assert isinstance(r, Assignment)
    assert (r.line_id, r.terminal_end) == ("DHN-NNR", "S")


def test_the_far_end_of_the_same_line_resolves_to_the_other_terminal():
    r = AssetResolver([DHN]).resolve(RecordFacts(station="NANDYAL 220KV DHN-NNR"))
    assert isinstance(r, Assignment) and r.terminal_end == "R"


def test_an_alias_of_the_substation_is_enough():
    r = AssetResolver([DHN]).resolve(RecordFacts(station="DHONE(SWS)"))
    assert isinstance(r, Assignment) and r.terminal_end == "S"


def test_a_manifest_decides_on_its_own_and_says_who_declared_it():
    """The operator's declaration is rank 1, above the CFG header."""
    r = AssetResolver([DHN, GRV]).resolve(
        RecordFacts(station="BRAHMANAKOTKUR"),
        manifest={"line_id": "GRV-MRD-1", "terminal_end": "S",
                  "source": "operator"})
    assert isinstance(r, Assignment)
    assert (r.line_id, r.terminal_end) == ("GRV-MRD-1", "S")
    assert any(h.source == "manifest" and "operator" in h.detail
               for h in r.evidence)


def test_a_path_rule_configured_in_the_registry_resolves_the_end():
    line = _line("KPK-GJW", "Kalpaka - Gajuwaka", 400.0, "KALPAKA", "GAJUWAKA",
                 path_rules=[r"(?i)/(?P<substation>kalpaka|gajuwaka)[ /-]"])
    r = AssetResolver([line]).resolve(
        RecordFacts(path="drs/400kv/gajuwaka-kalpakka/15251_Main-2_dr.cfg"))
    assert isinstance(r, Assignment)
    assert (r.line_id, r.terminal_end) == ("KPK-GJW", "R")


def test_the_ratios_corroborate_but_never_decide_alone():
    """Electrical evidence is rank 5: it can break nothing on its own."""
    line = _line("SOLO", "Solo line", 220.0, "AAA", "BBB",
                 ct=(800.0, 400.0), vt=(2000.0, 2000.0))
    r = AssetResolver([line]).resolve(
        RecordFacts(kv_nominal=220.0, ct_ratio=800.0, vt_ratio=2000.0))
    assert isinstance(r, Ambiguous)
    assert "below the" in r.reason


def test_two_lines_between_the_same_two_substations_are_refused():
    """Garividi-Maradam is double circuit. The station name cannot tell 205
    from 206, and guessing would locate a fault on the healthy circuit."""
    r = AssetResolver([GRV, GRV2]).resolve(RecordFacts(station="GARIVIDI"))
    assert isinstance(r, Ambiguous)
    assert "too close to call" in r.reason
    assert {c.line_id for c in r.candidates} == {"GRV-MRD-1", "GRV-MRD-2"}


def test_naming_the_circuit_resolves_what_the_station_alone_cannot():
    r = AssetResolver([GRV, GRV2]).resolve(
        RecordFacts(station="APTRANSCO_Maradam / 220KV LEVEL / LINE   206   "
                            "B206_21.1_7SA522 V4.7"))
    assert isinstance(r, Assignment)
    assert (r.line_id, r.terminal_end) == ("GRV-MRD-2", "R")


def test_a_record_matching_nothing_is_refused_with_the_reason():
    r = AssetResolver([DHN]).resolve(RecordFacts(station="SOMEWHERE ELSE",
                                                 path="/tmp/x.cfg"))
    assert isinstance(r, Ambiguous)
    assert "no evidence" in r.reason


def test_evidence_naming_only_the_line_can_never_choose_the_end():
    """It lifts both ends equally, so it decides the line and nothing more."""
    r = AssetResolver([DHN]).resolve(RecordFacts(station="220KV DHN NNR"))
    assert isinstance(r, Ambiguous)
    assert "too close to call" in r.reason
    assert {c.terminal_end for c in r.candidates} == {"S", "R"}


def test_a_sibling_settings_file_names_the_substation():
    r = AssetResolver([DHN]).resolve(RecordFacts(
        settings_substation="220KV DHN-NNR 18-3-2026", settings_feeder="DHONE"))
    assert isinstance(r, Assignment) and r.terminal_end == "S"


def test_the_assignment_carries_every_piece_of_evidence_it_used():
    r = AssetResolver([DHN]).resolve(RecordFacts(
        station="DHONE(SWS)", kv_nominal=220.0, ct_ratio=800.0, vt_ratio=2000.0))
    assert isinstance(r, Assignment)
    sources = {h.source for h in r.evidence}
    assert "header" in sources and "electrical" in sources
    assert all(str(h).startswith("[") for h in r.evidence)
