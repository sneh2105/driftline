# QA log (append only, Codex-owned)

## 2026-11-06 22:23 � qa/first-pass � pending
**Focus:** Ingest validation
**Tests added:** 2 parameterized cases in `test_mixed_timestamp_formats_are_accepted`, covering epoch/ISO and naive ISO/epoch pairs.
**Findings:** none
**Why these tests:** They verify that supported timestamp representations can be mixed within one event, beyond the same-format cases already covered.
**Verified:** `pytest tests/qa/test_ingest_validation.py -q` � 26 passed, 0 xfailed.

## 2026-11-06 22:25 � qa/first-pass � pending
**Focus:** Scoring properties
**Tests added:** 5 tests in `test_scoring_properties.py`: Hypothesis properties for slower median speed-component monotonicity, adding a reject without lowering the reject component, and scores staying within [0,100]; plus minimum-sample flags and empty-input behavior.
**Findings:** none
**Why these tests:** They check the scoring invariants from SPEC �4 and the minimum sample and empty-data behavior from SPEC �5 across generated inputs.
**Verified:** `pytest tests/qa -q` � 31 passed, 0 xfailed.

## 2026-11-06 22:27 · qa/first-pass · pending
**Focus:** Auth + tenant isolation
**Tests added:** 3 tests in `test_auth.py`: missing/invalid key rejection, bearer key acceptance, and project key data isolation.
**Findings:** none
**Why these tests:** They check the documented 401 behavior for absent or invalid credentials and verify that each project's key only sees its own approval records.
**Verified:** `pytest tests/qa/test_auth.py -q` — 3 passed, 0 xfailed.


## 2026-11-06 22:28 ? qa/first-pass ? pending
**Focus:** SDK failure modes
**Tests added:** 6 tests in `test_sdk_failure_modes.py`: network failure requeue and event identity, 5xx retry identity without duplicate queue entries, full queue drops without raising, approve/reject double-finalization in both orders, and public logging calls surviving network errors.
**Findings:** none
**Why these tests:** They cover the SDK guarantees in SPEC ?7 for retries, idempotency, bounded queue behavior, one-time review finalization, and non-blocking non-raising calls.
**Verified:** `pytest tests/qa/test_sdk_failure_modes.py -q` ? 6 passed, 0 xfailed.

## 2026-11-06 22:30 · qa/first-pass · pending
**Focus:** API read paths
**Tests added:** 3 tests in `test_api_read_paths.py` (one parameterized): documented minimum/maximum `days` bounds for overview and digest, unknown approver 404, and retrieval of an approver name containing spaces, URL-reserved punctuation, and Unicode.
**Findings:** none
**Why these tests:** They check the range and missing-resource behavior promised by SPEC §6 and ensure URL encoding does not make valid special-character approver names unreachable.
**Verified:** `pytest tests/qa/test_api_read_paths.py -q` — 4 passed, 0 xfailed.

## 2026-11-06 22:33 · qa/first-pass · pending
**Focus:** Guardrail Health diff
**Tests added:** 2 tests in `test_guardrail_diff.py`: `test_guardrail_diff_reports_only_new_pass_to_fail_regressions` checks first-run emptiness, a new failure, and no repeat alert; `test_guardrail_diff_excludes_improvements_and_adapter_errors` checks improvements and errored calls are excluded.
**Findings:** none
**Why these tests:** They verify the regression-only behavior in SPEC §12, guarding against alerting on known failures, improvements, or inconclusive adapter errors.
**Verified:** `pytest tests/qa/test_guardrail_diff.py -q` — 2 passed, 0 xfailed; `pytest tests/qa -q` — 46 passed, 0 xfailed.

## 2026-11-06 23:02 · qa/first-pass · pending
**Focus:** Rate limit + body cap
**Tests added:** 6 tests in `test_rate_limit_body_cap.py`: the 301st request returns 429 with Retry-After, a 1000-event batch counts as one request, project B remains available after project A reaches its limit, the exact 1 MiB body boundary, over-limit body rejection, and streamed chunked over-limit rejection.
**Findings:** BUG-1: a body exactly 1 MiB returns 413 instead of being accepted per SPEC §8; BUG-2: an over-limit chunked body returns 400 instead of 413 per SPEC §8.
**Why these tests:** They cover per-project isolation, documented fixed-window request counting, required retry metadata, and exact request body size enforcement across declared and streamed bodies.
**Verified:** `pytest tests/qa/test_rate_limit_body_cap.py -q` — 4 passed, 2 xfailed.
## 2026-11-06 23:03 - qa/first-pass - pending
**Focus:** Admin + key lifecycle
**Tests added:** 3 tests in test_admin_key_lifecycle.py: unset admin key denial for create and rotate, wrong admin key rejection, and key rotation invalidation with newly issued keys.
**Findings:** BUG-3: admin endpoints return 401 when DRIFTLINE_ADMIN_KEY is unset, instead of the 403 required by SPEC section 3; captured as a strict xfail.
**Why these tests:** They cover disabled-by-default admin access and verify that rotation replaces the active credential while returning the new key.
**Verified:** pytest tests/qa -q - 52 passed, 3 xfailed.

## 2026-11-06 23:05 - qa/first-pass - pending
**Focus:** Digest delivery
**Tests added:** 4 tests in test_digest_delivery.py: both channels disabled when unconfigured; Slack webhook receives a digest; SMTP still sends when Slack fails; and email stays disabled when either SMTP HOST or TO is missing.
**Findings:** none
**Why these tests:** They cover the delivery defaults, payload handoff, channel failure isolation, and SMTP activation rules specified in SPEC section 11.
**Verified:** `pytest tests/qa/test_digest_delivery.py -q` - 4 passed, 0 xfailed.
