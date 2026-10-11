# Evaluation

The NL-to-SQL benchmark ([ADR 0006](../docs/adr/0006-evaluation-methodology.md),
comparison rules in [ADR 0017](../docs/adr/0017-benchmark-comparison-and-verification.md)).

| Path | What |
|---|---|
| `benchmark/dev.yaml` | 30 development questions: the only split used while tuning |
| `benchmark/test.yaml` | 20 held-out questions: checkpoint runs only, never tuned on |
| `results/` | One JSON record + markdown report per run, committed |
| `triage/<run_id>.yaml` | Human failure categories for a run (optional) |

Commands run from `backend/` and need the local database (except `check`):

```sh
uv run python -m olist_nlsql.evaluation check                  # structure + validator, no db
uv run python -m olist_nlsql.evaluation snapshot --split dev   # store reference results
uv run python -m olist_nlsql.evaluation show --split dev dev-007
uv run python -m olist_nlsql.evaluation verify --split dev --by "Your Name" dev-007
uv run python -m olist_nlsql.evaluation run --split dev        # real model (Bedrock)
uv run python -m olist_nlsql.evaluation run --split test --checkpoint "end of phase 4"
uv run python -m olist_nlsql.evaluation report ../eval/results/<run_id>.json
```

## Verifying an item

An item is ground truth only after a person has checked it. Until then it is run but
not scored. For each item:

1. `show` it and read the question, notes, SQL and result.
2. Check that the SQL answers the question **as a business user would mean it**, using
   the catalog's metric definitions ([metrics.md](../docs/metrics.md)): right relation,
   right population (revenue orders, delivered orders…), right time window, right
   grain.
3. Check that the result looks right (magnitudes, row count, no NULL rankings).
4. Check that the comparison options fit: `order_matters` for rankings and series,
   `allow_percent` for rates, and a tolerance suited to the value.
5. `verify` it. If you change anything, re-run `snapshot` first. Editing the question,
   SQL, options or result after verifying un-verifies the item automatically.

Snapshots must come from a database built from the pinned Kaggle files
(`dbsetup download` + `build`).

## Runs

- `run` writes `results/<run_id>.json` and `.md`. Commit both. Metrics in reports are
  computed from the JSON, never typed in.
- `--fake-reference` answers each question with its own reference SQL. It's a harness
  self-test that should score 100%. Its reports are marked as such and must not be
  quoted as accuracy. Write them elsewhere with `--results-dir`.
- Test-split runs need `--checkpoint "reason"` and are always recorded. Don't change
  anything because of a test-split failure.

## Triage

Stage failures (generation, validation, execution) are categorised automatically.
Wrong results get a guess (`wrong_relation_or_join` when the relations differ,
otherwise `untriaged_mismatch`), and validator rejections still need splitting into
correct and false rejections. Record your call in `triage/<run_id>.yaml`:

```yaml
dev-007:
  category: wrong_filter_or_time_window   # see runner.CATEGORIES
  note: used delivered orders only
```

Then re-run `report` on the JSON.
