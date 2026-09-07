---
name: comtrade-corpus
description: Work on the COMTRADE parser, the conformance gate, or real vendor record files — editions, ASCII vs binary, .CFF vs four-file, channel-role resolution, CT/VT scaling, and what a failed check must do. Use whenever touching src/dranalyser/comtrade/, adding a vendor's files to tests/corpus/, or debugging "this record parses but the numbers are wrong".
---

# COMTRADE & the conformance gate — real files are not conformant

We write our own parser (§12) precisely because every off-the-shelf one assumes a
conformance that real relay files do not have. **Do not `pip install comtrade`** — the
architecture gate fails the build if any module imports one.

## What the parser must survive

- **Editions 1991 / 1999 / 2013.** 2013 adds the single-file `.CFF`, `float32` /
  `binary32` data, `time_code` / `local_code` / `tmq_code`, `leapsec`, and ns timestamps.
  `tmq_code` is what gates E4 (synchronised two-ended); its absence is not an error, it
  just means E4 is unavailable and E5 carries the answer.
- **Both container forms:** `.CFF` single file, and the four-file `.CFG/.DAT/.HDR/.INF`
  set — including the case where the four files disagree on case (`X.cfg` + `X.DAT`) or
  where `.HDR`/`.INF` are missing entirely.
- **ASCII and binary** `.DAT`, including binary32/float32 and the 16-bit forms.
- **Free-text channel names.** Vendors write `IL1`, `IA`, `I_R`, `Ir`, `IN`, `3I0`,
  `V_RY`, `UL12`… Channel-role resolution is a mapping problem with a per-vendor
  dictionary, not a regex someone tightens each time a file fails. Unresolved roles are
  reported as flags, never assumed.
- **Scaling.** `a`/`b` multiplier + offset, primary vs secondary (`PS` field), CT/VT
  ratios from the registry. A P/S convention mismatch between the two ends produces two
  confident, disagreeing locations from the same fault — this exact failure exists in the
  repo's real-record tests. When two records of one incident disagree beyond tolerance,
  suspect scaling and sampling rate before suspecting the estimator.
- **Multiple sample rates in one record** (`nrates` > 1) and the rate change mid-record.

## The conformance gate (§5.1) — pure, structured, and never a repair

`comtrade/conformance.py::check` returns **structured flags**, not booleans and not
exceptions. The rules:

1. A failed check **tags** the record; it does not fix it and does not drop it.
2. The tag travels all the way to the report (§2.5). "Record from end R excluded: neutral
   CT polarity reversed" is a usable sentence for the collection team; a silently
   corrected polarity is a wrong answer with no trace.
3. Never guess a CT ratio, a VT ratio, a nominal frequency, or a phase rotation.
4. The gate runs **before** any maths. Estimators assume gated input; they do not
   re-validate, and they must not be the place a bad ratio is first noticed.

## The corpus is the only real proof

`tests/corpus/` holds redacted real vendor files, and tests over it are marked
`@pytest.mark.corpus` so they skip cleanly when the files are absent.

When adding files:
- one directory per vendor/model (`siprotec/`, `rel670/`, `micom_p44x/`, `sel_411l/`…),
  with a short `README.md` saying which relay, which firmware if known, and **what was
  redacted** (substation names, line names, times);
- keep at least one *bad* record per class of defect found in the field — wrong ratio,
  reversed neutral CT, truncated record, missing far-end file. The gate's tests need
  failures to assert on, and every real defect that reaches production should end up here;
- disturbance records are utility operational data. `.gitignore` excludes record
  extensions everywhere except `tests/corpus/`; committing a record is a deliberate act.

**A synthetic-only pass proves nothing about vendor files.** Parser or gate changed →
run the corpus tests, and say how many vendor files were exercised.

## Same defect, all vendors

The parser has a branch per edition, per container form, per data format, and per vendor
naming dictionary. A bug found in one branch is nearly always in the siblings — see the
`same-defect-sweep` skill and enumerate the branches in the report.
