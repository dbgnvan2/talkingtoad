# Core Web Vitals fixtures — CONSTRUCTED, not recorded

**Read this before trusting a parser test in `tests/test_web_vitals.py`.**

These payloads are built from the documented CrUX and PSI response contracts.
They were **not** captured from the live APIs: no `TT_PSI_API_KEY` was available
when D2 was written, and the shared keyless PSI pool returned HTTP 429
("Quota exceeded for quota metric 'Queries'") on the attempt to record one.

That is exactly the situation P19/P20 warn about — a parser calibrated against an
idealised payload rather than what the producer actually emits. Two mitigations
are in place, and neither is a substitute for real capture:

1. `api/services/web_vitals.py` parses defensively. An unrecognised shape yields
   `None` ("not measured") rather than a crash or a confident wrong number.
2. `tests/test_web_vitals.py::TestLiveApiContract` runs against the real API and
   is **skipped unless `TT_PSI_API_KEY` is set**. The moment a key exists, real
   verification runs in CI and locally.

## When a key becomes available

```bash
export TT_PSI_API_KEY=...
python -m pytest tests/test_web_vitals.py::TestLiveApiContract -v
```

If it passes, re-record these fixtures from the live responses, update this file
to say they are recorded, and delete this warning. If it fails, the parser has
drifted from the real contract and that is the bug the live test exists to catch.
