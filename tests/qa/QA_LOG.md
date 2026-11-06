# QA log (append only, Codex-owned)

## 2026-11-06 22:23 · qa/first-pass · pending
**Focus:** Ingest validation
**Tests added:** 2 parameterized cases in `test_mixed_timestamp_formats_are_accepted`, covering epoch/ISO and naive ISO/epoch pairs.
**Findings:** none
**Why these tests:** They verify that supported timestamp representations can be mixed within one event, beyond the same-format cases already covered.
**Verified:** `pytest tests/qa/test_ingest_validation.py -q` — 26 passed, 0 xfailed.
