# Runbook

**Schedule:** nightly via GitHub Actions (`.github/workflows/pipeline.yml`), or manually with `python -m pipeline.run`.

**Exit codes:** `0` success, `1` one or more data quality checks failed (dashboard is still produced and the failure is recorded in `etl_run_log`).

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `HTTP 401` from ticket API | expired or wrong token | rotate the token and rerun |
| repeated `HTTP 503` warnings, then failure | ticketing vendor outage | rerun later; retries already cover short blips |
| `row count reconciles` FAIL | partial export or a transform dropping rows | compare source file counts with the transform log |
| `no billing after disconnect` FAIL | disconnect not synced to billing | raise with billing team; check the customer's end_date |
| `ValueError: unrecognized date` | new date format in an export | add the format to `transform.parse_date` and a test |

## Change management
1. Branch, change, add or update a test.
2. `python -m unittest discover -s tests` must pass locally.
3. Push; CI reruns tests and the full pipeline before merge.
