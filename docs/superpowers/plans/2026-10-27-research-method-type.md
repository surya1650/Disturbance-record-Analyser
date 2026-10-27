# Research Method Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reject array/non-string method selectors consistently with the bound API.

**Architecture:** One explicit string guard before the existing operator selection.

**Tech Stack:** Existing Python/NumPy/pytest.

**Spec:** docs/superpowers/specs/2026-10-27-research-method-type.md

## Global Constraints
- Legacy default/math and valid literal/NumPy scalar strings unchanged.
- Invalid/unknown selectors raise ValueError; no production/research promotion.
- Preserve historical evidence and local data; no field data or extra approval.
- Full suites serially, one fresh review/one TDD Important-fix pass.

## Review Focus
- A one-element array must not silently opt into the research estimator.
- Unknown selectors and malformed containers must fail consistently.
- Legitimate string selectors must retain existing phasor/bound semantics.
- Default calls must preserve the legacy operator and seed9984 refusal.
- Historical evidence bindings must not be rewritten after this API guard.

### Task 1: Selector guard and verification
**Files:** Modify src/dranalyser/dsp/core.py; create tests/test_method_selector.py; record result in project-docs/NEXT_SESSION.md after integration.
**Interfaces:** sliding_dft public signature unchanged; method must be str containing legacy/basis.
- [x] Write minimal array-selector refusal test and valid NumPy scalar-string physical-phasor check. Run focused RED.
- [x] Add isinstance(method,str) guard, run new/fractional/budget suites GREEN; architecture/focused Ruff. Commit.
- [x] Obtain one fresh whole-branch review, fix Important issues once via RED/GREEN. Merge with independently reviewed scalar study and run one combined primary full suite before push; verify remote/clean tree, preserve QA/ledger and native archive.
