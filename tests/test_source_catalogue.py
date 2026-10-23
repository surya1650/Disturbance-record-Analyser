"""Synthetic source fixtures; private operational workbook rows are never committed."""

import copy
import json

import pytest

from dranalyser.cli import main
from dranalyser.registry.catalogue import (
    FIELDS,
    build_catalogue,
    digest,
    impedance,
    number,
    ratio,
    reciprocal_candidates,
)
from dranalyser.registry.catalogue_io import import_snapshot, read_catalogue, review_template
from dranalyser.registry.catalogue_review import reviewed_line
from dranalyser.registry.loader import line_from_dict
from tests import test_application as fixtures

environment = fixtures.environment


def snapshot():
    headers = list(FIELDS.values()) + [
        "Z1",
        "T1",
        "Z2",
        "T2",
        "Z3",
        "T3",
        "Z4",
        "T4",
        "Quad +Seq R (Ω)",
        "Quad +Seq X (Ω)",
    ]

    def row(station, feeder):
        data = {
            "station": station,
            "feeder": feeder,
            "bus_id": None,
            "bus_number": 42,
            "date": "03/04/24",
            "reference": "SYNTHETIC/REF",
            "kv": 220,
            "length_km": 20,
            "z1": "2 +j 8 = 8.25",
            "z0": "6 +j 24 = 24.74",
            "ct_ratio": "800 /1 A",
            "vt_ratio": "220000 /110 V",
            "relay": "Example/TEST",
        }
        return [data[k] for k in FIELDS] + [6.6, 0, 10, 0.3, 12, 0.6, 20, 1.2, 2, 8]

    return {
        "schema": "dranalyser.google-sheet-snapshot.v1",
        "source": {"spreadsheet_id": "SYNTHETIC-ONLY", "modified_time": "2026-10-23T00:00:00Z"},
        "sheets": [
            {
                "properties": {"title": "Example TL", "sheetId": 123},
                "values": [headers, row("Alpha", "Beta -"), row("Beta", "Alpha -")],
            }
        ],
    }


def review(cat):
    return {
        "catalogue_hash": digest(cat),
        "reviewer": "Synthetic reviewer",
        "reason": "Synthetic exercise",
        "line_id": "EXAMPLE",
        "circuit_id": "test circuit",
        "parameter_evidence": "Synthetic fixture",
        "topology_evidence": "Synthetic uncoupled series circuit",
        "terminals": {"S": cat["rows"][0]["id"], "R": cat["rows"][1]["id"]},
        "parameter_row": cat["rows"][0]["id"],
        "impedance_basis": "primary_total_ohm",
        "double_circuit": False,
        "series_compensated": False,
        "series_only_model_confirmed": True,
        "instrument_declarations": {e: {"vt_type": "CVT", "vt_location": "line", "i_polarity": 1} for e in ("S", "R")},
    }


def test_shifted_columns_source_rows_units_dates_and_no_invented_identifiers():
    s = snapshot()
    before = copy.deepcopy(s)
    cat = build_catalogue(s)
    r = cat["rows"][0]
    assert s == before
    assert r["bus_id"] == "" and r["bus_number"] == "42"
    assert r["ct_ratio"]["ratio"] == 800 and r["vt_ratio"]["ratio"] == 2000
    assert r["reference_date"] == "2024-04-03" and not r["settings_effective_date_verified"]
    assert r["z1"]["r"] == 2 and r["z1"]["x"] == 8
    assert r["cells"]["station"].endswith("!A2")
    assert r["zones"][0]["reach_raw"] == 6.6 and r["zones"][0]["time_raw"] == 0
    assert not r["zones"][0]["characteristic_complete"]
    assert cat["summary"]["field_verified_rows"] == 0 and r["electrical_values_parseable"]


@pytest.mark.parametrize("bad", ["nan", "inf", "1e999", True, "=1+2", "2/3", "1,2"])
def test_number_parser_rejects_nonfinite_formulas_and_ambiguous_formats(bad):
    with pytest.raises(ValueError):
        number(bad)


@pytest.mark.parametrize("bad", ["800", "800/0 A", "0/1", "-800/1", "800/1/5", "1e999/1", "800/5 tap 1"])
def test_ratios_never_assume_a_secondary_or_repair_ambiguous_taps(bad):
    with pytest.raises(ValueError):
        ratio(bad)


@pytest.mark.parametrize("bad", ["2+j8 words", "2+j1e999", '__import__("os")', "8.25", "2+8j"])
def test_impedance_parser_has_no_eval_or_derived_fallback(bad):
    with pytest.raises(ValueError):
        impedance(bad)


def test_derived_column_conflict_is_not_silently_substituted():
    s = snapshot()
    s["sheets"][0]["values"][1][-1] = 80
    r = build_catalogue(s)["rows"][0]
    assert r["z1"]["x"] == 8 and not r["electrical_values_parseable"]
    assert any(i["code"] == "derived_column_conflict" for i in r["issues"])


def test_missing_id_is_not_filled_down_and_bus_number_is_not_a_bay_join():
    s = snapshot()
    s["sheets"][0]["values"][1][2] = "411111"
    cat = build_catalogue(s)
    assert cat["rows"][1]["bus_id"] == ""
    assert len(cat["rows"]) == 2


def test_reciprocal_candidates_preserve_circuit_suffix_and_multiple_candidates():
    s = snapshot()
    s["sheets"][0]["values"].append(copy.deepcopy(s["sheets"][0]["values"][2]))
    cat = build_catalogue(s)
    matches = reciprocal_candidates(cat, cat["rows"][0]["id"])
    assert len(matches) == 2 and all("candidate only" in c["status"] for c in matches)
    s["sheets"][0]["values"][1][1] = "Beta - 1&2"
    cat = build_catalogue(s)
    assert reciprocal_candidates(cat, cat["rows"][0]["id"]) == []


def test_reviewed_export_conserves_total_impedance_and_never_invents_towers_or_zones():
    cat = build_catalogue(snapshot())
    definition = reviewed_line(cat, review(cat))
    line = line_from_dict(definition)
    assert line.z1 == complex(2, 8) and line.z0 == complex(6, 24)
    assert line.length_km == 20 and not line.towers
    assert line.terminals["S"].substation == "Alpha"
    assert not line.terminals["S"].relays and "PROVISIONAL" in definition["parameter_status"]
    assert definition["source_provenance"]["selected_rows"]["S"]["hash"] == cat["rows"][0]["row_hash"]


def test_secondary_total_conversion_is_explicit_and_uses_vt_over_ct():
    cat = build_catalogue(snapshot())
    r = review(cat)
    r["impedance_basis"] = "secondary_total_ohm"
    line = line_from_dict(reviewed_line(cat, r))
    assert line.z1 == complex(5, 20)


@pytest.mark.parametrize(
    "mutation", ["stale", "unknown", "same_end", "base", "topology", "polarity", "identity", "reviewer"]
)
def test_missing_stale_or_ambiguous_review_inputs_refuse(mutation):
    cat = build_catalogue(snapshot())
    r = review(cat)
    if mutation == "stale":
        r["catalogue_hash"] = "0" * 64
    if mutation == "unknown":
        r["parameter_row"] = "absent"
    if mutation == "same_end":
        r["terminals"]["R"] = r["terminals"]["S"]
    if mutation == "base":
        r["impedance_basis"] = ""
    if mutation == "topology":
        r["double_circuit"] = "false"
    if mutation == "polarity":
        r["instrument_declarations"]["S"]["i_polarity"] = True
    if mutation == "identity":
        r["circuit_id"] = ""
    if mutation == "reviewer":
        r["reviewer"] = ""
    with pytest.raises(ValueError):
        reviewed_line(cat, r)


def test_different_end_parameters_need_an_explicit_resolution():
    s = snapshot()
    s["sheets"][0]["values"][2][7] = 21  # length field in this fixture
    cat = build_catalogue(s)
    r = review(cat)
    with pytest.raises(ValueError, match="disagreements"):
        reviewed_line(cat, r)
    r["parameter_conflict_resolution"] = "Use S synthetic length; R fixture deliberately perturbed."
    assert reviewed_line(cat, r)["sections"][0]["to_km"] == 20


def test_idempotent_import_tampering_and_no_overwrite(tmp_path):
    source, target = tmp_path / "snapshot.json", tmp_path / "cat.json"
    source.write_text(json.dumps(snapshot()), encoding="utf-8")
    imported = import_snapshot(source, target)
    assert import_snapshot(source, target) == imported
    assert read_catalogue(target) == imported
    assert not review_template(imported)["reviewer"]
    altered = json.loads(target.read_text())
    altered["catalogue"]["rows"][0]["length_km"] = 200
    target.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        read_catalogue(target)
    with pytest.raises(ValueError, match="exists"):
        import_snapshot(source, target)


def test_cli_import_review_and_export_do_not_touch_active_registry(tmp_path):
    source, cat, form, output = [tmp_path / p for p in ("snapshot.json", "cat.json", "review.json", "line.yaml")]
    source.write_text(json.dumps(snapshot()))
    assert main(["catalogue", "import", str(source), "--out", str(cat)]) == 0
    assert main(["catalogue", "review-template", str(cat), "--out", str(form)]) == 0
    assert main(["catalogue", "export", str(cat), "--review", str(form), "--out", str(output)]) == 2
    assert not output.exists()
    form.write_text(json.dumps(review(read_catalogue(cat)["catalogue"])))
    assert main(["catalogue", "export", str(cat), "--review", str(form), "--out", str(output)]) == 0


def test_catalogue_api_search_details_checksum_and_draft_are_isolated(environment):
    client, app, source, registry = environment
    assert not client.get("/api/catalogue").json()["available"]
    path = app.state.store.root / "snapshot.json"
    path.write_text(json.dumps(snapshot()))
    envelope = import_snapshot(path, app.state.store.root / "source-catalogue.json")
    files = {p.name: p.read_bytes() for p in registry.iterdir()}
    result = client.get("/api/catalogue?q=Alpha&limit=1").json()
    assert result["total"] == 2 and len(result["items"]) == 1
    row = client.get("/api/catalogue/rows/" + result["items"][0]["id"]).json()
    assert row["raw"] and row["cells"] and len(row["reciprocal_candidates"]) == 1
    draft = client.post("/api/catalogue/registry-draft", json=review(envelope["catalogue"]))
    assert draft.status_code == 200 and draft.json()["id"] == "EXAMPLE"
    assert client.get("/api/catalogue?limit=1000").status_code == 422
    assert client.get("/api/catalogue/rows/missing").status_code == 404
    assert client.post("/api/catalogue/registry-draft", json={}).status_code == 400
    assert not app.state.store.list()
    assert files == {p.name: p.read_bytes() for p in registry.iterdir()}
