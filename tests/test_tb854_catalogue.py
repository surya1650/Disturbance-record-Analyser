"""TB 854 retrieval/integration regression; NOT electrical validation."""
from dranalyser.cli import build_parser
from dranalyser.registry.model import uniform_line
from dranalyser.registry.settings import ProtectionSettings
from dranalyser.standards import audit_record, audit_settings, load_catalogue, load_sources, search_chunks
from dranalyser.standards.catalogue import context_text
from dranalyser.synth.generator import SynthSpec, generate


SOURCE = "cigre-tb854"


def test_tb854_manifest_locators_and_catalogued_status():
    source = [s for s in load_sources() if s["id"] == SOURCE]
    assert len(source) == 1
    assert source[0]["sha256"].lower() == "0406508feb3154dff584a5818823ea6be01b0dd1e82f523d0d7ac2d8797a7886"
    chunks = search_chunks(source_id=SOURCE)
    assert len(chunks) == 22
    assert len({c["id"] for c in chunks}) == len(chunks)
    assert len({c["locator"] for c in chunks}) == len(chunks)
    assert all(c["locator"] and c["rules"] for c in chunks)
    assert {c["analyzer_state"] for c in chunks} == {"catalogued"}
    assert {c["source_id"] for c in chunks} == {SOURCE}


def test_tb854_source_filter_composes_and_cannot_promote_guidance():
    chunks = search_chunks(source_id=SOURCE)
    assert chunks == [c for c in load_catalogue() if c["source_id"] == SOURCE]
    assert search_chunks(source_id="absent-source") == []
    assert search_chunks(source_id=SOURCE, active_only=True) == []
    assert search_chunks(active_only=True)  # non-vacuous: other sources are active
    assert all(c["source_id"] != SOURCE for c in search_chunks(active_only=True))
    topic = chunks[0]["topics"][0]
    filtered = search_chunks(source_id=SOURCE, asset_type="line", topic=topic)
    assert filtered
    assert all(c in chunks and any(topic in t for t in c["topics"]) for c in filtered)
    rendered = context_text(chunks)
    assert rendered.count("(catalogued)") == 22
    assert "(active)" not in rendered


def test_tb854_cli_context_is_source_scoped_and_explicitly_advisory(capsys):
    args = build_parser().parse_args(["standards", "--show-context", "--source", SOURCE])
    assert args.func(args) == 0
    text = capsys.readouterr().out
    for chunk in search_chunks(source_id=SOURCE):
        assert f"[{chunk['id']}] {SOURCE} {chunk['locator']} (catalogued)" in text
    for chunk in load_catalogue():
        if chunk["source_id"] != SOURCE:
            assert f"[{chunk['id']}]" not in text


def test_tb854_entries_do_not_become_automatic_record_or_settings_checks():
    case = generate(SynthSpec())
    line = uniform_line("T", "test", 220, 100, 0.03+0.4j, 0.25+1.2j)
    checks = audit_record(case.records["S"], line).checks + audit_settings(ProtectionSettings(), line).checks
    assert checks
    tb_ids = {c["id"] for c in search_chunks(source_id=SOURCE)}
    assert tb_ids.isdisjoint(c.id for c in checks)
    assert all("cigre" not in c.source.lower() and "854" not in c.source for c in checks)
