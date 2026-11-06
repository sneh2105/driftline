# QA log (append only, Codex-owned)

## 2026-11-06 22:23 · qa/first-pass · pending
**Focus:** Ingest validation
**Tests added:** 2 parameterized cases in `test_mixed_timestamp_formats_are_accepted`, covering epoch/ISO and naive ISO/epoch pairs.
**Findings:** none
**Why these tests:** They verify that supported timestamp representations can be mixed within one event, beyond the same-format cases already covered.
**Verified:** `pytest tests/qa/test_ingest_validation.py -q` — 26 passed, 0 xfailed.

## 2026-11-06 22:25 · qa/first-pass · pending
**Focus:** Scoring properties
**Tests added:** 5 tests in `test_scoring_properties.py`: Hypothesis properties for slower median speed-component monotonicity, adding a reject without lowering the reject component, and scores staying within [0,100]; plus minimum-sample flags and empty-input behavior.
**Findings:** none
**Why these tests:** They check the scoring invariants from SPEC §4 and the minimum sample and empty-data behavior from SPEC §5 across generated inputs.
**Verified:** `pytest tests/qa -q` — 31 passed, 0 xfailed.
