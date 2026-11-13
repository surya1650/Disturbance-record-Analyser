# Excel catalogue integration — 2026-11-13

## Goal and scope

Import the supplied workbook through Source catalogue: upload, preview, explicitly
activate, browse by circle/station/type, inspect source issues and keep the
existing source-bound transmission-line review flow. Preserve DR parsing,
incidents, approved registry definitions, engineering gates and the original
published checkout. The user has authorized implementation and review-branch
delivery; no cloud deployment or environment publication is included.

## Design

- Bounded XLSX reader with safe ZIP/XML preflight, original row/cell coordinates,
  preserved blanks and cached formula warnings. No formula execution or fill-down.
- Immutable content-addressed local imports and transactional active pointer;
  preview cannot activate. Stale activation conflicts require refresh.
- TL rows retain existing electrical parsing and review requirements. PTR rows
  are inventory only. Bus identifiers do not establish bay/circuit identity.
- Source catalogue upload/filter/detail UI with version history and original
  downloads. The operational registry and incident data remain separate.
- Legacy Google snapshots and source-catalogue.json remain supported.

## Verification and delivery

Synthetic parser/model/storage/API/UI tests; private workbook stays ignored.
Real-browser empty/upload/preview/activate/filter/version checks. Direct
architecture check, full pytest and Stage-A 10000. Record sanitized acceptance
and VM update instructions, then normal push to codex/operator-ui-review after
checking the latest remote. Never force push or commit private source rows.
