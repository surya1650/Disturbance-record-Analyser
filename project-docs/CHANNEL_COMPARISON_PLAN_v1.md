# Channel comparison continuation

2026-10-29. Continue the user-authorized channel-layout work on the published
`f52911e` snapshot. Preserve that implementation; do not restore the older draft.

## Problem and scope

`inspection-analysis.js` independently selects the first analog in each CFG.
The supplied screenshot shows IA beside VA. Comparing file positions obscures
the same electrical signal. Display all recoverable analogs in matched rows,
voltage first, other quantities next, current last, including explicit empty
counterparts. Apply the same default quantity order to the primary workbench.

Do not change source decoding, phasor estimators, ratios, incident assignment,
physical timing, location mathematics, stored data or published environment settings.
The current single-record workbench's bounded paging and native cursor transport
remain supported. Comparison is an overview; exact readings remain in that workbench.

## Constraints and basis

PROJECT_CONTEXT section 2 applies. A visual identity is not verified wiring,
common event, terminal identity or clock synchronization. Unknown and duplicate
identities remain unpaired. Residual, neutral, phase-pair and RMS identities stay
distinct. Independent units/scales are labelled. This layout/order is project UI
policy, not a standards-conformance claim. COMTRADE source IDs remain unchanged.

## Phases and acceptance

1. Pure `channel-comparison-model.js`: conservative identities, every analog once,
   order independent of CFG positions. Node tests cover reordered files, ambiguity,
   conflicting metadata, mixed phases/units, and 64 channels per source.
2. `channel-comparison-view.js` and stylesheet: shared row geometry with placeholders,
   labelled vertical axes and explicit independent sample-index axes; all channels.
   Integrate comparison and primary default ordering; prevent cross-quantity overlays.
3. Run focused tests, desktop/mobile browser checks against reordered synthetic
   records, architecture self-test/gate, Ruff, full tests and Stage-A 10,000.
   Record exact results and limits. No publishing or environment configuration changes.

## Data impact and expected change

No schema migration or numerical result changes. Existing captures and revisions
are untouched. Rows move into consistent quantity/phase order, and comparison shows
all channels instead of two individually chosen signals. Ambiguous channels gain
visible one-sided rows rather than a speculative partner.

## Risks

Vendor labels are not asset evidence. Conservative matching can leave channels
unpaired. Different sample rates and capture lengths do not establish a common
physical timeline; axes must say so. Independent vertical scales must not imply
equal amplitudes. Bounded display envelopes must not be presented as exact samples.
