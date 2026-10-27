# Independent Nonuniform Source Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline task-by-task. Steps use checkbox syntax.

**Goal:** Useful single-record analysis and unsynchronised record comparison without invented acquisition or field evidence.
**Architecture:** Strict observation loader, pure actual-time numerical model, independent incident comparison, standalone read-only report. Existing Record pipeline and gates stay unchanged.
**Tech Stack:** Existing Python, NumPy/SciPy, pytest and Jinja2.
**Spec:** docs/superpowers/specs/2026-10-27-nonuniform-analysis.md

## Global Constraints
- No raw/capture/DB/workbook/Dash or existing preview changes; no normal primary/clock/location promotion.
- Direct sample coordinates only; no resampling or missing observations imputed as zero.
- All statuses/denominators finite JSON; input/resource limits and numerical domains exactly as spec.
- Freeze144 disjoint cases before outcomes; preserve failures, historical manifests and full dependencies.
- One fresh whole-branch review and single TDD Important-fix pass, no repeat review.

## Review Focus
- Missing values/invalid CFG scaling must not become measured zero or calibrated engineering values.
- Coherent alias/gain defects can pass residual/stability tests; no authority may follow.
- Sparse/gapped/masked/extreme observations must refuse safely rather than create fitted certainty.
- Different local clocks/references and duplicates cannot establish event identity or independent corroboration.
- Bounded window budgets must expose incomplete coverage and retain every evaluated refusal.

### Task 1: Strict observations and direct-time numerical kernels
**Files:** create comtrade/source_observations.py, dsp/nonuniform.py, dsp/source_analysis.py; tests/test_nonuniform_source.py; architecture budget entries.
**Interfaces:** load_source(cfg_path,dat_path=None)->dict containing metadata, channels, source axis and digital observations; fit_source_window(t,y,frequency)->finite dict; source_frequency(t,values,nominal)->finite dict; analyse_source(observations)->dict.
- [ ] Write failing tests: irregular analytic harmonic/DC RMS/phase, off-nominal search, gap/mask/nonfinite/extreme/rank refusal, missing ASCII values and truncation, explicit/raw scaling, unknown timing sample-only fallback, digital boundaries and budget denominators. Expected missing-module RED.
- [ ] Implement strict loader and actual-time kernels/pipeline per spec. All outputs deny authority; compare half supports without assuming transient decay. Expected focused GREEN, architecture and changed-file Ruff pass.
- [ ] Full serial suite and commit. task-done tests/test_nonuniform_source.py tests/test_source_time.py tests/test_timestamp_recovery.py -q; expected GREEN.

### Task 2: Independent comparison, CLI and frozen validation
**Files:** dsp/source_compare.py; report/source_analysis.py and source_analysis.html; scripts/analyse_source_record.py; scripts/nonuniform_validation.py; tests/test_source_analysis_delivery.py; tracked synthetic evidence/report.
**Interfaces:** compare_sources(analyses,reference=None)->incident dict with independent records, digital local anchors and duplicate status; render_source_report(result)->escaped HTML; CLI --cfg one-or-more --output new-directory [--reference DIGITAL_LABEL].
- [ ] Write failing tests for one end, unsynchronised independent references, duplicates, initial-high missing anchor, degraded samples, escaped labels, exclusive CLI outputs and retained failed numerical rows. Expected RED.
- [ ] Implement bounded comparison/report/CLI and independent144-case protocol runner. Commit code freeze BEFORE outcomes. Expected focused GREEN.
- [ ] Run frozen144 plus alias/gain controls and unchanged Dhone replay privately; preserve every result and source binding. Expected analytic tolerances/refusals per frozen spec, originals/old parser block unchanged.
- [ ] Full serial suite, one fresh whole-branch review and single TDD Important pass; primary integration/full corpus verification/push. Preserve ignored QA/ledger; native archive; update handover/automation priority. Expected no unresolved Important, no field/clock claims.
