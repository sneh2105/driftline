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

## 2026-11-06 22:27 Â· qa/first-pass Â· pending
**Focus:** Auth + tenant isolation
**Tests added:** 3 tests in `test_auth.py`: missing/invalid key rejection, bearer key acceptance, and project key data isolation.
**Findings:** none
**Why these tests:** They check the documented 401 behavior for absent or invalid credentials and verify that each project's key only sees its own approval records.
**Verified:** `pytest tests/qa/test_auth.py -q` â€” 3 passed, 0 xfailed.


## 2026-11-06 22:28 ? qa/first-pass ? pending
**Focus:** SDK failure modes
**Tests added:** 6 tests in `test_sdk_failure_modes.py`: network failure requeue and event identity, 5xx retry identity without duplicate queue entries, full queue drops without raising, approve/reject double-finalization in both orders, and public logging calls surviving network errors.
**Findings:** none
**Why these tests:** They cover the SDK guarantees in SPEC ?7 for retries, idempotency, bounded queue behavior, one-time review finalization, and non-blocking non-raising calls.
**Verified:** `pytest tests/qa/test_sdk_failure_modes.py -q` ? 6 passed, 0 xfailed.

## 2026-11-06 22:30 Â· qa/first-pass Â· pending
**Focus:** API read paths
**Tests added:** 3 tests in `test_api_read_paths.py` (one parameterized): documented minimum/maximum `days` bounds for overview and digest, unknown approver 404, and retrieval of an approver name containing spaces, URL-reserved punctuation, and Unicode.
**Findings:** none
**Why these tests:** They check the range and missing-resource behavior promised by SPEC Â§6 and ensure URL encoding does not make valid special-character approver names unreachable.
**Verified:** `pytest tests/qa/test_api_read_paths.py -q` â€” 4 passed, 0 xfailed.
